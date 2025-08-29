"""Test value objects."""

import pytest
from hypothesis import given, strategies as st
from dataclasses import FrozenInstanceError

from src.domain.value_objects import TenantId, IdempotencyKey


class TestTenantId:
    """Test TenantId value object."""
    
    def test_normalizes_to_lowercase(self):
        """TenantId should normalize to lowercase."""
        tenant_id = TenantId("T_TENANT123")
        assert tenant_id.value == "t_tenant123"
    
    def test_strips_whitespace(self):
        """TenantId should strip leading and trailing whitespace."""
        tenant_id = TenantId("  t_tenant123  ")
        assert tenant_id.value == "t_tenant123"
    
    def test_normalizes_and_strips_combined(self):
        """TenantId should normalize case and strip whitespace."""
        tenant_id = TenantId("  T_TENANT123  ")
        assert tenant_id.value == "t_tenant123"
    
    def test_rejects_empty_string(self):
        """TenantId should reject empty string."""
        with pytest.raises(ValueError, match="Invalid tenant id format"):
            TenantId("")
    
    def test_rejects_whitespace_only(self):
        """TenantId should reject whitespace-only string."""
        with pytest.raises(ValueError, match="Invalid tenant id format"):
            TenantId("   ")
    
    def test_rejects_too_short(self):
        """TenantId should reject strings that don't match t_ prefix pattern."""
        with pytest.raises(ValueError, match="Invalid tenant id format"):
            TenantId("ab")
    
    def test_rejects_too_long(self):
        """TenantId should reject strings longer than allowed after t_ prefix."""
        long_id = "t_" + "a" * 48  # 50 chars total, exceeds 47 after t_
        with pytest.raises(ValueError, match="Invalid tenant id format"):
            TenantId(long_id)
    
    def test_accepts_valid_length(self):
        """TenantId should accept valid t_ prefix format."""
        # Minimum valid length: t_ + 1 char
        tenant_id = TenantId("t_a")
        assert tenant_id.value == "t_a"
        
        # Maximum valid length: t_ + 47 chars
        max_id = "t_" + "a" * 47
        tenant_id = TenantId(max_id)
        assert tenant_id.value == max_id
    
    def test_equality(self):
        """TenantId instances should be equal if values are equal."""
        tenant1 = TenantId("t_tenant123")
        tenant2 = TenantId("T_TENANT123")  # Different case, should normalize
        assert tenant1 == tenant2
    
    def test_hash_consistency(self):
        """TenantId hash should be consistent for equal values."""
        tenant1 = TenantId("t_tenant123")
        tenant2 = TenantId("T_TENANT123")
        assert hash(tenant1) == hash(tenant2)
    
    def test_string_representation(self):
        """TenantId should have meaningful string representation."""
        tenant_id = TenantId("t_tenant123")
        assert str(tenant_id) == "t_tenant123"
        assert repr(tenant_id) == "TenantId('t_tenant123')"
    
    @given(st.text(min_size=1, max_size=47, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))))
    def test_valid_tenant_ids_property(self, value):
        """Property test: valid tenant IDs should be accepted."""
        # Create valid t_ prefixed value
        test_value = f"t_{value}"
        # Skip if contains invalid chars after normalization
        normalized = test_value.strip().lower()
        if not normalized or len(normalized) < 3:
            pytest.skip("Too short after normalization")
        
        tenant_id = TenantId(test_value)
        assert tenant_id.value.startswith("t_")
        assert len(tenant_id.value) >= 3
        assert len(tenant_id.value) <= 49


