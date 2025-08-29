# Smart Rules Engine Ports

## Overview

Este documento define as interfaces (ports) do Smart Rules Engine usando Python Protocols, mantendo o domínio puro e desacoplado da infraestrutura.

## Repository Ports

### RuleSetRepository

```python
from typing import Protocol, Optional, List
from uuid import UUID
from datetime import datetime

from src.domain.value_objects import TenantId, Channel
from src.domain.rules import RuleSet, SemVer


class RuleSetRepository(Protocol):
    """Repository interface for RuleSet aggregate persistence."""
    
    async def get_by_id(
        self,
        rule_set_id: UUID,
        tenant_id: TenantId
    ) -> Optional[RuleSet]:
        """
        Retrieve a RuleSet by ID.
        
        Args:
            rule_set_id: Unique identifier of the rule set
            tenant_id: Tenant identifier for isolation
            
        Returns:
            RuleSet if found, None otherwise
        """
        ...
    
    async def get_by_channel(
        self,
        tenant_id: TenantId,
        channel: Channel
    ) -> Optional[RuleSet]:
        """
        Retrieve the current RuleSet for a specific channel.
        
        Args:
            tenant_id: Tenant identifier for isolation
            channel: Marketplace channel
            
        Returns:
            Current RuleSet for the channel if exists
        """
        ...
    
    async def find_by_version(
        self,
        tenant_id: TenantId,
        channel: Channel,
        version: SemVer
    ) -> Optional[RuleSet]:
        """
        Find a RuleSet containing a specific version.
        
        Args:
            tenant_id: Tenant identifier for isolation
            channel: Marketplace channel
            version: Semantic version to find
            
        Returns:
            RuleSet containing the version if exists
        """
        ...
    
    async def list_by_tenant(
        self,
        tenant_id: TenantId,
        include_deprecated: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[RuleSet]:
        """
        List all RuleSets for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            include_deprecated: Whether to include deprecated versions
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of RuleSets
        """
        ...
    
    async def save(
        self,
        rule_set: RuleSet
    ) -> None:
        """
        Persist a RuleSet aggregate.
        
        Args:
            rule_set: RuleSet to persist
            
        Raises:
            RepositoryError: If persistence fails
        """
        ...
    
    async def exists(
        self,
        tenant_id: TenantId,
        channel: Channel,
        version: SemVer
    ) -> bool:
        """
        Check if a specific version exists.
        
        Args:
            tenant_id: Tenant identifier
            channel: Marketplace channel
            version: Version to check
            
        Returns:
            True if version exists
        """
        ...
```

### RuleVersionRepository

```python
from typing import Protocol, Optional, List
from uuid import UUID

from src.domain.value_objects import TenantId
from src.domain.rules import RuleVersion, RuleStatus, SemVer


class RuleVersionRepository(Protocol):
    """Repository interface for RuleVersion entity persistence."""
    
    async def get_by_id(
        self,
        version_id: UUID,
        tenant_id: TenantId
    ) -> Optional[RuleVersion]:
        """
        Retrieve a RuleVersion by ID.
        
        Args:
            version_id: Unique identifier of the version
            tenant_id: Tenant identifier for isolation
            
        Returns:
            RuleVersion if found, None otherwise
        """
        ...
    
    async def find_published_versions(
        self,
        tenant_id: TenantId,
        channel: str,
        after_version: Optional[SemVer] = None
    ) -> List[RuleVersion]:
        """
        Find all published versions for a channel.
        
        Args:
            tenant_id: Tenant identifier
            channel: Marketplace channel
            after_version: Only return versions newer than this
            
        Returns:
            List of published RuleVersions
        """
        ...
    
    async def get_latest_by_status(
        self,
        tenant_id: TenantId,
        channel: str,
        status: RuleStatus
    ) -> Optional[RuleVersion]:
        """
        Get the latest version with a specific status.
        
        Args:
            tenant_id: Tenant identifier
            channel: Marketplace channel
            status: Version status to filter by
            
        Returns:
            Latest RuleVersion with the status if exists
        """
        ...
```

## Service Ports

### RuleEvaluator

