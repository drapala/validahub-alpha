"""Test TenantId edge cases, Unicode handling, and marketplace patterns."""

import pytest
from src.domain.value_objects import TenantId


class TestTenantIdEdgeCases:
    """Test TenantId with edge cases and Unicode."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("T_ACME123", "t_acme123"),
            (" t_acme123 ", "t_acme123"),
            ("  T_MARKETPLACE  ", "t_marketplace"),
            ("T_ML123", "t_ml123"),  # Mercado Livre prefix
            ("T_MG456", "t_mg456"),  # Magazine Luiza prefix
            ("T_AZ789", "t_az789"),  # Amazon prefix
        ],
    )
    def test_tenant_id_normalizes_lower_strip(self, raw, expected):
        """TenantId should normalize to lowercase and strip whitespace."""
        assert str(TenantId(raw)) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",  # Empty
            "t_",  # Prefix only
            "t_äcme",  # Non-ASCII
            "t_acme!",  # Special char
            "acme",  # Missing prefix
            "t_" + "a" * 48,  # Too long (50 chars total, 48 after t_)
            "ab",  # Too short
            "t",  # Too short
            "  ",  # Only whitespace
            "\t\n",  # Only whitespace chars
        ],
    )
    def test_tenant_id_rejects_invalid(self, raw):
        """TenantId should reject invalid formats."""
        with pytest.raises(ValueError):
            TenantId(raw)

    def test_tenant_id_rejects_zero_width_characters(self):
        """TenantId should reject zero-width characters."""
        with pytest.raises(ValueError):
            TenantId("t_\u200bacme123")  # Zero-width space

        with pytest.raises(ValueError):
            TenantId("t_ac\u200cme123")  # Zero-width non-joiner

        with pytest.raises(ValueError):
            TenantId("t_ac\u200dme123")  # Zero-width joiner

    def test_tenant_id_rejects_control_characters(self):
        """TenantId should reject control characters."""
        with pytest.raises(ValueError):
            TenantId("t_acme123\x00")  # Null byte

        with pytest.raises(ValueError):
            TenantId("t_ac\x1bme123")  # Escape character

        with pytest.raises(ValueError):
            TenantId("t_ac\x7fme123")  # Delete character

    @pytest.mark.parametrize(
        "marketplace_prefix",
        [
            "t_ml",  # Mercado Livre
            "t_mg",  # Magazine Luiza
            "t_az",  # Amazon
            "t_sh",  # Shopee
            "t_al",  # AliExpress
        ],
    )
    def test_tenant_id_accepts_marketplace_prefixes(self, marketplace_prefix):
        """TenantId should accept common marketplace prefixes."""
        tenant = TenantId(f"{marketplace_prefix}_seller123")
        assert str(tenant).startswith(marketplace_prefix)

    def test_tenant_id_accepts_underscore_and_numbers(self):
        """TenantId should accept underscore and numbers in valid positions."""
        valid_ids = [
            "t_123",
            "t_seller_123",
            "t_ml_store_456",
            "t_1234567890",
        ]

        for valid_id in valid_ids:
            tenant = TenantId(valid_id)
            assert str(tenant) == valid_id.lower()

    def test_tenant_id_rejects_hyphen(self):
        """TenantId should reject hyphen (not part of allowed chars)."""
        with pytest.raises(ValueError):
            TenantId("t_acme-corp123")

    def test_tenant_id_rejects_dot(self):
        """TenantId should reject dot (not part of allowed chars)."""
        with pytest.raises(ValueError):
            TenantId("t_acme123.com")

    def test_tenant_id_boundary_lengths(self):
        """Test TenantId at exact boundary lengths."""
        # Minimum valid: t_ + 1 char = 3 chars total
        min_tenant = TenantId("t_a")
        assert str(min_tenant) == "t_a"

        # Maximum valid: t_ + 47 chars = 49 chars total
        max_tenant = TenantId("t_" + "a" * 47)
        assert str(max_tenant) == "t_" + "a" * 47

        # One under minimum: t_ only = 2 chars
        with pytest.raises(ValueError):
            TenantId("t_")

        # One over maximum: t_ + 48 chars = 50 chars total
        with pytest.raises(ValueError):
            TenantId("t_" + "a" * 48)
