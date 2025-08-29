"""Job aggregate for ValidaHub domain.

This module implements the core Job aggregate following DDD principles.
The Job is the main aggregate root that manages CSV processing workflows.

This aggregate follows the Domain Events pattern - instead of direct logging,
it emits domain events that are collected and published by the application layer.
"""

import time
from dataclasses import dataclass, replace, field
from datetime import datetime, timezone
from enum import Enum
from typing import List
from uuid import uuid4

from src.domain.errors import DomainError, InvalidStateTransitionError
from src.domain.value_objects import JobId, TenantId
from src.domain.events import (
    DomainEvent,
    JobCreatedEvent, 
    JobStateTransitionAttemptedEvent,
    JobStateTransitionSucceededEvent,
    JobStateTransitionFailedEvent,
    JobAuditEvent
)


class JobStatus(Enum):
    """Job processing status with minimal state machine."""
    
    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass(frozen=True)
class Job:
    """
    Job aggregate representing a CSV processing job.
    
    This aggregate ensures valid state transitions and maintains invariants.
    It follows an immutable design pattern where state changes return new instances.
    
    Domain events are collected in _domain_events and should be retrieved and 
    published by the application layer after each domain operation.
    """
    
    id: JobId
    tenant_id: TenantId
    status: JobStatus
    created_at: datetime
    _domain_events: List[DomainEvent] = field(default_factory=list, init=False, compare=False)
    
    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        if not self.created_at.tzinfo:
            raise DomainError("created_at must be timezone-aware")
    
    @classmethod
    def create(cls, tenant_id: TenantId, correlation_id: str = None) -> "Job":
        """
        Factory method to create a new Job.
        
        Args:
            tenant_id: Tenant identifier
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            New Job instance in SUBMITTED status with domain events
        """
        start_time = time.time()
        job = cls(
            id=JobId(uuid4()),
            tenant_id=tenant_id,
            status=JobStatus.SUBMITTED,
            created_at=datetime.now(timezone.utc)
        )
        
        creation_duration_ms = (time.time() - start_time) * 1000
        
        # Emit job created event
        job._add_domain_event(
            JobCreatedEvent.create(
                job_id=str(job.id.value),
                tenant_id=job.tenant_id.value,
                status=job.status.value,
                creation_duration_ms=creation_duration_ms,
                correlation_id=correlation_id
            )
        )
        
        # Emit audit event for job submission
        job._add_domain_event(
            JobAuditEvent.create(
                job_id=str(job.id.value),
                tenant_id=job.tenant_id.value,
                event_type="JOB_SUBMITTED",
                status=job.status.value,
                correlation_id=correlation_id,
                actor_id=None
            )
        )
        
        return job
    
    def start(self, correlation_id: str = None) -> "Job":
        """
        Transition job to RUNNING state.
        
        Valid transitions:
        - SUBMITTED -> RUNNING
        - RETRYING -> RUNNING
        
        Args:
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            New Job instance in RUNNING status with domain events
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        start_time = time.time()
        target_status = JobStatus.RUNNING
        
        # Emit transition attempted event
        attempt_event = JobStateTransitionAttemptedEvent.create(
            job_id=str(self.id.value),
            tenant_id=self.tenant_id.value,
            from_status=self.status.value,
            to_status=target_status.value,
            correlation_id=correlation_id
        )
        
        if self.status not in [JobStatus.SUBMITTED, JobStatus.RETRYING]:
            # Emit transition failed event
            failed_event = JobStateTransitionFailedEvent.create(
                job_id=str(self.id.value),
                tenant_id=self.tenant_id.value,
                from_status=self.status.value,
                attempted_status=target_status.value,
                reason="Invalid state transition",
                correlation_id=correlation_id
            )
            
            # Create new job with events (for event collection even on failure)
            failed_job = replace(self)
            object.__setattr__(failed_job, '_domain_events', [])
            failed_job._add_domain_event(attempt_event)
            failed_job._add_domain_event(failed_event)
            
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=target_status.value
            )
        
        new_job = replace(self, status=target_status)
        object.__setattr__(new_job, '_domain_events', [])
        transition_duration_ms = (time.time() - start_time) * 1000
        
        # Add events to new job
        new_job._add_domain_event(attempt_event)
        
        # Emit successful transition event
        new_job._add_domain_event(
            JobStateTransitionSucceededEvent.create(
                job_id=str(new_job.id.value),
                tenant_id=new_job.tenant_id.value,
                from_status=self.status.value,
                to_status=new_job.status.value,
                transition_duration_ms=transition_duration_ms,
                correlation_id=correlation_id
            )
        )
        
        # Emit audit event
        new_job._add_domain_event(
            JobAuditEvent.create(
                job_id=str(new_job.id.value),
                tenant_id=new_job.tenant_id.value,
                event_type="JOB_STARTED",
                status=new_job.status.value,
                correlation_id=correlation_id,
                actor_id=None,
                from_status=self.status.value
            )
        )
        
        return new_job
    
    def complete(self, correlation_id: str = None) -> "Job":
        """
        Mark job as successfully completed.
        
        Valid transitions:
        - RUNNING -> COMPLETED
        
        Args:
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            New Job instance in COMPLETED status with domain events
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        start_time = time.time()
        target_status = JobStatus.COMPLETED
        
        # Emit transition attempted event
        attempt_event = JobStateTransitionAttemptedEvent.create(
            job_id=str(self.id.value),
            tenant_id=self.tenant_id.value,
            from_status=self.status.value,
            to_status=target_status.value,
            correlation_id=correlation_id
        )
        
        if self.status != JobStatus.RUNNING:
            # Emit transition failed event
            failed_event = JobStateTransitionFailedEvent.create(
                job_id=str(self.id.value),
                tenant_id=self.tenant_id.value,
                from_status=self.status.value,
                attempted_status=target_status.value,
                reason="Invalid state transition",
                correlation_id=correlation_id
            )
            
            # Create new job with events (for event collection even on failure)
            failed_job = replace(self)
            object.__setattr__(failed_job, '_domain_events', [])
            failed_job._add_domain_event(attempt_event)
            failed_job._add_domain_event(failed_event)
            
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=target_status.value
            )
        
        new_job = replace(self, status=target_status)
        object.__setattr__(new_job, '_domain_events', [])
        transition_duration_ms = (time.time() - start_time) * 1000
        
        # Calculate total job duration from creation to completion
        total_job_duration_ms = (datetime.now(timezone.utc).timestamp() - self.created_at.timestamp()) * 1000
        
        # Add events to new job
        new_job._add_domain_event(attempt_event)
        
        # Emit successful transition event
        new_job._add_domain_event(
            JobStateTransitionSucceededEvent.create(
                job_id=str(new_job.id.value),
                tenant_id=new_job.tenant_id.value,
                from_status=self.status.value,
                to_status=new_job.status.value,
                transition_duration_ms=transition_duration_ms,
                correlation_id=correlation_id,
                total_job_duration_ms=total_job_duration_ms
            )
        )
        
        # Emit audit event
        new_job._add_domain_event(
            JobAuditEvent.create(
                job_id=str(new_job.id.value),
                tenant_id=new_job.tenant_id.value,
                event_type="JOB_COMPLETED",
                status=new_job.status.value,
                correlation_id=correlation_id,
                actor_id=None,
                from_status=self.status.value
            )
        )
        
        return new_job
    
    def fail(self, error_message: str = None, correlation_id: str = None) -> "Job":
        """
        Mark job as failed.
        
        Valid transitions:
        - RUNNING -> FAILED
        
        Args:
            error_message: Optional error message for logging
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            New Job instance in FAILED status with domain events
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        start_time = time.time()
        target_status = JobStatus.FAILED
        
        # Emit transition attempted event
        attempt_event = JobStateTransitionAttemptedEvent.create(
            job_id=str(self.id.value),
            tenant_id=self.tenant_id.value,
            from_status=self.status.value,
            to_status=target_status.value,
            correlation_id=correlation_id
        )
        
        if self.status != JobStatus.RUNNING:
            # Emit transition failed event
            failed_event = JobStateTransitionFailedEvent.create(
                job_id=str(self.id.value),
                tenant_id=self.tenant_id.value,
                from_status=self.status.value,
                attempted_status=target_status.value,
                reason="Invalid state transition",
                correlation_id=correlation_id
            )
            
            # Create new job with events (for event collection even on failure)
            failed_job = replace(self)
            object.__setattr__(failed_job, '_domain_events', [])
            failed_job._add_domain_event(attempt_event)
            failed_job._add_domain_event(failed_event)
            
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=target_status.value
            )
        
        new_job = replace(self, status=target_status)
        object.__setattr__(new_job, '_domain_events', [])
        transition_duration_ms = (time.time() - start_time) * 1000
        
        # Add events to new job
        new_job._add_domain_event(attempt_event)
        
        # Emit successful transition event (with error message)
        new_job._add_domain_event(
            JobStateTransitionSucceededEvent.create(
                job_id=str(new_job.id.value),
                tenant_id=new_job.tenant_id.value,
                from_status=self.status.value,
                to_status=new_job.status.value,
                transition_duration_ms=transition_duration_ms,
                correlation_id=correlation_id,
                error_message=error_message
            )
        )
        
        # Emit audit event
        new_job._add_domain_event(
            JobAuditEvent.create(
                job_id=str(new_job.id.value),
                tenant_id=new_job.tenant_id.value,
                event_type="JOB_FAILED",
                status=new_job.status.value,
                correlation_id=correlation_id,
                actor_id=None,
                from_status=self.status.value
            )
        )
        
        return new_job
    
    def retry(self, retry_attempt: int = 1, correlation_id: str = None) -> "Job":
        """
        Mark job for retry after failure.
        
        Valid transitions:
        - FAILED -> RETRYING
        
        Args:
            retry_attempt: Current retry attempt number
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            New Job instance in RETRYING status with domain events
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        start_time = time.time()
        target_status = JobStatus.RETRYING
        
        # Emit transition attempted event
        attempt_event = JobStateTransitionAttemptedEvent.create(
            job_id=str(self.id.value),
            tenant_id=self.tenant_id.value,
            from_status=self.status.value,
            to_status=target_status.value,
            correlation_id=correlation_id
        )
        
        if self.status != JobStatus.FAILED:
            # Emit transition failed event
            failed_event = JobStateTransitionFailedEvent.create(
                job_id=str(self.id.value),
                tenant_id=self.tenant_id.value,
                from_status=self.status.value,
                attempted_status=target_status.value,
                reason="Invalid state transition",
                correlation_id=correlation_id
            )
            
            # Create new job with events (for event collection even on failure)
            failed_job = replace(self)
            object.__setattr__(failed_job, '_domain_events', [])
            failed_job._add_domain_event(attempt_event)
            failed_job._add_domain_event(failed_event)
            
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=target_status.value
            )
        
        new_job = replace(self, status=target_status)
        object.__setattr__(new_job, '_domain_events', [])
        transition_duration_ms = (time.time() - start_time) * 1000
        
        # Add events to new job
        new_job._add_domain_event(attempt_event)
        
        # Emit successful transition event (with retry attempt)
        new_job._add_domain_event(
            JobStateTransitionSucceededEvent.create(
                job_id=str(new_job.id.value),
                tenant_id=new_job.tenant_id.value,
                from_status=self.status.value,
                to_status=new_job.status.value,
                transition_duration_ms=transition_duration_ms,
                correlation_id=correlation_id,
                retry_attempt=retry_attempt
            )
        )
        
        # Emit audit event
        new_job._add_domain_event(
            JobAuditEvent.create(
                job_id=str(new_job.id.value),
                tenant_id=new_job.tenant_id.value,
                event_type="JOB_RETRIED",
                status=new_job.status.value,
                correlation_id=correlation_id,
                actor_id=None,
                from_status=self.status.value
            )
        )
        
        return new_job
    
    def is_terminal(self) -> bool:
        """
        Check if job is in a terminal state.
        
        Returns:
            True if job is in COMPLETED or FAILED state
        """
        return self.status in [JobStatus.COMPLETED, JobStatus.FAILED]
    
    def can_retry(self) -> bool:
        """
        Check if job can be retried.
        
        Returns:
            True if job is in FAILED state
        """
        return self.status == JobStatus.FAILED
    
    def get_domain_events(self) -> List[DomainEvent]:
        """
        Get all domain events emitted by this aggregate.
        
        Returns:
            List of domain events
        """
        return list(self._domain_events)
    
    def clear_domain_events(self) -> "Job":
        """
        Clear all domain events from this aggregate.
        
        Returns:
            New Job instance with cleared events
        """
        # Create a new job instance and manually set the empty events list
        new_job = replace(self)
        object.__setattr__(new_job, '_domain_events', [])
        return new_job
    
    def _add_domain_event(self, event: DomainEvent) -> None:
        """
        Add a domain event to this aggregate.
        
        Note: This modifies the internal list even though the dataclass is frozen.
        This is acceptable for internal event collection.
        
        Args:
            event: Domain event to add
        """
        self._domain_events.append(event)
    
    def __str__(self) -> str:
        """String representation."""
        return f"Job(id={self.id}, tenant_id={self.tenant_id}, status={self.status.value})"
