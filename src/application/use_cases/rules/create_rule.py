"""Create rule use case for ValidaHub Smart Rules Engine."""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from uuid import uuid4

from src.application.errors import ValidationError
from src.application.ports.rules import RuleRepository, RuleCompiler, CachePort, EventBusPort
from src.domain.value_objects import TenantId, Channel
from src.domain.rules.value_objects import RuleSetId, RuleDefinition, SemVer
from src.domain.rules.aggregates import RuleSet
from src.domain.rules.entities import RuleVersion


@dataclass(frozen=True)
class CreateRuleRequest:
    """Request DTO for rule creation."""
    tenant_id: str
    channel: str
    name: str
    version: str
    rules: List[Dict[str, Any]]
    description: Optional[str] = None
    created_by: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass(frozen=True)
class CreateRuleResponse:
    """Response DTO for rule creation."""
    rule_set_id: str
    name: str
    version: str
    status: str
    rules_count: int
    created_at: str
    validation_errors: List[str]
    
    @classmethod
    def from_rule_set(
        cls,
        rule_set: RuleSet,
        version: SemVer,
        validation_errors: List[str] = None
    ) -> "CreateRuleResponse":
        """Create response from rule set domain object."""
        rule_version = rule_set._get_version(version)
        return cls(
            rule_set_id=str(rule_set.id.value),
            name=rule_set.name,
            version=str(version),
            status=rule_version.status.value if rule_version else "unknown",
            rules_count=len(rule_version.rules) if rule_version else 0,
            created_at=rule_set.created_at.isoformat(),
            validation_errors=validation_errors or []
        )