class TestIdempotencyKey:
    """Test IdempotencyKey value object with strict security validation."""
    
    def test_accepts_valid_format(self):
        """IdempotencyKey should accept valid format (16-128 chars, A-Za-z0-9-_)."""
        # Valid key with hyphen and underscore, 16 characters
        key = IdempotencyKey("test-key_1234567")
        assert key.value == "test-key_1234567"
    
    def test_accepts_minimum_length(self):
        """IdempotencyKey should accept minimum valid length of 16 characters."""
        key = IdempotencyKey("1234567890123456")  # Exactly 16 characters
        assert key.value == "1234567890123456"
    
    def test_accepts_maximum_length(self):
        """IdempotencyKey should accept maximum valid length."""
        long_key = "A" * 128
        key = IdempotencyKey(long_key)
        assert key.value == long_key
    
    def test_accepts_all_allowed_characters(self):
        """IdempotencyKey should accept all allowed characters (A-Za-z0-9-_)."""
        # All allowed characters: uppercase, lowercase, digits, hyphen, underscore
        key = IdempotencyKey("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        assert key.value == "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    
    def test_rejects_too_short(self):
        """IdempotencyKey should reject strings shorter than 16 characters."""
        with pytest.raises(ValueError, match="Invalid idempotency key format"):
            IdempotencyKey("123456789012345")  # 15 characters
    
    def test_rejects_too_long(self):
        """IdempotencyKey should reject strings longer than 128 characters."""
        long_key = "a" * 129
        with pytest.raises(ValueError, match="Invalid idempotency key format"):
            IdempotencyKey(long_key)
    
    def test_rejects_invalid_characters(self):
        """IdempotencyKey should reject invalid characters."""
        invalid_keys = [
            "test key!1234567",  # space and exclamation (16 chars)
            "test@key12345678",   # @ symbol
            "test#key12345678",   # # symbol
            "test$key12345678",   # $ symbol
            "test%key12345678",   # % symbol
            "test&key12345678",   # & symbol
            "test*key12345678",   # * symbol
            "test(key)1234567",   # parentheses
            "test[key]1234567",   # brackets
            "test{key}1234567",   # braces
            "test.key12345678",   # dot (not allowed)
            "test:key12345678",   # colon (not allowed)
        ]
        
        for invalid_key in invalid_keys:
            with pytest.raises(ValueError, match="Invalid idempotency key format"):
                IdempotencyKey(invalid_key)
    
    def test_rejects_empty_string(self):
        """IdempotencyKey should reject empty string."""
        with pytest.raises(ValueError, match="Invalid idempotency key format"):
            IdempotencyKey("")
    
    def test_immutability(self):
        """IdempotencyKey should be immutable (frozen)."""
        key = IdempotencyKey("test-key-1234567")
        
        with pytest.raises(FrozenInstanceError):
            key.value = "new-value-123456"  # Should fail - frozen dataclass
    
    def test_equality(self):
        """IdempotencyKey instances should be equal if values are equal."""
        key1 = IdempotencyKey("test-key-1234567")
        key2 = IdempotencyKey("test-key-1234567")
        assert key1 == key2
    
    def test_hash_consistency(self):
        """IdempotencyKey hash should be consistent for equal values."""
        key1 = IdempotencyKey("test-key-1234567")
        key2 = IdempotencyKey("test-key-1234567")
        assert hash(key1) == hash(key2)
    
    def test_string_representation(self):
        """IdempotencyKey should have meaningful string representation."""
        key = IdempotencyKey("test-key-1234567")
        assert str(key) == "test-key-1234567"
        assert repr(key) == "IdempotencyKey('test-key-1234567')"
    
    def test_csv_formula_injection_protection(self):
        """IdempotencyKey should block CSV formula injection attempts."""
        # Test all formula characters that must be blocked when at start
        formula_starters = ['=', '+', '-', '@']
        
        for char in formula_starters:
            # Even with valid length and other valid chars, should reject formula start
            malicious_key = char + "A" * 15  # 16 chars total
            with pytest.raises(ValueError, match="Invalid idempotency key format"):
                IdempotencyKey(malicious_key)
            
            # Also test with longer valid-looking keys
            malicious_key = char + "valid_key_suffix123"
            with pytest.raises(ValueError, match="Invalid idempotency key format"):
                IdempotencyKey(malicious_key)
    
    def test_csv_formula_chars_allowed_not_at_start(self):
        """IdempotencyKey should allow hyphen (-) when not at start position."""
        # Hyphen is allowed as part of the pattern when not at start
        key = IdempotencyKey("valid-key-with-hyphens")
        assert key.value == "valid-key-with-hyphens"
        
        # Underscore should also work
        key = IdempotencyKey("valid_key_with_underscores")
        assert key.value == "valid_key_with_underscores"
        
        # Mixed case and numbers
        key = IdempotencyKey("Valid123-Key_456")
        assert key.value == "Valid123-Key_456"
    
    def test_security_neutral_error_messages(self):
        """IdempotencyKey should never expose input values in error messages."""
        # All validation failures should return the same neutral error message
        test_cases = [
            "",                          # Empty
            "short",                     # Too short
            "a" * 129,                   # Too long
            "=malicious_formula_123",    # CSV injection
            "@SUM(A1:A10)_padding",      # CSV formula
            "invalid.chars.here123",     # Invalid characters (dots)
            "spaces are not allowed",    # Spaces
            "special!@#$%^&*()chars",    # Special characters
        ]
        
        for invalid_input in test_cases:
            with pytest.raises(ValueError) as exc_info:
                IdempotencyKey(invalid_input)
            # Ensure error message is always the same and doesn't contain the input
            assert str(exc_info.value) == "Invalid idempotency key format"
            # Skip empty string check as it's technically contained in any string
            if invalid_input:
                assert invalid_input not in str(exc_info.value)
    
    @given(st.text(
        min_size=16, 
        max_size=128, 
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    ).filter(lambda x: x[0] not in "=+-@"))
    def test_valid_idempotency_keys_property(self, value):
        """Property test: valid idempotency keys should be accepted."""
        # Only test keys that don't start with CSV formula characters
        key = IdempotencyKey(value)
        assert key.value == value
        assert len(key.value) >= 16
        assert len(key.value) <= 128
    
    @given(st.one_of(
        # Too short (less than 16 chars)
        st.text(min_size=0, max_size=15, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"),
        # Too long (more than 128 chars)
        st.text(min_size=129, max_size=200, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"),
        # Invalid characters
        st.text(min_size=16, max_size=128).filter(
            lambda x: not all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in x)
        ),
        # CSV formula injection (starts with =, +, -, @)
        st.builds(
            lambda prefix, suffix: prefix + suffix,
            prefix=st.sampled_from(["=", "+", "-", "@"]),
            suffix=st.text(min_size=15, max_size=127, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        ),
    ))
    def test_invalid_idempotency_keys_property(self, value):
        """Property test: invalid idempotency keys should be rejected."""
        with pytest.raises(ValueError, match="Invalid idempotency key format"):
            IdempotencyKey(value)