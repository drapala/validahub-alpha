"""Aggregates for Rules bounded context.

This module contains the RuleSet aggregate root following DDD principles.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple, Mapping
from uuid import uuid4

from src.domain.value_objects import TenantId, Channel
from .value_objects import (
    RuleSetId,
    RuleStatus,
    SemVer,
    Compatibility,
)
from .entities import RuleVersion
from .events import (
    RuleSetCreatedEvent,
    RuleSetPublishedEvent,
    RuleSetDeprecatedEvent,
    RuleVersionAddedEvent,
    RuleSetRolledBackEvent,
)


@dataclass(frozen=True)
class RuleSet:
    """
    RuleSet aggregate root managing a collection of rule versions.
    
    This aggregate ensures version consistency, manages lifecycle transitions,
    and maintains backward compatibility policies.
    
    IMMUTABILITY DESIGN:
    All collection fields use immutable types (Tuple, Mapping) to prevent external
    mutation that would bypass domain validation and event emission. This ensures
    that modifications can only happen through proper domain methods like
    add_version(), publish_version(), etc., which maintain invariants and emit
    appropriate domain events.
    
    Example of what this prevents:
    - rule_set.versions.append(version)  # Would bypass validation
    - rule_set.published_versions.clear()  # Would violate state consistency  
    - rule_set.compatibility_policy["new_key"] = value  # Would bypass business rules
    """
    
    id: RuleSetId
    tenant_id: TenantId
    channel: Channel
    name: str
    description: Optional[str]
    versions: Tuple[RuleVersion, ...]
    current_version: Optional[SemVer]
    published_versions: Tuple[SemVer, ...]
    deprecated_versions: Tuple[SemVer, ...]
    compatibility_policy: Mapping[str, Any]
    created_at: datetime
    updated_at: datetime
    _domain_events: List[Any] = field(default_factory=list, init=False, compare=False)
    
    def __post_init__(self) -> None:
        """Validate aggregate invariants."""
        if not self.created_at.tzinfo:
            raise ValueError("created_at must be timezone-aware")
        
        if not self.updated_at.tzinfo:
            raise ValueError("updated_at must be timezone-aware")
        
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be before created_at")
        
        # Validate name
        if not self.name or len(self.name) > 100:
            raise ValueError("Invalid rule set name")
        
        # Validate current version is in versions list
        if self.current_version:
            version_exists = any(
                v.version == self.current_version 
                for v in self.versions
            )
            if not version_exists:
                raise ValueError("Current version not found in versions list")
        
        # Validate published versions are in correct status
        for version in self.versions:
            if version.version in self.published_versions:
                if version.status != RuleStatus.PUBLISHED:
                    raise ValueError("Published version must have PUBLISHED status")
            if version.version in self.deprecated_versions:
                if version.status != RuleStatus.DEPRECATED:
                    raise ValueError("Deprecated version must have DEPRECATED status")
    
    @classmethod
    def create(
        cls,
        tenant_id: TenantId,
        channel: Channel,
        name: str,
        description: Optional[str] = None,
        compatibility_policy: Optional[Dict[str, Any]] = None,
        created_by: str = None,
        correlation_id: Optional[str] = None
    ) -> "RuleSet":
        """
        Factory method to create a new RuleSet.
        
        Args:
            tenant_id: Tenant identifier
            channel: Marketplace channel
            name: Rule set name
            description: Optional description
            compatibility_policy: Version compatibility policy
            created_by: User who created the rule set
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            New RuleSet instance with domain events
        """
        rule_set = cls(
            id=RuleSetId(uuid4()),
            tenant_id=tenant_id,
            channel=channel,
            name=name,
            description=description,
            versions=(),
            current_version=None,
            published_versions=(),
            deprecated_versions=(),
            compatibility_policy=compatibility_policy or {
                "auto_apply_patch": True,
                "shadow_period_days": 30,
                "require_major_opt_in": True
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Emit creation event
        rule_set._add_domain_event(
            RuleSetCreatedEvent.create(
                rule_set_id=str(rule_set.id.value),
                tenant_id=tenant_id.value,
                channel=channel.value,
                name=name,
                created_by=created_by,
                correlation_id=correlation_id
            )
        )
        
        return rule_set
    
    def add_version(
        self,
        version: RuleVersion,
        added_by: str,
        correlation_id: Optional[str] = None
    ) -> "RuleSet":
        """
        Add a new rule version to the set.
        
        Args:
            version: RuleVersion to add
            added_by: User who added the version
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            New RuleSet instance with added version
            
        Raises:
            ValueError: If version already exists or violates constraints
        """
        # Check version doesn't already exist
        for existing in self.versions:
            if existing.version == version.version:
                raise ValueError(f"Version {version.version} already exists")
        
        # Check version sequence (new version should be higher)
        if self.versions:
            # Use SemVer's built-in comparison
            latest = max(self.versions, key=lambda v: v.version)
            if not version.version.is_newer_than(latest.version):
                raise ValueError("New version must be higher than existing versions")
        
        # Check backward compatibility if required
        if self.current_version and self.compatibility_policy.get("enforce_compatibility"):
            current = self._get_version(self.current_version)
            if current:
                compat = version.is_backward_compatible_with(current)
                if compat == Compatibility.MAJOR and not self.compatibility_policy.get("allow_breaking"):
                    raise ValueError("Breaking changes not allowed by policy")
        
        new_versions = self.versions + (version,)
        new_rule_set = replace(
            self,
            versions=new_versions,
            updated_at=datetime.now(timezone.utc),
            _domain_events=[]  # Create new RuleSet with empty events list
        )
        
        # Emit version added event
        new_rule_set._add_domain_event(
            RuleVersionAddedEvent.create(
                rule_set_id=str(new_rule_set.id.value),
                tenant_id=self.tenant_id.value,
                version=str(version.version),
                rule_count=len(version.rules),
                added_by=added_by,
                correlation_id=correlation_id
            )
        )
        
        return new_rule_set
    
    def publish_version(
        self,
        version: SemVer,
        checksum: str,
        published_by: str,
        make_current: bool = True,
        correlation_id: Optional[str] = None
    ) -> "RuleSet":
        """
        Publish a specific version making it available for use.
        
        Args:
            version: Version to publish
            checksum: Checksum for integrity
            published_by: User who published
            make_current: Whether to make this the current version
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            New RuleSet instance with published version
            
        Raises:
            ValueError: If version not found or already published
        """
        rule_version = self._get_version(version)
        if not rule_version:
            raise ValueError(f"Version {version} not found")
        
        if version in self.published_versions:
            raise ValueError(f"Version {version} already published")
        
        # Publish the version
        published_version = rule_version.publish(checksum, published_by)
        
        # Update versions tuple
        new_versions = tuple(
            published_version if v.version == version else v
            for v in self.versions
        )
        
        new_published = self.published_versions + (version,)
        new_current = version if make_current else self.current_version
        
        new_rule_set = replace(
            self,
            versions=new_versions,
            published_versions=new_published,
            current_version=new_current,
            updated_at=datetime.now(timezone.utc),
            _domain_events=[]  # Create new RuleSet with empty events list
        )
        
        # Copy events from version
        for event in published_version.get_domain_events():
            new_rule_set._add_domain_event(event)
        
        # Emit published event
        new_rule_set._add_domain_event(
            RuleSetPublishedEvent.create(
                rule_set_id=str(new_rule_set.id.value),
                tenant_id=self.tenant_id.value,
                version=str(version),
                is_current=make_current,
                published_by=published_by,
                correlation_id=correlation_id
            )
        )
        
        return new_rule_set
    
    def deprecate_version(
        self,
        version: SemVer,
        deprecated_by: str,
        reason: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> "RuleSet":
        """
        Deprecate a specific version.
        
        Args:
            version: Version to deprecate
            deprecated_by: User who deprecated
            reason: Optional deprecation reason
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            New RuleSet instance with deprecated version
            
        Raises:
            ValueError: If version not found or is current version
        """
        if version == self.current_version:
            raise ValueError("Cannot deprecate current version")
        
        rule_version = self._get_version(version)
        if not rule_version:
            raise ValueError(f"Version {version} not found")
        
        if version in self.deprecated_versions:
            raise ValueError(f"Version {version} already deprecated")
        
        # Deprecate the version
        deprecated_version = rule_version.deprecate(deprecated_by, reason)
        
        # Update versions tuple
        new_versions = tuple(
            deprecated_version if v.version == version else v
            for v in self.versions
        )
        
        new_deprecated = self.deprecated_versions + (version,)
        # Remove from published_versions to maintain consistency
        new_published = tuple(v for v in self.published_versions if v != version)
        
        new_rule_set = replace(
            self,
            versions=new_versions,
            published_versions=new_published,
            deprecated_versions=new_deprecated,
            updated_at=datetime.now(timezone.utc),
            _domain_events=[]  # Create new RuleSet with empty events list
        )
        
        # Copy events from version
        for event in deprecated_version.get_domain_events():
            new_rule_set._add_domain_event(event)
        
        # Emit deprecated event
        new_rule_set._add_domain_event(
            RuleSetDeprecatedEvent.create(
                rule_set_id=str(new_rule_set.id.value),
                tenant_id=self.tenant_id.value,
                version=str(version),
                reason=reason,
                deprecated_by=deprecated_by,
                correlation_id=correlation_id
            )
        )
        
        return new_rule_set
    
    def rollback_to_version(
        self,
        version: SemVer,
        rolled_back_by: str,
        reason: str,
        correlation_id: Optional[str] = None
    ) -> "RuleSet":
        """
        Rollback current version to a previous published version.
        
        Args:
            version: Version to rollback to
            rolled_back_by: User who initiated rollback
            reason: Reason for rollback
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            New RuleSet instance with rolled back version
            
        Raises:
            ValueError: If version not found or not published
        """
        if version not in self.published_versions:
            raise ValueError(f"Version {version} is not published")
        
        if version in self.deprecated_versions:
            raise ValueError(f"Cannot rollback to deprecated version {version}")
        
        if version == self.current_version:
            raise ValueError(f"Already at version {version}")
        
        previous_version = self.current_version
        
        new_rule_set = replace(
            self,
            current_version=version,
            updated_at=datetime.now(timezone.utc),
            _domain_events=[]  # Create new RuleSet with empty events list
        )
        
        # Emit rollback event
        new_rule_set._add_domain_event(
            RuleSetRolledBackEvent.create(
                rule_set_id=str(new_rule_set.id.value),
                tenant_id=self.tenant_id.value,
                from_version=str(previous_version) if previous_version else None,
                to_version=str(version),
                reason=reason,
                rolled_back_by=rolled_back_by,
                correlation_id=correlation_id
            )
        )
        
        return new_rule_set
    
    def get_current_version(self) -> Optional[RuleVersion]:
        """Get the current active version."""
        if not self.current_version:
            return None
        return self._get_version(self.current_version)
    
    def get_latest_version(self) -> Optional[RuleVersion]:
        """Get the latest version (published or not)."""
        if not self.versions:
            return None
        # Use SemVer's built-in comparison
        return max(self.versions, key=lambda v: v.version)
    
    def get_published_versions(self) -> Tuple[RuleVersion, ...]:
        """Get all published versions."""
        return tuple(v for v in self.versions if v.version in self.published_versions)
    
    def get_compatible_upgrade(self, from_version: SemVer) -> Optional[RuleVersion]:
        """
        Find the best compatible upgrade from a given version.
        
        Args:
            from_version: Version to upgrade from
            
        Returns:
            Best compatible version or None if no upgrade available
        """
        candidates = []
        
        for version in self.get_published_versions():
            if version.version.is_newer_than(from_version):
                compat = version.version.is_compatible_with(from_version)
                
                # Apply compatibility policy
                if compat == Compatibility.PATCH and self.compatibility_policy.get("auto_apply_patch"):
                    candidates.append((version, 3))  # Highest priority
                elif compat == Compatibility.MINOR:
                    candidates.append((version, 2))  # Medium priority
                elif compat == Compatibility.MAJOR and not self.compatibility_policy.get("require_major_opt_in"):
                    candidates.append((version, 1))  # Lowest priority
        
        if not candidates:
            return None
        
        # Sort by priority and version (using SemVer comparison)
        candidates.sort(key=lambda x: (x[1], x[0].version), reverse=True)
        return candidates[0][0]
    
    def _get_version(self, version: SemVer) -> Optional[RuleVersion]:
        """Get a specific version by SemVer."""
        for v in self.versions:
            if v.version == version:
                return v
        return None
    
    def _add_domain_event(self, event: Any) -> None:
        """Add a domain event to this aggregate."""
        self._domain_events.append(event)
    
    def get_domain_events(self) -> List[Any]:
        """Get all domain events from this aggregate and its entities."""
        events = list(self._domain_events)
        
        # Collect events from entities
        for version in self.versions:
            events.extend(version.get_domain_events())
        
        return events
    
    def clear_domain_events(self) -> "RuleSet":
        """Clear all domain events from this aggregate."""
        # Clear events from entities
        new_versions = tuple(
            version.clear_domain_events()
            for version in self.versions
        )
        
        # Create new RuleSet with cleared events
        return replace(
            self,
            versions=new_versions,
            _domain_events=[]
        )
    
    def __str__(self) -> str:
        """String representation."""
        return f"RuleSet(id={self.id}, channel={self.channel}, current={self.current_version})"