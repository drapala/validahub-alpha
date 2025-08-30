"""
LGPD-compliant data sanitizers for logging.
"""

import re
from typing import Any

from structlog.types import EventDict, WrappedLogger

# Sensitive field patterns that should be masked
SENSITIVE_PATTERNS = [
    r"password",
    r"pwd",
    r"secret",
    r"token",
    r"api_key",
    r"apikey",
    r"auth",
    r"credential",
    r"private",
    r"ssn",
    r"cpf",
    r"cnpj",
    r"credit_card",
    r"card_number",
    r"cvv",
    r"pin",
]

# Fields that should be partially masked
PARTIAL_MASK_FIELDS = {
    "tenant_id": lambda v: _mask_tenant_id(v),
    "idempotency_key": lambda v: _mask_idempotency_key(v),
    "file_ref": lambda v: _mask_file_ref(v),
    "file_reference": lambda v: _mask_file_ref(v),
    "email": lambda v: _mask_email(v),
    "phone": lambda v: _mask_phone(v),
    "seller_id": lambda v: _mask_id(v, "seller"),
}


class LGPDProcessor:
    """
    Structlog processor for LGPD compliance.

    Automatically masks sensitive data in log events.
    """

    def __call__(
        self,
        logger: WrappedLogger,
        name: str,
        event_dict: EventDict,
    ) -> EventDict:
        """Process log event and mask sensitive data."""
        return sanitize_for_log(event_dict)


def sanitize_for_log(data: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize a dictionary for LGPD-compliant logging.

    Args:
        data: Dictionary to sanitize

    Returns:
        Sanitized dictionary with masked sensitive data
    """
    sanitized = {}

    for key, value in data.items():
        # Check if field name indicates sensitive data
        if _is_sensitive_field(key):
            sanitized[key] = "***REDACTED***"
        # Check if field should be partially masked
        elif key in PARTIAL_MASK_FIELDS:
            if value is not None:
                sanitized[key] = PARTIAL_MASK_FIELDS[key](str(value))
            else:
                sanitized[key] = None
        # Recursively sanitize nested dictionaries
        elif isinstance(value, dict):
            sanitized[key] = sanitize_for_log(value)
        # Sanitize lists
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_for_log(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            sanitized[key] = value

    return sanitized


def mask_sensitive_data(data_type: str, value: str) -> str:
    """
    Mask sensitive data according to its type.

    Args:
        data_type: Type of data to mask
        value: Value to mask

    Returns:
        Masked value
    """
    if not value:
        return "***"

    maskers = {
        "tenant_id": _mask_tenant_id,
        "idempotency_key": _mask_idempotency_key,
        "file_ref": _mask_file_ref,
        "email": _mask_email,
        "phone": _mask_phone,
        "seller_id": lambda v: _mask_id(v, "seller"),
        "job_id": lambda v: _mask_id(v, "job"),
    }

    masker = maskers.get(data_type, lambda v: "***MASKED***")
    return masker(value)


def _is_sensitive_field(field_name: str) -> bool:
    """Check if a field name indicates sensitive data."""
    field_lower = field_name.lower()
    return any(re.search(pattern, field_lower) for pattern in SENSITIVE_PATTERNS)


def _mask_tenant_id(value: str) -> str:
    """Mask tenant ID keeping prefix and suffix."""
    if len(value) <= 6:
        return "***"
    return f"{value[:3]}***{value[-3:]}"


def _mask_idempotency_key(value: str) -> str:
    """Mask idempotency key keeping only first 8 chars."""
    if len(value) <= 8:
        return "***"
    return f"{value[:8]}***"


def _mask_file_ref(value: str) -> str:
    """Mask file reference keeping bucket/container info."""
    if value.startswith("s3://"):
        parts = value[5:].split("/", 1)
        bucket = parts[0] if parts else "***"
        return f"s3://{bucket}/***"
    elif value.startswith("gs://"):
        parts = value[5:].split("/", 1)
        bucket = parts[0] if parts else "***"
        return f"gs://{bucket}/***"
    elif value.startswith("azure://"):
        parts = value[8:].split("/", 1)
        container = parts[0] if parts else "***"
        return f"azure://{container}/***"
    elif "/" in value:
        # Local file path - keep only first directory
        parts = value.split("/")
        if len(parts) > 2:
            return f"{parts[0]}/***"
    return "***"


def _mask_email(value: str) -> str:
    """Mask email keeping domain."""
    if "@" in value:
        local, domain = value.rsplit("@", 1)
        if len(local) > 2:
            return f"{local[0]}***@{domain}"
        return f"***@{domain}"
    return "***"


def _mask_phone(value: str) -> str:
    """Mask phone number keeping country code and last 2 digits."""
    # Remove non-digits
    digits = re.sub(r"\D", "", value)
    if len(digits) > 4:
        return f"***{digits[-2:]}"
    return "***"


def _mask_id(value: str, prefix: str) -> str:
    """Mask IDs keeping prefix and last 4 chars."""
    if len(value) > 8:
        return f"{prefix}_***{value[-4:]}"
    return f"{prefix}_***"
