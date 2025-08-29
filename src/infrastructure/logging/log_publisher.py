"""Concrete implementation of LogPublisher for structured logging and audit events."""

from typing import List, Optional, Any, Dict

from src.application.ports import LogPublisher
from src.domain.events import (
    DomainEvent,
    JobCreatedEvent,
    JobStateTransitionAttemptedEvent,
    JobStateTransitionSucceededEvent,
    JobStateTransitionFailedEvent,
    JobAuditEvent,
    ValueObjectValidationEvent,
    SecurityThreatDetectedEvent
)

# Import logging infrastructure
from shared.logging import get_logger
from shared.logging.security import AuditLogger, AuditEventType, SecurityLogger, SecurityEventType


class ConcreteLogPublisher(LogPublisher):
    """
    Concrete implementation of LogPublisher that converts domain events 
    to structured logs and audit events using the existing logging infrastructure.
    """
    
    def __init__(self) -> None:
        """Initialize the log publisher with structured and audit loggers."""
        self._logger = get_logger("domain.events")
        self._audit = AuditLogger("domain.job")
        self._security = SecurityLogger("domain.security")
        
        # Mapping from domain event audit types to AuditEventType enum
        self._audit_type_mapping = {
            "JOB_SUBMITTED": AuditEventType.JOB_SUBMITTED,
            "JOB_STARTED": AuditEventType.JOB_STARTED,
            "JOB_COMPLETED": AuditEventType.JOB_COMPLETED,
            "JOB_FAILED": AuditEventType.JOB_FAILED,
            "JOB_RETRIED": AuditEventType.JOB_RETRIED,
        }
    
    def publish_events(self, events: List[DomainEvent]) -> None:
        """
        Publish domain events as structured logs and audit events.
        
        Args:
            events: List of domain events to publish
        """
        for event in events:
            try:
                self._publish_single_event(event)
            except Exception as e:
                # Log error but don't fail - logging failures should not break domain operations
                self._logger.error(
                    "failed_to_publish_domain_event",
                    event_type=type(event).__name__,
                    event_id=getattr(event, 'event_id', 'unknown'),
                    error=str(e),
                    error_type=e.__class__.__name__
                )
    
    def _publish_single_event(self, event: DomainEvent) -> None:
        """
        Publish a single domain event.
        
        Args:
            event: Domain event to publish
        """
        if isinstance(event, JobCreatedEvent):
            self._publish_job_created_event(event)
        elif isinstance(event, JobStateTransitionAttemptedEvent):
            self._publish_transition_attempted_event(event)
        elif isinstance(event, JobStateTransitionSucceededEvent):
            self._publish_transition_succeeded_event(event)
        elif isinstance(event, JobStateTransitionFailedEvent):
            self._publish_transition_failed_event(event)
        elif isinstance(event, JobAuditEvent):
            self._publish_job_audit_event(event)
        elif isinstance(event, ValueObjectValidationEvent):
            self._publish_value_object_validation_event(event)
        elif isinstance(event, SecurityThreatDetectedEvent):
            self._publish_security_threat_event(event)
        else:
            # Unknown event type - log as generic domain event
            self._publish_generic_domain_event(event)
    
    def _publish_job_created_event(self, event: JobCreatedEvent) -> None:
        """Publish job created event as structured log."""
        self._logger.info(
            "job_created",
            job_id=event.aggregate_id,
            tenant_id=event.tenant_id,
            status=event.status,
            correlation_id=event.correlation_id,
            creation_duration_ms=event.creation_duration_ms,
            event_id=event.event_id,
            occurred_at=event.occurred_at.isoformat()
        )
    
    def _publish_transition_attempted_event(self, event: JobStateTransitionAttemptedEvent) -> None:
        """Publish state transition attempted event as debug log."""
        self._logger.debug(
            "job_state_transition_attempted",
            job_id=event.aggregate_id,
            tenant_id=event.tenant_id,
            from_status=event.from_status,
            to_status=event.to_status,
            correlation_id=event.correlation_id,
            event_id=event.event_id,
            occurred_at=event.occurred_at.isoformat()
        )
    
    def _publish_transition_succeeded_event(self, event: JobStateTransitionSucceededEvent) -> None:
        """Publish successful state transition event as structured log."""
        # Determine log level based on target status
        log_method = self._logger.info
        log_event = "job_state_transition_successful"
        
        # Special handling for failure transitions
        if event.to_status == "failed":
            log_method = self._logger.error
            log_event = "job_state_transition_to_failed"
        elif event.to_status == "retrying":
            log_method = self._logger.info
            log_event = "job_state_transition_to_retry"
        
        # Build log data
        log_data = {
            "job_id": event.aggregate_id,
            "tenant_id": event.tenant_id,
            "from_status": event.from_status,
            "to_status": event.to_status,
            "transition_duration_ms": event.transition_duration_ms,
            "correlation_id": event.correlation_id,
            "event_id": event.event_id,
            "occurred_at": event.occurred_at.isoformat()
        }
        
        # Add optional fields if present
        if event.total_job_duration_ms is not None:
            log_data["total_job_duration_ms"] = event.total_job_duration_ms
        
        if event.error_message is not None:
            log_data["error_message"] = event.error_message
        
        if event.retry_attempt is not None:
            log_data["retry_attempt"] = event.retry_attempt
        
        log_method(log_event, **log_data)
    
    def _publish_transition_failed_event(self, event: JobStateTransitionFailedEvent) -> None:
        """Publish failed state transition event as warning log."""
        self._logger.warning(
            "invalid_state_transition_attempted",
            job_id=event.aggregate_id,
            tenant_id=event.tenant_id,
            current_status=event.from_status,
            attempted_status=event.attempted_status,
            reason=event.reason,
            correlation_id=event.correlation_id,
            event_id=event.event_id,
            occurred_at=event.occurred_at.isoformat()
        )
    
    def _publish_job_audit_event(self, event: JobAuditEvent) -> None:
        """Publish job audit event to audit system."""
        # Map event type to audit enum
        audit_event_type = self._audit_type_mapping.get(event.event_type)
        if audit_event_type is None:
            self._logger.warning(
                "unknown_audit_event_type",
                event_type=event.event_type,
                job_id=event.aggregate_id,
                event_id=event.event_id
            )
            return
        
        # Send to audit system
        self._audit.job_lifecycle(
            event_type=audit_event_type,
            job_id=event.aggregate_id,
            status=event.status,
            actor_id=event.actor_id,
            tenant_id=event.tenant_id,
            from_status=event.from_status
        )
        
        # Also log audit event occurrence
        self._logger.debug(
            "audit_event_published",
            event_type=event.event_type,
            job_id=event.aggregate_id,
            tenant_id=event.tenant_id,
            status=event.status,
            correlation_id=event.correlation_id,
            event_id=event.event_id
        )
    
    def _publish_generic_domain_event(self, event: DomainEvent) -> None:
        """Publish generic domain event for unknown event types."""
        self._logger.info(
            "domain_event_published",
            event_type=type(event).__name__,
            event_id=event.event_id,
            aggregate_id=event.aggregate_id,
            tenant_id=event.tenant_id,
            correlation_id=event.correlation_id,
            occurred_at=event.occurred_at.isoformat()
        )
    
    def _publish_value_object_validation_event(self, event: ValueObjectValidationEvent) -> None:
        """Publish value object validation events to appropriate log levels."""
        # Build base log data
        log_data = {
            "event_id": event.event_id,
            "tenant_id": event.tenant_id,
            "correlation_id": event.correlation_id,
            "occurred_at": event.occurred_at.isoformat(),
            "value_object_type": event.value_object_type,
            "validation_result": event.validation_result
        }
        
        # Add metadata if present
        if event.metadata:
            log_data.update(event.metadata)
        
        if event.validation_result == "failed":
            # Log validation failures as warnings with error details
            log_data.update({
                "error_type": event.error_type,
                "error_reason": event.error_reason
            })
            self._logger.warning(
                f"{event.value_object_type.lower()}_validation_failed",
                **log_data
            )
        else:
            # Log successful validations as debug events
            self._logger.debug(
                f"{event.value_object_type.lower()}_created",
                **log_data
            )
    
    def _publish_security_threat_event(self, event: SecurityThreatDetectedEvent) -> None:
        """Publish security threat events using the SecurityLogger."""
        # Map threat types to security event types
        if event.threat_type == "csv_formula":
            self._security.injection_attempt(
                injection_type="csv_formula",
                field_name=event.field_name,
                tenant_id=event.tenant_id,
                correlation_id=event.correlation_id,
                event_id=event.event_id,
                **(event.details or {})
            )
        elif event.threat_type == "unicode_control":
            self._security.injection_attempt(
                injection_type="unicode_control",
                field_name=event.field_name,
                tenant_id=event.tenant_id,
                correlation_id=event.correlation_id,
                event_id=event.event_id,
                **(event.details or {})
            )
        elif event.threat_type == "path_traversal":
            self._security.injection_attempt(
                injection_type="path_traversal",
                field_name=event.field_name,
                tenant_id=event.tenant_id,
                correlation_id=event.correlation_id,
                event_id=event.event_id,
                **(event.details or {})
            )
        elif event.threat_type == "dangerous_file":
            self._security.log_security_event(
                SecurityEventType.DANGEROUS_FILE,
                "Dangerous file extension blocked",
                severity=event.severity,
                field_name=event.field_name,
                tenant_id=event.tenant_id,
                correlation_id=event.correlation_id,
                event_id=event.event_id,
                **(event.details or {})
            )
        else:
            # Generic security threat logging
            self._logger.error(
                "security_threat_detected",
                threat_type=event.threat_type,
                field_name=event.field_name,
                severity=event.severity,
                tenant_id=event.tenant_id,
                correlation_id=event.correlation_id,
                event_id=event.event_id,
                occurred_at=event.occurred_at.isoformat(),
                details=event.details
            )