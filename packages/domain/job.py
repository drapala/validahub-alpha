"""Job aggregate for ValidaHub domain."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from packages.shared.logging import get_logger
from packages.shared.logging.security import AuditLogger, AuditEventType

from .value_objects import (
    TenantId,
    IdempotencyKey,
    FileReference,
    RulesProfileId,
    ProcessingCounters,
)


class JobStatus(Enum):
    """Job processing status."""
    
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    RETRYING = "retrying"


class InvalidTransition(Exception):
    """Invalid job state transition."""
    pass


@dataclass
class Job:
    """
    Job aggregate representing a CSV processing job.
    
    Ensures multi-tenant isolation and state transitions.
    """
    
    id: UUID
    tenant_id: TenantId
    seller_id: str
    channel: str
    job_type: str
    file_ref: FileReference
    rules_profile_id: RulesProfileId
    idempotency_key: Optional[IdempotencyKey]
    created_at: datetime
    updated_at: datetime
    _status: JobStatus = field(default=JobStatus.QUEUED, repr=False)
    _counters: ProcessingCounters = field(
        default_factory=lambda: ProcessingCounters(0, 0, 0, 0),
        repr=False
    )
    _started_at: Optional[datetime] = field(default=None, repr=False)
    _completed_at: Optional[datetime] = field(default=None, repr=False)
    _error_message: Optional[str] = field(default=None, repr=False)
    
    @classmethod
    def create(
        cls,
        tenant_id: TenantId,
        seller_id: str,
        channel: str,
        job_type: str,
        file_ref: FileReference,
        rules_profile_id: RulesProfileId,
        idempotency_key: Optional[IdempotencyKey] = None,
    ) -> "Job":
        """
        Factory method to create a new Job.
        
        Args:
            tenant_id: Tenant identifier
            seller_id: Seller identifier
            channel: Marketplace channel
            job_type: Type of job (csv_validation, etc.)
            file_ref: Reference to input file
            rules_profile_id: Rules profile to apply
            idempotency_key: Optional idempotency key
            
        Returns:
            New Job instance
        """
        logger = get_logger("domain.job")
        audit = AuditLogger("domain.job")
        
        now = datetime.now(timezone.utc)
        job_id = uuid4()
        
        job = cls(
            id=job_id,
            tenant_id=tenant_id,
            seller_id=seller_id,
            channel=channel,
            job_type=job_type,
            file_ref=file_ref,
            rules_profile_id=rules_profile_id,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        
        logger.info(
            "job_created",
            job_id=str(job_id),
            tenant_id=str(tenant_id),
            seller_id=seller_id,
            channel=channel,
            job_type=job_type,
            file_ref=str(file_ref),
            rules_profile_id=str(rules_profile_id),
            has_idempotency_key=idempotency_key is not None,
        )
        
        audit.job_lifecycle(
            event_type=AuditEventType.JOB_SUBMITTED,
            job_id=str(job_id),
            status=JobStatus.QUEUED.value,
            actor_id=seller_id,
            channel=channel,
            job_type=job_type,
        )
        
        return job
    
    @property
    def status(self) -> JobStatus:
        """Get current job status."""
        return self._status
    
    @property
    def counters(self) -> ProcessingCounters:
        """Get processing counters."""
        return self._counters
    
    @property
    def started_at(self) -> Optional[datetime]:
        """Get job start time."""
        return self._started_at
    
    @property
    def completed_at(self) -> Optional[datetime]:
        """Get job completion time."""
        return self._completed_at
    
    @property
    def error_message(self) -> Optional[str]:
        """Get error message if job failed."""
        return self._error_message
    
    def start_processing(self) -> None:
        """
        Transition job to RUNNING state.
        
        Raises:
            InvalidTransition: If transition is not allowed
        """
        logger = get_logger("domain.job")
        audit = AuditLogger("domain.job")
        
        if self._status not in [JobStatus.QUEUED, JobStatus.RETRYING]:
            logger.warning(
                "job_invalid_transition",
                job_id=str(self.id),
                tenant_id=str(self.tenant_id),
                from_status=self._status.value,
                to_status="running",
                seller_id=self.seller_id,
            )
            raise InvalidTransition(f"Cannot transition from {self._status} to running")
        
        old_status = self._status
        self._status = JobStatus.RUNNING
        self._started_at = datetime.now(timezone.utc)
        self.updated_at = self._started_at
        
        logger.info(
            "job_processing_started",
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            seller_id=self.seller_id,
            channel=self.channel,
            from_status=old_status.value,
            processing_started_at=self._started_at.isoformat(),
        )
        
        audit.job_lifecycle(
            event_type=AuditEventType.JOB_STARTED,
            job_id=str(self.id),
            status=JobStatus.RUNNING.value,
            actor_id=self.seller_id,
            from_status=old_status.value,
        )
    
    def complete_successfully(self, counters: ProcessingCounters) -> None:
        """
        Mark job as successfully completed.
        
        Args:
            counters: Final processing counters
            
        Raises:
            InvalidTransition: If job is not running
        """
        logger = get_logger("domain.job")
        audit = AuditLogger("domain.job")
        
        if self._status != JobStatus.RUNNING:
            logger.warning(
                "job_invalid_transition",
                job_id=str(self.id),
                tenant_id=str(self.tenant_id),
                from_status=self._status.value,
                to_status="succeeded",
            )
            raise InvalidTransition(f"Cannot complete job from {self._status}")
        
        self._status = JobStatus.SUCCEEDED
        self._counters = counters
        self._completed_at = datetime.now(timezone.utc)
        self.updated_at = self._completed_at
        
        duration_ms = None
        if self._started_at:
            duration_ms = (self._completed_at - self._started_at).total_seconds() * 1000
        
        logger.info(
            "job_completed_successfully",
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            seller_id=self.seller_id,
            channel=self.channel,
            total_items=counters.total,
            processed_items=counters.processed,
            errors=counters.errors,
            warnings=counters.warnings,
            success_rate=counters.get_success_rate(),
            duration_ms=duration_ms,
        )
        
        audit.job_lifecycle(
            event_type=AuditEventType.JOB_COMPLETED,
            job_id=str(self.id),
            status=JobStatus.SUCCEEDED.value,
            actor_id=self.seller_id,
            total_items=counters.total,
            errors=counters.errors,
            warnings=counters.warnings,
            duration_ms=duration_ms,
        )
    
    def fail(self, error_message: str) -> None:
        """
        Mark job as failed.
        
        Args:
            error_message: Error description
            
        Raises:
            InvalidTransition: If job is not running
        """
        logger = get_logger("domain.job")
        audit = AuditLogger("domain.job")
        
        if self._status != JobStatus.RUNNING:
            logger.warning(
                "job_invalid_transition",
                job_id=str(self.id),
                tenant_id=str(self.tenant_id),
                from_status=self._status.value,
                to_status="failed",
            )
            raise InvalidTransition(f"Cannot fail job from {self._status}")
        
        self._status = JobStatus.FAILED
        self._error_message = error_message
        self._completed_at = datetime.now(timezone.utc)
        self.updated_at = self._completed_at
        
        duration_ms = None
        if self._started_at:
            duration_ms = (self._completed_at - self._started_at).total_seconds() * 1000
        
        logger.error(
            "job_failed",
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            seller_id=self.seller_id,
            channel=self.channel,
            error_message=error_message[:200],  # Truncate for safety
            duration_ms=duration_ms,
        )
        
        audit.job_lifecycle(
            event_type=AuditEventType.JOB_FAILED,
            job_id=str(self.id),
            status=JobStatus.FAILED.value,
            actor_id=self.seller_id,
            error_summary=error_message[:100],
            duration_ms=duration_ms,
        )
    
    def cancel(self, reason: str = "User requested") -> None:
        """
        Cancel the job.
        
        Args:
            reason: Cancellation reason
            
        Raises:
            InvalidTransition: If job cannot be cancelled
        """
        logger = get_logger("domain.job")
        audit = AuditLogger("domain.job")
        
        if self._status in [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.EXPIRED]:
            logger.warning(
                "job_invalid_transition",
                job_id=str(self.id),
                tenant_id=str(self.tenant_id),
                from_status=self._status.value,
                to_status="cancelled",
            )
            raise InvalidTransition(f"Cannot cancel job from {self._status}")
        
        old_status = self._status
        self._status = JobStatus.CANCELLED
        self._completed_at = datetime.now(timezone.utc)
        self.updated_at = self._completed_at
        
        logger.info(
            "job_cancelled",
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            seller_id=self.seller_id,
            from_status=old_status.value,
            reason=reason,
        )
        
        audit.job_lifecycle(
            event_type=AuditEventType.JOB_CANCELLED,
            job_id=str(self.id),
            status=JobStatus.CANCELLED.value,
            actor_id=self.seller_id,
            from_status=old_status.value,
            reason=reason,
        )
    
    def mark_for_retry(self) -> None:
        """
        Mark job for retry after failure.
        
        Raises:
            InvalidTransition: If job cannot be retried
        """
        logger = get_logger("domain.job")
        audit = AuditLogger("domain.job")
        
        if self._status not in [JobStatus.FAILED, JobStatus.EXPIRED]:
            logger.warning(
                "job_invalid_transition",
                job_id=str(self.id),
                tenant_id=str(self.tenant_id),
                from_status=self._status.value,
                to_status="retrying",
            )
            raise InvalidTransition(f"Cannot retry job from {self._status}")
        
        old_status = self._status
        self._status = JobStatus.RETRYING
        self.updated_at = datetime.now(timezone.utc)
        
        logger.info(
            "job_marked_for_retry",
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            seller_id=self.seller_id,
            from_status=old_status.value,
            previous_error=self._error_message[:100] if self._error_message else None,
        )
        
        audit.job_lifecycle(
            event_type=AuditEventType.JOB_RETRIED,
            job_id=str(self.id),
            status=JobStatus.RETRYING.value,
            actor_id=self.seller_id,
            from_status=old_status.value,
        )
    
    def expire(self) -> None:
        """
        Mark job as expired.
        
        Raises:
            InvalidTransition: If job cannot be expired
        """
        logger = get_logger("domain.job")
        
        if self._status in [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.EXPIRED]:
            logger.warning(
                "job_invalid_transition",
                job_id=str(self.id),
                tenant_id=str(self.tenant_id),
                from_status=self._status.value,
                to_status="expired",
            )
            raise InvalidTransition(f"Cannot expire job from {self._status}")
        
        old_status = self._status
        self._status = JobStatus.EXPIRED
        self._completed_at = datetime.now(timezone.utc)
        self.updated_at = self._completed_at
        
        logger.warning(
            "job_expired",
            job_id=str(self.id),
            tenant_id=str(self.tenant_id),
            seller_id=self.seller_id,
            from_status=old_status.value,
            age_minutes=(self.updated_at - self.created_at).total_seconds() / 60,
        )
    
    def is_terminal(self) -> bool:
        """Check if job is in a terminal state."""
        return self._status in [
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.EXPIRED,
        ]
    
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self._status in [JobStatus.FAILED, JobStatus.EXPIRED]
    
    def get_duration_seconds(self) -> Optional[float]:
        """Get job duration in seconds if completed."""
        if self._started_at and self._completed_at:
            return (self._completed_at - self._started_at).total_seconds()
        return None
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Job(id={self.id}, tenant_id={self.tenant_id}, "
            f"status={self._status.value}, seller_id={self.seller_id})"
        )