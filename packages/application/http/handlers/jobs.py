"""HTTP handlers for job-related endpoints with secure idempotency."""

import uuid
from dataclasses import dataclass
from typing import Any

from packages.application.config import Config
from packages.application.errors import RateLimitExceeded, ValidationError
from packages.application.idempotency.resolver import resolve_idempotency_key, validate_resolved_key
from packages.application.idempotency.store import IdempotencyConflictError, IdempotencyStore
from packages.application.use_cases.submit_job import (
    SubmitJobRequest,
    SubmitJobUseCase,
)
from packages.domain.value_objects import TenantId

# Graceful handling of logging dependencies
try:
    from shared.logging import get_logger
    from shared.logging.security import SecurityEventType, SecurityLogger
except ImportError:
    # Fallback logging for testing without full dependencies
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)
    
    class SecurityLogger:
        def __init__(self, name: str):
            self.logger = logging.getLogger(name)
        
        def log_security_event(self, event_type, message, **kwargs):
            self.logger.warning(f"Security event: {message}", extra=kwargs)
        
        class SecurityEventType:
            INVALID_KEY = "invalid_key"


@dataclass
class HttpJobSubmissionRequest:
    """HTTP-specific job submission request with headers."""
    # Core request data
    tenant_id: str
    seller_id: str
    channel: str
    job_type: str
    file_ref: str
    rules_profile_id: str
    
    # HTTP headers
    idempotency_key_raw: str | None = None
    request_id: str | None = None
    
    # HTTP context
    method: str = "POST"
    route_template: str = "/jobs"


@dataclass  
class HttpJobSubmissionResponse:
    """HTTP-specific job submission response with metadata."""
    # Core response data
    job_id: str
    status: str
    file_ref: str
    created_at: str
    
    # HTTP metadata
    idempotency_key_resolved: str
    request_id: str
    is_idempotent_replay: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "file_ref": self.file_ref,
            "created_at": self.created_at,
            "meta": {
                "idempotency_key": self.idempotency_key_resolved,
                "request_id": self.request_id,
                "is_replay": self.is_idempotent_replay
            }
        }


