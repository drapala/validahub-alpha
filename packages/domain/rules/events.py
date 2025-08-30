"""Domain events for Rules bounded context.

This module defines domain events specific to the Rules context.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.domain.events import DomainEvent

# RuleSet Events

@dataclass(frozen=True)
class RuleSetCreatedEvent(DomainEvent):
    """Event emitted when a new rule set is created."""
    
    channel: str = ""
    name: str = ""
    created_by: str | None = None
    
    @classmethod
    def create(
        cls,
        rule_set_id: str,
        tenant_id: str,
        channel: str,
        name: str,
        created_by: str | None = None,
        correlation_id: str | None = None
    ) -> "RuleSetCreatedEvent":
        """Factory method to create a RuleSetCreatedEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=rule_set_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            channel=channel,
            name=name,
            created_by=created_by
        )


@dataclass(frozen=True)
class RuleSetPublishedEvent(DomainEvent):
    """Event emitted when a rule set version is published."""
    
    version: str = ""
    is_current: bool = False
    published_by: str = ""
    
    @classmethod
    def create(
        cls,
        rule_set_id: str,
        tenant_id: str,
        version: str,
        is_current: bool,
        published_by: str,
        correlation_id: str | None = None
    ) -> "RuleSetPublishedEvent":
        """Factory method to create a RuleSetPublishedEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=rule_set_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            version=version,
            is_current=is_current,
            published_by=published_by
        )


@dataclass(frozen=True)
class RuleSetDeprecatedEvent(DomainEvent):
    """Event emitted when a rule set version is deprecated."""
    
    version: str = ""
    reason: str | None = None
    deprecated_by: str = ""
    
    @classmethod
    def create(
        cls,
        rule_set_id: str,
        tenant_id: str,
        version: str,
        reason: str | None,
        deprecated_by: str,
        correlation_id: str | None = None
    ) -> "RuleSetDeprecatedEvent":
        """Factory method to create a RuleSetDeprecatedEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=rule_set_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            version=version,
            reason=reason,
            deprecated_by=deprecated_by
        )


@dataclass(frozen=True)
class RuleSetRolledBackEvent(DomainEvent):
    """Event emitted when a rule set is rolled back to a previous version."""
    
    from_version: str | None = None
    to_version: str = ""
    reason: str = ""
    rolled_back_by: str = ""
    
    @classmethod
    def create(
        cls,
        rule_set_id: str,
        tenant_id: str,
        from_version: str | None,
        to_version: str,
        reason: str,
        rolled_back_by: str,
        correlation_id: str | None = None
    ) -> "RuleSetRolledBackEvent":
        """Factory method to create a RuleSetRolledBackEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=rule_set_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            from_version=from_version,
            to_version=to_version,
            reason=reason,
            rolled_back_by=rolled_back_by
        )


# RuleVersion Events

@dataclass(frozen=True)
class RuleVersionCreatedEvent(DomainEvent):
    """Event emitted when a new rule version is created."""
    
    version: str = ""
    rule_count: int = 0
    created_by: str = ""
    
    @classmethod
    def create(
        cls,
        rule_version_id: str,
        tenant_id: str,
        version: str,
        rule_count: int,
        created_by: str,
        correlation_id: str | None = None
    ) -> "RuleVersionCreatedEvent":
        """Factory method to create a RuleVersionCreatedEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=rule_version_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            version=version,
            rule_count=rule_count,
            created_by=created_by
        )


@dataclass(frozen=True)
class RuleVersionAddedEvent(DomainEvent):
    """Event emitted when a rule version is added to a rule set."""
    
    version: str = ""
    rule_count: int = 0
    added_by: str = ""
    
    @classmethod
    def create(
        cls,
        rule_set_id: str,
        tenant_id: str,
        version: str,
        rule_count: int,
        added_by: str,
        correlation_id: str | None = None
    ) -> "RuleVersionAddedEvent":
        """Factory method to create a RuleVersionAddedEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=rule_set_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            version=version,
            rule_count=rule_count,
            added_by=added_by
        )


@dataclass(frozen=True)
class RuleValidatedEvent(DomainEvent):
    """Event emitted when rules are validated."""
    
    version: str = ""
    validation_result: bool = False
    error_count: int = 0
    validated_by: str = ""
    
    @classmethod
    def create(
        cls,
        rule_version_id: str,
        tenant_id: str,
        version: str,
        validation_result: bool,
        error_count: int,
        validated_by: str,
        correlation_id: str | None = None
    ) -> "RuleValidatedEvent":
        """Factory method to create a RuleValidatedEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=rule_version_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            version=version,
            validation_result=validation_result,
            error_count=error_count,
            validated_by=validated_by
        )


