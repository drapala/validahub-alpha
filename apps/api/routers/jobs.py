"""Job management endpoints for ValidaHub API.

This module provides REST endpoints for job operations:
- POST /jobs - Submit new job for processing
- GET /jobs/{job_id} - Get job details
- POST /jobs/{job_id}/retry - Retry failed job
- GET /jobs - List jobs with filtering
- GET /jobs/stream - Server-sent events for job updates

All endpoints follow the OpenAPI specification and include
proper validation, authorization, and error handling.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Request, Depends, HTTPException, status, Header, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from packages.application.use_cases.submit_job import SubmitJobUseCase, SubmitJobRequest, SubmitJobResponse
from packages.application.use_cases.get_job import GetJobUseCase, GetJobRequest, GetJobResponse
from packages.application.use_cases.retry_job import RetryJobUseCase, RetryJobRequest, RetryJobResponse
from packages.domain.errors import (
    DomainError, AggregateNotFoundError, RateLimitExceededError,
    IdempotencyViolationError, SecurityViolationError
)

try:
    from packages.shared.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)


logger = get_logger("apps.api.jobs")
router = APIRouter()


# Request/Response models
class SubmitJobRequestModel(BaseModel):
    """Request model for job submission."""
    channel: str = Field(..., description="Marketplace or channel identifier")
    type: str = Field(..., description="Type of processing (validation, correction, enrichment)")
    file_ref: str = Field(..., description="Reference to input file")
    rules_profile_id: str = Field(..., description="Rule pack version to use", regex=r"^[a-z_]+@\d+\.\d+\.\d+$")
    seller_id: str = Field(..., description="Seller identifier")
    callback_url: Optional[str] = Field(None, description="Optional webhook URL for notifications")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "channel": "mercado_livre",
                "type": "validation",
                "file_ref": "s3://uploads/tenant123/products.csv",
                "rules_profile_id": "ml@1.2.3",
                "seller_id": "seller_456",
                "callback_url": "https://webhook.example.com/jobs",
                "metadata": {"source": "manual_upload", "batch_id": "batch_001"}
            }
        }


class JobResponseModel(BaseModel):
    """Response model for job details."""
    job_id: str = Field(..., description="Unique job identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    seller_id: str = Field(..., description="Seller identifier")
    channel: str = Field(..., description="Marketplace or channel identifier")
    type: str = Field(..., description="Type of processing")
    status: str = Field(..., description="Current job status")
    file_ref: str = Field(..., description="Reference to input file")
    output_ref: Optional[str] = Field(None, description="Reference to output file")
    rules_profile_id: str = Field(..., description="Rule pack version used")
    counters: Dict[str, int] = Field(..., description="Processing counters")
    callback_url: Optional[str] = Field(None, description="Webhook URL")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")


class JobListResponseModel(BaseModel):
    """Response model for job listing."""
    data: List[JobResponseModel] = Field(..., description="List of jobs")
    meta: Dict[str, Any] = Field(..., description="Pagination metadata")


class RetryJobResponseModel(BaseModel):
    """Response model for job retry."""
    new_job_id: str = Field(..., description="New job ID for retry")
    original_job_id: str = Field(..., description="Original failed job ID")
    tenant_id: str = Field(..., description="Tenant identifier")
    status: str = Field(..., description="New job status")
    created_at: str = Field(..., description="Creation timestamp")


# Dependency injection (mock implementation)
def get_submit_job_use_case() -> SubmitJobUseCase:
    """Get SubmitJobUseCase instance with dependencies."""
    # In a real application, this would use a DI container
    # to inject the actual implementations of the ports
    raise NotImplementedError("Dependency injection not yet configured")


def get_get_job_use_case() -> GetJobUseCase:
    """Get GetJobUseCase instance with dependencies."""
    raise NotImplementedError("Dependency injection not yet configured")


def get_retry_job_use_case() -> RetryJobUseCase:
    """Get RetryJobUseCase instance with dependencies."""
    raise NotImplementedError("Dependency injection not yet configured")


def validate_tenant_header(x_tenant_id: str = Header(..., description="Tenant identifier")) -> str:
    """Validate tenant ID header."""
    if not x_tenant_id or not x_tenant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-Id header is required"
        )
    
    # Basic format validation
    if not x_tenant_id.startswith("t_") or len(x_tenant_id) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant ID format"
        )
    
    return x_tenant_id.strip()


def validate_idempotency_key(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
) -> Optional[str]:
    """Validate idempotency key header for POST operations."""
    if idempotency_key:
        if len(idempotency_key) < 16 or len(idempotency_key) > 128:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Idempotency-Key must be between 16 and 128 characters"
            )
    
    return idempotency_key


def get_request_context(request: Request) -> Dict[str, Any]:
    """Extract request context from FastAPI request."""
    return {
        "request_id": getattr(request.state, 'request_id', None),
        "user_id": getattr(request.state, 'user_id', None),
        "trace_id": request.headers.get("x-trace-id"),
    }


# Job endpoints
@router.post(
    "",
    response_model=JobResponseModel,
    status_code=status.HTTP_201_CREATED,
    summary="Submit new job for processing",
    description="Submit a new job for CSV validation and processing with idempotency support"
)
async def submit_job(
    request: Request,
    job_request: SubmitJobRequestModel,
    tenant_id: str = Depends(validate_tenant_header),
    idempotency_key: Optional[str] = Depends(validate_idempotency_key),
    submit_job_use_case: SubmitJobUseCase = Depends(get_submit_job_use_case),
):
    """Submit a new job for processing."""
    try:
        # Get request context
        context = get_request_context(request)
        
        # Create use case request
        use_case_request = SubmitJobRequest(
            tenant_id=tenant_id,
            seller_id=job_request.seller_id,
            channel=job_request.channel,
            job_type=job_request.type,
            file_ref=job_request.file_ref,
            rules_profile_id=job_request.rules_profile_id,
            idempotency_key=idempotency_key,
            callback_url=job_request.callback_url,
            metadata=job_request.metadata,
            request_id=context["request_id"],
            user_id=context["user_id"],
            trace_id=context["trace_id"],
        )
        
        # Execute use case
        response = submit_job_use_case.execute(use_case_request)
        
        # Return response
        return JobResponseModel(
            job_id=response.job_id,
            tenant_id=response.tenant_id,
            seller_id=job_request.seller_id,
            channel=job_request.channel,
            type=job_request.type,
            status=response.status,
            file_ref=job_request.file_ref,
            output_ref=None,
            rules_profile_id=job_request.rules_profile_id,
            counters={"total": 0, "processed": 0, "errors": 0, "warnings": 0},
            callback_url=job_request.callback_url,
            metadata=job_request.metadata,
            created_at=response.created_at,
            updated_at=response.created_at,
            completed_at=None,
        )
        
    except DomainError as error:
        logger.warning(
            "job_submission_domain_error",
            tenant_id=tenant_id,
            error=str(error),
            error_type=error.__class__.__name__,
            request_id=context.get("request_id"),
        )
        raise
    
    except Exception as error:
        logger.error(
            "job_submission_unexpected_error",
            tenant_id=tenant_id,
            error=str(error),
            error_type=error.__class__.__name__,
            request_id=context.get("request_id"),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit job"
        )


@router.get(
    "/{job_id}",
    response_model=JobResponseModel,
    summary="Get job details",
    description="Retrieve detailed information about a specific job"
)
async def get_job(
    request: Request,
    job_id: UUID,
    tenant_id: str = Depends(validate_tenant_header),
    get_job_use_case: GetJobUseCase = Depends(get_get_job_use_case),
):
    """Get job details by ID."""
    try:
        # Get request context
        context = get_request_context(request)
        
        # Create use case request
        use_case_request = GetJobRequest(
            tenant_id=tenant_id,
            job_id=str(job_id),
            request_id=context["request_id"],
            user_id=context["user_id"],
            trace_id=context["trace_id"],
        )
        
        # Execute use case
        response = get_job_use_case.execute(use_case_request)
        
        # Return response
        return JobResponseModel(**response.__dict__)
        
    except AggregateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    except DomainError as error:
        logger.warning(
            "get_job_domain_error",
            tenant_id=tenant_id,
            job_id=str(job_id),
            error=str(error),
            error_type=error.__class__.__name__,
            request_id=context.get("request_id"),
        )
        raise
    
    except Exception as error:
        logger.error(
            "get_job_unexpected_error",
            tenant_id=tenant_id,
            job_id=str(job_id),
            error=str(error),
            error_type=error.__class__.__name__,
            request_id=context.get("request_id"),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job"
        )


@router.post(
    "/{job_id}/retry",
    response_model=RetryJobResponseModel,
    summary="Retry failed job",
    description="Create a new job to retry a failed job with same configuration"
)
async def retry_job(
    request: Request,
    job_id: UUID,
    tenant_id: str = Depends(validate_tenant_header),
    retry_job_use_case: RetryJobUseCase = Depends(get_retry_job_use_case),
):
    """Retry a failed job."""
    try:
        # Get request context
        context = get_request_context(request)
        
        # Create use case request
        use_case_request = RetryJobRequest(
            tenant_id=tenant_id,
            job_id=str(job_id),
            request_id=context["request_id"],
            user_id=context["user_id"],
            trace_id=context["trace_id"],
        )
        
        # Execute use case
        response = retry_job_use_case.execute(use_case_request)
        
        # Return response
        return RetryJobResponseModel(**response.__dict__)
        
    except AggregateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    except DomainError as error:
        logger.warning(
            "job_retry_domain_error",
            tenant_id=tenant_id,
            job_id=str(job_id),
            error=str(error),
            error_type=error.__class__.__name__,
            request_id=context.get("request_id"),
        )
        raise
    
    except Exception as error:
        logger.error(
            "job_retry_unexpected_error",
            tenant_id=tenant_id,
            job_id=str(job_id),
            error=str(error),
            error_type=error.__class__.__name__,
            request_id=context.get("request_id"),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry job"
        )


@router.get(
    "",
    response_model=JobListResponseModel,
    summary="List jobs",
    description="List jobs for the tenant with optional filtering and pagination"
)
async def list_jobs(
    request: Request,
    tenant_id: str = Depends(validate_tenant_header),
    status: Optional[str] = Query(None, description="Filter by job status"),
    channel: Optional[str] = Query(None, description="Filter by channel"),
    type: Optional[str] = Query(None, description="Filter by job type"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
):
    """List jobs with filtering and pagination."""
    try:
        # Mock implementation for now
        # In a real implementation, you would:
        # 1. Create a ListJobsUseCase
        # 2. Inject dependencies
        # 3. Execute the use case
        # 4. Return paginated results
        
        logger.info(
            "list_jobs_requested",
            tenant_id=tenant_id,
            status=status,
            channel=channel,
            type=type,
            limit=limit,
            offset=offset,
            request_id=get_request_context(request)["request_id"],
        )
        
        # Return empty list for now
        return JobListResponseModel(
            data=[],
            meta={
                "limit": limit,
                "offset": offset,
                "total": 0,
                "has_more": False,
            }
        )
        
    except Exception as error:
        logger.error(
            "list_jobs_error",
            tenant_id=tenant_id,
            error=str(error),
            error_type=error.__class__.__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list jobs"
        )


@router.get(
    "/stream",
    summary="Job event stream",
    description="Server-sent events stream for real-time job updates"
)
async def stream_job_events(
    request: Request,
    tenant_id: str = Depends(validate_tenant_header),
):
    """Stream job events using Server-Sent Events."""
    async def event_generator():
        """Generate Server-Sent Events for job updates."""
        try:
            logger.info(
                "job_stream_started",
                tenant_id=tenant_id,
                request_id=get_request_context(request)["request_id"],
            )
            
            # Send initial connection event
            yield f"data: {{\"type\": \"connected\", \"tenant_id\": \"{tenant_id}\"}}\n\n"
            
            # Keep connection alive with periodic heartbeat
            # In a real implementation, you would:
            # 1. Subscribe to job events from Redis/message queue
            # 2. Filter events for the tenant
            # 3. Format as Server-Sent Events
            # 4. Handle client disconnection
            
            import asyncio
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                
                # Send heartbeat every 20 seconds
                yield f"event: heartbeat\ndata: {{\"timestamp\": \"{int(time.time())}\"}}\n\n"
                await asyncio.sleep(20)
                
        except Exception as error:
            logger.error(
                "job_stream_error",
                tenant_id=tenant_id,
                error=str(error),
                error_type=error.__class__.__name__,
            )
            yield f"event: error\ndata: {{\"error\": \"Stream error occurred\"}}\n\n"
        
        finally:
            logger.info(
                "job_stream_ended",
                tenant_id=tenant_id,
            )
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        }
    )