```python
from typing import Protocol, Dict, Any, List
from dataclasses import dataclass

from src.domain.rules import RuleVersion, RuleDefinition


@dataclass
class EvaluationResult:
    """Result of rule evaluation."""
    rule_id: str
    field: str
    passed: bool
    severity: str
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class RuleEvaluator(Protocol):
    """Service for evaluating rules against data."""
    
    async def evaluate(
        self,
        rules: RuleVersion,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[EvaluationResult]:
        """
        Evaluate rules against a data record.
        
        Args:
            rules: RuleVersion containing rules to evaluate
            data: Data record to validate
            context: Optional evaluation context
            
        Returns:
            List of evaluation results
        """
        ...
    
    async def evaluate_batch(
        self,
        rules: RuleVersion,
        data_batch: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[int, List[EvaluationResult]]:
        """
        Evaluate rules against a batch of records.
        
        Args:
            rules: RuleVersion containing rules to evaluate
            data_batch: List of data records
            context: Optional evaluation context
            
        Returns:
            Dictionary mapping record index to evaluation results
        """
        ...
    
    def compile_rule(
        self,
        rule: RuleDefinition
    ) -> Any:
        """
        Compile a rule definition into an optimized form.
        
        Args:
            rule: Rule definition to compile
            
        Returns:
            Compiled rule representation
        """
        ...
```

### RuleValidator

```python
from typing import Protocol, List, Tuple

from src.domain.rules import RuleVersion, RuleDefinition


class RuleValidator(Protocol):
    """Service for validating rule definitions."""
    
    async def validate_syntax(
        self,
        rule: RuleDefinition
    ) -> Tuple[bool, List[str]]:
        """
        Validate rule syntax and structure.
        
        Args:
            rule: Rule to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        ...
    
    async def validate_version(
        self,
        version: RuleVersion
    ) -> Tuple[bool, List[str]]:
        """
        Validate an entire rule version.
        
        Args:
            version: RuleVersion to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        ...
    
    async def check_conflicts(
        self,
        rules: List[RuleDefinition]
    ) -> List[Tuple[str, str, str]]:
        """
        Check for conflicts between rules.
        
        Args:
            rules: List of rules to check
            
        Returns:
            List of conflicts (rule1_id, rule2_id, conflict_description)
        """
        ...
```

### CompatibilityChecker

```python
from typing import Protocol, List, Dict, Any

from src.domain.rules import RuleVersion, Compatibility


class CompatibilityChecker(Protocol):
    """Service for checking version compatibility."""
    
    async def check_compatibility(
        self,
        old_version: RuleVersion,
        new_version: RuleVersion
    ) -> Compatibility:
        """
        Check compatibility between two versions.
        
        Args:
            old_version: Current version
            new_version: New version to check
            
        Returns:
            Compatibility level
        """
        ...
    
    async def get_breaking_changes(
        self,
        old_version: RuleVersion,
        new_version: RuleVersion
    ) -> List[Dict[str, Any]]:
        """
        Identify breaking changes between versions.
        
        Args:
            old_version: Current version
            new_version: New version
            
        Returns:
            List of breaking changes with details
        """
        ...
    
    async def suggest_migration_path(
        self,
        from_version: RuleVersion,
        to_version: RuleVersion
    ) -> List[str]:
        """
        Suggest migration steps between versions.
        
        Args:
            from_version: Starting version
            to_version: Target version
            
        Returns:
            List of migration steps
        """
        ...
```

## Event Bus Ports

### EventBus

```python
from typing import Protocol, List, Any
from datetime import datetime

from src.domain.events import DomainEvent


class EventBus(Protocol):
    """Interface for publishing domain events."""
    
    async def publish(
        self,
        event: DomainEvent
    ) -> None:
        """
        Publish a single domain event.
        
        Args:
            event: Domain event to publish
            
        Raises:
            EventPublishError: If publishing fails
        """
        ...
    
    async def publish_batch(
        self,
        events: List[DomainEvent]
    ) -> None:
        """
        Publish multiple events atomically.
        
        Args:
            events: List of domain events
            
        Raises:
            EventPublishError: If any event fails to publish
        """
        ...
    
    async def schedule(
        self,
        event: DomainEvent,
        publish_at: datetime
    ) -> str:
        """
        Schedule an event for future publication.
        
        Args:
            event: Domain event to schedule
            publish_at: When to publish the event
            
        Returns:
            Schedule ID for cancellation
        """
        ...
```

### EventStore

