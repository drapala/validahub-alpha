"""Submit Job use case for ValidaHub application layer.

This use case orchestrates the job submission process including:
- Rate limiting validation
- Idempotency checking
- Job creation and persistence
- Event publishing
- Audit logging

Following SOLID principles and DDD patterns.
"""

import time
from dataclasses import dataclass
from typing import Any

from packages.application.ports import (
    AuditLogger,
    EventBus,
    EventOutbox,
    JobRepository,
    MetricsCollector,
    ObjectStorage,
    RateLimiter,
    TracingContext,
)
from packages.domain.enums import JobType
from packages.domain.errors import (
    BusinessRuleViolationError,
    RateLimitExceededError,
)
from packages.domain.job import Job
from packages.domain.value_objects import (
    Channel,
    FileReference,
    IdempotencyKey,
    RulesProfileId,
    TenantId,
)

try:
    from packages.shared.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)


@dataclass(frozen=True)
class SubmitJobRequest:
    """Input data for job submission."""
    tenant_id: str
    seller_id: str
    channel: str
    job_type: str
    file_ref: str
    rules_profile_id: str
    idempotency_key: str | None = None
    callback_url: str | None = None
    metadata: dict[str, Any] | None = None
    # Observability context
    request_id: str | None = None
    user_id: str | None = None
    trace_id: str | None = None


@dataclass(frozen=True)
class SubmitJobResponse:
    """Output data from job submission."""
    job_id: str
    tenant_id: str
    status: str
    created_at: str
    # Rate limiting info
    rate_limit_remaining: int
    rate_limit_reset: int


