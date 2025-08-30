"""Unit tests for idempotency store."""

from datetime import UTC, datetime, timedelta

import pytest
from src.application.idempotency.store import (
    IdempotencyConflictError,
    IdempotencyRecord,
    InMemoryIdempotencyStore,
)
from src.domain.value_objects import TenantId


class TestIdempotencyRecord:
    """Test cases for IdempotencyRecord."""

    def test_record_creation(self):
        """Test creating an idempotency record."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=24)

        record = IdempotencyRecord(
            tenant_id="t_test123",
            key="test-key-1234567890",
            response_hash="hash123",
            response_data={"job_id": "job_123", "status": "queued"},
            created_at=now,
            expires_at=expires,
        )

        assert record.tenant_id == "t_test123"
        assert record.key == "test-key-1234567890"
        assert not record.is_expired()

    def test_record_expired(self):
        """Test record expiration check."""
        now = datetime.now(UTC)
        past = now - timedelta(hours=1)

        record = IdempotencyRecord(
            tenant_id="t_test123",
            key="test-key-1234567890",
            response_hash="hash123",
            response_data={"job_id": "job_123"},
            created_at=past - timedelta(hours=24),
            expires_at=past,
        )

        assert record.is_expired()

    def test_record_matches_response(self):
        """Test response matching with constant-time comparison."""
        response_data = {"job_id": "job_123", "status": "queued", "file_ref": "file.csv"}

        # Create record with this response
        record = IdempotencyRecord(
            tenant_id="t_test123",
            key="test-key-1234567890",
            response_hash="dummy",  # Will be computed in matches_response
            response_data=response_data,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )

        # Should match same data
        assert record.matches_response(response_data)

        # Should not match different data
        different_data = {"job_id": "job_456", "status": "queued", "file_ref": "file.csv"}
        assert not record.matches_response(different_data)

        # Should not match data with different order (but same content)
        # Note: Our implementation sorts keys, so order shouldn't matter
        reordered_data = {"status": "queued", "job_id": "job_123", "file_ref": "file.csv"}
        assert record.matches_response(reordered_data)


class TestInMemoryIdempotencyStore:
    """Test cases for InMemoryIdempotencyStore."""

    def setup_method(self):
        """Set up test fixtures."""
        self.store = InMemoryIdempotencyStore()
        self.tenant_id = TenantId("t_test123")
        self.key = "test-key-1234567890"
        self.response_data = {
            "job_id": "job_123",
            "status": "queued",
            "file_ref": "file.csv",
            "created_at": "2023-12-01T10:00:00Z",
        }

    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        result = self.store.get(self.tenant_id, "nonexistent-key")
        assert result is None

    def test_put_and_get_key(self):
        """Test storing and retrieving a key."""
        # Store the record
        record = self.store.put(self.tenant_id, self.key, self.response_data)

        assert record.tenant_id == self.tenant_id.value
        assert record.key == self.key
        assert record.response_data == self.response_data
        assert not record.is_expired()

        # Retrieve the record
        retrieved = self.store.get(self.tenant_id, self.key)

        assert retrieved is not None
        assert retrieved.tenant_id == record.tenant_id
        assert retrieved.key == record.key
        assert retrieved.response_data == record.response_data

    def test_put_duplicate_same_response(self):
        """Test storing duplicate key with same response."""
        # Store first record
        record1 = self.store.put(self.tenant_id, self.key, self.response_data)

        # Store duplicate with same response - should return existing
        record2 = self.store.put(self.tenant_id, self.key, self.response_data)

        assert record1.tenant_id == record2.tenant_id
        assert record1.key == record2.key
        assert record1.created_at == record2.created_at  # Same record returned

    def test_put_duplicate_different_response(self):
        """Test storing duplicate key with different response."""
        # Store first record
        self.store.put(self.tenant_id, self.key, self.response_data)

        # Try to store duplicate with different response
        different_data = {**self.response_data, "job_id": "job_456"}

        with pytest.raises(IdempotencyConflictError) as exc_info:
            self.store.put(self.tenant_id, self.key, different_data)

        assert exc_info.value.tenant_id == self.tenant_id.value
        assert exc_info.value.key == self.key

    def test_delete_key(self):
        """Test deleting a key."""
        # Store a record
        self.store.put(self.tenant_id, self.key, self.response_data)

        # Verify it exists
        assert self.store.get(self.tenant_id, self.key) is not None

        # Delete it
        deleted = self.store.delete(self.tenant_id, self.key)
        assert deleted is True

        # Verify it's gone
        assert self.store.get(self.tenant_id, self.key) is None

        # Try to delete again
        deleted_again = self.store.delete(self.tenant_id, self.key)
        assert deleted_again is False

    def test_tenant_isolation(self):
        """Test that tenants are isolated."""
        tenant1 = TenantId("t_tenant1")
        tenant2 = TenantId("t_tenant2")
        same_key = "shared-key-1234567890"

        data1 = {"job_id": "job_123", "tenant": "tenant1"}
        data2 = {"job_id": "job_456", "tenant": "tenant2"}

        # Store for both tenants
        self.store.put(tenant1, same_key, data1)
        self.store.put(tenant2, same_key, data2)

        # Retrieve for each tenant
        record1 = self.store.get(tenant1, same_key)
        record2 = self.store.get(tenant2, same_key)

        assert record1 is not None
        assert record2 is not None
        assert record1.response_data == data1
        assert record2.response_data == data2

    def test_expired_record_cleanup(self):
        """Test that expired records are cleaned up on access."""
        # Store a record with very short TTL
        record = self.store.put(self.tenant_id, self.key, self.response_data, ttl_seconds=0)

        # Manually expire the record
        import time

        time.sleep(0.1)  # Wait a bit to ensure expiration

        # Should be cleaned up when accessed
        retrieved = self.store.get(self.tenant_id, self.key)
        assert retrieved is None

    def test_clear_all_records(self):
        """Test clearing all records."""
        tenant1 = TenantId("t_tenant1")
        tenant2 = TenantId("t_tenant2")

        # Store records for multiple tenants
        self.store.put(tenant1, "key1", {"data": "1"})
        self.store.put(tenant2, "key2", {"data": "2"})

        # Verify they exist
        assert self.store.get(tenant1, "key1") is not None
        assert self.store.get(tenant2, "key2") is not None

        # Clear all
        self.store.clear()

        # Verify they're gone
        assert self.store.get(tenant1, "key1") is None
        assert self.store.get(tenant2, "key2") is None

    def test_custom_ttl(self):
        """Test storing records with custom TTL."""
        # Store with 1 hour TTL
        ttl_seconds = 3600
        record = self.store.put(self.tenant_id, self.key, self.response_data, ttl_seconds)

        # Check expiration time is approximately correct
        expected_expires = record.created_at + timedelta(seconds=ttl_seconds)
        time_diff = abs((record.expires_at - expected_expires).total_seconds())
        assert time_diff < 1.0  # Within 1 second


class TestIdempotencyConflictError:
    """Test cases for IdempotencyConflictError."""

    def test_error_creation(self):
        """Test creating an idempotency conflict error."""
        tenant_id = "t_test123"
        key = "test-key-1234567890"

        error = IdempotencyConflictError(tenant_id, key)

        assert error.tenant_id == tenant_id
        assert error.key == key
        assert tenant_id in str(error)
        assert "already exists" in str(error)
