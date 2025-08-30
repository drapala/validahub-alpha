"""Domain events for ValidaHub.

This module defines domain events that are emitted by aggregates when
significant business events occur. These events are used for logging,
auditing, and eventual consistency between bounded contexts.
"""

import threading
from abc import ABC
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class DomainEvent(ABC):
    """Base class for all domain events."""

    event_id: str
    aggregate_id: str
    tenant_id: str
    occurred_at: datetime
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        """Validate domain event invariants."""
        if not self.occurred_at.tzinfo:
            raise ValueError("occurred_at must be timezone-aware")


@dataclass(frozen=True)
class JobCreatedEvent(DomainEvent):
    """Event emitted when a new job is created."""

    status: str = ""
    creation_duration_ms: float = 0.0

    @classmethod
    def create(
        cls,
        job_id: str,
        tenant_id: str,
        status: str,
        creation_duration_ms: float,
        correlation_id: str | None = None,
    ) -> "JobCreatedEvent":
        """Factory method to create a JobCreatedEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=job_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            status=status,
            creation_duration_ms=creation_duration_ms,
        )


@dataclass(frozen=True)
class JobStateTransitionAttemptedEvent(DomainEvent):
    """Event emitted when a job state transition is attempted (before validation)."""

    from_status: str = ""
    to_status: str = ""

    @classmethod
    def create(
        cls,
        job_id: str,
        tenant_id: str,
        from_status: str,
        to_status: str,
        correlation_id: str | None = None,
    ) -> "JobStateTransitionAttemptedEvent":
        """Factory method to create a JobStateTransitionAttemptedEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=job_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            from_status=from_status,
            to_status=to_status,
        )


@dataclass(frozen=True)
class JobStateTransitionSucceededEvent(DomainEvent):
    """Event emitted when a job state transition succeeds."""

    from_status: str = ""
    to_status: str = ""
    transition_duration_ms: float = 0.0
    total_job_duration_ms: float | None = None
    error_message: str | None = None
    retry_attempt: int | None = None

    @classmethod
    def create(
        cls,
        job_id: str,
        tenant_id: str,
        from_status: str,
        to_status: str,
        transition_duration_ms: float,
        correlation_id: str | None = None,
        total_job_duration_ms: float | None = None,
        error_message: str | None = None,
        retry_attempt: int | None = None,
    ) -> "JobStateTransitionSucceededEvent":
        """Factory method to create a JobStateTransitionSucceededEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=job_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            from_status=from_status,
            to_status=to_status,
            transition_duration_ms=transition_duration_ms,
            total_job_duration_ms=total_job_duration_ms,
            error_message=error_message,
            retry_attempt=retry_attempt,
        )


@dataclass(frozen=True)
class JobStateTransitionFailedEvent(DomainEvent):
    """Event emitted when a job state transition fails validation."""

    from_status: str = ""
    attempted_status: str = ""
    reason: str = ""

    @classmethod
    def create(
        cls,
        job_id: str,
        tenant_id: str,
        from_status: str,
        attempted_status: str,
        reason: str,
        correlation_id: str | None = None,
    ) -> "JobStateTransitionFailedEvent":
        """Factory method to create a JobStateTransitionFailedEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=job_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            from_status=from_status,
            attempted_status=attempted_status,
            reason=reason,
        )


# Audit events for integration with existing audit system
@dataclass(frozen=True)
class JobAuditEvent(DomainEvent):
    """Event for job audit trail integration."""

    event_type: str = ""  # Maps to AuditEventType
    status: str = ""
    actor_id: str | None = None
    from_status: str | None = None

    @classmethod
    def create(
        cls,
        job_id: str,
        tenant_id: str,
        event_type: str,
        status: str,
        correlation_id: str | None = None,
        actor_id: str | None = None,
        from_status: str | None = None,
    ) -> "JobAuditEvent":
        """Factory method to create a JobAuditEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=job_id,
            tenant_id=tenant_id,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            event_type=event_type,
            status=status,
            actor_id=actor_id,
            from_status=from_status,
        )


# Value Object Events for logging and security purposes
@dataclass(frozen=True)
class ValueObjectValidationEvent(DomainEvent):
    """Event emitted when value object validation occurs (success or failure)."""

    value_object_type: str = ""
    validation_result: str = ""  # "success" or "failed"
    error_type: str | None = None
    error_reason: str | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def create_validation_failed(
        cls,
        value_object_type: str,
        error_type: str,
        error_reason: str,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        **metadata: Any,
    ) -> "ValueObjectValidationEvent":
        """Create a validation failed event."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id="value_object_validation",
            tenant_id=tenant_id or "unknown",
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            value_object_type=value_object_type,
            validation_result="failed",
            error_type=error_type,
            error_reason=error_reason,
            metadata=metadata,
        )

    @classmethod
    def create_validation_success(
        cls,
        value_object_type: str,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        **metadata: Any,
    ) -> "ValueObjectValidationEvent":
        """Create a validation success event."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id="value_object_validation",
            tenant_id=tenant_id or "unknown",
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            value_object_type=value_object_type,
            validation_result="success",
            metadata=metadata,
        )


@dataclass(frozen=True)
class SecurityThreatDetectedEvent(DomainEvent):
    """Event emitted when a security threat is detected in value object validation."""

    threat_type: str = ""  # "injection_attempt", "dangerous_file", etc.
    field_name: str = ""
    severity: str = "WARNING"  # "LOW", "WARNING", "ERROR", "CRITICAL"
    details: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        threat_type: str,
        field_name: str,
        severity: str = "WARNING",
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        **details: Any,
    ) -> "SecurityThreatDetectedEvent":
        """Create a security threat detected event."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id="security_threat_detection",
            tenant_id=tenant_id or "unknown",
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            threat_type=threat_type,
            field_name=field_name,
            severity=severity,
            details=details,
        )


# Thread-local event collector for value objects
_thread_local = threading.local()


class DomainEventCollector:
    """Collects domain events during value object creation."""

    @classmethod
    def collect_event(cls, event: DomainEvent) -> None:
        """Add an event to the current thread's collection."""
        if not hasattr(_thread_local, "events"):
            _thread_local.events = []
        _thread_local.events.append(event)

    @classmethod
    def get_collected_events(cls) -> list[DomainEvent]:
        """Get all collected events for the current thread."""
        if not hasattr(_thread_local, "events"):
            return []
        return _thread_local.events.copy()

    @classmethod
    def clear_collected_events(cls) -> None:
        """Clear all collected events for the current thread."""
        if hasattr(_thread_local, "events"):
            _thread_local.events.clear()
