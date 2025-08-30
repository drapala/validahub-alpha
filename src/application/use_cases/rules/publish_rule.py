"""Publish rule use case for ValidaHub Smart Rules Engine."""

from dataclasses import dataclass
from typing import Optional, List

from src.application.errors import ValidationError
from src.application.ports.rules import RuleRepository, RuleCompiler, CachePort, EventBusPort
from src.domain.value_objects import TenantId
from src.domain.rules.value_objects import RuleSetId, SemVer
from src.domain.rules.aggregates import RuleSet


@dataclass(frozen=True)
class PublishRuleRequest:
    """Request DTO for rule publication."""
    tenant_id: str
    rule_set_id: str
    version: str
    make_current: bool = True
    published_by: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass(frozen=True)
class PublishRuleResponse:
    """Response DTO for rule publication."""
    rule_set_id: str
    name: str
    version: str
    status: str
    is_current: bool
    checksum: str
    published_at: str
    compilation_errors: List[str]
    
    @classmethod
    def from_rule_set(
        cls,
        rule_set: RuleSet,
        version: SemVer,
        checksum: str,
        compilation_errors: List[str] = None
    ) -> "PublishRuleResponse":
        """Create response from rule set domain object."""
        rule_version = rule_set._get_version(version)
        return cls(
            rule_set_id=str(rule_set.id.value),
            name=rule_set.name,
            version=str(version),
            status=rule_version.status.value if rule_version else "unknown",
            is_current=rule_set.current_version == version,
            checksum=checksum,
            published_at=rule_version.published_at.isoformat() if rule_version and rule_version.published_at else "",
            compilation_errors=compilation_errors or []
        )


class PublishRuleUseCase:
    """Use case for publishing rule sets to make them available for use."""
    
    def __init__(
        self,
        rule_repository: RuleRepository,
        rule_compiler: RuleCompiler,
        cache_port: CachePort,
        event_bus: EventBusPort
    ) -> None:
        """
        Initialize use case with dependencies.
        
        Args:
            rule_repository: Repository for rule persistence
            rule_compiler: Compiler for rule validation and IR generation
            cache_port: Cache for compiled rules
            event_bus: Event bus for publishing domain events
        """
        self._rule_repository = rule_repository
        self._rule_compiler = rule_compiler
        self._cache_port = cache_port
        self._event_bus = event_bus
    
    def execute(self, request: PublishRuleRequest) -> PublishRuleResponse:
        """
        Execute rule publication use case.
        
        Args:
            request: Rule publication request
            
        Returns:
            Rule publication response
            
        Raises:
            ValidationError: If input validation fails
        """
        # Validate request
        self._validate_request(request)
        
        # Convert to value objects
        tenant_id = TenantId(request.tenant_id)
        rule_set_id = RuleSetId(request.rule_set_id)
        version = SemVer.from_string(request.version)
        
        # Find rule set
        rule_set = self._rule_repository.find_by_id(tenant_id, rule_set_id)
        if not rule_set:
            raise ValidationError("Rule set not found")
        
        # Get version to publish
        rule_version = rule_set._get_version(version)
        if not rule_version:
            raise ValidationError(f"Version {version} not found")
        
        # Validate rules before publishing
        validation_errors = self._rule_compiler.validate_rules(rule_version.rules)
        if validation_errors:
            raise ValidationError(f"Cannot publish invalid rules: {'; '.join(validation_errors)}")
        
        # Compile rules to intermediate representation
        try:
            compiled_rules = self._rule_compiler.compile_rules(rule_version.rules)
            checksum = compiled_rules.checksum
            compilation_errors = []
        except Exception as e:
            raise ValidationError(f"Rule compilation failed: {e}")
        
        # Publish version
        published_rule_set = rule_set.publish_version(
            version=version,
            checksum=checksum,
            published_by=request.published_by or "system",
            make_current=request.make_current,
            correlation_id=request.correlation_id
        )
        
        # Save updated rule set
        saved_rule_set = self._rule_repository.save(published_rule_set)
        
        # Cache compiled rules
        try:
            self._cache_port.store_compiled_rules(
                tenant_id=tenant_id,
                rule_set_id=rule_set_id,
                version=version,
                compiled_rules=compiled_rules,
                ttl_seconds=3600  # 1 hour default TTL
            )
        except Exception:
            # Don't fail publication if caching fails
            pass
        
        # Publish domain events
        try:
            events = saved_rule_set.get_domain_events()
            if events:
                self._event_bus.publish_rule_events(events)
                saved_rule_set = saved_rule_set.clear_domain_events()
        except Exception:
            # Don't fail use case if event publishing fails
            pass
        
        return PublishRuleResponse.from_rule_set(
            saved_rule_set,
            version,
            checksum,
            compilation_errors
        )
    
    def _validate_request(self, request: PublishRuleRequest) -> None:
        """Validate rule publication request."""
        validation_errors = []
        
        # Validate required fields
        if not request.tenant_id or not request.tenant_id.strip():
            validation_errors.append("tenant_id is required")
        
        if not request.rule_set_id or not request.rule_set_id.strip():
            validation_errors.append("rule_set_id is required")
        
        if not request.version or not request.version.strip():
            validation_errors.append("version is required")
        
        if validation_errors:
            raise ValidationError("; ".join(validation_errors))
        
        # Validate version format
        try:
            SemVer.from_string(request.version)
        except ValueError:
            raise ValidationError("invalid version format, must be 'major.minor.patch'")
        
        # Validate rule set ID format
        try:
            from uuid import UUID
            UUID(request.rule_set_id)
        except ValueError:
            raise ValidationError("invalid rule_set_id format")
        
        # Validate value objects
        try:
            TenantId(request.tenant_id)
        except ValueError as e:
            raise ValidationError(f"invalid tenant_id: {e}")