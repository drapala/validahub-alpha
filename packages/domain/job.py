"""Job aggregate for ValidaHub domain.

This module implements the core Job aggregate following DDD principles.
The Job is the main aggregate root that manages CSV processing workflows.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from .enums import JobStatus, JobType
from .events import DomainEvent, JobSubmitted, JobStarted, JobSucceeded, JobFailed, JobCancelled, JobRetried, JobExpired
from .value_objects import JobId, TenantId, Channel, FileReference, RulesProfileId, ProcessingCounters, IdempotencyKey
from .errors import DomainError, InvalidStateTransitionError

try:
    from packages.shared.logging import get_logger
    from packages.shared.logging.security import AuditLogger, AuditEventType
except ImportError:
    # Fallback logging for testing without full dependencies
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)
    
    class AuditEventType:
        JOB_SUBMITTED = "job_submitted"
        JOB_STARTED = "job_started"
        JOB_COMPLETED = "job_completed"
        JOB_FAILED = "job_failed"
        JOB_RETRIED = "job_retried"
        JOB_CANCELLED = "job_cancelled"
        JOB_EXPIRED = "job_expired"

    class AuditLogger:
        def __init__(self, name: str):
            self.logger = logging.getLogger(name)
        
        def job_lifecycle(self, **kwargs):
            self.logger.info("Job lifecycle event", extra=kwargs)


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
    output_ref: Optional[str] = None
    idempotency_key: Optional[IdempotencyKey] = None
    callback_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    
    # Event collection for publishing
    _events: List[DomainEvent] = field(default_factory=list, init=False)
    
    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        logger = get_logger("domain.job")
        
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
        
        logger.debug(
            "job_aggregate_initialized",
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            status=self.status.value,
            type=self.type.value,
            channel=str(self.channel),
        )
    
    @classmethod
    def create(
        cls,
        tenant_id: TenantId,
        seller_id: str,
        channel: Channel,
        job_type: JobType,
        file_ref: FileReference,
        rules_profile_id: RulesProfileId,
        idempotency_key: Optional[IdempotencyKey] = None,
        callback_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        actor_id: Optional[str] = None,
        trace_id: Optional[str] = None,
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
        logger = get_logger("domain.job")
        audit_logger = AuditLogger("domain.job")
        
        job_id = JobId(uuid4())
        now = datetime.now(timezone.utc)
        
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
        
        # Audit logging
        audit_logger.job_lifecycle(
            event_type=AuditEventType.JOB_SUBMITTED,
            job_id=str(job_id),
            tenant_id=str(tenant_id),
            seller_id=seller_id,
            status=JobStatus.QUEUED.value,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        
        logger.info(
            "job_created",
            job_id=str(job_id),
            tenant_id=str(tenant_id),
            seller_id=seller_id,
            channel=str(channel),
            type=job_type.value,
            rules_profile_id=str(rules_profile_id),
        )
        
        return job
    
    def start(self, actor_id: Optional[str] = None, trace_id: Optional[str] = None) -> "Job":
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
        
        logger = get_logger("domain.job")
        audit_logger = AuditLogger("domain.job")
        now = datetime.now(timezone.utc)
        
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
        
        # Audit logging
        audit_logger.job_lifecycle(
            event_type=AuditEventType.JOB_STARTED,
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            status=JobStatus.RUNNING.value,
            from_status=self.status.value,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        
        logger.info(
            "job_started",
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            from_status=self.status.value,
            to_status=JobStatus.RUNNING.value,
        )
        
        return new_job
    
    def succeed(
        self,
        counters: ProcessingCounters,
        output_ref: Optional[str] = None,
        duration_ms: Optional[int] = None,
        actor_id: Optional[str] = None,
        trace_id: Optional[str] = None,
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
        
        logger = get_logger("domain.job")
        audit_logger = AuditLogger("domain.job")
        now = datetime.now(timezone.utc)
        
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
        
        # Audit logging
        audit_logger.job_lifecycle(
            event_type=AuditEventType.JOB_COMPLETED,
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            status=JobStatus.SUCCEEDED.value,
            from_status=self.status.value,
            duration_ms=duration_ms,
            counters=counters.__dict__,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        
        logger.info(
            "job_succeeded",
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            duration_ms=duration_ms,
            counters=counters.__dict__,
        )
        
        return new_job
    
    def fail(
        self,
        error_code: str,
        error_message: str,
        counters: Optional[ProcessingCounters] = None,
        duration_ms: Optional[int] = None,
        retry_count: int = 0,
        actor_id: Optional[str] = None,
        trace_id: Optional[str] = None,
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
        
        logger = get_logger("domain.job")
        audit_logger = AuditLogger("domain.job")
        now = datetime.now(timezone.utc)
        
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
        
        # Audit logging
        audit_logger.job_lifecycle(
            event_type=AuditEventType.JOB_FAILED,
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            status=JobStatus.FAILED.value,
            from_status=self.status.value,
            error_code=error_code,
            retry_count=retry_count,
            duration_ms=duration_ms,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        
        logger.error(
            "job_failed",
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            error_code=error_code,
            error_message=error_message,
            duration_ms=duration_ms,
        )
        
        return new_job
    
    def cancel(
        self,
        reason: str,
        actor_id: Optional[str] = None,
        trace_id: Optional[str] = None,
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
        
        logger = get_logger("domain.job")
        audit_logger = AuditLogger("domain.job")
        now = datetime.now(timezone.utc)
        
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
        
        # Audit logging
        audit_logger.job_lifecycle(
            event_type=AuditEventType.JOB_CANCELLED,
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            status=JobStatus.CANCELLED.value,
            from_status=self.status.value,
            reason=reason,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        
        logger.info(
            "job_cancelled",
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            reason=reason,
        )
        
        return new_job
    
    def retry(
        self,
        actor_id: Optional[str] = None,
        trace_id: Optional[str] = None,
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
        
        logger = get_logger("domain.job")
        audit_logger = AuditLogger("domain.job")
        
        # Create new job with same configuration but new ID
        new_job_id = JobId(uuid4())
        now = datetime.now(timezone.utc)
        
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
        
        # Audit logging
        audit_logger.job_lifecycle(
            event_type=AuditEventType.JOB_RETRIED,
            job_id=str(new_job_id),
            tenant_id=str(self.tenant_id),
            original_job_id=str(self.id),
            actor_id=actor_id,
            trace_id=trace_id,
        )
        
        logger.info(
            "job_retried",
            job_id=str(new_job_id),
            original_job_id=str(self.id),
            tenant_id=str(self.tenant_id),
        )
        
        return retry_job
    
    def expire(
        self,
        ttl_seconds: int,
        actor_id: Optional[str] = None,
        trace_id: Optional[str] = None,
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
        
        logger = get_logger("domain.job")
        audit_logger = AuditLogger("domain.job")
        now = datetime.now(timezone.utc)
        
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
        
        # Audit logging
        audit_logger.job_lifecycle(
            event_type=AuditEventType.JOB_EXPIRED,
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            status=JobStatus.EXPIRED.value,
            from_status=self.status.value,
            ttl_seconds=ttl_seconds,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        
        logger.warning(
            "job_expired",
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            ttl_seconds=ttl_seconds,
        )
        
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
    
    def get_events(self) -> List[DomainEvent]:
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