"""Job aggregate for ValidaHub domain.

This module implements the core Job aggregate following DDD principles.
The Job is the main aggregate root that manages CSV processing workflows.
"""

import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from src.domain.errors import DomainError, InvalidStateTransitionError
from src.domain.value_objects import JobId, TenantId
from shared.logging.security import AuditLogger, AuditEventType
from shared.logging import get_logger
from shared.logging.context import get_correlation_id

# Module-level audit logger for job lifecycle events
_AUDIT = AuditLogger("domain.job")

# Structured logger for domain events and state transitions
logger = get_logger("domain.job")


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
        start_time = time.time()
        job = cls(
            id=JobId(uuid4()),
            tenant_id=tenant_id,
            status=JobStatus.SUBMITTED,
            created_at=datetime.now(timezone.utc)
        )
        
        # Structured logging for job creation
        logger.info(
            "job_created",
            job_id=str(job.id.value),
            tenant_id=job.tenant_id.value,
            status=job.status.value,
            correlation_id=get_correlation_id(),
            creation_duration_ms=(time.time() - start_time) * 1000
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
        start_time = time.time()
        
        if self.status not in [JobStatus.SUBMITTED, JobStatus.RETRYING]:
            # Log invalid transition attempt
            logger.warning(
                "invalid_state_transition_attempted",
                job_id=str(self.id.value),
                tenant_id=self.tenant_id.value,
                current_status=self.status.value,
                attempted_status=JobStatus.RUNNING.value,
                correlation_id=get_correlation_id()
            )
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=JobStatus.RUNNING.value
            )
        
        new_job = replace(self, status=JobStatus.RUNNING)
        
        # Structured logging for successful transition
        logger.info(
            "job_state_transition_successful",
            job_id=str(new_job.id.value),
            tenant_id=new_job.tenant_id.value,
            from_status=self.status.value,
            to_status=new_job.status.value,
            transition_duration_ms=(time.time() - start_time) * 1000,
            correlation_id=get_correlation_id()
        )
        
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
        start_time = time.time()
        
        if self.status != JobStatus.RUNNING:
            # Log invalid transition attempt
            logger.warning(
                "invalid_state_transition_attempted",
                job_id=str(self.id.value),
                tenant_id=self.tenant_id.value,
                current_status=self.status.value,
                attempted_status=JobStatus.COMPLETED.value,
                correlation_id=get_correlation_id()
            )
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=JobStatus.COMPLETED.value
            )
        
        new_job = replace(self, status=JobStatus.COMPLETED)
        
        # Calculate job duration
        job_duration_ms = (new_job.created_at.timestamp() - self.created_at.timestamp()) * 1000 if hasattr(self, 'created_at') else None
        
        # Structured logging for successful completion
        logger.info(
            "job_state_transition_successful",
            job_id=str(new_job.id.value),
            tenant_id=new_job.tenant_id.value,
            from_status=self.status.value,
            to_status=new_job.status.value,
            transition_duration_ms=(time.time() - start_time) * 1000,
            total_job_duration_ms=job_duration_ms,
            correlation_id=get_correlation_id()
        )
        
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
    
    def fail(self, error_message: str = None) -> "Job":
        """
        Mark job as failed.
        
        Valid transitions:
        - RUNNING -> FAILED
        
        Args:
            error_message: Optional error message for logging
            
        Returns:
            New Job instance in FAILED status
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        start_time = time.time()
        
        if self.status != JobStatus.RUNNING:
            # Log invalid transition attempt
            logger.warning(
                "invalid_state_transition_attempted",
                job_id=str(self.id.value),
                tenant_id=self.tenant_id.value,
                current_status=self.status.value,
                attempted_status=JobStatus.FAILED.value,
                correlation_id=get_correlation_id()
            )
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=JobStatus.FAILED.value
            )
        
        new_job = replace(self, status=JobStatus.FAILED)
        
        # Structured logging for failure with error context
        logger.error(
            "job_state_transition_to_failed",
            job_id=str(new_job.id.value),
            tenant_id=new_job.tenant_id.value,
            from_status=self.status.value,
            to_status=new_job.status.value,
            transition_duration_ms=(time.time() - start_time) * 1000,
            error_message=error_message,
            correlation_id=get_correlation_id()
        )
        
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
    
    def retry(self, retry_attempt: int = 1) -> "Job":
        """
        Mark job for retry after failure.
        
        Valid transitions:
        - FAILED -> RETRYING
        
        Args:
            retry_attempt: Current retry attempt number
            
        Returns:
            New Job instance in RETRYING status
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        start_time = time.time()
        
        if self.status != JobStatus.FAILED:
            # Log invalid transition attempt
            logger.warning(
                "invalid_state_transition_attempted",
                job_id=str(self.id.value),
                tenant_id=self.tenant_id.value,
                current_status=self.status.value,
                attempted_status=JobStatus.RETRYING.value,
                correlation_id=get_correlation_id()
            )
            raise InvalidStateTransitionError(
                from_state=self.status.value,
                to_state=JobStatus.RETRYING.value
            )
        
        new_job = replace(self, status=JobStatus.RETRYING)
        
        # Structured logging for retry with attempt number
        logger.info(
            "job_state_transition_to_retry",
            job_id=str(new_job.id.value),
            tenant_id=new_job.tenant_id.value,
            from_status=self.status.value,
            to_status=new_job.status.value,
            transition_duration_ms=(time.time() - start_time) * 1000,
            retry_attempt=retry_attempt,
            correlation_id=get_correlation_id()
        )
        
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
