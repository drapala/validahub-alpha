"""Domain events following CloudEvents specification."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID, uuid4

from .enums import EventType, JobStatus, JobType
from .value_objects import JobId, TenantId, ProcessingCounters


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events following CloudEvents 1.0 specification.
    
    CloudEvents attributes:
    - id: Unique event identifier
    - source: Event producer (apps/api, packages/domain, etc.)
    - specversion: CloudEvents version (1.0)
    - type: Event type (job.submitted, job.succeeded, etc.)
    - time: Event timestamp
    - subject: Resource identifier (job:uuid)
    - datacontenttype: Content type of data payload
    - trace_id: Distributed tracing correlation ID
    - tenant_id: Multi-tenant identifier
    - actor_id: User/system that triggered the event
    - schema_version: Event schema version for evolution
    - data: Event-specific payload
    """
    
    # CloudEvents standard attributes
    id: str
    source: str
    specversion: str
    type: EventType
    time: datetime
    subject: str
    datacontenttype: str
    
    # ValidaHub extensions
    trace_id: Optional[str]
    tenant_id: str
    actor_id: Optional[str]
    schema_version: str
    data: Dict[str, Any]
    
    @classmethod
    def create(
        cls,
        event_type: EventType,
        subject: str,
        tenant_id: TenantId,
        data: Dict[str, Any],
        actor_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        source: str = "packages/domain",
    ) -> 'DomainEvent':
        """Create a new domain event with CloudEvents structure."""
        return cls(
            id=str(uuid4()),
            source=source,
            specversion="1.0",
            type=event_type,
            time=datetime.utcnow(),
            subject=subject,
            datacontenttype="application/json",
            trace_id=trace_id,
            tenant_id=str(tenant_id),
            actor_id=actor_id,
            schema_version="1",
            data=data,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to CloudEvents dictionary format."""
        result = {
            "id": self.id,
            "source": self.source,
            "specversion": self.specversion,
            "type": self.type.value,
            "time": self.time.isoformat() + "Z",
            "subject": self.subject,
            "datacontenttype": self.datacontenttype,
            "tenant_id": self.tenant_id,
            "schema_version": self.schema_version,
            "data": self.data,
        }
        
        # Add optional attributes if present
        if self.trace_id:
            result["trace_id"] = self.trace_id
        if self.actor_id:
            result["actor_id"] = self.actor_id
            
        return result


@dataclass(frozen=True)
class JobSubmitted(DomainEvent):
    """Event raised when a new job is submitted to the system."""
    
    @classmethod
    def create(
        cls,
        job_id: JobId,
        tenant_id: TenantId,
        seller_id: str,
        channel: str,
        job_type: JobType,
        file_ref: str,
        rules_profile_id: str,
        idempotency_key: Optional[str] = None,
        callback_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        actor_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> 'JobSubmitted':
        """Create JobSubmitted event."""
        data = {
            "job_id": str(job_id),
            "seller_id": seller_id,
            "channel": channel,
            "type": job_type.value,
            "file_ref": file_ref,
            "rules_profile_id": rules_profile_id,
        }
        
        if idempotency_key:
            data["idempotency_key"] = idempotency_key
        if callback_url:
            data["callback_url"] = callback_url
        if metadata:
            data["metadata"] = metadata
            
        return cls(
            **DomainEvent.create(
                event_type=EventType.JOB_SUBMITTED,
                subject=f"job:{job_id}",
                tenant_id=tenant_id,
                data=data,
                actor_id=actor_id,
                trace_id=trace_id,
            ).__dict__
        )


@dataclass(frozen=True)
class JobStarted(DomainEvent):
    """Event raised when job processing begins."""
    
    @classmethod
    def create(
        cls,
        job_id: JobId,
        tenant_id: TenantId,
        actor_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> 'JobStarted':
        """Create JobStarted event."""
        data = {
            "job_id": str(job_id),
            "started_at": datetime.utcnow().isoformat() + "Z",
        }
            
        return cls(
            **DomainEvent.create(
                event_type=EventType.JOB_STARTED,
                subject=f"job:{job_id}",
                tenant_id=tenant_id,
                data=data,
                actor_id=actor_id,
                trace_id=trace_id,
            ).__dict__
        )


@dataclass(frozen=True)
class JobSucceeded(DomainEvent):
    """Event raised when job completes successfully."""
    
    @classmethod
    def create(
        cls,
        job_id: JobId,
        tenant_id: TenantId,
        counters: ProcessingCounters,
        duration_ms: int,
        output_ref: Optional[str] = None,
        actor_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> 'JobSucceeded':
        """Create JobSucceeded event."""
        data = {
            "job_id": str(job_id),
            "counters": {
                "total": counters.total,
                "processed": counters.processed,
                "errors": counters.errors,
                "warnings": counters.warnings,
            },
            "duration_ms": duration_ms,
            "completed_at": datetime.utcnow().isoformat() + "Z",
        }
        
        if output_ref:
            data["output_ref"] = output_ref
            
        return cls(
            **DomainEvent.create(
                event_type=EventType.JOB_SUCCEEDED,
                subject=f"job:{job_id}",
                tenant_id=tenant_id,
                data=data,
                actor_id=actor_id,
                trace_id=trace_id,
            ).__dict__
        )


@dataclass(frozen=True)
class JobFailed(DomainEvent):
    """Event raised when job fails with errors."""
    
    @classmethod
    def create(
        cls,
        job_id: JobId,
        tenant_id: TenantId,
        error_code: str,
        error_message: str,
        counters: Optional[ProcessingCounters] = None,
        duration_ms: Optional[int] = None,
        retry_count: int = 0,
        actor_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> 'JobFailed':
        """Create JobFailed event."""
        data = {
            "job_id": str(job_id),
            "error_code": error_code,
            "error_message": error_message,
            "retry_count": retry_count,
            "failed_at": datetime.utcnow().isoformat() + "Z",
        }
        
        if counters:
            data["counters"] = {
                "total": counters.total,
                "processed": counters.processed,
                "errors": counters.errors,
                "warnings": counters.warnings,
            }
        
        if duration_ms is not None:
            data["duration_ms"] = duration_ms
            
        return cls(
            **DomainEvent.create(
                event_type=EventType.JOB_FAILED,
                subject=f"job:{job_id}",
                tenant_id=tenant_id,
                data=data,
                actor_id=actor_id,
                trace_id=trace_id,
            ).__dict__
        )


@dataclass(frozen=True)
class JobCancelled(DomainEvent):
    """Event raised when job is cancelled by user or system."""
    
    @classmethod
    def create(
        cls,
        job_id: JobId,
        tenant_id: TenantId,
        reason: str,
        counters: Optional[ProcessingCounters] = None,
        actor_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> 'JobCancelled':
        """Create JobCancelled event."""
        data = {
            "job_id": str(job_id),
            "reason": reason,
            "cancelled_at": datetime.utcnow().isoformat() + "Z",
        }
        
        if counters:
            data["counters"] = {
                "total": counters.total,
                "processed": counters.processed,
                "errors": counters.errors,
                "warnings": counters.warnings,
            }
            
        return cls(
            **DomainEvent.create(
                event_type=EventType.JOB_CANCELLED,
                subject=f"job:{job_id}",
                tenant_id=tenant_id,
                data=data,
                actor_id=actor_id,
                trace_id=trace_id,
            ).__dict__
        )


@dataclass(frozen=True)
class JobRetried(DomainEvent):
    """Event raised when job is retried after failure."""
    
    @classmethod
    def create(
        cls,
        job_id: JobId,
        tenant_id: TenantId,
        original_job_id: JobId,
        retry_count: int,
        actor_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> 'JobRetried':
        """Create JobRetried event."""
        data = {
            "job_id": str(job_id),
            "original_job_id": str(original_job_id),
            "retry_count": retry_count,
            "retried_at": datetime.utcnow().isoformat() + "Z",
        }
            
        return cls(
            **DomainEvent.create(
                event_type=EventType.JOB_RETRIED,
                subject=f"job:{job_id}",
                tenant_id=tenant_id,
                data=data,
                actor_id=actor_id,
                trace_id=trace_id,
            ).__dict__
        )


@dataclass(frozen=True)
class JobExpired(DomainEvent):
    """Event raised when job expires before processing."""
    
    @classmethod
    def create(
        cls,
        job_id: JobId,
        tenant_id: TenantId,
        ttl_seconds: int,
        actor_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> 'JobExpired':
        """Create JobExpired event."""
        data = {
            "job_id": str(job_id),
            "ttl_seconds": ttl_seconds,
            "expired_at": datetime.utcnow().isoformat() + "Z",
        }
            
        return cls(
            **DomainEvent.create(
                event_type=EventType.JOB_EXPIRED,
                subject=f"job:{job_id}",
                tenant_id=tenant_id,
                data=data,
                actor_id=actor_id,
                trace_id=trace_id,
            ).__dict__
        )