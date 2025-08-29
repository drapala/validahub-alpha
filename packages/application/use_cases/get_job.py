"""Get Job use case for ValidaHub application layer.

This use case orchestrates the job retrieval process including:
- Job existence and ownership validation  
- Authorization checking
- Job data projection for API response
- Access logging

Following SOLID principles and DDD patterns.
"""

import time
from dataclasses import dataclass
from typing import Any

from packages.application.ports import (
    AuditLogger,
    AuthenticationService,
    JobRepository,
    MetricsCollector,
    TracingContext,
)
from packages.domain.errors import AggregateNotFoundError, TenantIsolationError
from packages.domain.job import Job
from packages.domain.value_objects import JobId, TenantId

try:
    from packages.shared.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)


@dataclass(frozen=True)
class GetJobRequest:
    """Input data for job retrieval."""
    tenant_id: str
    job_id: str
    # Observability context
    request_id: str | None = None
    user_id: str | None = None
    trace_id: str | None = None


@dataclass(frozen=True)
class GetJobResponse:
    """Output data from job retrieval."""
    job_id: str
    tenant_id: str
    seller_id: str
    channel: str
    type: str
    status: str
    file_ref: str
    output_ref: str | None
    rules_profile_id: str
    counters: dict[str, int]
    callback_url: str | None
    metadata: dict[str, Any] | None
    created_at: str
    updated_at: str
    completed_at: str | None


