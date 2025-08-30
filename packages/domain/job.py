"""Job aggregate for ValidaHub domain.

This module implements the core Job aggregate following DDD principles.
The Job is the main aggregate root that manages CSV processing workflows.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .enums import JobStatus, JobType
from .errors import DomainError, InvalidStateTransitionError
from .events import (
    DomainEvent,
    JobCancelled,
    JobExpired,
    JobFailed,
    JobRetried,
    JobStarted,
    JobSubmitted,
    JobSucceeded,
)
from .value_objects import (
    Channel,
    FileReference,
    IdempotencyKey,
    JobId,
    ProcessingCounters,
    RulesProfileId,
    TenantId,
)


@dataclass
class Job:
    """
    Job aggregate representing a CSV processing job.
    
    This aggregate ensures valid state transitions, maintains invariants,
    and collects domain events for publishing. It represents the complete
    lifecycle of a job from submission to completion or failure.
    
    Multi-tenant by design: All operations include tenant_id for isolation.
    """
    
    # Core identifiers
    id: JobId
    tenant_id: TenantId
    seller_id: str
    
    # Job configuration
    channel: Channel
    type: JobType
    file_ref: FileReference
    rules_profile_id: RulesProfileId
    
    # State management
    status: JobStatus
    counters: ProcessingCounters = field(default_factory=lambda: ProcessingCounters(0, 0, 0, 0))
    
    # Optional attributes
    output_ref: str | None = None
    idempotency_key: IdempotencyKey | None = None
    callback_url: str | None = None
    metadata: dict[str, Any] | None = None
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    
    # Event collection for publishing
    _events: list[DomainEvent] = field(default_factory=list, init=False)
    
    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        
        # Timezone validation
        if not self.created_at.tzinfo:
            raise DomainError("created_at must be timezone-aware")
        if not self.updated_at.tzinfo:
            raise DomainError("updated_at must be timezone-aware")
        if self.completed_at and not self.completed_at.tzinfo:
            raise DomainError("completed_at must be timezone-aware")
        
        # Timestamp consistency
        if self.updated_at < self.created_at:
            raise DomainError("updated_at cannot be before created_at")
        if self.completed_at and self.completed_at < self.created_at:
            raise DomainError("completed_at cannot be before created_at")
        
        # Status consistency
        if self.status.is_completed() and not self.completed_at:
            # Set completed_at if status is terminal but timestamp is missing
            object.__setattr__(self, 'completed_at', self.updated_at)
        
        # Seller ID validation
        if not self.seller_id or not isinstance(self.seller_id, str):
            raise DomainError("seller_id must be a non-empty string")
    
    @classmethod
    def create(
        cls,
        tenant_id: TenantId,
        seller_id: str,
        channel: Channel,
        job_type: JobType,
        file_ref: FileReference,
        rules_profile_id: RulesProfileId,
        idempotency_key: IdempotencyKey | None = None,
        callback_url: str | None = None,
        metadata: dict[str, Any] | None = None,
        actor_id: str | None = None,
        trace_id: str | None = None,
    ) -> "Job":
        """
        Factory method to create a new Job.
        
        Args:
            tenant_id: Tenant identifier for multi-tenancy
            seller_id: Seller identifier within tenant
            channel: Marketplace/channel for processing rules
            job_type: Type of processing (validation, correction, enrichment)
            file_ref: Reference to input file
            rules_profile_id: Rule pack version to use
            idempotency_key: Optional idempotency key for safe retries
            callback_url: Optional webhook URL for notifications
            metadata: Optional additional metadata
            actor_id: Optional actor who triggered the creation
            trace_id: Optional trace ID for distributed tracing
            
        Returns:
            New Job instance in QUEUED status
        """
        
        job_id = JobId(uuid4())
        now = datetime.now(UTC)
        
        job = cls(
            id=job_id,
            tenant_id=tenant_id,
            seller_id=seller_id,
            channel=channel,
            type=job_type,
            file_ref=file_ref,
            rules_profile_id=rules_profile_id,
            status=JobStatus.QUEUED,
            idempotency_key=idempotency_key,
            callback_url=callback_url,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        
        # Collect domain event
        event = JobSubmitted.create(
            job_id=job_id,
            tenant_id=tenant_id,
            seller_id=seller_id,
            channel=str(channel),
            job_type=job_type,
            file_ref=str(file_ref),
            rules_profile_id=str(rules_profile_id),
            idempotency_key=str(idempotency_key) if idempotency_key else None,
            callback_url=callback_url,
            metadata=metadata,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        job._events.append(event)
        
        
        return job
    
    def start(self, actor_id: str | None = None, trace_id: str | None = None) -> "Job":
        """
        Transition job to RUNNING state.
        
        Valid transitions:
        - QUEUED -> RUNNING
        - RETRYING -> RUNNING
        
        Args:
            actor_id: Optional actor who triggered the start
            trace_id: Optional trace ID for distributed tracing
        
        Returns:
            New Job instance in RUNNING status
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        if not self.status.can_transition_to(JobStatus.RUNNING):
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=JobStatus.RUNNING.value
            )
        
        now = datetime.now(UTC)
        
        # Create new job instance with updated state
        new_job = Job(
            id=self.id,
            tenant_id=self.tenant_id,
            seller_id=self.seller_id,
            channel=self.channel,
            type=self.type,
            file_ref=self.file_ref,
            rules_profile_id=self.rules_profile_id,
            status=JobStatus.RUNNING,
            counters=self.counters,
            output_ref=self.output_ref,
            idempotency_key=self.idempotency_key,
            callback_url=self.callback_url,
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=now,
            completed_at=self.completed_at,
        )
        
        # Collect domain event
        event = JobStarted.create(
            job_id=self.id,
            tenant_id=self.tenant_id,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        new_job._events.append(event)
        
        
        return new_job
    
    def succeed(
        self,
        counters: ProcessingCounters,
        output_ref: str | None = None,
        duration_ms: int | None = None,
        actor_id: str | None = None,
        trace_id: str | None = None,
    ) -> "Job":
        """
        Mark job as successfully completed.
        
        Valid transitions:
        - RUNNING -> SUCCEEDED
        
        Args:
            counters: Final processing counters
            output_ref: Optional reference to output file
            duration_ms: Optional processing duration in milliseconds
            actor_id: Optional actor who triggered completion
            trace_id: Optional trace ID for distributed tracing
        
        Returns:
            New Job instance in SUCCEEDED status
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        if not self.status.can_transition_to(JobStatus.SUCCEEDED):
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=JobStatus.SUCCEEDED.value
            )
        
        now = datetime.now(UTC)
        
        # Create new job instance with updated state
        new_job = Job(
            id=self.id,
            tenant_id=self.tenant_id,
            seller_id=self.seller_id,
            channel=self.channel,
            type=self.type,
            file_ref=self.file_ref,
            rules_profile_id=self.rules_profile_id,
            status=JobStatus.SUCCEEDED,
            counters=counters,
            output_ref=output_ref,
            idempotency_key=self.idempotency_key,
            callback_url=self.callback_url,
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=now,
            completed_at=now,
        )
        
        # Calculate duration if not provided
        if duration_ms is None:
            duration_ms = int((now - self.created_at).total_seconds() * 1000)
        
        # Collect domain event
        event = JobSucceeded.create(
            job_id=self.id,
            tenant_id=self.tenant_id,
            counters=counters,
            duration_ms=duration_ms,
            output_ref=output_ref,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        new_job._events.append(event)
        
        
        return new_job
    
    def fail(
        self,
        error_code: str,
        error_message: str,
        counters: ProcessingCounters | None = None,
        duration_ms: int | None = None,
        retry_count: int = 0,
        actor_id: str | None = None,
        trace_id: str | None = None,
    ) -> "Job":
        """
        Mark job as failed.
        
        Valid transitions:
        - RUNNING -> FAILED
        
        Args:
            error_code: Error classification code
            error_message: Human-readable error message
            counters: Optional processing counters at time of failure
            duration_ms: Optional processing duration in milliseconds
            retry_count: Number of retries attempted
            actor_id: Optional actor who triggered failure
            trace_id: Optional trace ID for distributed tracing
        
        Returns:
            New Job instance in FAILED status
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        if not self.status.can_transition_to(JobStatus.FAILED):
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=JobStatus.FAILED.value
            )
        
        now = datetime.now(UTC)
        
        # Create new job instance with updated state
        new_job = Job(
            id=self.id,
            tenant_id=self.tenant_id,
            seller_id=self.seller_id,
            channel=self.channel,
            type=self.type,
            file_ref=self.file_ref,
            rules_profile_id=self.rules_profile_id,
            status=JobStatus.FAILED,
            counters=counters or self.counters,
            output_ref=self.output_ref,
            idempotency_key=self.idempotency_key,
            callback_url=self.callback_url,
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=now,
            completed_at=now,
        )
        
        # Calculate duration if not provided
        if duration_ms is None:
            duration_ms = int((now - self.created_at).total_seconds() * 1000)
        
        # Collect domain event
        event = JobFailed.create(
            job_id=self.id,
            tenant_id=self.tenant_id,
            error_code=error_code,
            error_message=error_message,
            counters=counters,
            duration_ms=duration_ms,
            retry_count=retry_count,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        new_job._events.append(event)
        
        
        return new_job
    
    def cancel(
        self,
        reason: str,
        actor_id: str | None = None,
        trace_id: str | None = None,
    ) -> "Job":
        """
        Cancel the job.
        
        Valid transitions:
        - QUEUED -> CANCELLED
        - RUNNING -> CANCELLED
        
        Args:
            reason: Reason for cancellation
            actor_id: Optional actor who triggered cancellation
            trace_id: Optional trace ID for distributed tracing
        
        Returns:
            New Job instance in CANCELLED status
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        if not self.status.can_transition_to(JobStatus.CANCELLED):
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=JobStatus.CANCELLED.value
            )
        
        now = datetime.now(UTC)
        
        # Create new job instance with updated state
        new_job = Job(
            id=self.id,
            tenant_id=self.tenant_id,
            seller_id=self.seller_id,
            channel=self.channel,
            type=self.type,
            file_ref=self.file_ref,
            rules_profile_id=self.rules_profile_id,
            status=JobStatus.CANCELLED,
            counters=self.counters,
            output_ref=self.output_ref,
            idempotency_key=self.idempotency_key,
            callback_url=self.callback_url,
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=now,
            completed_at=now,
        )
        
        # Collect domain event
        event = JobCancelled.create(
            job_id=self.id,
            tenant_id=self.tenant_id,
            reason=reason,
            counters=self.counters,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        new_job._events.append(event)
        
        
        return new_job
    
    def retry(
        self,
        actor_id: str | None = None,
        trace_id: str | None = None,
    ) -> "Job":
        """
        Create a new job for retry after failure.
        
        This creates a completely new job instance with a new ID,
        inheriting the configuration from the failed job.
        
        Args:
            actor_id: Optional actor who triggered retry
            trace_id: Optional trace ID for distributed tracing
        
        Returns:
            New Job instance for retry
            
        Raises:
            InvalidStateTransitionError: If current job cannot be retried
        """
        if not self.can_retry():
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state="retried"
            )
        
        
        # Create new job with same configuration but new ID
        new_job_id = JobId(uuid4())
        now = datetime.now(UTC)
        
        retry_job = Job(
            id=new_job_id,
            tenant_id=self.tenant_id,
            seller_id=self.seller_id,
            channel=self.channel,
            type=self.type,
            file_ref=self.file_ref,
            rules_profile_id=self.rules_profile_id,
            status=JobStatus.QUEUED,
            counters=ProcessingCounters(0, 0, 0, 0),  # Reset counters
            idempotency_key=None,  # Clear idempotency key for retry
            callback_url=self.callback_url,
            metadata=self.metadata,
            created_at=now,
            updated_at=now,
        )
        
        # Collect domain event
        event = JobRetried.create(
            job_id=new_job_id,
            tenant_id=self.tenant_id,
            original_job_id=self.id,
            retry_count=1,  # TODO: Track retry count in metadata
            actor_id=actor_id,
            trace_id=trace_id,
        )
        retry_job._events.append(event)
        
        
        return retry_job
    
    def expire(
        self,
        ttl_seconds: int,
        actor_id: str | None = None,
        trace_id: str | None = None,
    ) -> "Job":
        """
        Mark job as expired due to timeout.
        
        Valid transitions:
        - QUEUED -> EXPIRED
        
        Args:
            ttl_seconds: Time-to-live in seconds that was exceeded
            actor_id: Optional actor who triggered expiration
            trace_id: Optional trace ID for distributed tracing
        
        Returns:
            New Job instance in EXPIRED status
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        if not self.status.can_transition_to(JobStatus.EXPIRED):
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=JobStatus.EXPIRED.value
            )
        
        now = datetime.now(UTC)
        
        # Create new job instance with updated state
        new_job = Job(
            id=self.id,
            tenant_id=self.tenant_id,
            seller_id=self.seller_id,
            channel=self.channel,
            type=self.type,
            file_ref=self.file_ref,
            rules_profile_id=self.rules_profile_id,
            status=JobStatus.EXPIRED,
            counters=self.counters,
            output_ref=self.output_ref,
            idempotency_key=self.idempotency_key,
            callback_url=self.callback_url,
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=now,
            completed_at=now,
        )
        
        # Collect domain event
        event = JobExpired.create(
            job_id=self.id,
            tenant_id=self.tenant_id,
            ttl_seconds=ttl_seconds,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        new_job._events.append(event)
        
        
        return new_job
    
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.status == JobStatus.FAILED
    
    def is_terminal(self) -> bool:
        """Check if job is in a terminal state."""
        return self.status.is_terminal()
    
    def is_active(self) -> bool:
        """Check if job is actively being processed."""
        return self.status.is_active()
    
    def is_completed(self) -> bool:
        """Check if job has completed (successfully or with failure)."""
        return self.status.is_completed()
    
    def get_events(self) -> list[DomainEvent]:
        """Get collected domain events for publishing."""
        return self._events.copy()
    
    def clear_events(self) -> None:
        """Clear collected domain events after publishing."""
        self._events.clear()
    
    def __str__(self) -> str:
        """String representation."""
        return f"Job(id={self.id}, tenant_id={self.tenant_id}, status={self.status.value})"
    
    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"Job(id={self.id}, tenant_id={self.tenant_id}, seller_id='{self.seller_id}', "
            f"channel={self.channel}, type={self.type.value}, status={self.status.value})"
        )