"""
Logging factory with structured logging and LGPD compliance.
"""

import os
import sys
from typing import Any, Dict, Optional

import structlog
from structlog.contextvars import merge_contextvars
from structlog.processors import (
    TimeStamper,
    add_log_level,
    CallsiteParameter,
    CallsiteParameterAdder,
    ExceptionPrettyPrinter,
    JSONRenderer,
    KeyValueRenderer,
    UnicodeDecoder,
)
from structlog.stdlib import (
    ProcessorFormatter,
    add_logger_name,
    BoundLogger,
)

from .sanitizers import LGPDProcessor


def get_logger(name: str) -> BoundLogger:
    """
    Get a structured logger with ValidaHub context.
    
    Args:
        name: Logger name (e.g., "domain.job", "application.submit_job")
        
    Returns:
        Configured structured logger with LGPD compliance
    """
    return structlog.get_logger(name).bind(
        service="validahub",
        version=os.getenv("SERVICE_VERSION", "1.0.0"),
        environment=os.getenv("ENVIRONMENT", "development"),
    )


def configure_logging(
    environment: str = "development",
    log_level: str = "INFO",
    json_logs: bool = True,
    include_caller_info: bool = True,
) -> None:
    """
    Configure structured logging for ValidaHub.
    
    Args:
        environment: Environment name (development, staging, production)
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Whether to output JSON formatted logs
        include_caller_info: Include file, function, and line number
    """
    
    # Common processors for all environments
    processors = [
        # Add contextual variables from context vars
        merge_contextvars,
        # Add timestamp in ISO format
        TimeStamper(fmt="ISO", utc=True),
        # Add log level
        add_log_level,
        # Add logger name
        add_logger_name,
        # Unicode decoding for strings
        UnicodeDecoder(),
        # LGPD compliance - mask sensitive data
        LGPDProcessor(),
    ]
    
    # Add caller information in development
    if include_caller_info and environment == "development":
        processors.append(
            CallsiteParameterAdder(
                parameters=[
                    CallsiteParameter.FILENAME,
                    CallsiteParameter.FUNC_NAME,
                    CallsiteParameter.LINENO,
                ],
                additional_ignores=["structlog", "logging"],
            )
        )
    
    # Add exception formatting
    if environment == "development":
        processors.append(ExceptionPrettyPrinter())
    
    # Choose renderer based on environment
    if json_logs:
        processors.append(JSONRenderer(sort_keys=True))
    else:
        processors.append(KeyValueRenderer(key_order=["timestamp", "level", "event", "logger"]))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(_get_log_level_int(log_level)),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging to use structlog
    import logging
    
    handler = logging.StreamHandler()
    handler.setFormatter(ProcessorFormatter(processors=processors))
    
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(_get_log_level_int(log_level))


def _get_log_level_int(level: str) -> int:
    """Convert string log level to integer."""
    import logging
    
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return levels.get(level.upper(), logging.INFO)