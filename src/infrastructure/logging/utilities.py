"""Logging contracts for application ports.

This module defines logging decorators and utilities for consistent
logging across all port implementations.
"""

import functools
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TypeVar

from shared.logging import get_logger
from shared.logging.context import get_correlation_id

T = TypeVar("T")


class LoggingPort(ABC):
    """Base port with built-in logging capabilities."""

    def __init__(self, logger_name: str | None = None):
        """Initialize port with logger."""
        self._logger = get_logger(logger_name or self.__class__.__name__)

    @abstractmethod
    def get_component_name(self) -> str:
        """Get component name for logging context."""
        pass


def log_port_operation(
    operation_name: str,
    log_args: bool = True,
    log_result: bool = False,
    sensitive_args: list[str] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for logging port operations with performance metrics.

    Args:
        operation_name: Name of the operation being performed
        log_args: Whether to log method arguments
        log_result: Whether to log the operation result
        sensitive_args: List of argument names that contain sensitive data

    Returns:
        Decorated function with logging
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs) -> T:
            # Get logger from self if available, otherwise create one
            logger = getattr(self, "_logger", get_logger(self.__class__.__name__))

            # Prepare log context
            correlation_id = get_correlation_id()
            start_time = time.time()

            # Filter sensitive arguments
            safe_kwargs = kwargs.copy()
            if sensitive_args:
                for arg_name in sensitive_args:
                    if arg_name in safe_kwargs:
                        safe_kwargs[arg_name] = "***REDACTED***"

            # Log operation start
            log_data = {
                "operation": operation_name,
                "component": self.__class__.__name__,
                "correlation_id": correlation_id,
            }

            if log_args:
                if args:
                    log_data["args_count"] = len(args)
                if safe_kwargs:
                    log_data["kwargs"] = safe_kwargs

            logger.debug(f"{operation_name}_started", **log_data)

            try:
                # Execute the operation
                result = func(self, *args, **kwargs)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log successful completion
                success_log = {
                    "operation": operation_name,
                    "component": self.__class__.__name__,
                    "correlation_id": correlation_id,
                    "duration_ms": duration_ms,
                    "status": "success",
                }

                if log_result and result is not None:
                    # Add result metadata without exposing sensitive data
                    if hasattr(result, "__len__"):
                        success_log["result_count"] = len(result)
                    elif hasattr(result, "id"):
                        success_log["result_id"] = str(result.id)
                    else:
                        success_log["result_type"] = type(result).__name__

                logger.info(f"{operation_name}_completed", **success_log)

                return result

            except Exception as e:
                # Calculate duration even for failures
                duration_ms = (time.time() - start_time) * 1000

                # Log failure with error details
                logger.error(
                    f"{operation_name}_failed",
                    operation=operation_name,
                    component=self.__class__.__name__,
                    correlation_id=correlation_id,
                    duration_ms=duration_ms,
                    status="failed",
                    error=str(e),
                    error_type=e.__class__.__name__,
                )

                # Re-raise the exception
                raise

        return wrapper

    return decorator


def log_repository_query(
    query_type: str, table_name: str | None = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Specialized decorator for repository query operations.

    Args:
        query_type: Type of query (select, insert, update, delete)
        table_name: Name of the database table being queried

    Returns:
        Decorated function with query-specific logging
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs) -> T:
            logger = getattr(self, "_logger", get_logger(f"repository.{self.__class__.__name__}"))

            start_time = time.time()
            correlation_id = get_correlation_id()

            # Extract tenant_id if present in arguments
            tenant_id = None
            if args and hasattr(args[0], "value"):
                tenant_id = args[0].value
            elif "tenant_id" in kwargs:
                tenant_id = (
                    kwargs["tenant_id"].value
                    if hasattr(kwargs["tenant_id"], "value")
                    else kwargs["tenant_id"]
                )

            logger.debug(
                "database_query_starting",
                query_type=query_type,
                table=table_name or "unknown",
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                function=func.__name__,
            )

            try:
                result = func(self, *args, **kwargs)

                duration_ms = (time.time() - start_time) * 1000

                # Determine result metrics
                rows_affected = 0
                if result is None:
                    rows_affected = 0
                elif hasattr(result, "__len__"):
                    rows_affected = len(result)
                elif query_type in ["insert", "update", "delete"]:
                    rows_affected = 1

                logger.info(
                    "database_query_completed",
                    query_type=query_type,
                    table=table_name or "unknown",
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    duration_ms=duration_ms,
                    rows_affected=rows_affected,
                    result_found=result is not None,
                )

                # Warn if query is slow
                if duration_ms > 100:  # More than 100ms is considered slow
                    logger.warning(
                        "slow_database_query",
                        query_type=query_type,
                        table=table_name or "unknown",
                        tenant_id=tenant_id,
                        correlation_id=correlation_id,
                        duration_ms=duration_ms,
                        threshold_ms=100,
                    )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                logger.error(
                    "database_query_failed",
                    query_type=query_type,
                    table=table_name or "unknown",
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    duration_ms=duration_ms,
                    error=str(e),
                    error_type=e.__class__.__name__,
                )
                raise

        return wrapper

    return decorator


