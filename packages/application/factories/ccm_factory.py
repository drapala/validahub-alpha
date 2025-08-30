"""
Factory for creating CCM validation results with proper date parsing.

This factory handles the parsing of external date strings using dateutil,
keeping the domain layer free from parsing libraries.
"""

import logging
from datetime import datetime
from typing import Any

from dateutil import parser as date_parser

from domain.rules.engine.ccm import CCMValidationResult, ValidationSeverity

logger = logging.getLogger(__name__)


class CCMFactory:
    """Factory for creating CCM-related domain objects."""

    @staticmethod
    def create_date_validation_result(
        field: str,
        value: Any,
        required: bool = False
    ) -> CCMValidationResult:
        """
        Create a validation result for date fields.
        
        This method handles date parsing using dateutil, keeping the domain pure.
        
        Args:
            field: The field name being validated
            value: The date value to parse (string or datetime)
            required: Whether the field is required
            
        Returns:
            CCMValidationResult with parsed date or validation error
        """
        # Handle empty values
        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                return CCMValidationResult(
                    field=field,
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Campo {field} é obrigatório",
                    original_value=value,
                )
            return CCMValidationResult(
                field=field,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Campo opcional vazio",
                original_value=value,
            )
        
        # Parse the date
        try:
            if isinstance(value, datetime):
                parsed_date = value
            else:
                # Use dateutil for flexible date parsing
                parsed_date = date_parser.parse(str(value))
            
            return CCMValidationResult(
                field=field,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Data válida",
                original_value=value,
                normalized_value=parsed_date.isoformat(),
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse date for field {field}: {e}")
            return CCMValidationResult(
                field=field,
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Formato de data inválido: {str(e)}",
                suggestion="Use formatos como YYYY-MM-DD, DD/MM/YYYY, etc.",
                original_value=value,
            )

    @staticmethod
    def normalize_date(value: Any) -> str | None:
        """
        Normalize a date value to ISO format.
        
        Args:
            value: The date value to normalize
            
        Returns:
            ISO formatted date string or None if parsing fails
        """
        if not value or (isinstance(value, str) and not value.strip()):
            return None
            
        try:
            if isinstance(value, datetime):
                return value.isoformat()
            
            # Use dateutil for flexible parsing
            parsed_date = date_parser.parse(str(value))
            return parsed_date.isoformat()
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to normalize date: {e}")
            return None