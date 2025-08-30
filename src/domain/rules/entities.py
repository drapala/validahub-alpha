"""Entities for Rules bounded context.

This module contains entities that belong to the RuleSet aggregate.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from uuid import uuid4

from src.domain.value_objects import TenantId
from .value_objects import (
    RuleVersionId,
    RuleDefinition,
    RuleStatus,
    SemVer,
    Compatibility,
    RuleMetadata,
)
from .events import (
    RuleVersionCreatedEvent,
    RuleValidatedEvent,
)


@dataclass(frozen=True)
class RuleVersion:
    """
    Entity representing a version of rules within a RuleSet.
    
    This entity is part of the RuleSet aggregate and manages individual
    rule versions with their lifecycle and validation status.
    
    IMMUTABILITY DESIGN:
    The 'rules' field uses Tuple instead of List to prevent external mutation
    that would bypass domain validation. This ensures that rule modifications
    can only happen through proper entity methods that maintain data integrity
    and business invariants.
    
    Example of what this prevents:
    - rule_version.rules.append(new_rule)  # Would bypass ID uniqueness validation
    - rule_version.rules.clear()  # Would violate "at least one rule" constraint
    - rule_version.rules[0] = different_rule  # Would bypass type validation
    
    Use get_rules_by_*() methods to safely query rules without mutation risk.
    """
    
    id: RuleVersionId
    version: SemVer
    status: RuleStatus
    rules: Tuple[RuleDefinition, ...]
    metadata: RuleMetadata
    validation_errors: Optional[List[str]] = None
    compatibility_notes: Optional[Dict[str, Any]] = None
    checksum: Optional[str] = None
    _domain_events: List[Any] = field(default_factory=list, init=False, compare=False)
    
    def __post_init__(self) -> None:
        """Validate entity invariants."""
        # Validate rules list is not empty
        if not self.rules:
            raise ValueError("Rule version must contain at least one rule")
        
        # Validate unique rule IDs within version
        rule_ids = [str(rule.id) for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Duplicate rule IDs within version")
        
        # Validate status transitions
        if self.status == RuleStatus.VALIDATED and self.validation_errors:
            raise ValueError("Validated rules cannot have validation errors")
        
        if self.status == RuleStatus.PUBLISHED and not self.checksum:
            raise ValueError("Published rules must have a checksum")
    
    @classmethod
    def create(
        cls,
        version: SemVer,
        rules: List[RuleDefinition],
        created_by: str,
        tenant_id: TenantId,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        correlation_id: Optional[str] = None
    ) -> "RuleVersion":
        """
        Factory method to create a new RuleVersion in DRAFT status.
        
        Args:
            version: Semantic version for this rule version
            rules: List of rule definitions
            created_by: User who created the version
            tenant_id: Tenant identifier
            description: Optional description
            tags: Optional tags for categorization
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            New RuleVersion instance in DRAFT status with domain events
        """
        rule_version = cls(
            id=RuleVersionId(uuid4()),
            version=version,
            status=RuleStatus.DRAFT,
            rules=rules,
            metadata=RuleMetadata(
                created_by=created_by,
                created_at=datetime.now(timezone.utc),
                description=description,
                tags=tags
            ),
            validation_errors=None,
            compatibility_notes=None,
            checksum=None
        )
        
        # Emit creation event
        rule_version._add_domain_event(
            RuleVersionCreatedEvent.create(
                rule_version_id=str(rule_version.id.value),
                tenant_id=tenant_id.value,
                version=str(rule_version.version),
                rule_count=len(rules),
                created_by=created_by,
                correlation_id=correlation_id
            )
        )
        
        return rule_version
    
    def validate(
        self,
        tenant_id: TenantId,
        validated_by: str,
        validation_result: bool,
        errors: Optional[List[str]] = None,
        correlation_id: Optional[str] = None
    ) -> "RuleVersion":
        """
        Validate the rule version and transition to VALIDATED status if successful.
        
        Args:
            tenant_id: Tenant identifier
            validated_by: User who performed validation
            validation_result: Whether validation passed
            errors: List of validation errors if failed
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            New RuleVersion instance with updated status
            
        Raises:
            ValueError: If transition is not allowed
        """
        if self.status != RuleStatus.DRAFT:
            raise ValueError(f"Cannot validate rules in {self.status.value} status")
        
        new_status = RuleStatus.VALIDATED if validation_result else RuleStatus.DRAFT
        new_version = replace(
            self,
            status=new_status,
            validation_errors=None if validation_result else errors,
            metadata=replace(
                self.metadata,
                modified_by=validated_by,
                modified_at=datetime.now(timezone.utc)
            ),
            _domain_events=[]  # Create new entity with empty events list
        )
        
        # Emit validation event
        new_version._add_domain_event(
            RuleValidatedEvent.create(
                rule_version_id=str(new_version.id.value),
                tenant_id=tenant_id.value,
                version=str(new_version.version),
                validation_result=validation_result,
                error_count=len(errors) if errors else 0,
                validated_by=validated_by,
                correlation_id=correlation_id
            )
        )
        
        return new_version
    
    def publish(self, checksum: str, published_by: str) -> "RuleVersion":
        """
        Publish the rule version making it immutable.
        
        Args:
            checksum: Checksum for integrity verification
            published_by: User who published the version
            
        Returns:
            New RuleVersion instance in PUBLISHED status
            
        Raises:
            ValueError: If transition is not allowed
        """
        if self.status != RuleStatus.VALIDATED:
            raise ValueError(f"Cannot publish rules in {self.status.value} status")
        
        new_version = replace(
            self,
            status=RuleStatus.PUBLISHED,
            checksum=checksum,
            metadata=replace(
                self.metadata,
                modified_by=published_by,
                modified_at=datetime.now(timezone.utc)
            ),
            _domain_events=[]  # Create new entity with empty events list
        )
        
        return new_version
    
    def deprecate(self, deprecated_by: str, reason: Optional[str] = None) -> "RuleVersion":
        """
        Deprecate the rule version.
        
        Args:
            deprecated_by: User who deprecated the version
            reason: Optional reason for deprecation
            
        Returns:
            New RuleVersion instance in DEPRECATED status
            
        Raises:
            ValueError: If transition is not allowed
        """
        if self.status != RuleStatus.PUBLISHED:
            raise ValueError(f"Cannot deprecate rules in {self.status.value} status")
        
        # Update compatibility notes if reason provided
        updated_notes = self.compatibility_notes or {}
        if reason:
            updated_notes = {**updated_notes, "deprecation_reason": reason}
        
        new_version = replace(
            self,
            status=RuleStatus.DEPRECATED,
            metadata=replace(
                self.metadata,
                modified_by=deprecated_by,
                modified_at=datetime.now(timezone.utc)
            ),
            compatibility_notes=updated_notes if reason else self.compatibility_notes,
            _domain_events=[]  # Create new entity with empty events list
        )
        
        return new_version
    
    def is_backward_compatible_with(self, other: "RuleVersion") -> Compatibility:
        """
        Check backward compatibility with another version.
        
        Args:
            other: Another RuleVersion to compare with
            
        Returns:
            Compatibility level between versions
        """
        # Version-based compatibility check
        version_compat = self.version.is_compatible_with(other.version)
        
        # Rule-based compatibility check
        # Major: removed rules or changed rule types
        # Minor: new rules added
        # Patch: only rule conditions or messages changed
        
        self_rule_ids = {str(rule.id) for rule in self.rules}
        other_rule_ids = {str(rule.id) for rule in other.rules}
        
        # Check for removed rules (major change)
        if other_rule_ids - self_rule_ids:
            return Compatibility.MAJOR
        
        # Check for rule type changes (major change)
        self_rule_types = {str(rule.id): rule.type for rule in self.rules}
        other_rule_types = {str(rule.id): rule.type for rule in other.rules if str(rule.id) in self_rule_ids}
        
        for rule_id in other_rule_types:
            if self_rule_types.get(rule_id) != other_rule_types[rule_id]:
                return Compatibility.MAJOR
        
        # Check for new rules (minor change)
        if self_rule_ids - other_rule_ids:
            return Compatibility.MINOR
        
        # Otherwise it's a patch change
        return Compatibility.PATCH
    
    def get_rule_by_id(self, rule_id: str) -> Optional[RuleDefinition]:
        """Get a specific rule by its ID."""
        for rule in self.rules:
            if str(rule.id) == rule_id:
                return rule
        return None
    
    def get_rules_by_field(self, field: str) -> Tuple[RuleDefinition, ...]:
        """Get all rules that apply to a specific field."""
        return tuple(rule for rule in self.rules if rule.field == field)
    
    def get_rules_by_severity(self, severity: str) -> Tuple[RuleDefinition, ...]:
        """Get all rules with a specific severity level."""
        return tuple(rule for rule in self.rules if rule.severity == severity)
    
    def _add_domain_event(self, event: Any) -> None:
        """Add a domain event to this entity."""
        self._domain_events.append(event)
    
    def get_domain_events(self) -> List[Any]:
        """Get all domain events from this entity."""
        return list(self._domain_events)
    
    def clear_domain_events(self) -> "RuleVersion":
        """Clear all domain events from this entity."""
        return replace(self, _domain_events=[])
    
    def __str__(self) -> str:
        """String representation."""
        return f"RuleVersion(id={self.id}, version={self.version}, status={self.status.value})"