def log_rate_limit_check(func: Callable[..., bool]) -> Callable[..., bool]:
    """
    Decorator specifically for rate limiter check operations.

    Args:
        func: Rate limiter check function

    Returns:
        Decorated function with rate limit specific logging
    """

    @functools.wraps(func)
    def wrapper(self, tenant_id, resource: str, *args, **kwargs) -> bool:
        logger = getattr(self, "_logger", get_logger("rate_limiter"))

        start_time = time.time()
        correlation_id = get_correlation_id()

        # Extract tenant_id value
        tenant_id_value = tenant_id.value if hasattr(tenant_id, "value") else str(tenant_id)

        logger.debug(
            "rate_limit_check_starting",
            tenant_id=tenant_id_value,
            resource=resource,
            correlation_id=correlation_id,
        )

        try:
            # Perform the rate limit check
            allowed = func(self, tenant_id, resource, *args, **kwargs)

            duration_ms = (time.time() - start_time) * 1000

            if allowed:
                logger.info(
                    "rate_limit_allowed",
                    tenant_id=tenant_id_value,
                    resource=resource,
                    correlation_id=correlation_id,
                    duration_ms=duration_ms,
                    decision="allowed",
                )
            else:
                logger.warning(
                    "rate_limit_exceeded",
                    tenant_id=tenant_id_value,
                    resource=resource,
                    correlation_id=correlation_id,
                    duration_ms=duration_ms,
                    decision="denied",
                )

            return allowed

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            logger.error(
                "rate_limit_check_failed",
                tenant_id=tenant_id_value,
                resource=resource,
                correlation_id=correlation_id,
                duration_ms=duration_ms,
                error=str(e),
                error_type=e.__class__.__name__,
            )
            raise

    return wrapper


def log_event_publish(func: Callable[..., None]) -> Callable[..., None]:
    """
    Decorator for event bus publish operations.

    Args:
        func: Event publish function

    Returns:
        Decorated function with event publishing logging
    """

    @functools.wraps(func)
    def wrapper(self, event, *args, **kwargs) -> None:
        logger = getattr(self, "_logger", get_logger("event_bus"))

        start_time = time.time()
        correlation_id = get_correlation_id()

        # Extract event metadata
        event_type = getattr(event, "type", "unknown")
        event_id = getattr(event, "id", "unknown")
        tenant_id = getattr(event, "tenant_id", None)
        subject = getattr(event, "subject", None)

        logger.info(
            "domain_event_publishing",
            event_type=event_type,
            event_id=event_id,
            tenant_id=tenant_id,
            subject=subject,
            correlation_id=correlation_id,
        )

        try:
            # Publish the event
            func(self, event, *args, **kwargs)

            duration_ms = (time.time() - start_time) * 1000

            logger.info(
                "domain_event_published_successfully",
                event_type=event_type,
                event_id=event_id,
                tenant_id=tenant_id,
                subject=subject,
                correlation_id=correlation_id,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            logger.error(
                "domain_event_publish_failed",
                event_type=event_type,
                event_id=event_id,
                tenant_id=tenant_id,
                subject=subject,
                correlation_id=correlation_id,
                duration_ms=duration_ms,
                error=str(e),
                error_type=e.__class__.__name__,
            )
            raise

    return wrapper
