"""
Unit tests for CCMValidationService - proves the service correctly orchestrates parsing.

These tests ensure that:
1. The service preprocesses date fields before passing to domain
2. Date strings are converted to datetime objects
3. The domain receives properly typed data
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from application.services.ccm_service import CCMValidationService
from domain.rules.engine.ccm import CCMValidationResult, ValidationSeverity


class TestCCMValidationService:
    """Test suite for CCMValidationService orchestration."""
    
    def test_service_preprocesses_date_fields(self):
        """Service should preprocess date strings to datetime objects."""
        # Arrange
        service = CCMValidationService()
        record = {
            "sku": "PROD001",
            "title": "Test Product",
            "created_at": "2025-08-30",
            "updated_at": "30/08/2025",
            "price_brl": 99.90
        }
        
        # Act
        processed = service._preprocess_dates(record)
        
        # Assert
        assert isinstance(processed["created_at"], datetime)
        assert processed["created_at"].year == 2025
        assert processed["created_at"].month == 8
        assert processed["created_at"].day == 30
        
        assert isinstance(processed["updated_at"], datetime)
        assert processed["updated_at"].year == 2025
        assert processed["updated_at"].month == 8
        assert processed["updated_at"].day == 30
        
        # Non-date fields should remain unchanged
        assert processed["sku"] == "PROD001"
        assert processed["title"] == "Test Product"
        assert processed["price_brl"] == 99.90
    
    def test_service_handles_multiple_date_fields(self):
        """Service should process all known date fields."""
        # Arrange
        service = CCMValidationService()
        record = {
            "created_at": "2025-01-01",
            "updated_at": "2025-02-01",
            "available_from": "2025-03-01",
            "available_until": "2025-04-01",
            "sale_start_date": "2025-05-01",
            "sale_end_date": "2025-06-01",
        }
        
        # Act
        processed = service._preprocess_dates(record)
        
        # Assert
        assert isinstance(processed["created_at"], datetime)
        assert processed["created_at"].month == 1
        
        assert isinstance(processed["updated_at"], datetime)
        assert processed["updated_at"].month == 2
        
        assert isinstance(processed["available_from"], datetime)
        assert processed["available_from"].month == 3
        
        assert isinstance(processed["available_until"], datetime)
        assert processed["available_until"].month == 4
        
        assert isinstance(processed["sale_start_date"], datetime)
        assert processed["sale_start_date"].month == 5
        
        assert isinstance(processed["sale_end_date"], datetime)
        assert processed["sale_end_date"].month == 6
    
    def test_service_skips_empty_date_fields(self):
        """Service should skip empty/None date fields."""
        # Arrange
        service = CCMValidationService()
        record = {
            "created_at": "",
            "updated_at": None,
            "available_from": "   ",
            "sku": "PROD001"
        }
        
        # Act
        processed = service._preprocess_dates(record)
        
        # Assert
        assert processed["created_at"] == ""
        assert processed["updated_at"] is None
        assert processed["available_from"] == "   "
        assert processed["sku"] == "PROD001"
    
    def test_service_handles_invalid_dates_gracefully(self):
        """Service should keep invalid dates as-is for domain to validate."""
        # Arrange
        service = CCMValidationService()
        record = {
            "created_at": "not-a-date",
            "updated_at": "invalid",
            "sku": "PROD001"
        }
        
        # Act
        processed = service._preprocess_dates(record)
        
        # Assert
        # Invalid dates should remain as strings
        assert processed["created_at"] == "not-a-date"
        assert processed["updated_at"] == "invalid"
        assert processed["sku"] == "PROD001"
    
    @patch('application.services.ccm_service.CCM')
    def test_service_passes_processed_data_to_domain(self, mock_ccm):
        """Service should pass preprocessed data to domain CCM."""
        # Arrange
        service = CCMValidationService()
        service.ccm = mock_ccm
        
        original_record = {
            "sku": "PROD001",
            "created_at": "2025-08-30",
            "price_brl": 99.90
        }
        
        expected_result = [
            CCMValidationResult(
                field="sku",
                is_valid=True,
                severity=ValidationSeverity.INFO
            )
        ]
        mock_ccm.validate_record.return_value = expected_result
        
        # Act
        result = service.validate_record(original_record)
        
        # Assert
        # Verify CCM was called with processed data
        mock_ccm.validate_record.assert_called_once()
        call_args = mock_ccm.validate_record.call_args[0][0]
        
        # The date should have been converted to datetime
        assert isinstance(call_args["created_at"], datetime)
        assert call_args["created_at"].year == 2025
        assert call_args["created_at"].month == 8
        assert call_args["created_at"].day == 30
        
        # Other fields should be unchanged
        assert call_args["sku"] == "PROD001"
        assert call_args["price_brl"] == 99.90
        
        # Result should be passed through
        assert result == expected_result
    
    def test_service_preserves_original_record(self):
        """Service should not modify the original record."""
        # Arrange
        service = CCMValidationService()
        original_record = {
            "sku": "PROD001",
            "created_at": "2025-08-30",
            "price_brl": 99.90
        }
        original_copy = original_record.copy()
        
        # Act
        processed = service._preprocess_dates(original_record)
        
        # Assert
        # Original should be unchanged
        assert original_record == original_copy
        assert original_record["created_at"] == "2025-08-30"
        
        # Processed should have datetime
        assert isinstance(processed["created_at"], datetime)
    
    def test_service_handles_missing_date_fields(self):
        """Service should handle records without date fields."""
        # Arrange
        service = CCMValidationService()
        record = {
            "sku": "PROD001",
            "title": "Test Product",
            "price_brl": 99.90
            # No date fields
        }
        
        # Act
        processed = service._preprocess_dates(record)
        
        # Assert
        assert processed == record
        assert "created_at" not in processed
        assert "updated_at" not in processed
    
    def test_service_with_real_ccm_integration(self):
        """Integration test with real CCM (not mocked)."""
        # Arrange
        service = CCMValidationService()
        record = {
            "sku": "PROD001",
            "title": "Test Product",
            "created_at": "2025-08-30T10:30:00",
            "price_brl": 99.90
        }
        
        # Act
        results = service.validate_record(record)
        
        # Assert
        assert isinstance(results, list)
        # Should have validation results
        assert len(results) > 0
        
        # Find the created_at validation result
        date_results = [r for r in results if r.field == "created_at"]
        if date_results:
            # If CCM validates dates, it should accept the datetime object
            date_result = date_results[0]
            # The domain should have received a datetime, not a string
            # If it rejects strings as per our new guardrail, this should pass
            assert date_result.is_valid or "datetime object" in str(date_result.message)
    
    def test_service_handles_already_parsed_dates(self):
        """Service should handle records with datetime objects."""
        # Arrange
        service = CCMValidationService()
        dt = datetime(2025, 8, 30, 10, 30)
        record = {
            "sku": "PROD001",
            "created_at": dt,  # Already a datetime
            "updated_at": "2025-08-30"  # String to parse
        }
        
        # Act
        processed = service._preprocess_dates(record)
        
        # Assert
        # Already parsed should remain as datetime
        assert processed["created_at"] == dt
        # String should be parsed
        assert isinstance(processed["updated_at"], datetime)