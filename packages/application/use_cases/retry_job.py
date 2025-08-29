"""Retry Job use case for ValidaHub application layer.

This use case orchestrates the job retry process including:
- Job existence and ownership validation
- Job retry eligibility checking
- New job creation for retry
- Event publishing
- Audit logging

Following SOLID principles and DDD patterns.
"""

from dataclasses import dataclass
from typing import Optional
import time

from packages.domain.job import Job
from packages.domain.value_objects import JobId, TenantId
from packages.domain.errors import (
    AggregateNotFoundError, InvalidStateTransitionError,
    TenantIsolationError, BusinessRuleViolationError
)
from packages.application.ports import (
    JobRepository, EventBus, EventOutbox,
    AuditLogger, MetricsCollector, TracingContext
)

try:
    from packages.shared.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)


@dataclass(frozen=True)
class RetryJobRequest:
    """Input data for job retry."""
    tenant_id: str
    job_id: str
    # Observability context
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    trace_id: Optional[str] = None


@dataclass(frozen=True)
class RetryJobResponse:
    """Output data from job retry."""
    new_job_id: str
    original_job_id: str
    tenant_id: str
    status: str
    created_at: str


class RetryJobUseCase:
    """
    Use case for retrying a failed job.
    
    This use case implements the following business logic:
    1. Validate job exists and belongs to tenant
    2. Check job is in a state eligible for retry
    3. Create new job for retry with same configuration
    4. Persist new job with events
    5. Publish domain events
    6. Record metrics and audit logs
    
    The retry creates a completely new job instance, not modifying the original.
    """
    
    def __init__(
        self,
        job_repository: JobRepository,
        event_bus: EventBus,
        event_outbox: EventOutbox,
        audit_logger: AuditLogger,
        metrics_collector: MetricsCollector,
        tracing_context: TracingContext,
    ):
        self.job_repository = job_repository
        self.event_bus = event_bus
        self.event_outbox = event_outbox
        self.audit_logger = audit_logger
        self.metrics_collector = metrics_collector
        self.tracing_context = tracing_context
        self.logger = get_logger("application.retry_job")
    
    def execute(self, request: RetryJobRequest) -> RetryJobResponse:
        """
        Execute job retry use case.
        
        Args:
            request: Job retry request data
            
        Returns:
            Job retry response data
            
        Raises:
            AggregateNotFoundError: If job doesn't exist
            TenantIsolationError: If job belongs to different tenant
            InvalidStateTransitionError: If job cannot be retried
            BusinessRuleViolationError: If retry violates business rules
        """
        span_context = self.tracing_context.create_span(
            "retry_job_use_case",
            parent_context=request.trace_id,
        )
        
        start_time = time.time()
        
        try:
            # Convert and validate input
            tenant_id = TenantId(request.tenant_id)
            job_id = JobId(request.job_id)
            
            self.logger.info(
                "job_retry_started",
                tenant_id=str(tenant_id),
                job_id=str(job_id),
                request_id=request.request_id,
                user_id=request.user_id,
                trace_id=request.trace_id,
            )
            
            # Step 1: Find and validate job
            original_job = self._find_and_validate_job(tenant_id, job_id)
            
            # Step 2: Check retry eligibility
            self._validate_retry_eligibility(original_job, request.request_id)
            
            # Step 3: Create retry job
            retry_job = original_job.retry(
                actor_id=request.user_id,
                trace_id=request.trace_id,
            )
            
            # Step 4: Persist retry job with events
            saved_retry_job = self.job_repository.save(retry_job)
            
            # Step 5: Store events for eventual publishing
            self.event_outbox.store_events(
                saved_retry_job.get_events(),
                correlation_id=request.request_id,
            )
            
            # Step 6: Record metrics and audit
            self._record_success_metrics(tenant_id, start_time)
            self._audit_job_retry(original_job, saved_retry_job, request)
            
            self.logger.info(
                "job_retry_completed",
                original_job_id=str(original_job.id),
                new_job_id=str(saved_retry_job.id),
                tenant_id=str(tenant_id),
                duration_ms=int((time.time() - start_time) * 1000),
                request_id=request.request_id,
            )
            
            return RetryJobResponse(
                new_job_id=str(saved_retry_job.id),
                original_job_id=str(original_job.id),
                tenant_id=str(tenant_id),
                status=saved_retry_job.status.value,
                created_at=saved_retry_job.created_at.isoformat() + "Z",
            )
            
        except Exception as error:
            # Record failure metrics and audit
            self._record_failure_metrics(
                tenant_id if 'tenant_id' in locals() else None,
                error,
                start_time,
            )
            
            if 'tenant_id' in locals() and request.request_id:
                self._audit_job_retry_failure(
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
    
    def _find_and_validate_job(self, tenant_id: TenantId, job_id: JobId) -> Job:
        """Find job and validate ownership."""
        job = self.job_repository.find_by_id(tenant_id, job_id)
        
        if not job:
            self.logger.warning(
                "job_not_found_for_retry",
                tenant_id=str(tenant_id),
                job_id=str(job_id),
            )
            
            raise AggregateNotFoundError(
                aggregate_type="Job",
                identifier=str(job_id),
            )
        
        # Double-check tenant isolation (should be enforced by repository)
        if str(job.tenant_id) != str(tenant_id):
            self.logger.error(
                "tenant_isolation_violation_on_retry",
                requested_tenant=str(tenant_id),
                actual_tenant=str(job.tenant_id),
                job_id=str(job_id),
            )
            
            raise TenantIsolationError(
                requested_tenant=str(tenant_id),
                actual_tenant=str(job.tenant_id),
            )
        
        return job
    
    def _validate_retry_eligibility(self, job: Job, request_id: Optional[str]) -> None:
        """Validate that job can be retried."""
        if not job.can_retry():
            self.logger.warning(
                "job_not_eligible_for_retry",
                job_id=str(job.id),
                tenant_id=str(job.tenant_id),
                current_status=job.status.value,
                request_id=request_id,
            )
            
            raise InvalidStateTransitionError(
                from_state=job.status.value,
                to_state="retried",
            )
        
        # Additional business rules for retry eligibility
        # Example: Check if too many retries have been attempted
        retry_count = self._get_retry_count(job)
        max_retries = 3  # Business rule: max 3 retries
        
        if retry_count >= max_retries:
            self.logger.warning(
                "job_max_retries_exceeded",
                job_id=str(job.id),
                tenant_id=str(job.tenant_id),
                retry_count=retry_count,
                max_retries=max_retries,
                request_id=request_id,
            )
            
            raise BusinessRuleViolationError(
                rule_name="max_retry_attempts",
                violation_details=f"Job has already been retried {retry_count} times (max: {max_retries})",
            )
        
        self.logger.debug(
            "job_retry_eligibility_validated",
            job_id=str(job.id),
            tenant_id=str(job.tenant_id),
            retry_count=retry_count,
            request_id=request_id,
        )
    
    def _get_retry_count(self, job: Job) -> int:
        """
        Get the number of times this job has been retried.
        
        This is a simplified implementation. In a real system, this would
        track retry chains through metadata or a separate table.
        """
        # For now, return 0. This should be implemented based on your
        # specific retry tracking strategy
        return 0
    
    def _record_success_metrics(self, tenant_id: TenantId, start_time: float) -> None:
        """Record success metrics."""
        duration_ms = (time.time() - start_time) * 1000
        
        tags = {
            "tenant_id": str(tenant_id),
            "result": "success",
        }
        
        self.metrics_collector.increment_counter("jobs_retried_total", tags)
        self.metrics_collector.record_histogram("job_retry_duration_ms", duration_ms, tags)
    
    def _record_failure_metrics(
        self,
        tenant_id: Optional[TenantId],
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
        
        self.metrics_collector.increment_counter("jobs_retried_total", tags)
        self.metrics_collector.record_histogram("job_retry_duration_ms", duration_ms, tags)
    
    def _audit_job_retry(
        self,
        original_job: Job,
        retry_job: Job,
        request: RetryJobRequest,
    ) -> None:
        """Create audit log entry for successful job retry."""
        self.audit_logger.log_event(
            event_type="job_retried",
            tenant_id=str(original_job.tenant_id),
            user_id=request.user_id,
            resource_type="job",
            resource_id=str(original_job.id),
            action="retry",
            result="success",
            request_id=request.request_id or "",
            metadata={
                "original_job_id": str(original_job.id),
                "new_job_id": str(retry_job.id),
                "original_status": original_job.status.value,
                "seller_id": original_job.seller_id,
                "channel": str(original_job.channel),
                "job_type": original_job.type.value,
            },
        )
    
    def _audit_job_retry_failure(
        self,
        tenant_id: str,
        request: RetryJobRequest,
        error_message: str,
    ) -> None:
        """Create audit log entry for failed job retry."""
        self.audit_logger.log_event(
            event_type="job_retry_failed",
            tenant_id=tenant_id,
            user_id=request.user_id,
            resource_type="job",
            resource_id=request.job_id,
            action="retry",
            result="failure",
            request_id=request.request_id or "",
            metadata={
                "error_message": error_message,
            },
        )