"""Unit tests for idempotency key resolver."""

import os
import re
from unittest.mock import patch

import pytest
from src.application.idempotency.resolver import (
    CSV_FORMULA_CHARS,
    _canonicalize_key,
    _create_scope_hash,
    _ensure_safe_first_char,
    _is_legacy_key,
    resolve_idempotency_key,
    validate_resolved_key,
)
from src.domain.value_objects import TenantId


class TestIdempotencyKeyResolver:
    """Test cases for idempotency key resolution."""

    def test_resolve_key_none_generates_secure_key(self):
        """Test that None raw key generates a secure key."""
        tenant_id = TenantId("t_test123")

        resolved = resolve_idempotency_key(None, tenant_id, "POST", "/jobs")

        # Should generate a secure key
        assert 16 <= len(resolved) <= 128
        assert resolved[0] not in CSV_FORMULA_CHARS
        assert re.match(r"^[A-Za-z0-9_-]+$", resolved)
        assert validate_resolved_key(resolved)

    def test_resolve_key_empty_string_generates_secure_key(self):
        """Test that empty string generates a secure key."""
        tenant_id = TenantId("t_test123")

        resolved = resolve_idempotency_key("", tenant_id, "POST", "/jobs")

        # Should generate a secure key
        assert 16 <= len(resolved) <= 128
        assert resolved[0] not in CSV_FORMULA_CHARS
        assert validate_resolved_key(resolved)

    def test_resolve_key_whitespace_generates_secure_key(self):
        """Test that whitespace-only key generates a secure key."""
        tenant_id = TenantId("t_test123")

        resolved = resolve_idempotency_key("   ", tenant_id, "POST", "/jobs")

        # Should generate a secure key
        assert 16 <= len(resolved) <= 128
        assert resolved[0] not in CSV_FORMULA_CHARS
        assert validate_resolved_key(resolved)

    def test_resolve_key_secure_format_accepted(self):
        """Test that secure format keys are accepted as-is."""
        tenant_id = TenantId("t_test123")
        secure_key = "abc123def456ghi789jk"  # 20 chars, alphanumeric

        resolved = resolve_idempotency_key(secure_key, tenant_id, "POST", "/jobs")

        # Should return exactly the input key
        assert resolved == secure_key
        assert validate_resolved_key(resolved)

    @patch.dict(os.environ, {"IDEMP_COMPAT_MODE": "canonicalize"})
    def test_resolve_key_legacy_canonicalized(self):
        """Test that legacy keys are canonicalized in canonicalize mode."""
        tenant_id = TenantId("t_test123")
        legacy_key = "order.123:item"  # Contains dots and colons

        resolved = resolve_idempotency_key(legacy_key, tenant_id, "POST", "/jobs")

        # Should be canonicalized to secure format
        assert resolved != legacy_key
        assert 16 <= len(resolved) <= 128
        assert resolved[0] not in CSV_FORMULA_CHARS
        assert validate_resolved_key(resolved)

    @patch.dict(os.environ, {"IDEMP_COMPAT_MODE": "reject"})
    def test_resolve_key_legacy_rejected(self):
        """Test that legacy keys are rejected in reject mode."""
        tenant_id = TenantId("t_test123")
        legacy_key = "order.123"  # Contains dots

        with pytest.raises(ValueError, match="Legacy idempotency key format not supported"):
            resolve_idempotency_key(legacy_key, tenant_id, "POST", "/jobs")

    def test_resolve_key_short_key_canonicalized(self):
        """Test that short keys (<16 chars) are canonicalized."""
        tenant_id = TenantId("t_test123")
        short_key = "abc123"  # Only 6 chars

        resolved = resolve_idempotency_key(short_key, tenant_id, "POST", "/jobs")

        # Should be canonicalized
        assert resolved != short_key
        assert len(resolved) >= 16
        assert validate_resolved_key(resolved)

    def test_resolve_key_formula_char_canonicalized(self):
        """Test that keys starting with formula chars are canonicalized."""
        tenant_id = TenantId("t_test123")

        for formula_char in CSV_FORMULA_CHARS:
            dangerous_key = f"{formula_char}validkey1234567890"

            resolved = resolve_idempotency_key(dangerous_key, tenant_id, "POST", "/jobs")

            # Should be canonicalized and safe
            assert resolved != dangerous_key
            assert resolved[0] not in CSV_FORMULA_CHARS
            assert validate_resolved_key(resolved)

    @patch.dict(os.environ, {"IDEMP_COMPAT_MODE": "reject"})
    def test_resolve_key_formula_char_rejected(self):
        """Test that keys starting with formula chars are rejected in reject mode."""
        tenant_id = TenantId("t_test123")

        for formula_char in CSV_FORMULA_CHARS:
            dangerous_key = f"{formula_char}validkey1234567890"

            with pytest.raises(ValueError, match="cannot start with formula characters"):
                resolve_idempotency_key(dangerous_key, tenant_id, "POST", "/jobs")

    def test_resolve_key_tenant_isolation(self):
        """Test that same raw key produces different resolved keys for different tenants."""
        raw_key = "order.123"
        tenant1 = TenantId("t_tenant1")
        tenant2 = TenantId("t_tenant2")

        resolved1 = resolve_idempotency_key(raw_key, tenant1, "POST", "/jobs")
        resolved2 = resolve_idempotency_key(raw_key, tenant2, "POST", "/jobs")

        # Should be different due to tenant isolation
        assert resolved1 != resolved2
        assert validate_resolved_key(resolved1)
        assert validate_resolved_key(resolved2)

    def test_resolve_key_scope_isolation(self):
        """Test that same raw key produces different resolved keys for different scopes."""
        raw_key = "order.123"
        tenant_id = TenantId("t_test123")

        resolved1 = resolve_idempotency_key(raw_key, tenant_id, "POST", "/jobs")
        resolved2 = resolve_idempotency_key(raw_key, tenant_id, "PUT", "/jobs/123")

        # Should be different due to scope isolation
        assert resolved1 != resolved2
        assert validate_resolved_key(resolved1)
        assert validate_resolved_key(resolved2)

    def test_resolve_key_deterministic(self):
        """Test that key resolution is deterministic."""
        tenant_id = TenantId("t_test123")
        raw_key = "order.123"

        resolved1 = resolve_idempotency_key(raw_key, tenant_id, "POST", "/jobs")
        resolved2 = resolve_idempotency_key(raw_key, tenant_id, "POST", "/jobs")

        # Should be identical
        assert resolved1 == resolved2

    def test_resolve_key_whitespace_trimmed(self):
        """Test that whitespace is trimmed from raw keys."""
        tenant_id = TenantId("t_test123")
        base_key = "validkey1234567890ab"

        resolved1 = resolve_idempotency_key(base_key, tenant_id, "POST", "/jobs")
        resolved2 = resolve_idempotency_key(f"  {base_key}  ", tenant_id, "POST", "/jobs")

        # Should be identical after trimming
        assert resolved1 == resolved2


