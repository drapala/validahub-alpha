"""Fake implementations for testing."""

from dataclasses import dataclass, field
from typing import Any

from src.application.ports import EventBus, JobRepository, RateLimiter
from src.domain.value_objects import IdempotencyKey, TenantId


@dataclass
class FakeJobRepository(JobRepository):
    """Fake job repository for testing."""

    _jobs: dict[str, Any] = field(default_factory=dict)
    _idempotency_index: dict[tuple, str] = field(default_factory=dict)

    def get_by_id(self, job_id: str) -> Any | None:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def get_by_idempotency_key(self, tenant_id: str, idempotency_key: str) -> Any | None:
        """Get job by tenant and idempotency key."""
        job_id = self._idempotency_index.get((tenant_id, idempotency_key))
        if job_id:
            return self._jobs.get(job_id)
        return None

    def save(self, job: Any) -> Any:
        """Save job to fake storage."""
        self._jobs[job.id] = job
        if hasattr(job, "idempotency_key") and job.idempotency_key:
            self._idempotency_index[(job.tenant_id, job.idempotency_key)] = job.id
        return job

    def find_by_idempotency_key(self, tenant_id: TenantId, key: IdempotencyKey) -> Any | None:
        """Find job by tenant and idempotency key (port interface)."""
        return self.get_by_idempotency_key(tenant_id.value, key.value)


@dataclass
class FakeEventBus(EventBus):
    """Fake event bus for testing."""

    published_events: list[Any] = field(default_factory=list)

    def publish(self, event: Any) -> None:
        """Publish event to fake bus."""
        self.published_events.append(event)

    def clear(self) -> None:
        """Clear published events."""
        self.published_events.clear()

    def get_events_by_type(self, event_type: str) -> list[Any]:
        """Get events by type."""
        return [
            event
            for event in self.published_events
            if hasattr(event, "type") and event.type == event_type
        ]


@dataclass
class FakeRateLimiter(RateLimiter):
    """Fake rate limiter for testing."""

    _limits: dict[str, int] = field(default_factory=dict)
    _exceeded: bool = False

    def check_limit(self, tenant_id: str, limit: int = 10) -> bool:
        """Check if tenant has exceeded rate limit."""
        if self._exceeded:
            return False

        current = self._limits.get(tenant_id, 0)
        self._limits[tenant_id] = current + 1
        return current < limit

    def check_and_consume(self, tenant_id: TenantId, resource: str) -> bool:
        """Check rate limit and consume token (port interface)."""
        return self.check_limit(tenant_id.value)

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

    _files: dict[str, bytes] = field(default_factory=dict)

    def generate_presigned_url(self, file_ref: str, expires_in: int = 3600) -> str:
        """Generate fake presigned URL."""
        return f"https://fake-storage.com/presigned/{file_ref}?expires={expires_in}"

    def put_object(self, file_ref: str, content: bytes) -> None:
        """Store fake object."""
        self._files[file_ref] = content

    def get_object(self, file_ref: str) -> bytes | None:
        """Get fake object."""
        return self._files.get(file_ref)
