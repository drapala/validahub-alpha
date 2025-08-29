"""Application ports (interfaces) for ValidaHub.

This module defines the contracts between the application layer and external systems.
All external dependencies must be implemented through these interfaces.
"""

from abc import ABC, abstractmethod
from typing import Optional

from src.domain.job import Job
from src.domain.value_objects import TenantId, IdempotencyKey


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
