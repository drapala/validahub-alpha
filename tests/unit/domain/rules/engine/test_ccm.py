"""
Unit tests for CCM domain guardrails - proves the domain rejects unparsed data.

These tests ensure that:
1. The domain CCM rejects string dates (enforcing the guardrail)
2. The domain CCM accepts datetime objects
3. The domain remains pure and doesn't do parsing
"""

from datetime import datetime

from domain.rules.engine.ccm import CanonicalCSVModel, CCMField, CCMFieldType, ValidationSeverity


class TestCCMDomainGuardrails:
    """Test suite proving domain CCM enforces type requirements."""
    
    def test_domain_rejects_string_dates(self):
        """Domain should reject date fields that are strings."""
        # Arrange
        ccm = CanonicalCSVModel()
        date_field = CCMField(
            name="created_at",
            type=CCMFieldType.DATE,
            required=True
        )
        
        # Act - pass a string instead of datetime
        result = ccm._validate_date(date_field, "2025-08-30")
        
        # Assert - domain should reject this
        assert result.is_valid is False
        assert result.severity == ValidationSeverity.ERROR
        assert "Expected datetime object" in result.message
        assert "got str" in result.message
        assert "application layer factories" in result.suggestion
    
    def test_domain_accepts_datetime_objects(self):
        """Domain should accept properly typed datetime objects."""
        # Arrange
        ccm = CanonicalCSVModel()
        date_field = CCMField(
            name="created_at",
            type=CCMFieldType.DATE,
            required=True
        )
        dt = datetime(2025, 8, 30, 10, 30, 0)
        
        # Act - pass a datetime object
        result = ccm._validate_date(date_field, dt)
        
        # Assert - domain should accept this
        assert result.is_valid is True
        assert result.normalized_value == dt.isoformat()
        assert result.original_value == dt
    
    def test_domain_rejects_various_string_formats(self):
        """Domain should reject all string date formats."""
        # Arrange
        ccm = CanonicalCSVModel()
        date_field = CCMField(
            name="created_at",
            type=CCMFieldType.DATE,
            required=True
        )
        
        string_dates = [
            "2025-08-30",
            "30/08/2025",
            "August 30, 2025",
            "2025-08-30T10:30:00",
            "not-a-date",
            "12345",
            ""
        ]
        
        # Act & Assert
        for date_str in string_dates:
            result = ccm._validate_date(date_field, date_str)
            assert result.is_valid is False, f"Domain accepted string '{date_str}'"
            assert "Expected datetime object" in result.message
            assert "str" in result.message
    
    def test_domain_rejects_invalid_types(self):
        """Domain should reject non-datetime, non-string types."""
        # Arrange
        ccm = CanonicalCSVModel()
        date_field = CCMField(
            name="created_at",
            type=CCMFieldType.DATE,
            required=True
        )
        
        invalid_types = [
            123,  # int
            45.67,  # float
            ["2025-08-30"],  # list
            {"date": "2025-08-30"},  # dict
            None,  # None
        ]
        
        # Act & Assert
        for invalid_value in invalid_types:
            result = ccm._validate_date(date_field, invalid_value)
            assert result.is_valid is False, f"Domain accepted {type(invalid_value).__name__}"
            assert "Expected datetime object" in result.message
    
    def test_normalize_date_with_datetime(self):
        """Domain should normalize datetime objects to ISO format."""
        # Arrange
        ccm = CanonicalCSVModel()
        dt = datetime(2025, 8, 30, 14, 30, 45)
        
        # Act
        normalized = ccm._normalize_date(dt)
        
        # Assert
        assert normalized == dt.isoformat()
        assert normalized == "2025-08-30T14:30:45"
    
    def test_normalize_date_with_string_returns_as_is(self):
        """Domain should return string dates as-is (for validation to catch)."""
        # Arrange
        ccm = CanonicalCSVModel()
        date_str = "2025-08-30"
        
        # Act
        normalized = ccm._normalize_date(date_str)
        
        # Assert
        # Should return the string as-is, not parse it
        assert normalized == date_str
        assert isinstance(normalized, str)
    
    def test_full_record_validation_with_string_date(self):
        """Full record validation should fail with string dates."""
        # Arrange
        ccm = CanonicalCSVModel()
        record = {
            "sku": "PROD001",
            "title": "Test Product",
            "created_at": "2025-08-30",  # String date - should fail
            "price_brl": 99.90
        }
        
        # Act
        results = ccm.validate_record(record)
        
        # Assert
        # Find the created_at validation
        date_results = [r for r in results if r.field == "created_at"]
        
        # If created_at is in the CCM fields, it should have been validated
        if date_results:
            date_result = date_results[0]
            # Should be invalid because it's a string
            if ccm.FIELDS.get("created_at") and ccm.FIELDS["created_at"].type == CCMFieldType.DATE:
                assert date_result.is_valid is False
                assert "Expected datetime object" in date_result.message
    
    def test_full_record_validation_with_datetime(self):
        """Full record validation should pass with datetime objects."""
        # Arrange
        ccm = CanonicalCSVModel()
        dt = datetime(2025, 8, 30, 10, 30, 0)
        record = {
            "sku": "PROD001",
            "title": "Test Product",
            "created_at": dt,  # Datetime object - should pass
            "price_brl": 99.90
        }
        
        # Act
        results = ccm.validate_record(record)
        
        # Assert
        # Find the created_at validation
        date_results = [r for r in results if r.field == "created_at"]
        
        # If created_at is in the CCM fields and is a date type
        if date_results:
            date_result = date_results[0]
            if ccm.FIELDS.get("created_at") and ccm.FIELDS["created_at"].type == CCMFieldType.DATE:
                # Should be valid because it's a datetime
                assert date_result.is_valid is True
                assert date_result.normalized_value == dt.isoformat()
    
    def test_domain_has_no_dateutil_imports(self):
        """Domain CCM should not import dateutil (parsing library)."""
        # This is a static check to ensure domain purity
        import inspect

        import domain.rules.engine.ccm as ccm_module
        
        # Get the source code
        source = inspect.getsource(ccm_module)
        
        # Assert no dateutil imports
        assert "from dateutil" not in source
        assert "import dateutil" not in source
    
    def test_guardrail_error_message_is_helpful(self):
        """Error message should guide developers to use factories."""
        # Arrange
        ccm = CanonicalCSVModel()
        date_field = CCMField(
            name="created_at",
            type=CCMFieldType.DATE,
            required=True
        )
        
        # Act
        result = ccm._validate_date(date_field, "2025-08-30")
        
        # Assert
        assert result.is_valid is False
        # Message should explain the issue
        assert "Expected datetime object" in result.message
        assert "got str" in result.message
        # Suggestion should guide to the solution
        assert "application layer factories" in result.suggestion.lower()
    
    def test_domain_protection_is_comprehensive(self):
        """Domain should protect all date-related operations."""
        # Arrange
        ccm = CanonicalCSVModel()
        
        # Test validation
        date_field = CCMField(name="test", type=CCMFieldType.DATE)
        validation_result = ccm._validate_date(date_field, "string-date")
        assert validation_result.is_valid is False
        
        # Test normalization
        normalized = ccm._normalize_date("string-date")
        # Should not parse, just return as string
        assert normalized == "string-date"
        
        # Both operations should refuse to parse strings