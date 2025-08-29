"""
ValidaHub Structured Logging with LGPD Compliance.

This module provides structured logging capabilities with:
- LGPD-compliant data masking
- Multi-tenant context tracking
- Security event auditing
- Performance metrics collection
- Correlation ID management
"""

from .context import (
    get_correlation_id,
    inject_correlation_id,
    with_request_context,
    with_tenant_context,
)
from .factory import configure_logging, get_logger
from .sanitizers import mask_sensitive_data, sanitize_for_log
from .security import AuditLogger, SecurityLogger

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