class CreateRuleUseCase:
    """Use case for creating new rule sets and versions."""
    
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
            rule_compiler: Compiler for rule validation
            cache_port: Cache for compiled rules
            event_bus: Event bus for publishing domain events
        """
        self._rule_repository = rule_repository
        self._rule_compiler = rule_compiler
        self._cache_port = cache_port
        self._event_bus = event_bus
    
    def execute(self, request: CreateRuleRequest) -> CreateRuleResponse:
        """
        Execute rule creation use case.
        
        Args:
            request: Rule creation request
            
        Returns:
            Rule creation response
            
        Raises:
            ValidationError: If input validation fails
        """
        # Validate request
        self._validate_request(request)
        
        # Convert to value objects
        tenant_id = TenantId(request.tenant_id)
        channel = Channel(request.channel)
        version = SemVer.from_string(request.version)
        
        # Convert rules to domain objects
        rule_definitions = []
        for rule_data in request.rules:
            try:
                rule_def = self._convert_to_rule_definition(rule_data)
                rule_definitions.append(rule_def)
            except ValueError as e:
                raise ValidationError(f"Invalid rule definition: {e}")
        
        # Validate rules using compiler
        validation_errors = self._rule_compiler.validate_rules(rule_definitions)
        
        # Check if rule set exists
        existing_rule_set = self._rule_repository.find_by_name(tenant_id, request.name)
        
        if existing_rule_set:
            # Add version to existing rule set
            rule_set = self._add_version_to_existing(
                existing_rule_set,
                version,
                rule_definitions,
                request.created_by,
                request.correlation_id
            )
        else:
            # Create new rule set
            rule_set = self._create_new_rule_set(
                tenant_id,
                channel,
                request.name,
                version,
                rule_definitions,
                request.description,
                request.created_by,
                request.correlation_id
            )
        
        # Save rule set
        saved_rule_set = self._rule_repository.save(rule_set)
        
        # Publish domain events
        try:
            events = saved_rule_set.get_domain_events()
            if events:
                self._event_bus.publish_rule_events(events)
                saved_rule_set = saved_rule_set.clear_domain_events()
        except Exception:
            # Don't fail use case if event publishing fails
            pass
        
        return CreateRuleResponse.from_rule_set(
            saved_rule_set,
            version,
            validation_errors
        )
    
    def _validate_request(self, request: CreateRuleRequest) -> None:
        """Validate rule creation request."""
        validation_errors = []
        
        # Validate required fields
        if not request.tenant_id or not request.tenant_id.strip():
            validation_errors.append("tenant_id is required")
        
        if not request.channel or not request.channel.strip():
            validation_errors.append("channel is required")
        
        if not request.name or not request.name.strip():
            validation_errors.append("name is required")
        
        if not request.version or not request.version.strip():
            validation_errors.append("version is required")
        
        if not request.rules or len(request.rules) == 0:
            validation_errors.append("at least one rule is required")
        
        if validation_errors:
            raise ValidationError("; ".join(validation_errors))
        
        # Validate name length and format
        if len(request.name) > 100:
            raise ValidationError("name must be 100 characters or less")
        
        # Validate version format
        try:
            SemVer.from_string(request.version)
        except ValueError:
            raise ValidationError("invalid version format, must be 'major.minor.patch'")
        
        # Validate value objects
        try:
            TenantId(request.tenant_id)
        except ValueError as e:
            raise ValidationError(f"invalid tenant_id: {e}")
        
        try:
            Channel(request.channel)
        except ValueError as e:
            raise ValidationError(f"invalid channel: {e}")
    
    def _convert_to_rule_definition(self, rule_data: Dict[str, Any]) -> RuleDefinition:
        """Convert rule data dict to RuleDefinition domain object."""
        from src.domain.rules.value_objects import RuleId, RuleType
        
        required_fields = ["id", "type", "field", "condition", "message", "severity"]
        for field in required_fields:
            if field not in rule_data:
                raise ValueError(f"missing required field: {field}")
        
        return RuleDefinition(
            id=RuleId(rule_data["id"]),
            type=RuleType(rule_data["type"]),
            field=rule_data["field"],
            condition=rule_data["condition"],
            message=rule_data["message"],
            severity=rule_data["severity"],
            metadata=rule_data.get("metadata")
        )
    
    def _create_new_rule_set(
        self,
        tenant_id: TenantId,
        channel: Channel,
        name: str,
        version: SemVer,
        rules: List[RuleDefinition],
        description: Optional[str],
        created_by: Optional[str],
        correlation_id: Optional[str]
    ) -> RuleSet:
        """Create new rule set with initial version."""
        from src.domain.rules.value_objects import RuleMetadata, RuleVersionId
        from datetime import datetime, timezone
        
        # Create rule set
        rule_set = RuleSet.create(
            tenant_id=tenant_id,
            channel=channel,
            name=name,
            description=description,
            created_by=created_by,
            correlation_id=correlation_id
        )
        
        # Create metadata
        metadata = RuleMetadata(
            created_by=created_by or "system",
            created_at=datetime.now(timezone.utc),
            description=f"Initial version {version}"
        )
        
        # Create rule version
        rule_version = RuleVersion.create(
            id=RuleVersionId(uuid4()),
            version=version,
            rules=rules,
            metadata=metadata,
            created_by=created_by or "system",
            correlation_id=correlation_id
        )
        
        # Add version to rule set
        return rule_set.add_version(
            rule_version,
            created_by or "system",
            correlation_id
        )
    
    def _add_version_to_existing(
        self,
        rule_set: RuleSet,
        version: SemVer,
        rules: List[RuleDefinition],
        created_by: Optional[str],
        correlation_id: Optional[str]
    ) -> RuleSet:
        """Add new version to existing rule set."""
        from src.domain.rules.value_objects import RuleMetadata, RuleVersionId
        from datetime import datetime, timezone
        
        # Create metadata
        metadata = RuleMetadata(
            created_by=created_by or "system",
            created_at=datetime.now(timezone.utc),
            description=f"Version {version}"
        )
        
        # Create rule version
        rule_version = RuleVersion.create(
            id=RuleVersionId(uuid4()),
            version=version,
            rules=rules,
            metadata=metadata,
            created_by=created_by or "system",
            correlation_id=correlation_id
        )
        
        # Add version to rule set
        return rule_set.add_version(
            rule_version,
            created_by or "system",
            correlation_id
        )