class SubmitJobUseCase:
    """
    Use case for submitting a new job for processing.
    
    This use case implements the following business logic:
    1. Validate rate limits for tenant
    2. Check file reference accessibility
    3. Verify idempotency constraints
    4. Create and validate job aggregate
    5. Persist job with events
    6. Publish domain events
    7. Record metrics and audit logs
    
    All operations are atomic and follow eventual consistency patterns.
    """
    
    def __init__(
        self,
        job_repository: JobRepository,
        rate_limiter: RateLimiter,
        event_bus: EventBus,
        event_outbox: EventOutbox,
        object_storage: ObjectStorage,
        audit_logger: AuditLogger,
        metrics_collector: MetricsCollector,
        tracing_context: TracingContext,
    ):
        self.job_repository = job_repository
        self.rate_limiter = rate_limiter
        self.event_bus = event_bus
        self.event_outbox = event_outbox
        self.object_storage = object_storage
        self.audit_logger = audit_logger
        self.metrics_collector = metrics_collector
        self.tracing_context = tracing_context
        self.logger = get_logger("application.submit_job")
    
    def execute(self, request: SubmitJobRequest) -> SubmitJobResponse:
        """
        Execute job submission use case.
        
        Args:
            request: Job submission request data
            
        Returns:
            Job submission response data
            
        Raises:
            RateLimitExceededError: If tenant rate limit exceeded
            IdempotencyViolationError: If idempotency key conflicts
            SecurityViolationError: If file reference is invalid/dangerous
            BusinessRuleViolationError: If business rules are violated
        """
        span_context = self.tracing_context.create_span(
            "submit_job_use_case",
            parent_context=request.trace_id,
        )
        
        start_time = time.time()
        
        try:
            # Convert and validate input
            tenant_id = TenantId(request.tenant_id)
            channel = Channel(request.channel)
            job_type = JobType(request.job_type)
            file_ref = FileReference(request.file_ref)
            rules_profile_id = RulesProfileId.from_string(request.rules_profile_id)
            
            idempotency_key = None
            if request.idempotency_key:
                idempotency_key = IdempotencyKey(request.idempotency_key)
            
            self.logger.info(
                "job_submission_started",
                tenant_id=str(tenant_id),
                seller_id=request.seller_id,
                channel=str(channel),
                job_type=job_type.value,
                request_id=request.request_id,
                user_id=request.user_id,
                trace_id=request.trace_id,
            )
            
            # Step 1: Check rate limits
            self._check_rate_limits(tenant_id, request.request_id)
            
            # Step 2: Validate file reference
            self._validate_file_reference(file_ref, tenant_id, request.request_id)
            
            # Step 3: Check idempotency
            existing_job = self._check_idempotency(
                tenant_id, idempotency_key, request.request_id
            )
            if existing_job:
                return self._create_response_from_existing_job(existing_job)
            
            # Step 4: Create job aggregate
            job = Job.create(
                tenant_id=tenant_id,
                seller_id=request.seller_id,
                channel=channel,
                job_type=job_type,
                file_ref=file_ref,
                rules_profile_id=rules_profile_id,
                idempotency_key=idempotency_key,
                callback_url=request.callback_url,
                metadata=request.metadata,
                actor_id=request.user_id,
                trace_id=request.trace_id,
            )
            
            # Step 5: Persist job with events (atomic transaction)
            saved_job = self.job_repository.save(job)
            
            # Step 6: Store events for eventual publishing
            self.event_outbox.store_events(
                saved_job.get_events(),
                correlation_id=request.request_id,
            )
            
            # Step 7: Record metrics and audit
            self._record_success_metrics(tenant_id, job_type, start_time)
            self._audit_job_submission(saved_job, request)
            
            # Get rate limit info for response
            rate_limit_info = self.rate_limiter.get_limit_info(
                tenant_id, "job_submission"
            )
            
            self.logger.info(
                "job_submission_completed",
                job_id=str(saved_job.id),
                tenant_id=str(tenant_id),
                status=saved_job.status.value,
                duration_ms=int((time.time() - start_time) * 1000),
                request_id=request.request_id,
            )
            
            return SubmitJobResponse(
                job_id=str(saved_job.id),
                tenant_id=str(tenant_id),
                status=saved_job.status.value,
                created_at=saved_job.created_at.isoformat() + "Z",
                rate_limit_remaining=rate_limit_info.get("remaining", 0),
                rate_limit_reset=rate_limit_info.get("reset_time", 0),
            )
            
        except Exception as error:
            # Record failure metrics and audit
            self._record_failure_metrics(
                tenant_id if 'tenant_id' in locals() else None,
                error,
                start_time,
            )
            
            if 'tenant_id' in locals() and request.request_id:
                self._audit_job_submission_failure(
                    str(tenant_id),
                    request,
                    str(error),
                )
            
            self.tracing_context.finish_span(
                span_context,
                error=error,
            )
            
            raise
        
        finally:
            self.tracing_context.finish_span(span_context)
    
    def _check_rate_limits(self, tenant_id: TenantId, request_id: str | None) -> None:
        """Check if tenant has exceeded rate limits."""
        if not self.rate_limiter.check_and_consume(tenant_id, "job_submission"):
            rate_limit_info = self.rate_limiter.get_limit_info(tenant_id, "job_submission")
            
            self.logger.warning(
                "rate_limit_exceeded",
                tenant_id=str(tenant_id),
                resource="job_submission",
                reset_time=rate_limit_info.get("reset_time"),
                request_id=request_id,
            )
            
            raise RateLimitExceededError(
                tenant_id=str(tenant_id),
                limit_type="job_submission",
                reset_time=rate_limit_info.get("reset_time", int(time.time()) + 3600),
            )
    
    def _validate_file_reference(
        self,
        file_ref: FileReference,
        tenant_id: TenantId,
        request_id: str | None,
    ) -> None:
        """Validate that file reference is accessible and valid."""
        try:
            # For S3 references, check if object exists
            if file_ref.get_scheme() == "s3":
                bucket = file_ref.get_bucket()
                key = file_ref.get_key()
                
                if not self.object_storage.object_exists(bucket, key):
                    raise BusinessRuleViolationError(
                        rule_name="file_accessibility",
                        violation_details=f"File not found: {file_ref}",
                    )
                
                # Get metadata to validate file
                metadata = self.object_storage.get_object_metadata(bucket, key)
                if metadata:
                    # Validate file size (example: max 100MB)
                    file_size = metadata.get("size", 0)
                    if file_size > 100 * 1024 * 1024:
                        raise BusinessRuleViolationError(
                            rule_name="file_size_limit",
                            violation_details=f"File too large: {file_size} bytes",
                        )
            
            self.logger.debug(
                "file_reference_validated",
                file_ref=str(file_ref),
                tenant_id=str(tenant_id),
                request_id=request_id,
            )
            
        except Exception as error:
            self.logger.error(
                "file_reference_validation_failed",
                file_ref=str(file_ref),
                tenant_id=str(tenant_id),
                error=str(error),
                request_id=request_id,
            )
            
            if isinstance(error, BusinessRuleViolationError):
                raise
            
            raise BusinessRuleViolationError(
                rule_name="file_validation",
                violation_details="Unable to validate file reference",
            )
    
    def _check_idempotency(
        self,
        tenant_id: TenantId,
        idempotency_key: IdempotencyKey | None,
        request_id: str | None,
    ) -> Job | None:
        """Check idempotency constraints and return existing job if found."""
        if not idempotency_key:
            return None
        
        existing_job = self.job_repository.find_by_idempotency_key(
            tenant_id, idempotency_key
        )
        
        if existing_job:
            self.logger.info(
                "idempotent_job_submission",
                existing_job_id=str(existing_job.id),
                tenant_id=str(tenant_id),
                idempotency_key=str(idempotency_key),
                request_id=request_id,
            )
            
            # Return existing job for idempotent response
            return existing_job
        
        return None
    
    def _create_response_from_existing_job(self, job: Job) -> SubmitJobResponse:
        """Create response from existing job for idempotent requests."""
        # Get current rate limit info
        rate_limit_info = self.rate_limiter.get_limit_info(
            job.tenant_id, "job_submission"
        )
        
        return SubmitJobResponse(
            job_id=str(job.id),
            tenant_id=str(job.tenant_id),
            status=job.status.value,
            created_at=job.created_at.isoformat() + "Z",
            rate_limit_remaining=rate_limit_info.get("remaining", 0),
            rate_limit_reset=rate_limit_info.get("reset_time", 0),
        )
    
    def _record_success_metrics(
        self,
        tenant_id: TenantId,
        job_type: JobType,
        start_time: float,
    ) -> None:
        """Record success metrics."""
        duration_ms = (time.time() - start_time) * 1000
        
        tags = {
            "tenant_id": str(tenant_id),
            "job_type": job_type.value,
            "result": "success",
        }
        
        self.metrics_collector.increment_counter("jobs_submitted_total", tags)
        self.metrics_collector.record_histogram("job_submission_duration_ms", duration_ms, tags)
    
    def _record_failure_metrics(
        self,
        tenant_id: TenantId | None,
        error: Exception,
        start_time: float,
    ) -> None:
        """Record failure metrics."""
        duration_ms = (time.time() - start_time) * 1000
        
        tags = {
            "tenant_id": str(tenant_id) if tenant_id else "unknown",
            "error_type": error.__class__.__name__,
            "result": "failure",
        }
        
        self.metrics_collector.increment_counter("jobs_submitted_total", tags)
        self.metrics_collector.record_histogram("job_submission_duration_ms", duration_ms, tags)
    
    def _audit_job_submission(self, job: Job, request: SubmitJobRequest) -> None:
        """Create audit log entry for successful job submission."""
        self.audit_logger.log_event(
            event_type="job_submitted",
            tenant_id=str(job.tenant_id),
            user_id=request.user_id,
            resource_type="job",
            resource_id=str(job.id),
            action="submit",
            result="success",
            request_id=request.request_id or "",
            metadata={
                "seller_id": job.seller_id,
                "channel": str(job.channel),
                "job_type": job.type.value,
                "rules_profile_id": str(job.rules_profile_id),
                "has_idempotency_key": job.idempotency_key is not None,
                "has_callback_url": job.callback_url is not None,
            },
        )
    
    def _audit_job_submission_failure(
        self,
        tenant_id: str,
        request: SubmitJobRequest,
        error_message: str,
    ) -> None:
        """Create audit log entry for failed job submission."""
        self.audit_logger.log_event(
            event_type="job_submission_failed",
            tenant_id=tenant_id,
            user_id=request.user_id,
            resource_type="job",
            resource_id="",  # No job created
            action="submit",
            result="failure",
            request_id=request.request_id or "",
            metadata={
                "seller_id": request.seller_id,
                "channel": request.channel,
                "job_type": request.job_type,
                "error_message": error_message,
            },
        )