class GetJobUseCase:
    """
    Use case for retrieving job details.
    
    This use case implements the following business logic:
    1. Validate job exists and belongs to tenant
    2. Check user authorization to access job
    3. Project job data for API response
    4. Record access metrics and audit logs
    
    All operations follow security-first principles with tenant isolation.
    """
    
    def __init__(
        self,
        job_repository: JobRepository,
        auth_service: AuthenticationService,
        audit_logger: AuditLogger,
        metrics_collector: MetricsCollector,
        tracing_context: TracingContext,
    ):
        self.job_repository = job_repository
        self.auth_service = auth_service
        self.audit_logger = audit_logger
        self.metrics_collector = metrics_collector
        self.tracing_context = tracing_context
        self.logger = get_logger("application.get_job")
    
    def execute(self, request: GetJobRequest) -> GetJobResponse:
        """
        Execute job retrieval use case.
        
        Args:
            request: Job retrieval request data
            
        Returns:
            Job details response data
            
        Raises:
            AggregateNotFoundError: If job doesn't exist
            TenantIsolationError: If job belongs to different tenant
            SecurityViolationError: If user doesn't have permission
        """
        span_context = self.tracing_context.create_span(
            "get_job_use_case",
            parent_context=request.trace_id,
        )
        
        start_time = time.time()
        
        try:
            # Convert and validate input
            tenant_id = TenantId(request.tenant_id)
            job_id = JobId(request.job_id)
            
            self.logger.debug(
                "job_retrieval_started",
                tenant_id=str(tenant_id),
                job_id=str(job_id),
                request_id=request.request_id,
                user_id=request.user_id,
                trace_id=request.trace_id,
            )
            
            # Step 1: Find and validate job
            job = self._find_and_validate_job(tenant_id, job_id)
            
            # Step 2: Check authorization (if user_id provided)
            if request.user_id:
                self._check_authorization(tenant_id, job, request.user_id)
            
            # Step 3: Project job data for response
            response = self._create_response(job)
            
            # Step 4: Record metrics and audit
            self._record_success_metrics(tenant_id, start_time)
            self._audit_job_access(job, request)
            
            self.logger.debug(
                "job_retrieval_completed",
                job_id=str(job_id),
                tenant_id=str(tenant_id),
                status=job.status.value,
                duration_ms=int((time.time() - start_time) * 1000),
                request_id=request.request_id,
            )
            
            return response
            
        except Exception as error:
            # Record failure metrics and audit
            self._record_failure_metrics(
                tenant_id if 'tenant_id' in locals() else None,
                error,
                start_time,
            )
            
            if 'tenant_id' in locals() and request.request_id:
                self._audit_job_access_failure(
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
            self.logger.info(
                "job_not_found",
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
                "tenant_isolation_violation_on_get",
                requested_tenant=str(tenant_id),
                actual_tenant=str(job.tenant_id),
                job_id=str(job_id),
            )
            
            raise TenantIsolationError(
                requested_tenant=str(tenant_id),
                actual_tenant=str(job.tenant_id),
            )
        
        return job
    
    def _check_authorization(self, tenant_id: TenantId, job: Job, user_id: str) -> None:
        """Check if user is authorized to access this job."""
        # Check if user has read permission for jobs in this tenant
        has_permission = self.auth_service.check_permissions(
            tenant_id=tenant_id,
            user_id=user_id,
            resource="job",
            action="read",
        )
        
        if not has_permission:
            self.logger.warning(
                "job_access_unauthorized",
                tenant_id=str(tenant_id),
                job_id=str(job.id),
                user_id=user_id,
            )
            
            from packages.domain.errors import SecurityViolationError
            raise SecurityViolationError(
                violation_type="unauthorized_access",
                details=f"User {user_id} not authorized to access job {job.id}",
            )
    
    def _create_response(self, job: Job) -> GetJobResponse:
        """Project job domain model to response DTO."""
        return GetJobResponse(
            job_id=str(job.id),
            tenant_id=str(job.tenant_id),
            seller_id=job.seller_id,
            channel=str(job.channel),
            type=job.type.value,
            status=job.status.value,
            file_ref=str(job.file_ref),
            output_ref=job.output_ref,
            rules_profile_id=str(job.rules_profile_id),
            counters={
                "total": job.counters.total,
                "processed": job.counters.processed,
                "errors": job.counters.errors,
                "warnings": job.counters.warnings,
            },
            callback_url=job.callback_url,
            metadata=job.metadata,
            created_at=job.created_at.isoformat() + "Z",
            updated_at=job.updated_at.isoformat() + "Z",
            completed_at=job.completed_at.isoformat() + "Z" if job.completed_at else None,
        )
    
    def _record_success_metrics(self, tenant_id: TenantId, start_time: float) -> None:
        """Record success metrics."""
        duration_ms = (time.time() - start_time) * 1000
        
        tags = {
            "tenant_id": str(tenant_id),
            "result": "success",
        }
        
        self.metrics_collector.increment_counter("jobs_retrieved_total", tags)
        self.metrics_collector.record_histogram("job_retrieval_duration_ms", duration_ms, tags)
    
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
        
        self.metrics_collector.increment_counter("jobs_retrieved_total", tags)
        self.metrics_collector.record_histogram("job_retrieval_duration_ms", duration_ms, tags)
    
    def _audit_job_access(self, job: Job, request: GetJobRequest) -> None:
        """Create audit log entry for successful job access."""
        self.audit_logger.log_event(
            event_type="job_accessed",
            tenant_id=str(job.tenant_id),
            user_id=request.user_id,
            resource_type="job",
            resource_id=str(job.id),
            action="read",
            result="success",
            request_id=request.request_id or "",
            metadata={
                "job_status": job.status.value,
                "seller_id": job.seller_id,
                "channel": str(job.channel),
                "job_type": job.type.value,
            },
        )
    
    def _audit_job_access_failure(
        self,
        tenant_id: str,
        request: GetJobRequest,
        error_message: str,
    ) -> None:
        """Create audit log entry for failed job access."""
        self.audit_logger.log_event(
            event_type="job_access_failed",
            tenant_id=tenant_id,
            user_id=request.user_id,
            resource_type="job",
            resource_id=request.job_id,
            action="read",
            result="failure",
            request_id=request.request_id or "",
            metadata={
                "error_message": error_message,
            },
        )