"""
ValidaHub Structured Logging with LGPD Compliance.

This module provides structured logging capabilities with:
- LGPD-compliant data masking
- Multi-tenant context tracking
- Security event auditing
- Performance metrics collection
- Correlation ID management
"""

from .factory import configure_logging, get_logger
from .sanitizers import mask_sensitive_data, sanitize_for_log
from .context import (
    with_request_context,
    with_tenant_context,
    get_correlation_id,
    inject_correlation_id,
)
from .security import SecurityLogger, AuditLogger

__all__ = [
    "configure_logging",
    "get_logger",
    "mask_sensitive_data",
    "sanitize_for_log",
    "with_request_context",
    "with_tenant_context",
    "get_correlation_id",
    "inject_correlation_id",
    "SecurityLogger",
    "AuditLogger",
]