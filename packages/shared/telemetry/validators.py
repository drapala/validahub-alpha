"""
Validators for telemetry data quality and CloudEvents compliance.
"""

from typing import Any

from jsonschema import ValidationError, validate

from .envelope import CloudEventEnvelope

# CloudEvents 1.0 JSON Schema
CLOUDEVENTS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["id", "source", "specversion", "type"],
    "properties": {
        "id": {
            "type": "string",
            "minLength": 1
        },
        "source": {
            "type": "string",
            "format": "uri-reference"
        },
        "specversion": {
            "type": "string",
            "enum": ["1.0"]
        },
        "type": {
            "type": "string",
            "minLength": 1
        },
        "time": {
            "type": "string",
            "format": "date-time"
        },
        "subject": {
            "type": "string"
        },
        "datacontenttype": {
            "type": "string"
        },
        "data": {
            "type": "object"
        }
    },
    "additionalProperties": True
}


def validate_cloudevents(event: CloudEventEnvelope) -> bool:
    """
    Validate CloudEvent against CloudEvents 1.0 specification.
    
    Args:
        event: CloudEvent to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If event is not valid
    """
    event_dict = event.to_dict()
    
    try:
        validate(instance=event_dict, schema=CLOUDEVENTS_SCHEMA)
        return True
    except ValidationError as error:
        raise ValidationError(f"CloudEvent validation failed: {error.message}")


