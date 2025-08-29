"""Application ports (interfaces) for ValidaHub.

This module defines the contracts between the application layer and external systems.
All external dependencies must be implemented through these interfaces following
the Dependency Inversion Principle.

Ports are organized by:
- Persistence: Data storage and retrieval
- Communication: Events, notifications, and messaging
- External Services: Object storage, authentication, etc.
- Observability: Logging, metrics, and tracing
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from packages.domain.enums import JobStatus, JobType
from packages.domain.events import DomainEvent
from packages.domain.job import Job
from packages.domain.value_objects import IdempotencyKey, JobId, TenantId


# Persistence Ports
class JobRepository(ABC):
    """Port for job persistence operations with multi-tenant isolation."""
    
    @abstractmethod
    def save(self, job: Job) -> Job:
        """
        Save job to storage with optimistic concurrency control.
        
        Args:
            job: Job instance to save
            
        Returns:
            Saved job instance (may include generated fields)
            
        Raises:
            ConcurrencyError: If job was modified by another process
            TenantIsolationError: If tenant isolation is violated
        """
        pass
    
    @abstractmethod
    def find_by_id(self, tenant_id: TenantId, job_id: JobId) -> Job | None:
        """
        Find job by ID within tenant context.
        
        Args:
            tenant_id: Tenant identifier for isolation
            job_id: Job identifier
            
        Returns:
            Job if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_by_idempotency_key(
        self, 
        tenant_id: TenantId, 
        key: IdempotencyKey
    ) -> Job | None:
        """
        Find job by tenant and idempotency key.
        
        Args:
            tenant_id: Tenant identifier
            key: Idempotency key
            
        Returns:
            Job if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_by_tenant(
        self,
        tenant_id: TenantId,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Job]:
        """
        Find jobs by tenant with optional filtering.
        
        Args:
            tenant_id: Tenant identifier
            status: Optional status filter
            job_type: Optional job type filter
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of jobs matching criteria
        """
        pass
    
    @abstractmethod
    def count_by_tenant(
        self,
        tenant_id: TenantId,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
    ) -> int:
        """
        Count jobs by tenant with optional filtering.
        
        Args:
            tenant_id: Tenant identifier
            status: Optional status filter
            job_type: Optional job type filter
            
        Returns:
            Total number of jobs matching criteria
        """
        pass


class EventOutbox(ABC):
    """Port for reliable event publishing using outbox pattern."""
    
    @abstractmethod
    def store_events(self, events: list[DomainEvent], correlation_id: str | None = None) -> None:
        """
        Store events in outbox for later publishing.
        
        Args:
            events: List of domain events to store
            correlation_id: Optional correlation ID for tracing
        """
        pass
    
    @abstractmethod
    def get_pending_events(self, limit: int = 100) -> list[DomainEvent]:
        """
        Get pending events for publishing.
        
        Args:
            limit: Maximum number of events to retrieve
            
        Returns:
            List of pending domain events
        """
        pass
    
    @abstractmethod
    def mark_published(self, event_ids: list[str]) -> None:
        """
        Mark events as successfully published.
        
        Args:
            event_ids: List of event IDs to mark as published
        """
        pass


# Communication Ports
class EventBus(ABC):
    """Port for domain event publishing to message queues."""
    
    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        """
        Publish domain event to event bus.
        
        Args:
            event: Domain event to publish
        """
        pass
    
    @abstractmethod
    def publish_batch(self, events: list[DomainEvent]) -> None:
        """
        Publish multiple domain events as a batch.
        
        Args:
            events: List of domain events to publish
        """
        pass


class NotificationService(ABC):
    """Port for sending notifications (webhooks, emails, etc.)."""
    
    @abstractmethod
    def send_webhook(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """
        Send webhook notification.
        
        Args:
            url: Webhook URL
            payload: JSON payload to send
            headers: Optional HTTP headers
            tenant_id: Optional tenant ID for rate limiting
        """
        pass


class JobEventStream(ABC):
    """Port for real-time job event streaming (SSE)."""
    
    @abstractmethod
    async def subscribe(self, tenant_id: TenantId) -> AsyncIterator[DomainEvent]:
        """
        Subscribe to job events for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Yields:
            Domain events for the tenant
        """
        pass


# External Services Ports
class ObjectStorage(ABC):
    """Port for object storage operations (S3-compatible)."""
    
    @abstractmethod
    def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        operation: str = "get",
        expiration: int = 900,  # 15 minutes
    ) -> str:
        """
        Generate presigned URL for object access.
        
        Args:
            bucket: Bucket name
            key: Object key
            operation: Operation type ('get' or 'put')
            expiration: URL expiration time in seconds
            
        Returns:
            Presigned URL
        """
        pass
    
    @abstractmethod
    def object_exists(self, bucket: str, key: str) -> bool:
        """
        Check if object exists in storage.
        
        Args:
            bucket: Bucket name
            key: Object key
            
        Returns:
            True if object exists, False otherwise
        """
        pass
    
    @abstractmethod
    def get_object_metadata(self, bucket: str, key: str) -> dict[str, Any] | None:
        """
        Get object metadata.
        
        Args:
            bucket: Bucket name
            key: Object key
            
        Returns:
            Object metadata dict or None if not found
        """
        pass


class RateLimiter(ABC):
    """Port for rate limiting operations using token bucket algorithm."""
    
    @abstractmethod
    def check_and_consume(
        self,
        tenant_id: TenantId,
        resource: str,
        tokens: int = 1,
    ) -> bool:
        """
        Check rate limit and consume tokens if available.
        
        Args:
            tenant_id: Tenant identifier
            resource: Resource being rate limited (e.g., "job_submission")
            tokens: Number of tokens to consume
            
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        pass
    
    @abstractmethod
    def get_limit_info(self, tenant_id: TenantId, resource: str) -> dict[str, Any]:
        """
        Get current rate limit information.
        
        Args:
            tenant_id: Tenant identifier
            resource: Resource being rate limited
            
        Returns:
            Dict with 'remaining', 'reset_time', 'limit' keys
        """
        pass


