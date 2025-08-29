"""Idempotency store interface and implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
import hmac
import hashlib

from src.domain.value_objects import TenantId


@dataclass(frozen=True)
class IdempotencyRecord:
    """Record stored for idempotency tracking."""
    tenant_id: str
    key: str
    response_hash: str
    response_data: dict[str, Any]
    created_at: datetime
    expires_at: datetime
    
    def is_expired(self) -> bool:
        """Check if this record has expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    def matches_response(self, response_data: dict[str, Any]) -> bool:
        """Check if response data matches stored hash using constant-time comparison."""
        # Create hash of the current response data
        response_str = str(sorted(response_data.items()))
        current_hash = hashlib.sha256(response_str.encode('utf-8')).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(self.response_hash, current_hash)


class IdempotencyStore(ABC):
    """Abstract interface for idempotency storage."""
    
    @abstractmethod
    def get(self, tenant_id: TenantId, key: str) -> Optional[IdempotencyRecord]:
        """
        Get idempotency record for tenant and key.
        
        Args:
            tenant_id: Tenant identifier
            key: Idempotency key (already resolved/canonicalized)
            
        Returns:
            IdempotencyRecord if found and not expired, None otherwise
        """
        pass
    
    @abstractmethod
    def put(
        self, 
        tenant_id: TenantId, 
        key: str, 
        response_data: dict[str, Any],
        ttl_seconds: int = 86400  # 24 hours default
    ) -> IdempotencyRecord:
        """
        Store idempotency record.
        
        Args:
            tenant_id: Tenant identifier
            key: Idempotency key (already resolved/canonicalized)
            response_data: Response data to hash and store
            ttl_seconds: Time to live in seconds
            
        Returns:
            Created IdempotencyRecord
            
        Raises:
            IdempotencyConflictError: If key already exists with different response
        """
        pass
    
    @abstractmethod
    def delete(self, tenant_id: TenantId, key: str) -> bool:
        """
        Delete idempotency record.
        
        Args:
            tenant_id: Tenant identifier
            key: Idempotency key
            
        Returns:
            True if record was deleted, False if not found
        """
        pass


class IdempotencyConflictError(Exception):
    """Raised when idempotency key exists with different response data."""
    
    def __init__(self, tenant_id: str, key: str):
        self.tenant_id = tenant_id
        self.key = key
        super().__init__(
            f"Idempotency conflict for tenant {tenant_id}: key already exists with different response"
        )


class InMemoryIdempotencyStore(IdempotencyStore):
    """In-memory idempotency store for testing/development."""
    
    def __init__(self):
        self._records: dict[tuple[str, str], IdempotencyRecord] = {}
    
    def get(self, tenant_id: TenantId, key: str) -> Optional[IdempotencyRecord]:
        """Get record from memory store."""
        record_key = (tenant_id.value, key)
        record = self._records.get(record_key)
        
        if record and record.is_expired():
            # Clean up expired record
            del self._records[record_key]
            return None
            
        return record
    
    def put(
        self, 
        tenant_id: TenantId, 
        key: str, 
        response_data: dict[str, Any],
        ttl_seconds: int = 86400
    ) -> IdempotencyRecord:
        """Store record in memory."""
        record_key = (tenant_id.value, key)
        
        # Check for existing record
        existing = self.get(tenant_id, key)
        if existing:
            if not existing.matches_response(response_data):
                raise IdempotencyConflictError(tenant_id.value, key)
            return existing
        
        # Create response hash
        response_str = str(sorted(response_data.items()))
        response_hash = hashlib.sha256(response_str.encode('utf-8')).hexdigest()
        
        # Create new record
        now = datetime.now(timezone.utc)
        record = IdempotencyRecord(
            tenant_id=tenant_id.value,
            key=key,
            response_hash=response_hash,
            response_data=response_data,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds)
        )
        
        self._records[record_key] = record
        return record
    
    def delete(self, tenant_id: TenantId, key: str) -> bool:
        """Delete record from memory store."""
        record_key = (tenant_id.value, key)
        if record_key in self._records:
            del self._records[record_key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all records (for testing)."""
        self._records.clear()