"""
Security and audit logging utilities.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog
from structlog.stdlib import BoundLogger

from .context import get_correlation_id, get_request_id, get_tenant_id


class SecurityEventType(Enum):
    """Types of security events."""
    
    # Authentication & Authorization
    AUTH_FAILED = "auth_failed"
    AUTH_SUCCESS = "auth_success"
    PERMISSION_DENIED = "permission_denied"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_INVALID = "token_invalid"
    
    # Input Validation
    INJECTION_ATTEMPT = "injection_attempt"
    CSV_INJECTION = "csv_injection"
    SQL_INJECTION = "sql_injection"
    PATH_TRAVERSAL = "path_traversal"
    XSS_ATTEMPT = "xss_attempt"
    
    # Rate Limiting
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    BRUTE_FORCE_DETECTED = "brute_force_detected"
    
    # Data Access
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_EXPORT = "data_export"
    BULK_DOWNLOAD = "bulk_download"
    
    # File Security
    DANGEROUS_FILE = "dangerous_file"
    FILE_SIZE_EXCEEDED = "file_size_exceeded"
    INVALID_FILE_TYPE = "invalid_file_type"
    
    # System Security
    CONFIG_CHANGE = "config_change"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


class AuditEventType(Enum):
    """Types of audit events."""
    
    # CRUD Operations
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    
    # Job Lifecycle
    JOB_SUBMITTED = "job_submitted"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_CANCELLED = "job_cancelled"
    JOB_RETRIED = "job_retried"
    
    # Data Operations
    DATA_IMPORTED = "data_imported"
    DATA_EXPORTED = "data_exported"
    DATA_VALIDATED = "data_validated"
    DATA_CORRECTED = "data_corrected"
    
    # User Actions
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTERED = "user_registered"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    
    # System Events
    CONFIG_UPDATED = "config_updated"
    SYSTEM_STARTED = "system_started"
    SYSTEM_STOPPED = "system_stopped"


class SecurityLogger:
    """
    Logger for security events with automatic context enrichment.
    """
    
    def __init__(self, component: str):
        """
        Initialize security logger.
        
        Args:
            component: Component name (e.g., "domain.value_objects")
        """
        self.logger: BoundLogger = structlog.get_logger(f"security.{component}")
        self.component = component
    
    def log_security_event(
        self,
        event_type: SecurityEventType,
        message: str,
        severity: str = "WARNING",
        **context: Any,
    ) -> None:
        """
        Log a security event with full context.
        
        Args:
            event_type: Type of security event
            message: Human-readable message
            severity: Log level (INFO, WARNING, ERROR, CRITICAL)
            **context: Additional context data
        """
        event_data = {
            "event_type": event_type.value,
            "component": self.component,
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": get_request_id(),
            "correlation_id": get_correlation_id(),
            "tenant_id": get_tenant_id(),
            **context,
        }
        
        # Choose log method based on severity
        log_method = getattr(self.logger, severity.lower(), self.logger.warning)
        log_method(message, **event_data)
    
    def injection_attempt(
        self,
        injection_type: str,
        input_value: str | None = None,
        field_name: str | None = None,
        **context: Any,
    ) -> None:
        """Log an injection attempt."""
        self.log_security_event(
            SecurityEventType.INJECTION_ATTEMPT,
            f"{injection_type} injection attempt detected",
            severity="ERROR",
            injection_type=injection_type,
            field_name=field_name,
            input_length=len(input_value) if input_value else 0,
            **context,
        )
    
    def rate_limit_exceeded(
        self,
        resource: str,
        limit: int,
        window: str,
        **context: Any,
    ) -> None:
        """Log rate limit violation."""
        self.log_security_event(
            SecurityEventType.RATE_LIMIT_EXCEEDED,
            f"Rate limit exceeded for {resource}",
            severity="WARNING",
            resource=resource,
            limit=limit,
            window=window,
            **context,
        )
    
    def unauthorized_access(
        self,
        resource: str,
        action: str,
        reason: str,
        **context: Any,
    ) -> None:
        """Log unauthorized access attempt."""
        self.log_security_event(
            SecurityEventType.UNAUTHORIZED_ACCESS,
            f"Unauthorized {action} on {resource}",
            severity="ERROR",
            resource=resource,
            action=action,
            reason=reason,
            **context,
        )


class AuditLogger:
    """
    Logger for audit trail with immutable event records.
    """
    
    def __init__(self, component: str):
        """
        Initialize audit logger.
        
        Args:
            component: Component name
        """
        self.logger: BoundLogger = structlog.get_logger(f"audit.{component}")
        self.component = component
    
    def log_audit_event(
        self,
        event_type: AuditEventType,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        **context: Any,
    ) -> None:
        """
        Log an audit event with full context.
        
        Args:
            event_type: Type of audit event
            entity_type: Type of entity affected
            entity_id: ID of entity affected
            action: Action performed
            actor_id: ID of actor performing action
            before: State before change
            after: State after change
            **context: Additional context
        """
        event_data = {
            "event_type": event_type.value,
            "component": self.component,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "actor_id": actor_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": get_request_id(),
            "correlation_id": get_correlation_id(),
            "tenant_id": get_tenant_id(),
            **context,
        }
        
        # Add state changes if provided
        if before is not None:
            event_data["before"] = before
        if after is not None:
            event_data["after"] = after
        
        # Audit events are always INFO level
        self.logger.info(f"Audit: {action} on {entity_type}", **event_data)
    
    def job_lifecycle(
        self,
        event_type: AuditEventType,
        job_id: str,
        status: str,
        actor_id: str | None = None,
        **context: Any,
    ) -> None:
        """Log job lifecycle event."""
        self.log_audit_event(
            event_type=event_type,
            entity_type="job",
            entity_id=job_id,
            action=event_type.value,
            actor_id=actor_id,
            status=status,
            **context,
        )
    
    def data_operation(
        self,
        operation: str,
        entity_type: str,
        count: int,
        actor_id: str | None = None,
        **context: Any,
    ) -> None:
        """Log data operation event."""
        action = f"{operation} {count} {entity_type} records"
        self.log_audit_event(
            event_type=AuditEventType.DATA_IMPORTED if operation == "import" else AuditEventType.DATA_EXPORTED,
            entity_type=entity_type,
            entity_id=f"{entity_type}_batch",
            action=action,
            actor_id=actor_id,
            count=count,
            **context,
        )