"""Submit Job use case."""

import time
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from packages.shared.logging import get_logger
from packages.shared.logging.context import with_request_context, generate_request_id
from packages.shared.logging.security import SecurityLogger

from domain.job import Job
from domain.value_objects import TenantId, IdempotencyKey, FileReference, RulesProfileId
from application.ports import JobRepository, EventBus, RateLimiter


@dataclass
class SubmitJobRequest:
    """Request to submit a new job."""
    
    tenant_id: str
    seller_id: str
    channel: str
    job_type: str
    file_ref: str
    rules_profile_id: str
    idempotency_key: Optional[str] = None


@dataclass
class SubmitJobResponse:
    """Response from job submission."""
    
    job_id: UUID
    status: str
    message: str


class RateLimitExceeded(Exception):
    """Rate limit exceeded for tenant."""
    pass


class SubmitJobUseCase:
    """Use case for submitting a new job."""
    
    def __init__(
        self,
        job_repository: JobRepository,
        event_bus: EventBus,
        rate_limiter: RateLimiter,
    ):
        """
        Initialize use case.
        
        Args:
            job_repository: Repository for job persistence
            event_bus: Event bus for publishing domain events
            rate_limiter: Rate limiter for tenant throttling
        """
        self.job_repository = job_repository
        self.event_bus = event_bus
        self.rate_limiter = rate_limiter
        self.logger = get_logger("application.submit_job")
        self.security_logger = SecurityLogger("application.submit_job")
    
    def execute(self, request: SubmitJobRequest) -> SubmitJobResponse:
        """
        Execute job submission.
        
        Args:
            request: Job submission request
            
        Returns:
            Job submission response
            
        Raises:
            RateLimitExceeded: If tenant exceeds rate limit
            ValueError: If request is invalid
        """
        request_id = generate_request_id()
        start_time = time.perf_counter()
        
        # Add request context for all logs in this execution
        with_request_context(
            request_id=request_id,
            tenant_id=request.tenant_id,
            actor_id=request.seller_id,
        )
        
        self.logger.info(
            "job_submission_started",
            request_id=request_id,
            tenant_id=request.tenant_id,
            seller_id=request.seller_id,
            channel=request.channel,
            job_type=request.job_type,
            has_idempotency_key=request.idempotency_key is not None,
        )
        
        try:
            # Parse and validate value objects
            tenant_id = TenantId(request.tenant_id)
            file_ref = FileReference(request.file_ref)
            rules_profile_id = RulesProfileId.from_string(request.rules_profile_id)
            idempotency_key = IdempotencyKey(request.idempotency_key) if request.idempotency_key else None
            
            # Check rate limit
            if not self.rate_limiter.check_limit(request.tenant_id):
                self.security_logger.rate_limit_exceeded(
                    resource="job_submission",
                    limit=100,  # TODO: Get from config
                    window="1m",
                    tenant_id=request.tenant_id,
                    seller_id=request.seller_id,
                )
                raise RateLimitExceeded(f"Rate limit exceeded for tenant {request.tenant_id}")
            
            # Check for duplicate submission
            if idempotency_key:
                duplicate_job = self.job_repository.find_by_idempotency_key(
                    tenant_id, idempotency_key
                )
                if duplicate_job:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    
                    self.logger.info(
                        "job_submission_duplicate",
                        request_id=request_id,
                        job_id=str(duplicate_job.id),
                        tenant_id=request.tenant_id,
                        idempotency_key=str(idempotency_key),
                        duration_ms=duration_ms,
                    )
                    
                    return SubmitJobResponse(
                        job_id=duplicate_job.id,
                        status=duplicate_job.status.value,
                        message="Duplicate job found"
                    )
            
            # Create new job
            job = Job.create(
                tenant_id=tenant_id,
                seller_id=request.seller_id,
                channel=request.channel,
                job_type=request.job_type,
                file_ref=file_ref,
                rules_profile_id=rules_profile_id,
                idempotency_key=idempotency_key,
            )
            
            # Save job
            self.job_repository.save(job)
            
            # Publish job submitted event
            self.event_bus.publish({
                "type": "job.submitted",
                "job_id": str(job.id),
                "tenant_id": str(tenant_id),
                "seller_id": request.seller_id,
                "channel": request.channel,
            })
            
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            self.logger.info(
                "job_submission_completed",
                request_id=request_id,
                job_id=str(job.id),
                tenant_id=request.tenant_id,
                seller_id=request.seller_id,
                duration_ms=duration_ms,
            )
            
            return SubmitJobResponse(
                job_id=job.id,
                status=job.status.value,
                message="Job submitted successfully"
            )
            
        except RateLimitExceeded:
            raise
        except ValueError as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            self.logger.warning(
                "job_submission_validation_failed",
                request_id=request_id,
                tenant_id=request.tenant_id,
                seller_id=request.seller_id,
                error_type="validation_error",
                error_message=str(e),
                duration_ms=duration_ms,
            )
            raise
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            self.logger.error(
                "job_submission_failed",
                request_id=request_id,
                tenant_id=request.tenant_id,
                seller_id=request.seller_id,
                error_type=type(e).__name__,
                error_message=str(e),
                duration_ms=duration_ms,
                exc_info=True,
            )
            raise