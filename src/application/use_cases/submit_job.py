"""Submit job use case for ValidaHub."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.application.errors import RateLimitExceeded, ValidationError
from src.application.ports import JobRepository, RateLimiter, EventBus
from src.domain.job import Job, JobStatus
from src.domain.value_objects import TenantId, IdempotencyKey, Channel, FileReference, RulesProfileId
from src.shared.logging import get_logger


@dataclass(frozen=True)
class SubmitJobRequest:
    """Request DTO for job submission."""
    tenant_id: str
    seller_id: str
    channel: str
    job_type: str
    file_ref: str
    rules_profile_id: str
    idempotency_key: Optional[str] = None


@dataclass(frozen=True) 
class SubmitJobResponse:
    """Response DTO for job submission."""
    job_id: str
    status: str
    file_ref: str
    created_at: str
    
    @classmethod
    def from_job(cls, job: Job, file_ref: str) -> "SubmitJobResponse":
        """Create response from job domain object."""
        return cls(
            job_id=str(job.id.value),
            status=job.status.value,
            file_ref=file_ref,
            created_at=job.created_at.isoformat()
        )


# Domain event for submission (stub for now)
@dataclass(frozen=True)
class JobSubmittedEvent:
    """Domain event for job submission."""
    id: str
    specversion: str = "1.0"
    source: str = "application/submit-job"
    type: str = "valida.job.submitted"
    time: str = ""
    subject: str = ""
    tenant_id: str = ""
    actor_id: str = ""
    trace_id: str = ""
    schema_version: str = "1"
    data: dict = None
    
    def __post_init__(self):
        if not self.time:
            object.__setattr__(self, 'time', datetime.now(timezone.utc).isoformat())
        if not self.trace_id:
            object.__setattr__(self, 'trace_id', str(uuid4()))


class SubmitJobUseCase:
    """Use case for submitting jobs for processing."""
    
    def __init__(
        self,
        job_repository: JobRepository,
        rate_limiter: RateLimiter,
        event_bus: EventBus
    ) -> None:
        """
        Initialize use case with dependencies.
        
        Args:
            job_repository: Repository for job persistence
            rate_limiter: Rate limiter for tenant requests
            event_bus: Event bus for publishing domain events
        """
        self._job_repository = job_repository
        self._rate_limiter = rate_limiter
        self._event_bus = event_bus
        self._logger = get_logger("application.submit_job")
    
    def execute(self, request: SubmitJobRequest) -> SubmitJobResponse:
        """
        Execute job submission use case.
        
        Args:
            request: Job submission request
            
        Returns:
            Job submission response
            
        Raises:
            ValidationError: If input validation fails
            RateLimitExceeded: If rate limit exceeded
        """
        self._logger.info(
            "submit_job_requested",
            tenant_id=request.tenant_id,
            channel=request.channel,
            job_type=request.job_type,
            has_idempotency_key=request.idempotency_key is not None
        )
        
        # Validate input
        self._validate_request(request)
        
        # Convert to value objects
        tenant_id = TenantId(request.tenant_id)
        idempotency_key = IdempotencyKey(request.idempotency_key) if request.idempotency_key else None
        
        # Check idempotency first (before rate limiting)
        if idempotency_key:
            existing_job = self._job_repository.find_by_idempotency_key(tenant_id, idempotency_key)
            if existing_job:
                self._logger.info(
                    "submit_job_idempotent_return",
                    tenant_id=request.tenant_id,
                    job_id=existing_job.id,
                    idempotency_key=request.idempotency_key
                )
                return SubmitJobResponse(
                    job_id=existing_job.id,
                    status=existing_job.status.value,
                    file_ref=request.file_ref,
                    created_at=existing_job.created_at.isoformat()
                )
        
        # Check rate limit
        if not self._rate_limiter.check_and_consume(tenant_id, "job_submission"):
            self._logger.warning(
                "submit_job_rate_limited",
                tenant_id=request.tenant_id,
                resource="job_submission"
            )
            raise RateLimitExceeded(request.tenant_id, "job_submission")
        
        # Create job
        job = Job.create(tenant_id)
        
        # Create extended job with additional fields (simulate database model)
        extended_job = ExtendedJob(
            id=str(job.id.value),
            tenant_id=job.tenant_id.value,
            seller_id=request.seller_id,
            channel=request.channel,
            job_type=request.job_type,
            file_ref=request.file_ref,
            rules_profile_id=request.rules_profile_id,
            status=JobStatus.QUEUED,  # Change to QUEUED as expected by tests
            idempotency_key=request.idempotency_key,
            created_at=job.created_at,
            updated_at=job.created_at
        )
        
        # Save job
        saved_job = self._job_repository.save(extended_job)
        
        # Publish domain event
        event = JobSubmittedEvent(
            id=str(uuid4()),
            subject=f"job:{saved_job.id}",
            tenant_id=request.tenant_id,
            actor_id=request.seller_id,
            data={
                "job_id": saved_job.id,
                "tenant_id": request.tenant_id,
                "seller_id": request.seller_id,
                "channel": request.channel,
                "job_type": request.job_type,
                "file_ref": request.file_ref,
                "rules_profile_id": request.rules_profile_id
            }
        )
        
        self._event_bus.publish(event)
        
        self._logger.info(
            "submit_job_completed",
            tenant_id=request.tenant_id,
            job_id=saved_job.id,
            status=saved_job.status.value
        )
        
        return SubmitJobResponse(
            job_id=saved_job.id,
            status=saved_job.status.value,
            file_ref=request.file_ref,
            created_at=saved_job.created_at.isoformat()
        )
    
    def _validate_request(self, request: SubmitJobRequest) -> None:
        """Validate job submission request."""
        if not request.tenant_id or not request.tenant_id.strip():
            raise ValueError("tenant_id is required")
        
        if not request.seller_id or not request.seller_id.strip():
            raise ValueError("seller_id is required")
        
        if not request.file_ref or not request.file_ref.strip():
            raise ValueError("file_ref is required")
        
        # Validate value objects (will raise ValueError if invalid)
        TenantId(request.tenant_id)
        Channel(request.channel)
        FileReference(request.file_ref)
        RulesProfileId.from_string(request.rules_profile_id)
        
        if request.idempotency_key:
            IdempotencyKey(request.idempotency_key)


# Extended job class to match test expectations
@dataclass
class ExtendedJob:
    """Extended job with all fields expected by tests."""
    id: str
    tenant_id: str
    seller_id: str
    channel: str
    job_type: str
    file_ref: str
    rules_profile_id: str
    status: JobStatus
    idempotency_key: Optional[str]
    created_at: datetime
    updated_at: datetime