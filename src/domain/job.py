"""Job aggregate for ValidaHub domain.

This module implements the core Job aggregate following DDD principles.
The Job is the main aggregate root that manages CSV processing workflows.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from domain.errors import DomainError, InvalidStateTransitionError
from domain.value_objects import JobId, TenantId
from shared.logging.security import AuditLogger, AuditEventType

# Module-level audit logger for job lifecycle events
_AUDIT = AuditLogger("domain.job")


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
    """
    
    id: JobId
    tenant_id: TenantId
    status: JobStatus
    created_at: datetime
    
    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        if not self.created_at.tzinfo:
            raise DomainError("created_at must be timezone-aware")
    
    @classmethod
    def create(cls, tenant_id: TenantId) -> "Job":
        """
        Factory method to create a new Job.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            New Job instance in SUBMITTED status
        """
        job = cls(
            id=JobId(uuid4()),
            tenant_id=tenant_id,
            status=JobStatus.SUBMITTED,
            created_at=datetime.now(timezone.utc)
        )
        # Audit: job submitted
        _AUDIT.job_lifecycle(
            event_type=AuditEventType.JOB_SUBMITTED,
            job_id=str(job.id.value),
            status=job.status.value,
            actor_id=None,
            tenant_id=job.tenant_id.value,
        )
        return job
    
    def start(self) -> "Job":
        """
        Transition job to RUNNING state.
        
        Valid transitions:
        - SUBMITTED -> RUNNING
        - RETRYING -> RUNNING
        
        Returns:
            New Job instance in RUNNING status
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        if self.status not in [JobStatus.SUBMITTED, JobStatus.RETRYING]:
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=JobStatus.RUNNING.value
            )
        new_job = replace(self, status=JobStatus.RUNNING)
        # Audit: job started
        _AUDIT.job_lifecycle(
            event_type=AuditEventType.JOB_STARTED,
            job_id=str(new_job.id.value),
            status=new_job.status.value,
            actor_id=None,
            tenant_id=new_job.tenant_id.value,
            from_status=self.status.value,
        )
        return new_job
    
    def complete(self) -> "Job":
        """
        Mark job as successfully completed.
        
        Valid transitions:
        - RUNNING -> COMPLETED
        
        Returns:
            New Job instance in COMPLETED status
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        if self.status != JobStatus.RUNNING:
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=JobStatus.COMPLETED.value
            )
        
        new_job = replace(self, status=JobStatus.COMPLETED)
        # Audit: job completed
        _AUDIT.job_lifecycle(
            event_type=AuditEventType.JOB_COMPLETED,
            job_id=str(new_job.id.value),
            status=new_job.status.value,
            actor_id=None,
            tenant_id=new_job.tenant_id.value,
            from_status=self.status.value,
        )
        return new_job
    
    def fail(self) -> "Job":
        """
        Mark job as failed.
        
        Valid transitions:
        - RUNNING -> FAILED
        
        Returns:
            New Job instance in FAILED status
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        if self.status != JobStatus.RUNNING:
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=JobStatus.FAILED.value
            )
        
        new_job = replace(self, status=JobStatus.FAILED)
        # Audit: job failed
        _AUDIT.job_lifecycle(
            event_type=AuditEventType.JOB_FAILED,
            job_id=str(new_job.id.value),
            status=new_job.status.value,
            actor_id=None,
            tenant_id=new_job.tenant_id.value,
            from_status=self.status.value,
        )
        return new_job
    
    def retry(self) -> "Job":
        """
        Mark job for retry after failure.
        
        Valid transitions:
        - FAILED -> RETRYING
        
        Returns:
            New Job instance in RETRYING status
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        if self.status != JobStatus.FAILED:
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=JobStatus.RETRYING.value
            )
        
        new_job = replace(self, status=JobStatus.RETRYING)
        # Audit: job retried
        _AUDIT.job_lifecycle(
            event_type=AuditEventType.JOB_RETRIED,
            job_id=str(new_job.id.value),
            status=new_job.status.value,
            actor_id=None,
            tenant_id=new_job.tenant_id.value,
            from_status=self.status.value,
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
    
    def __str__(self) -> str:
        """String representation."""
        return f"Job(id={self.id}, tenant_id={self.tenant_id}, status={self.status.value})"
