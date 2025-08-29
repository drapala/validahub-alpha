"""Application ports (interfaces) for ValidaHub.

This module defines the contracts between the application layer and external systems.
All external dependencies must be implemented through these interfaces.
"""

from abc import ABC, abstractmethod
from typing import Optional, List

from src.domain.job import Job
from src.domain.value_objects import TenantId, IdempotencyKey
from src.application.ports.logging import LoggingPort


class JobRepository(ABC):
    """Port for job persistence operations."""
    
    @abstractmethod
    def save(self, job: Job) -> Job:
        """
        Save job to storage.
        
        Args:
            job: Job instance to save
            
        Returns:
            Saved job instance (may include generated fields)
        """
        pass
    
    @abstractmethod
    def find_by_idempotency_key(
        self, 
        tenant_id: TenantId, 
        key: IdempotencyKey
    ) -> Optional[Job]:
        """
        Find job by tenant and idempotency key.
        
        Args:
            tenant_id: Tenant identifier
            key: Idempotency key
            
        Returns:
            Job if found, None otherwise
        """
        pass


class RateLimiter(ABC):
    """Port for rate limiting operations."""
    
    @abstractmethod
    def check_and_consume(self, tenant_id: TenantId, resource: str) -> bool:
        """
        Check rate limit and consume token if available.
        
        Args:
            tenant_id: Tenant identifier
            resource: Resource being rate limited (e.g., "job_submission")
            
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        pass


class EventBus(ABC):
    """Port for domain event publishing."""
    
    @abstractmethod
    def publish(self, event: 'DomainEvent') -> None:
        """
        Publish domain event.
        
        Args:
            event: Domain event to publish
        """
        pass


class LogPublisher(ABC):
    """Port for publishing domain events as structured logs and audit events."""
    
    @abstractmethod
    def publish_events(self, events: List['DomainEvent']) -> None:
        """
        Publish a list of domain events as structured logs.
        
        This port is responsible for:
        - Converting domain events to structured logs
        - Sending audit events to the audit system
        - Ensuring proper log levels and formatting
        - Handling correlation IDs and tenant context
        
        Args:
            events: List of domain events to publish as logs
        """
        pass


class SecretsManager(ABC):
    """Port for secure secrets and configuration management."""
    
    @abstractmethod
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a configuration value by key.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        pass
    
    @abstractmethod
    def get_database_url(self) -> str:
        """Get database connection URL."""
        pass
    
    @abstractmethod
    def get_redis_url(self) -> str:
        """Get Redis connection URL."""
        pass
    
    @abstractmethod
    def get_jwt_keys(self) -> tuple[str, str]:
        """
        Get JWT public and private keys.
        
        Returns:
            Tuple of (public_key, private_key)
        """
        pass
    
    @abstractmethod
    def get_s3_config(self) -> dict:
        """Get S3/MinIO configuration."""
        pass
    
    @abstractmethod
    def get_opentelemetry_config(self) -> dict:
        """Get OpenTelemetry configuration."""
        pass
    
    @abstractmethod
    def refresh_cache(self) -> None:
        """Refresh cached configuration values."""
        pass