def validate_metrics(
    name: str,
    value: float,
    tags: dict[str, str] | None = None
) -> bool:
    """
    Validate metric data for quality and compliance.
    
    Args:
        name: Metric name
        value: Metric value  
        tags: Optional metric tags
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If metric is invalid
    """
    # Validate metric name
    if not name or not isinstance(name, str):
        raise ValueError("Metric name must be a non-empty string")
    
    if len(name) > 200:
        raise ValueError("Metric name too long (max 200 characters)")
    
    # Check for valid characters (Prometheus compatible)
    import re
    if not re.match(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$', name):
        raise ValueError("Metric name contains invalid characters")
    
    # Validate value
    if not isinstance(value, int | float):
        raise ValueError("Metric value must be numeric")
    
    if not (-1e308 <= value <= 1e308):  # Avoid infinity
        raise ValueError("Metric value out of range")
    
    # Validate tags
    if tags:
        if not isinstance(tags, dict):
            raise ValueError("Tags must be a dictionary")
        
        if len(tags) > 50:
            raise ValueError("Too many tags (max 50)")
        
        for key, val in tags.items():
            if not isinstance(key, str) or not isinstance(val, str):
                raise ValueError("Tag keys and values must be strings")
            
            if len(key) > 100 or len(val) > 200:
                raise ValueError("Tag key/value too long")
    
    return True


def validate_event_data(
    event_type: str,
    data: dict[str, Any]
) -> list[str]:
    """
    Validate event data for completeness and quality.
    
    Args:
        event_type: Type of CloudEvent
        data: Event data payload
        
    Returns:
        List of validation warnings (empty if all good)
    """
    warnings = []
    
    # Common validations
    if not data:
        warnings.append("Event data is empty")
        return warnings
    
    # Job event validations
    if event_type.startswith("job."):
        job_warnings = _validate_job_event_data(data)
        warnings.extend(job_warnings)
    
    # API event validations
    elif event_type.startswith("api."):
        api_warnings = _validate_api_event_data(data)
        warnings.extend(api_warnings)
    
    # Business event validations
    elif data.get("_event_category") == "business":
        business_warnings = _validate_business_event_data(data)
        warnings.extend(business_warnings)
    
    # Check for sensitive data
    sensitive_warnings = _check_for_sensitive_data(data)
    warnings.extend(sensitive_warnings)
    
    return warnings


def _validate_job_event_data(data: dict[str, Any]) -> list[str]:
    """Validate job-specific event data."""
    warnings = []
    
    required_fields = ["job_id"]
    for field in required_fields:
        if field not in data:
            warnings.append(f"Missing required job field: {field}")
    
    # Validate job_id format (should be UUID)
    if "job_id" in data:
        job_id = data["job_id"]
        if not isinstance(job_id, str) or len(job_id) != 36:
            warnings.append("job_id should be a valid UUID")
    
    # Validate counters if present
    if "counters" in data:
        counters = data["counters"]
        if not isinstance(counters, dict):
            warnings.append("counters should be a dictionary")
        else:
            for key in ["total", "processed", "errors", "warnings"]:
                if key in counters and not isinstance(counters[key], int):
                    warnings.append(f"counters.{key} should be an integer")
    
    # Validate duration if present
    if "duration_seconds" in data:
        duration = data["duration_seconds"]
        if not isinstance(duration, int | float) or duration < 0:
            warnings.append("duration_seconds should be a non-negative number")
    
    return warnings


def _validate_api_event_data(data: dict[str, Any]) -> list[str]:
    """Validate API-specific event data."""
    warnings = []
    
    # Check for HTTP fields
    if "status_code" in data:
        status = data["status_code"]
        if not isinstance(status, int) or not (100 <= status <= 599):
            warnings.append("status_code should be a valid HTTP status code")
    
    if "duration_ms" in data:
        duration = data["duration_ms"]
        if not isinstance(duration, int | float) or duration < 0:
            warnings.append("duration_ms should be a non-negative number")
    
    # Check for endpoint information
    if "endpoint" in data and not isinstance(data["endpoint"], str):
        warnings.append("endpoint should be a string")
    
    return warnings


def _validate_business_event_data(data: dict[str, Any]) -> list[str]:
    """Validate business-specific event data."""
    warnings = []
    
    # Check revenue/cost fields
    if "_revenue_impact_brl" in data:
        revenue = data["_revenue_impact_brl"]
        if not isinstance(revenue, int | float):
            warnings.append("_revenue_impact_brl should be numeric")
    
    if "_cost_impact_brl" in data:
        cost = data["_cost_impact_brl"]
        if not isinstance(cost, int | float) or cost < 0:
            warnings.append("_cost_impact_brl should be non-negative number")
    
    return warnings


def _check_for_sensitive_data(data: dict[str, Any]) -> list[str]:
    """Check event data for potentially sensitive information."""
    warnings = []
    
    # Check for common sensitive field patterns
    sensitive_patterns = [
        "password", "token", "secret", "key", "credential",
        "cpf", "cnpj", "email", "phone", "address"
    ]
    
    def check_dict(obj: dict[str, Any], path: str = ""):
        for key, value in obj.items():
            current_path = f"{path}.{key}" if path else key
            
            # Check key names
            key_lower = key.lower()
            for pattern in sensitive_patterns:
                if pattern in key_lower:
                    warnings.append(f"Potentially sensitive field: {current_path}")
                    break
            
            # Recursively check nested objects
            if isinstance(value, dict):
                check_dict(value, current_path)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        check_dict(item, f"{current_path}[{i}]")
    
    check_dict(data)
    
    return warnings


class TelemetryValidator:
    """Comprehensive validator for telemetry data quality."""
    
    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self.validation_errors = []
        self.validation_warnings = []
    
    def validate_event(self, event: CloudEventEnvelope) -> bool:
        """
        Validate CloudEvent comprehensively.
        
        Args:
            event: Event to validate
            
        Returns:
            True if valid (in non-strict mode, warnings don't fail)
        """
        self.validation_errors.clear()
        self.validation_warnings.clear()
        
        try:
            # CloudEvents spec validation
            validate_cloudevents(event)
            
            # Data quality validation
            if event.data:
                warnings = validate_event_data(event.type, event.data)
                self.validation_warnings.extend(warnings)
            
            # In strict mode, warnings become errors
            if self.strict_mode and self.validation_warnings:
                self.validation_errors.extend(self.validation_warnings)
                self.validation_warnings.clear()
            
            return len(self.validation_errors) == 0
            
        except ValidationError as error:
            self.validation_errors.append(str(error))
            return False
    
    def validate_metric(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None
    ) -> bool:
        """
        Validate metric comprehensively.
        
        Args:
            name: Metric name
            value: Metric value
            tags: Optional tags
            
        Returns:
            True if valid
        """
        self.validation_errors.clear()
        
        try:
            validate_metrics(name, value, tags)
            return True
        except ValueError as error:
            self.validation_errors.append(str(error))
            return False
    
    def get_validation_report(self) -> dict[str, Any]:
        """Get detailed validation report."""
        return {
            "valid": len(self.validation_errors) == 0,
            "errors": self.validation_errors.copy(),
            "warnings": self.validation_warnings.copy(),
            "error_count": len(self.validation_errors),
            "warning_count": len(self.validation_warnings),
        }