class AuthenticationService(ABC):
    """Port for JWT authentication and authorization."""
    
    @abstractmethod
    def validate_token(self, token: str) -> dict[str, Any]:
        """
        Validate JWT token and extract claims.
        
        Args:
            token: JWT token string
            
        Returns:
            Token claims dict
            
        Raises:
            SecurityViolationError: If token is invalid
        """
        pass
    
    @abstractmethod
    def check_permissions(
        self,
        tenant_id: TenantId,
        user_id: str,
        resource: str,
        action: str,
    ) -> bool:
        """
        Check if user has permission for action on resource.
        
        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            resource: Resource being accessed
            action: Action being performed
            
        Returns:
            True if permission granted, False otherwise
        """
        pass


# Observability Ports
class AuditLogger(ABC):
    """Port for immutable audit logging."""
    
    @abstractmethod
    def log_event(
        self,
        event_type: str,
        tenant_id: str,
        user_id: str | None,
        resource_type: str,
        resource_id: str,
        action: str,
        result: str,
        request_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Log audit event with immutable record.
        
        Args:
            event_type: Type of audit event
            tenant_id: Tenant identifier
            user_id: User identifier (if applicable)
            resource_type: Type of resource being accessed
            resource_id: Resource identifier
            action: Action being performed
            result: Action result (success/failure)
            request_id: Request correlation ID
            metadata: Optional additional metadata
        """
        pass


class MetricsCollector(ABC):
    """Port for application metrics collection."""
    
    @abstractmethod
    def increment_counter(
        self,
        name: str,
        tags: dict[str, str] | None = None,
        value: int = 1,
    ) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            tags: Optional metric tags
            value: Value to increment by
        """
        pass
    
    @abstractmethod
    def record_histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """
        Record a histogram metric.
        
        Args:
            name: Metric name
            value: Metric value
            tags: Optional metric tags
        """
        pass
    
    @abstractmethod
    def set_gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """
        Set a gauge metric.
        
        Args:
            name: Metric name
            value: Metric value
            tags: Optional metric tags
        """
        pass


class TracingContext(ABC):
    """Port for distributed tracing context management."""
    
    @abstractmethod
    def create_span(
        self,
        operation_name: str,
        parent_context: str | None = None,
    ) -> str:
        """
        Create a new tracing span.
        
        Args:
            operation_name: Name of the operation
            parent_context: Optional parent span context
            
        Returns:
            Span context ID
        """
        pass
    
    @abstractmethod
    def finish_span(
        self,
        span_context: str,
        tags: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        """
        Finish a tracing span.
        
        Args:
            span_context: Span context ID
            tags: Optional span tags
            error: Optional error that occurred
        """
        pass