```python
from typing import Protocol, List, Optional
from datetime import datetime
from uuid import UUID

from src.domain.events import DomainEvent


class EventStore(Protocol):
    """Interface for event sourcing storage."""
    
    async def append(
        self,
        stream_id: str,
        events: List[DomainEvent],
        expected_version: Optional[int] = None
    ) -> int:
        """
        Append events to a stream.
        
        Args:
            stream_id: Stream identifier (aggregate_id)
            events: Events to append
            expected_version: Expected stream version for optimistic locking
            
        Returns:
            New stream version
            
        Raises:
            ConcurrencyError: If expected_version doesn't match
        """
        ...
    
    async def read_stream(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: Optional[int] = None
    ) -> List[DomainEvent]:
        """
        Read events from a stream.
        
        Args:
            stream_id: Stream identifier
            from_version: Starting version (inclusive)
            to_version: Ending version (inclusive)
            
        Returns:
            List of events in order
        """
        ...
    
    async def read_by_correlation(
        self,
        correlation_id: str
    ) -> List[DomainEvent]:
        """
        Read all events with a correlation ID.
        
        Args:
            correlation_id: Correlation identifier
            
        Returns:
            List of correlated events
        """
        ...
```

## Cache Ports

### RuleCache

```python
from typing import Protocol, Optional, Any
from datetime import timedelta

from src.domain.rules import RuleVersion


class RuleCache(Protocol):
    """Interface for caching compiled rules."""
    
    async def get_compiled(
        self,
        cache_key: str
    ) -> Optional[Any]:
        """
        Retrieve compiled rules from cache.
        
        Args:
            cache_key: Cache key for the compiled rules
            
        Returns:
            Compiled rules if cached, None otherwise
        """
        ...
    
    async def set_compiled(
        self,
        cache_key: str,
        compiled_rules: Any,
        ttl: timedelta
    ) -> None:
        """
        Cache compiled rules.
        
        Args:
            cache_key: Cache key
            compiled_rules: Compiled rule representation
            ttl: Time to live
        """
        ...
    
    async def invalidate_channel(
        self,
        tenant_id: str,
        channel: str
    ) -> None:
        """
        Invalidate all cached rules for a channel.
        
        Args:
            tenant_id: Tenant identifier
            channel: Channel to invalidate
        """
        ...
    
    async def warmup(
        self,
        version: RuleVersion
    ) -> None:
        """
        Pre-warm cache with a rule version.
        
        Args:
            version: RuleVersion to cache
        """
        ...
```

## Notification Ports

### NotificationService

```python
from typing import Protocol, List, Dict, Any

from src.domain.rules import RuleSet, RuleVersion


class NotificationService(Protocol):
    """Service for notifying about rule changes."""
    
    async def notify_version_published(
        self,
        rule_set: RuleSet,
        version: RuleVersion,
        subscribers: List[str]
    ) -> None:
        """
        Notify subscribers about a new published version.
        
        Args:
            rule_set: RuleSet containing the version
            version: Published version
            subscribers: List of subscriber identifiers
        """
        ...
    
    async def notify_deprecation(
        self,
        rule_set: RuleSet,
        version: RuleVersion,
        sunset_date: datetime,
        affected_tenants: List[str]
    ) -> None:
        """
        Notify about version deprecation.
        
        Args:
            rule_set: RuleSet containing the version
            version: Deprecated version
            sunset_date: When version will be removed
            affected_tenants: Tenants using this version
        """
        ...
    
    async def alert_rollback(
        self,
        rule_set: RuleSet,
        from_version: str,
        to_version: str,
        reason: str
    ) -> None:
        """
        Alert about version rollback.
        
        Args:
            rule_set: RuleSet being rolled back
            from_version: Version rolling back from
            to_version: Version rolling back to
            reason: Rollback reason
        """
        ...
```

## Analytics Ports

### RuleMetrics

```python
from typing import Protocol, Dict, Any
from datetime import datetime, timedelta

from src.domain.rules import RuleVersion


class RuleMetrics(Protocol):
    """Interface for rule execution metrics."""
    
    async def record_evaluation(
        self,
        rule_id: str,
        version: str,
        passed: bool,
        duration_ms: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a rule evaluation metric.
        
        Args:
            rule_id: Rule identifier
            version: Rule version
            passed: Whether rule passed
            duration_ms: Evaluation duration
            metadata: Additional metadata
        """
        ...
    
    async def get_success_rate(
        self,
        rule_id: str,
        version: str,
        period: timedelta
    ) -> float:
        """
        Get rule success rate for a period.
        
        Args:
            rule_id: Rule identifier
            version: Rule version
            period: Time period to analyze
            
        Returns:
            Success rate (0.0 to 1.0)
        """
        ...
    
    async def get_performance_stats(
        self,
        version: RuleVersion,
        period: timedelta
    ) -> Dict[str, Any]:
        """
        Get performance statistics for a version.
        
        Args:
            version: RuleVersion to analyze
            period: Time period
            
        Returns:
            Performance statistics dictionary
        """
        ...
```