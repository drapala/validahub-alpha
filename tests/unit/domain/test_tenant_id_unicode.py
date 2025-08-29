"""Test TenantId edge cases, Unicode handling, and marketplace patterns."""

import pytest
from domain.value_objects import TenantId


class TestTenantIdEdgeCases:
    """Test TenantId with edge cases and Unicode."""
    
    @pytest.mark.parametrize("raw,expected", [
        ("T_ACME", "t_acme"),
        (" t_acme ", "t_acme"),
        ("  T_MARKETPLACE  ", "t_marketplace"),
        ("T_ML", "t_ml"),  # Mercado Livre prefix
        ("T_MG", "t_mg"),  # Magazine Luiza prefix
        ("T_AZ", "t_az"),  # Amazon prefix
    ])
    def test_tenant_id_normalizes_lower_strip(self, raw, expected):
        """TenantId should normalize to lowercase and strip whitespace."""
        assert str(TenantId(raw)) == expected
    
    @pytest.mark.parametrize("raw", [
        "",  # Empty
        "t_",  # Prefix only
        "t_äcme",  # Non-ASCII
        "t_acme!",  # Special char
        "acme",  # Missing prefix
        "t_" + "a" * 48,  # Too long (51 chars total)
        "ab",  # Too short
        "t",  # Too short
        "  ",  # Only whitespace
        "\t\n",  # Only whitespace chars
    ])
    def test_tenant_id_rejects_invalid(self, raw):
        """TenantId should reject invalid formats."""
        with pytest.raises(ValueError):
            TenantId(raw)
    
    def test_tenant_id_rejects_zero_width_characters(self):
        """TenantId should reject zero-width characters."""
        with pytest.raises(ValueError):
            TenantId("t_\u200bacme")  # Zero-width space
        
        with pytest.raises(ValueError):
            TenantId("t_ac\u200cme")  # Zero-width non-joiner
        
        with pytest.raises(ValueError):
            TenantId("t_ac\u200dme")  # Zero-width joiner
    
    def test_tenant_id_rejects_control_characters(self):
        """TenantId should reject control characters."""
        with pytest.raises(ValueError):
            TenantId("t_acme\x00")  # Null byte
        
        with pytest.raises(ValueError):
            TenantId("t_ac\x1bme")  # Escape character
        
        with pytest.raises(ValueError):
            TenantId("t_ac\x7fme")  # Delete character
    
    @pytest.mark.parametrize("marketplace_prefix", [
        "t_ml",  # Mercado Livre
        "t_mg",  # Magazine Luiza  
        "t_az",  # Amazon
        "t_sh",  # Shopee
        "t_al",  # AliExpress
    ])
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
            TenantId("t_acme-corp")
    
    def test_tenant_id_rejects_dot(self):
        """TenantId should reject dot (not part of allowed chars)."""
        with pytest.raises(ValueError):
            TenantId("t_acme.com")
    
    def test_tenant_id_boundary_lengths(self):
        """Test TenantId at exact boundary lengths."""
        # Minimum valid: 3 chars
        min_tenant = TenantId("abc")
        assert str(min_tenant) == "abc"
        
        # Maximum valid: 50 chars
        max_tenant = TenantId("a" * 50)
        assert str(max_tenant) == "a" * 50
        
        # One under minimum: 2 chars
        with pytest.raises(ValueError):
            TenantId("ab")
        
        # One over maximum: 51 chars
        with pytest.raises(ValueError):
            TenantId("a" * 51)