class TestValidateResolvedKey:
    """Test cases for resolved key validation."""

    def test_validate_valid_key(self):
        """Test that valid keys pass validation."""
        valid_keys = [
            "abcdef1234567890",  # 16 chars
            "a" * 128,  # 128 chars (max)
            "abc-def_123",  # With hyphens and underscores
            "ABC123def456",  # Mixed case
        ]

        for key in valid_keys:
            assert validate_resolved_key(key), f"Key should be valid: {key}"

    def test_validate_invalid_length(self):
        """Test that keys with invalid length fail validation."""
        invalid_keys = [
            "",  # Empty
            "a",  # Too short (1 char)
            "a" * 15,  # Too short (15 chars)
            "a" * 129,  # Too long (129 chars)
        ]

        for key in invalid_keys:
            assert not validate_resolved_key(key), f"Key should be invalid: {key}"

    def test_validate_formula_chars(self):
        """Test that keys starting with formula chars fail validation."""
        for formula_char in CSV_FORMULA_CHARS:
            key = f"{formula_char}validkey1234567"
            assert not validate_resolved_key(key), f"Key should be invalid: {key}"

    def test_validate_invalid_chars(self):
        """Test that keys with invalid characters fail validation."""
        invalid_keys = [
            "key with spaces1234",  # Spaces
            "key.with.dots123456",  # Dots
            "key:with:colons1234",  # Colons
            "key@with@at123456",  # At symbols
            "key+with+plus123456",  # Plus signs
            "key/with/slash123456",  # Slashes
        ]

        for key in invalid_keys:
            assert not validate_resolved_key(key), f"Key should be invalid: {key}"


class TestHelperFunctions:
    """Test cases for helper functions."""

    def test_is_legacy_key(self):
        """Test legacy key detection."""
        legacy_keys = [
            "short",  # Too short
            "key.with.dots",
            "key:with:colons",
            "key with spaces",
            "key<with>brackets",
            "key{with}braces",
            "key|with|pipes",
            "key\\with\\backslashes",
        ]

        secure_keys = [
            "validkey1234567890",  # 18 chars, valid
            "a" * 16,  # Exactly 16 chars
            "abc-def_123456789",  # With allowed chars
        ]

        for key in legacy_keys:
            assert _is_legacy_key(key), f"Should detect as legacy: {key}"

        for key in secure_keys:
            assert not _is_legacy_key(key), f"Should NOT detect as legacy: {key}"

    def test_canonicalize_key_deterministic(self):
        """Test that canonicalization is deterministic."""
        tenant_id = "t_test123"
        raw_key = "order.123:item"

        canonical1 = _canonicalize_key(tenant_id, raw_key)
        canonical2 = _canonicalize_key(tenant_id, raw_key)

        assert canonical1 == canonical2
        assert len(canonical1) == 22  # 16 bytes base64url = 22 chars without padding

    def test_canonicalize_key_tenant_isolation(self):
        """Test that canonicalization provides tenant isolation."""
        raw_key = "order.123"
        tenant1 = "t_tenant1"
        tenant2 = "t_tenant2"

        canonical1 = _canonicalize_key(tenant1, raw_key)
        canonical2 = _canonicalize_key(tenant2, raw_key)

        assert canonical1 != canonical2

    def test_ensure_safe_first_char(self):
        """Test CSV formula character prevention."""
        # Safe keys should be unchanged
        safe_keys = ["abcdef", "123456", "_test", "A"]
        for key in safe_keys:
            assert _ensure_safe_first_char(key) == key

        # Dangerous keys should be prefixed
        for formula_char in CSV_FORMULA_CHARS:
            dangerous_key = f"{formula_char}test"
            safe_key = _ensure_safe_first_char(dangerous_key)
            assert safe_key == f"k{dangerous_key}"
            assert safe_key[0] not in CSV_FORMULA_CHARS

    def test_create_scope_hash(self):
        """Test scope hash generation."""
        hash1 = _create_scope_hash("POST", "/jobs")
        hash2 = _create_scope_hash("PUT", "/jobs/123")
        hash3 = _create_scope_hash("post", "/jobs")  # Different case

        # Should be different for different scopes
        assert hash1 != hash2

        # Should be case-insensitive for method
        assert hash1 == hash3

        # Should be 8 characters
        assert len(hash1) == 8
        assert len(hash2) == 8
