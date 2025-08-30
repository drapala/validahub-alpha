"""
Unit tests for CCMFactory - proves that the factory correctly handles date parsing.

These tests ensure that:
1. Valid date strings in various formats are parsed correctly
2. Invalid date strings raise appropriate errors
3. The factory returns proper domain objects
"""

import pytest
from datetime import datetime

from application.factories.ccm_factory import CCMFactory
from domain.rules.engine.ccm import ValidationSeverity


class TestCCMFactory:
    """Test suite for CCMFactory date parsing capabilities."""
    
    def test_parse_iso_date_format(self):
        """Factory should parse ISO format dates correctly."""
        # Arrange
        factory = CCMFactory()
        iso_date = "2025-08-30"
        
        # Act
        result = factory.normalize_date(iso_date)
        
        # Assert
        assert result is not None
        assert "2025-08-30" in result
        # Verify it's a valid ISO format
        parsed = datetime.fromisoformat(result)
        assert parsed.year == 2025
        assert parsed.month == 8
        assert parsed.day == 30
    
    def test_parse_brazilian_date_format(self):
        """Factory should parse Brazilian DD/MM/YYYY format."""
        # Arrange
        factory = CCMFactory()
        br_date = "30/08/2025"
        
        # Act
        result = factory.normalize_date(br_date)
        
        # Assert
        assert result is not None
        parsed = datetime.fromisoformat(result)
        assert parsed.year == 2025
        assert parsed.month == 8
        assert parsed.day == 30
    
    def test_parse_us_date_format(self):
        """Factory should parse US MM/DD/YYYY format."""
        # Arrange
        factory = CCMFactory()
        us_date = "08/30/2025"
        
        # Act
        result = factory.normalize_date(us_date)
        
        # Assert
        assert result is not None
        parsed = datetime.fromisoformat(result)
        assert parsed.year == 2025
        assert parsed.month == 8
        assert parsed.day == 30
    
    def test_parse_datetime_with_time(self):
        """Factory should parse full datetime strings."""
        # Arrange
        factory = CCMFactory()
        datetime_str = "2025-08-30T14:30:00"
        
        # Act
        result = factory.normalize_date(datetime_str)
        
        # Assert
        assert result is not None
        parsed = datetime.fromisoformat(result)
        assert parsed.year == 2025
        assert parsed.month == 8
        assert parsed.day == 30
        assert parsed.hour == 14
        assert parsed.minute == 30
    
    def test_parse_human_readable_date(self):
        """Factory should parse human-readable date formats."""
        # Arrange
        factory = CCMFactory()
        human_date = "August 30, 2025"
        
        # Act
        result = factory.normalize_date(human_date)
        
        # Assert
        assert result is not None
        parsed = datetime.fromisoformat(result)
        assert parsed.year == 2025
        assert parsed.month == 8
        assert parsed.day == 30
    
    def test_parse_datetime_object_passthrough(self):
        """Factory should pass through datetime objects unchanged."""
        # Arrange
        factory = CCMFactory()
        dt = datetime(2025, 8, 30, 14, 30, 0)
        
        # Act
        result = factory.normalize_date(dt)
        
        # Assert
        assert result == dt.isoformat()
    
    def test_invalid_date_returns_none(self):
        """Factory should return None for invalid date strings."""
        # Arrange
        factory = CCMFactory()
        invalid_dates = [
            "not-a-date",
            "invalid",
            "12345",
            "2025-13-45",  # Invalid month/day
            "abcd-ef-gh",
        ]
        
        # Act & Assert
        for invalid_date in invalid_dates:
            result = factory.normalize_date(invalid_date)
            assert result is None, f"Expected None for '{invalid_date}', got {result}"
    
    def test_empty_date_returns_none(self):
        """Factory should return None for empty/None values."""
        # Arrange
        factory = CCMFactory()
        
        # Act & Assert
        assert factory.normalize_date(None) is None
        assert factory.normalize_date("") is None
        assert factory.normalize_date("   ") is None
    
    def test_create_date_validation_result_valid(self):
        """Factory should create valid result for parseable dates."""
        # Arrange
        factory = CCMFactory()
        
        # Act
        result = factory.create_date_validation_result(
            field="created_at",
            value="2025-08-30",
            required=True
        )
        
        # Assert
        assert result.is_valid is True
        assert result.field == "created_at"
        assert result.severity == ValidationSeverity.INFO
        assert result.message == "Data válida"
        assert "2025-08-30" in result.normalized_value
    
    def test_create_date_validation_result_invalid(self):
        """Factory should create error result for invalid dates."""
        # Arrange
        factory = CCMFactory()
        
        # Act
        result = factory.create_date_validation_result(
            field="created_at",
            value="not-a-date",
            required=True
        )
        
        # Assert
        assert result.is_valid is False
        assert result.field == "created_at"
        assert result.severity == ValidationSeverity.ERROR
        assert "Formato de data inválido" in result.message
        assert result.suggestion is not None
        assert result.normalized_value is None
    
    def test_create_date_validation_result_empty_required(self):
        """Factory should create error for empty required date."""
        # Arrange
        factory = CCMFactory()
        
        # Act
        result = factory.create_date_validation_result(
            field="created_at",
            value="",
            required=True
        )
        
        # Assert
        assert result.is_valid is False
        assert result.field == "created_at"
        assert result.severity == ValidationSeverity.ERROR
        assert "obrigatório" in result.message
    
    def test_create_date_validation_result_empty_optional(self):
        """Factory should allow empty optional dates."""
        # Arrange
        factory = CCMFactory()
        
        # Act
        result = factory.create_date_validation_result(
            field="updated_at",
            value="",
            required=False
        )
        
        # Assert
        assert result.is_valid is True
        assert result.field == "updated_at"
        assert result.severity == ValidationSeverity.INFO
        assert "opcional" in result.message.lower()
    
    def test_various_date_formats_consistency(self):
        """Factory should consistently parse various valid formats."""
        # Arrange
        factory = CCMFactory()
        date_formats = [
            "2025-08-30",
            "2025/08/30", 
            "30-08-2025",
            "30/08/2025",
            "Aug 30, 2025",
            "30 Aug 2025",
            "2025-08-30 00:00:00",
        ]
        
        # Act & Assert
        for date_str in date_formats:
            result = factory.normalize_date(date_str)
            assert result is not None, f"Failed to parse '{date_str}'"
            # All should resolve to the same date
            parsed = datetime.fromisoformat(result.split('T')[0])
            assert parsed.year == 2025, f"Wrong year for '{date_str}'"
            assert parsed.month == 8, f"Wrong month for '{date_str}'"
            assert parsed.day == 30, f"Wrong day for '{date_str}'"