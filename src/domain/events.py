"""Domain events for ValidaHub.

This module defines domain events that are emitted by aggregates when 
significant business events occur. These events are used for logging,
auditing, and eventual consistency between bounded contexts.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import uuid4

from src.domain.value_objects import JobId, TenantId


@dataclass(frozen=True)
class DomainEvent(ABC):
    """Base class for all domain events."""
    
    event_id: str
    aggregate_id: str
    tenant_id: str
    occurred_at: datetime
    correlation_id: Optional[str] = None
    
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
        job_id: JobId,
        tenant_id: TenantId,
        status: str,
        creation_duration_ms: float,
        correlation_id: Optional[str] = None
    ) -> "JobCreatedEvent":
        """Factory method to create a JobCreatedEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=str(job_id.value),
            tenant_id=tenant_id.value,
            occurred_at=datetime.now(timezone.utc),
            correlation_id=correlation_id,
            status=status,
            creation_duration_ms=creation_duration_ms
        )


@dataclass(frozen=True)
class JobStateTransitionAttemptedEvent(DomainEvent):
    """Event emitted when a job state transition is attempted (before validation)."""
    
    from_status: str = ""
    to_status: str = ""
    
    @classmethod
    def create(
        cls,
        job_id: JobId,
        tenant_id: TenantId,
        from_status: str,
        to_status: str,
        correlation_id: Optional[str] = None
    ) -> "JobStateTransitionAttemptedEvent":
        """Factory method to create a JobStateTransitionAttemptedEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=str(job_id.value),
            tenant_id=tenant_id.value,
            occurred_at=datetime.now(timezone.utc),
            correlation_id=correlation_id,
            from_status=from_status,
            to_status=to_status
        )


@dataclass(frozen=True)
class JobStateTransitionSucceededEvent(DomainEvent):
    """Event emitted when a job state transition succeeds."""
    
    from_status: str = ""
    to_status: str = ""
    transition_duration_ms: float = 0.0
    total_job_duration_ms: Optional[float] = None
    error_message: Optional[str] = None
    retry_attempt: Optional[int] = None
    
    @classmethod
    def create(
        cls,
        job_id: JobId,
        tenant_id: TenantId,
        from_status: str,
        to_status: str,
        transition_duration_ms: float,
        correlation_id: Optional[str] = None,
        total_job_duration_ms: Optional[float] = None,
        error_message: Optional[str] = None,
        retry_attempt: Optional[int] = None
    ) -> "JobStateTransitionSucceededEvent":
        """Factory method to create a JobStateTransitionSucceededEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=str(job_id.value),
            tenant_id=tenant_id.value,
            occurred_at=datetime.now(timezone.utc),
            correlation_id=correlation_id,
            from_status=from_status,
            to_status=to_status,
            transition_duration_ms=transition_duration_ms,
            total_job_duration_ms=total_job_duration_ms,
            error_message=error_message,
            retry_attempt=retry_attempt
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
        job_id: JobId,
        tenant_id: TenantId,
        from_status: str,
        attempted_status: str,
        reason: str,
        correlation_id: Optional[str] = None
    ) -> "JobStateTransitionFailedEvent":
        """Factory method to create a JobStateTransitionFailedEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=str(job_id.value),
            tenant_id=tenant_id.value,
            occurred_at=datetime.now(timezone.utc),
            correlation_id=correlation_id,
            from_status=from_status,
            attempted_status=attempted_status,
            reason=reason
        )


# Audit events for integration with existing audit system
@dataclass(frozen=True)
class JobAuditEvent(DomainEvent):
    """Event for job audit trail integration."""
    
    event_type: str = ""  # Maps to AuditEventType
    status: str = ""
    actor_id: Optional[str] = None
    from_status: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        job_id: JobId,
        tenant_id: TenantId,
        event_type: str,
        status: str,
        correlation_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        from_status: Optional[str] = None
    ) -> "JobAuditEvent":
        """Factory method to create a JobAuditEvent."""
        return cls(
            event_id=str(uuid4()),
            aggregate_id=str(job_id.value),
            tenant_id=tenant_id.value,
            occurred_at=datetime.now(timezone.utc),
            correlation_id=correlation_id,
            event_type=event_type,
            status=status,
            actor_id=actor_id,
            from_status=from_status
        )