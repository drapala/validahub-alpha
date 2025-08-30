"""
Application service for CCM validation with proper data parsing.

This service handles parsing of external data before passing to the domain layer,
keeping the domain pure from parsing libraries.
"""

import logging
from typing import Any

from application.factories.ccm_factory import CCMFactory
from domain.rules.engine.ccm import CCM, CCMValidationResult

logger = logging.getLogger(__name__)


class CCMValidationService:
    """Service for validating records against the Canonical CSV Model."""
    
    def __init__(self):
        """Initialize the CCM validation service."""
        self.ccm = CCM
        self.factory = CCMFactory()
    
    def validate_record(self, record: dict[str, Any]) -> list[CCMValidationResult]:
        """
        Validate a record against CCM with proper data parsing.
        
        This method handles parsing of date fields before validation,
        keeping the domain layer free from parsing logic.
        
        Args:
            record: Dictionary containing the record to validate
            
        Returns:
            List of validation results for each field
        """
        # Pre-process date fields using the factory
        processed_record = self._preprocess_dates(record)
        
        # Now validate using the domain CCM
        return self.ccm.validate_record(processed_record)
    
    def _preprocess_dates(self, record: dict[str, Any]) -> dict[str, Any]:
        """
        Pre-process date fields in the record.
        
        Args:
            record: Original record with potential date strings
            
        Returns:
            Record with date strings parsed to datetime objects
        """
        processed = record.copy()
        
        # List of known date fields in CCM
        date_fields = [
            "created_at",
            "updated_at", 
            "available_from",
            "available_until",
            "sale_start_date",
            "sale_end_date",
        ]
        
        for field in date_fields:
            if field in processed and processed[field]:
                # Use factory to normalize the date
                normalized = self.factory.normalize_date(processed[field])
                if normalized:
                    # Parse it to datetime for the domain
                    from datetime import datetime
                    try:
                        # The factory returns ISO format, parse it back to datetime
                        processed[field] = datetime.fromisoformat(normalized)
                    except (ValueError, TypeError):
                        # If parsing fails, keep original value
                        # The domain validation will catch this
                        pass
        
        return processed