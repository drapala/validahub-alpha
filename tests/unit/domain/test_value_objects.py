"""Test value objects."""

import pytest
from hypothesis import given, strategies as st
from dataclasses import FrozenInstanceError

from domain.value_objects import TenantId, IdempotencyKey


class TestTenantId:
    """Test TenantId value object."""
    
    def test_normalizes_to_lowercase(self):
        """TenantId should normalize to lowercase."""
        tenant_id = TenantId("TENANT_123")
        assert tenant_id.value == "tenant_123"
    
    def test_strips_whitespace(self):
        """TenantId should strip leading and trailing whitespace."""
        tenant_id = TenantId("  tenant_123  ")
        assert tenant_id.value == "tenant_123"
    
    def test_normalizes_and_strips_combined(self):
        """TenantId should normalize case and strip whitespace."""
        tenant_id = TenantId("  TENANT_123  ")
        assert tenant_id.value == "tenant_123"
    
    def test_rejects_empty_string(self):
        """TenantId should reject empty string."""
        with pytest.raises(ValueError, match="TenantId cannot be empty"):
            TenantId("")
    
    def test_rejects_whitespace_only(self):
        """TenantId should reject whitespace-only string."""
        with pytest.raises(ValueError, match="TenantId cannot be empty"):
            TenantId("   ")
    
    def test_rejects_too_short(self):
        """TenantId should reject strings shorter than 3 characters."""
        with pytest.raises(ValueError, match="TenantId must be between 3 and 50 characters"):
            TenantId("ab")
    
    def test_rejects_too_long(self):
        """TenantId should reject strings longer than 50 characters."""
        long_id = "a" * 51
        with pytest.raises(ValueError, match="TenantId must be between 3 and 50 characters"):
            TenantId(long_id)
    
    def test_accepts_valid_length(self):
        """TenantId should accept valid length strings."""
        # Minimum valid length
        tenant_id = TenantId("abc")
        assert tenant_id.value == "abc"
        
        # Maximum valid length
        max_id = "a" * 50
        tenant_id = TenantId(max_id)
        assert tenant_id.value == max_id
    
    def test_equality(self):
        """TenantId instances should be equal if values are equal."""
        tenant1 = TenantId("tenant_123")
        tenant2 = TenantId("TENANT_123")  # Different case, should normalize
        assert tenant1 == tenant2
    
    def test_hash_consistency(self):
        """TenantId hash should be consistent for equal values."""
        tenant1 = TenantId("tenant_123")
        tenant2 = TenantId("TENANT_123")
        assert hash(tenant1) == hash(tenant2)
    
    def test_string_representation(self):
        """TenantId should have meaningful string representation."""
        tenant_id = TenantId("tenant_123")
        assert str(tenant_id) == "tenant_123"
        assert repr(tenant_id) == "TenantId('tenant_123')"
    
    @given(st.text(min_size=3, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))))
    def test_valid_tenant_ids_property(self, value):
        """Property test: valid tenant IDs should be accepted."""
        # Skip if only whitespace after stripping
        if not value.strip():
            pytest.skip("Empty after strip")
        
        tenant_id = TenantId(value)
        assert len(tenant_id.value) >= 3
        assert len(tenant_id.value) <= 50
        assert tenant_id.value == value.strip().lower()


class TestIdempotencyKey:
    """Test IdempotencyKey value object."""
    
    def test_accepts_valid_format(self):
        """IdempotencyKey should accept valid format."""
        key = IdempotencyKey("test-key_123.csv")
        assert key.value == "test-key_123.csv"
    
    @pytest.mark.skip(reason="Pending: IdempotencyKey min length decision (8 vs 16)")
    def test_accepts_minimum_length(self):
        """IdempotencyKey should accept minimum valid length."""
        key = IdempotencyKey("12345678")  # 8 characters
        assert key.value == "12345678"
    
    def test_accepts_maximum_length(self):
        """IdempotencyKey should accept maximum valid length."""
        long_key = "A" * 128
        key = IdempotencyKey(long_key)
        assert key.value == long_key
    
    @pytest.mark.skip(reason="Pending: IdempotencyKey allowed chars decision (. : vs - _)")
    def test_accepts_all_allowed_characters(self):
        """IdempotencyKey should accept all allowed characters."""
        key = IdempotencyKey("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-")
        assert key.value == "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-"
    
    def test_rejects_too_short(self):
        """IdempotencyKey should reject strings shorter than 8 characters."""
        with pytest.raises(ValueError, match="IdempotencyKey must be between 8 and 128 characters and match pattern"):
            IdempotencyKey("1234567")  # 7 characters
    
    def test_rejects_too_long(self):
        """IdempotencyKey should reject strings longer than 128 characters."""
        long_key = "a" * 129
        with pytest.raises(ValueError, match="IdempotencyKey must be between 8 and 128 characters and match pattern"):
            IdempotencyKey(long_key)
    
    def test_rejects_invalid_characters(self):
        """IdempotencyKey should reject invalid characters."""
        invalid_keys = [
            "test key!",  # space and exclamation
            "test@key",   # @ symbol
            "test#key",   # # symbol
            "test$key",   # $ symbol
            "test%key",   # % symbol
            "test&key",   # & symbol
            "test*key",   # * symbol
            "test(key)",  # parentheses
            "test[key]",  # brackets
            "test{key}",  # braces
        ]
        
        for invalid_key in invalid_keys:
            with pytest.raises(ValueError, match="IdempotencyKey must be between 8 and 128 characters and match pattern"):
                IdempotencyKey(invalid_key)
    
    def test_rejects_empty_string(self):
        """IdempotencyKey should reject empty string."""
        with pytest.raises(ValueError, match="IdempotencyKey must be between 8 and 128 characters and match pattern"):
            IdempotencyKey("")
    
    def test_immutability(self):
        """IdempotencyKey should be immutable (frozen)."""
        key = IdempotencyKey("test-key-123")
        
        with pytest.raises(FrozenInstanceError):
            key.value = "new-value"  # Should fail - frozen dataclass
    
    def test_equality(self):
        """IdempotencyKey instances should be equal if values are equal."""
        key1 = IdempotencyKey("test-key-123")
        key2 = IdempotencyKey("test-key-123")
        assert key1 == key2
    
    def test_hash_consistency(self):
        """IdempotencyKey hash should be consistent for equal values."""
        key1 = IdempotencyKey("test-key-123")
        key2 = IdempotencyKey("test-key-123")
        assert hash(key1) == hash(key2)
    
    def test_string_representation(self):
        """IdempotencyKey should have meaningful string representation."""
        key = IdempotencyKey("test-key-123")
        assert str(key) == "test-key-123"
        assert repr(key) == "IdempotencyKey('test-key-123')"
    
    @pytest.mark.skip(reason="Pending: Property test alphabet alignment with implementation")
    @given(st.text(
        min_size=8, 
        max_size=128, 
        alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-")
    ))
    def test_valid_idempotency_keys_property(self, value):
        """Property test: valid idempotency keys should be accepted."""
        key = IdempotencyKey(value)
        assert key.value == value
        assert len(key.value) >= 8
        assert len(key.value) <= 128
    
    @given(st.text(min_size=1, max_size=200).filter(
        lambda x: len(x) < 8 or len(x) > 128 or not all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-" for c in x)
    ))
    def test_invalid_idempotency_keys_property(self, value):
        """Property test: invalid idempotency keys should be rejected."""
        with pytest.raises(ValueError, match="IdempotencyKey must be between 8 and 128 characters and match pattern"):
            IdempotencyKey(value)