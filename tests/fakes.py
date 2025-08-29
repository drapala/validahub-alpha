"""Fake implementations for testing."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class FakeJobRepository:
    """Fake job repository for testing."""
    
    _jobs: Dict[str, Any] = field(default_factory=dict)
    _idempotency_index: Dict[tuple, str] = field(default_factory=dict)
    
    def get_by_id(self, job_id: str) -> Optional[Any]:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    def get_by_idempotency_key(self, tenant_id: str, idempotency_key: str) -> Optional[Any]:
        """Get job by tenant and idempotency key."""
        job_id = self._idempotency_index.get((tenant_id, idempotency_key))
        if job_id:
            return self._jobs.get(job_id)
        return None
    
    def save(self, job: Any) -> None:
        """Save job to fake storage."""
        self._jobs[job.id] = job
        if hasattr(job, 'idempotency_key') and job.idempotency_key:
            self._idempotency_index[(job.tenant_id, job.idempotency_key)] = job.id


@dataclass
class FakeEventBus:
    """Fake event bus for testing."""
    
    published_events: List[Any] = field(default_factory=list)
    
    def publish(self, event: Any) -> None:
        """Publish event to fake bus."""
        self.published_events.append(event)
    
    def clear(self) -> None:
        """Clear published events."""
        self.published_events.clear()
    
    def get_events_by_type(self, event_type: str) -> List[Any]:
        """Get events by type."""
        return [
            event for event in self.published_events 
            if hasattr(event, 'type') and event.type == event_type
        ]


@dataclass
class FakeRateLimiter:
    """Fake rate limiter for testing."""
    
    _limits: Dict[str, int] = field(default_factory=dict)
    _exceeded: bool = False
    
    def check_limit(self, tenant_id: str, limit: int = 10) -> bool:
        """Check if tenant has exceeded rate limit."""
        if self._exceeded:
            return False
        
        current = self._limits.get(tenant_id, 0)
        self._limits[tenant_id] = current + 1
        return current < limit
    
    def set_exceeded(self, exceeded: bool = True) -> None:
        """Set rate limit exceeded for testing."""
        self._exceeded = exceeded
    
    def reset(self) -> None:
        """Reset rate limiter."""
        self._limits.clear()
        self._exceeded = False


@dataclass
class FakeObjectStorage:
    """Fake object storage for testing."""
    
    _files: Dict[str, bytes] = field(default_factory=dict)
    
    def generate_presigned_url(self, file_ref: str, expires_in: int = 3600) -> str:
        """Generate fake presigned URL."""
        return f"https://fake-storage.com/presigned/{file_ref}?expires={expires_in}"
    
    def put_object(self, file_ref: str, content: bytes) -> None:
        """Store fake object."""
        self._files[file_ref] = content
    
    def get_object(self, file_ref: str) -> Optional[bytes]:
        """Get fake object."""
        return self._files.get(file_ref)