class JobsHttpHandler:
    """HTTP handler for job operations with secure idempotency."""
    
    def __init__(
        self,
        submit_job_use_case: SubmitJobUseCase,
        idempotency_store: IdempotencyStore
    ):
        """
        Initialize handler with dependencies.
        
        Args:
            submit_job_use_case: Use case for job submission
            idempotency_store: Store for idempotency records
        """
        self._submit_job_use_case = submit_job_use_case
        self._idempotency_store = idempotency_store
        self._logger = get_logger("application.http.jobs")
        self._security_logger = SecurityLogger("application.http.jobs")
    
    def submit_job(self, request: HttpJobSubmissionRequest) -> HttpJobSubmissionResponse:
        """
        Handle job submission with secure idempotency resolution.
        
        Args:
            request: HTTP job submission request
            
        Returns:
            HTTP job submission response
            
        Raises:
            ValidationError: If request validation fails
            RateLimitExceeded: If rate limit exceeded
            ValueError: If idempotency key is invalid in REJECT mode
        """
        request_id = request.request_id or str(uuid.uuid4())
        
        self._logger.info(
            "job_submission_requested",
            request_id=request_id,
            tenant_id=request.tenant_id,
            channel=request.channel,
            job_type=request.job_type,
            has_raw_idempotency_key=request.idempotency_key_raw is not None,
            compat_mode=Config.get_idemp_compat_mode().value
        )
        
        try:
            # Step 1: Resolve idempotency key securely
            tenant_id = TenantId(request.tenant_id)
            resolved_key = resolve_idempotency_key(
                request.idempotency_key_raw,
                tenant_id,
                request.method,
                request.route_template
            )
            
            # Step 2: Validate resolved key meets security requirements
            if not validate_resolved_key(resolved_key):
                self._security_logger.log_security_event(
                    SecurityEventType.INVALID_FILE_TYPE if hasattr(SecurityEventType, 'INVALID_FILE_TYPE') else SecurityEventType.SUSPICIOUS_ACTIVITY,
                    "Resolved idempotency key failed validation",
                    severity="ERROR",
                    tenant_id=request.tenant_id,
                    request_id=request_id,
                    key_length=len(resolved_key)
                )
                raise ValidationError("idempotency_key", "Invalid idempotency key")
            
            # Step 3: Check for existing idempotent response
            existing_record = self._idempotency_store.get(tenant_id, resolved_key)
            if existing_record:
                self._logger.info(
                    "idempotent_response_returned",
                    request_id=request_id,
                    tenant_id=request.tenant_id,
                    resolved_key_length=len(resolved_key),
                    record_age_seconds=(existing_record.created_at.timestamp())
                )
                
                # Return cached response
                cached_data = existing_record.response_data
                return HttpJobSubmissionResponse(
                    job_id=cached_data["job_id"],
                    status=cached_data["status"],
                    file_ref=cached_data["file_ref"],
                    created_at=cached_data["created_at"],
                    idempotency_key_resolved=resolved_key,
                    request_id=request_id,
                    is_idempotent_replay=True
                )
            
            # Step 4: Execute use case (new request)
            use_case_request = SubmitJobRequest(
                tenant_id=request.tenant_id,
                seller_id=request.seller_id,
                channel=request.channel,
                job_type=request.job_type,
                file_ref=request.file_ref,
                rules_profile_id=request.rules_profile_id,
                idempotency_key=resolved_key  # Pass resolved key
            )
            
            use_case_response = self._submit_job_use_case.execute(use_case_request)
            
            # Step 5: Store idempotent response
            response_data = {
                "job_id": use_case_response.job_id,
                "status": use_case_response.status,
                "file_ref": use_case_response.file_ref,
                "created_at": use_case_response.created_at
            }
            
            try:
                self._idempotency_store.put(tenant_id, resolved_key, response_data)
            except IdempotencyConflictError:
                # Race condition - another request created the same response
                self._logger.warning(
                    "idempotency_race_condition_detected",
                    request_id=request_id,
                    tenant_id=request.tenant_id,
                    resolved_key_length=len(resolved_key)
                )
                # Continue - our response is still valid
            
            # Step 6: Return HTTP response
            self._logger.info(
                "job_submission_completed",
                request_id=request_id,
                tenant_id=request.tenant_id,
                job_id=use_case_response.job_id,
                status=use_case_response.status,
                resolved_key_length=len(resolved_key)
            )
            
            return HttpJobSubmissionResponse(
                job_id=use_case_response.job_id,
                status=use_case_response.status,
                file_ref=use_case_response.file_ref,
                created_at=use_case_response.created_at,
                idempotency_key_resolved=resolved_key,
                request_id=request_id,
                is_idempotent_replay=False
            )
            
        except ValueError as e:
            # Handle key resolution/validation errors
            if "Legacy idempotency key" in str(e) or "formula characters" in str(e):
                self._logger.warning(
                    "idempotency_key_rejected",
                    request_id=request_id,
                    tenant_id=request.tenant_id,
                    error=str(e),
                    compat_mode=Config.get_idemp_compat_mode().value
                )
                raise ValidationError("idempotency_key", "Invalid idempotency key format")
            
            # Re-raise other validation errors
            raise
        
        except RateLimitExceeded:
            # Re-raise rate limit errors without modification
            raise
            
        except Exception as e:
            self._logger.error(
                "job_submission_failed",
                request_id=request_id,
                tenant_id=request.tenant_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise


def get_idempotency_key_header(headers: dict[str, str]) -> str | None:
    """
    Extract idempotency key from HTTP headers.
    
    Supports multiple header names for compatibility:
    - Idempotency-Key (preferred)
    - X-Idempotency-Key
    - Idempotency-Token (legacy)
    
    Args:
        headers: HTTP headers dictionary (case-insensitive)
        
    Returns:
        Raw idempotency key if present, None otherwise
    """
    # Normalize headers to lowercase for lookup
    lower_headers = {k.lower(): v for k, v in headers.items()}
    
    # Try preferred header first
    for header_name in ["idempotency-key", "x-idempotency-key", "idempotency-token"]:
        if header_name in lower_headers:
            value = lower_headers[header_name]
            if value and value.strip():
                return value.strip()
    
    return None


def get_request_id_header(headers: dict[str, str]) -> str | None:
    """
    Extract request ID from HTTP headers.
    
    Args:
        headers: HTTP headers dictionary (case-insensitive)
        
    Returns:
        Request ID if present, None otherwise
    """
    lower_headers = {k.lower(): v for k, v in headers.items()}
    
    for header_name in ["x-request-id", "request-id"]:
        if header_name in lower_headers:
            value = lower_headers[header_name]
            if value and value.strip():
                return value.strip()
    
    return None