# Rule Evaluation Events (Runtime)

@dataclass(frozen=True)
class RuleEvaluationEvent(DomainEvent):
    """Event emitted when a rule is evaluated against data."""
    
    rule_id: str = ""
    rule_version: str = ""
    field: str = ""
    value: Any = None
    passed: bool = False
    severity: str = ""
    message: str | None = None
    
    @classmethod
    def create(
        cls,
        job_id: str,
        tenant_id: str,
        rule_id: str,
        rule_version: str,
        field: str,
        value: Any,
        passed: bool,
        severity: str,
        message: str | None = None,
        correlation_id: str | None = None
    ) -> "RuleEvaluationEvent":
        """Factory method to create a RuleEvaluationEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=job_id,  # Associated with job being validated
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            rule_id=rule_id,
            rule_version=rule_version,
            field=field,
            value=value,
            passed=passed,
            severity=severity,
            message=message
        )


@dataclass(frozen=True)
class RuleSetAppliedEvent(DomainEvent):
    """Event emitted when a rule set is applied to a job."""
    
    rule_set_id: str = ""
    rule_version: str = ""
    total_rules: int = 0
    rules_passed: int = 0
    rules_failed: int = 0
    evaluation_duration_ms: float = 0.0
    
    @classmethod
    def create(
        cls,
        job_id: str,
        tenant_id: str,
        rule_set_id: str,
        rule_version: str,
        total_rules: int,
        rules_passed: int,
        rules_failed: int,
        evaluation_duration_ms: float,
        correlation_id: str | None = None
    ) -> "RuleSetAppliedEvent":
        """Factory method to create a RuleSetAppliedEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=job_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            rule_set_id=rule_set_id,
            rule_version=rule_version,
            total_rules=total_rules,
            rules_passed=rules_passed,
            rules_failed=rules_failed,
            evaluation_duration_ms=evaluation_duration_ms
        )


# Integration Events (for cross-context communication)

@dataclass(frozen=True)
class RulesReadyForJobEvent(DomainEvent):
    """Integration event: Rules are ready to be applied to a job."""
    
    job_id: str = ""
    rule_set_id: str = ""
    rule_version: str = ""
    channel: str = ""
    
    @classmethod
    def create(
        cls,
        job_id: str,
        tenant_id: str,
        rule_set_id: str,
        rule_version: str,
        channel: str,
        correlation_id: str | None = None
    ) -> "RulesReadyForJobEvent":
        """Factory method to create a RulesReadyForJobEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=job_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            job_id=job_id,
            rule_set_id=rule_set_id,
            rule_version=rule_version,
            channel=channel
        )


@dataclass(frozen=True)
class RuleViolationDetectedEvent(DomainEvent):
    """Integration event: Rule violation detected during validation."""
    
    job_id: str = ""
    rule_id: str = ""
    field: str = ""
    severity: str = ""
    row_number: int | None = None
    column_name: str | None = None
    violation_details: dict[str, Any] | None = None
    
    @classmethod
    def create(
        cls,
        job_id: str,
        tenant_id: str,
        rule_id: str,
        field: str,
        severity: str,
        row_number: int | None = None,
        column_name: str | None = None,
        violation_details: dict[str, Any] | None = None,
        correlation_id: str | None = None
    ) -> "RuleViolationDetectedEvent":
        """Factory method to create a RuleViolationDetectedEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=job_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            job_id=job_id,
            rule_id=rule_id,
            field=field,
            severity=severity,
            row_number=row_number,
            column_name=column_name,
            violation_details=violation_details
        )