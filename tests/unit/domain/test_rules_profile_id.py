"""Test RulesProfileId normalization and SemVer validation."""

import pytest
from src.domain.value_objects import RulesProfileId


class TestRulesProfileId:
    """Test RulesProfileId with channel normalization and SemVer."""
    
    def test_rules_profile_from_string_normalizes_channel_and_semver(self):
        """RulesProfileId should normalize channel to lowercase and validate SemVer."""
        rp = RulesProfileId.from_string(" Mercado_Livre @ 1.2.3 ")
        assert str(rp) == "mercado_livre@1.2.3"
        assert rp.channel == "mercado_livre"
        assert rp.version == "1.2.3"
        assert rp.major == 1
        assert rp.minor == 2
        assert rp.patch == 3
    
    def test_rules_profile_accepts_various_channels(self):
        """RulesProfileId should accept various marketplace channels."""
        channels = [
            ("MercadoLivre", "1.0.0", "mercadolivre@1.0.0"),
            ("Magazine_Luiza", "2.1.0", "magazine_luiza@2.1.0"),
            ("AMAZON", "3.0.1", "amazon@3.0.1"),
            ("shopee", "1.2.3", "shopee@1.2.3"),
            ("AliExpress", "0.1.0", "aliexpress@0.1.0"),
        ]
        
        for channel, version, expected in channels:
            rp = RulesProfileId.from_string(f"{channel}@{version}")
            assert str(rp) == expected
    
    @pytest.mark.parametrize("invalid_format", [
        "mercado_livre@1.2",  # Missing patch
        "mercado@1",  # Missing minor and patch
        "mercado@",  # Missing version
        "@1.2.3",  # Missing channel
        "mercado_livre",  # No @ separator
        "1.2.3",  # No channel
        "mercado livre@1.2.3",  # Space in channel
        "mercado@1.2.3.4",  # Too many version parts
        "mercado@v1.2.3",  # Version with 'v' prefix
        "mercado@1.2.3-beta",  # Pre-release version (if not supported)
        "mercado@1.2.3+build",  # Build metadata (if not supported)
    ])
    def test_rules_profile_rejects_invalid_semver(self, invalid_format):
        """RulesProfileId should reject invalid SemVer formats."""
        with pytest.raises(ValueError):
            RulesProfileId.from_string(invalid_format)
    
    def test_rules_profile_rejects_invalid_version_numbers(self):
        """RulesProfileId should reject non-numeric version components."""
        invalid_versions = [
            "channel@a.b.c",
            "channel@1.b.3",
            "channel@1.2.c",
            "channel@-1.2.3",
            "channel@1.-2.3",
            "channel@1.2.-3",
        ]
        
        for invalid in invalid_versions:
            with pytest.raises(ValueError):
                RulesProfileId.from_string(invalid)
    
    def test_rules_profile_version_comparison(self):
        """RulesProfileId should support version comparison."""
        rp1 = RulesProfileId.from_string("mercado@1.0.0")
        rp2 = RulesProfileId.from_string("mercado@1.2.0")
        rp3 = RulesProfileId.from_string("mercado@1.2.3")
        rp4 = RulesProfileId.from_string("mercado@2.0.0")
        
        # Test version components are integers
        assert rp1.major == 1 and rp1.minor == 0 and rp1.patch == 0
        assert rp2.major == 1 and rp2.minor == 2 and rp2.patch == 0
        assert rp3.major == 1 and rp3.minor == 2 and rp3.patch == 3
        assert rp4.major == 2 and rp4.minor == 0 and rp4.patch == 0
        
        # Can be used for version comparison logic
        assert (rp4.major, rp4.minor, rp4.patch) > (rp3.major, rp3.minor, rp3.patch)
        assert (rp3.major, rp3.minor, rp3.patch) > (rp2.major, rp2.minor, rp2.patch)
        assert (rp2.major, rp2.minor, rp2.patch) > (rp1.major, rp1.minor, rp1.patch)
    
    def test_rules_profile_strips_whitespace(self):
        """RulesProfileId should strip whitespace from channel and version."""
        rp = RulesProfileId.from_string("  mercado  @  1.2.3  ")
        assert str(rp) == "mercado@1.2.3"
    
    def test_rules_profile_handles_underscores_and_hyphens(self):
        """RulesProfileId should handle underscores and hyphens in channel names."""
        rp1 = RulesProfileId.from_string("mercado_livre@1.0.0")
        assert rp1.channel == "mercado_livre"
        
        rp2 = RulesProfileId.from_string("mercado-livre@1.0.0")
        assert rp2.channel == "mercado-livre"
        
        rp3 = RulesProfileId.from_string("mercado_livre-br@1.0.0")
        assert rp3.channel == "mercado_livre-br"
    
    def test_rules_profile_equality(self):
        """RulesProfileId instances should be equal if channel and version match."""
        rp1 = RulesProfileId.from_string("mercado@1.2.3")
        rp2 = RulesProfileId.from_string("MERCADO@1.2.3")  # Different case
        rp3 = RulesProfileId.from_string("mercado@1.2.4")  # Different patch
        
        assert rp1 == rp2  # Case-insensitive channel
        assert rp1 != rp3  # Different version
    
    def test_rules_profile_hash_consistency(self):
        """RulesProfileId hash should be consistent for equal instances."""
        rp1 = RulesProfileId.from_string("mercado@1.2.3")
        rp2 = RulesProfileId.from_string("MERCADO@1.2.3")
        
        assert hash(rp1) == hash(rp2)
    
    def test_rules_profile_string_representation(self):
        """RulesProfileId should have consistent string representation."""
        rp = RulesProfileId.from_string("Mercado_Livre@1.2.3")
        assert str(rp) == "mercado_livre@1.2.3"
        assert repr(rp) == "RulesProfileId('mercado_livre@1.2.3')"
    
    def test_rules_profile_is_immutable(self):
        """RulesProfileId should be immutable."""
        rp = RulesProfileId.from_string("mercado@1.2.3")
        
        with pytest.raises(Exception):
            object.__setattr__(rp, "channel", "amazon")
        
        with pytest.raises(Exception):
            object.__setattr__(rp, "version", "2.0.0")
        
        with pytest.raises(Exception):
            object.__setattr__(rp, "major", 2)
    
    def test_rules_profile_zero_versions(self):
        """RulesProfileId should accept 0 in version numbers."""
        rp = RulesProfileId.from_string("channel@0.0.0")
        assert rp.major == 0
        assert rp.minor == 0
        assert rp.patch == 0
        
        rp2 = RulesProfileId.from_string("channel@0.1.0")
        assert rp2.major == 0
        assert rp2.minor == 1
        assert rp2.patch == 0