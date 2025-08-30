"""Distributed tracing decorators and performance utilities.

This module provides decorators and utilities for distributed tracing,
performance monitoring, and cross-service correlation.
"""

import functools
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, TypeVar
from uuid import uuid4

from shared.logging import get_logger
from shared.logging.context import get_correlation_id, set_correlation_id

T = TypeVar("T")

# Context variables for tracing
trace_context: ContextVar[Optional["TraceContext"]] = ContextVar("trace_context", default=None)


@dataclass
class TraceContext:
    """Context for distributed tracing."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    operation_name: str | None = None
    service_name: str = "validahub"
    tags: dict[str, Any] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


class PerformanceLevel(Enum):
    """Performance level thresholds."""

    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"
    CRITICAL = "critical"


def get_performance_level(
    duration_ms: float, thresholds: dict[str, float] = None
) -> PerformanceLevel:
    """
    Determine performance level based on duration.

    Args:
        duration_ms: Duration in milliseconds
        thresholds: Custom thresholds (optional)

    Returns:
        Performance level
    """
    if thresholds is None:
        thresholds = {
            "fast": 50,  # < 50ms is fast
            "normal": 200,  # < 200ms is normal
            "slow": 1000,  # < 1000ms is slow
            "critical": 1000,  # >= 1000ms is critical
        }

    if duration_ms < thresholds["fast"]:
        return PerformanceLevel.FAST
    elif duration_ms < thresholds["normal"]:
        return PerformanceLevel.NORMAL
    elif duration_ms < thresholds["slow"]:
        return PerformanceLevel.SLOW
    else:
        return PerformanceLevel.CRITICAL


def generate_span_id() -> str:
    """Generate a unique span ID."""
    return str(uuid4())[:16]  # Use first 16 chars for shorter IDs


def with_distributed_tracing(
    operation_name: str, service_name: str = "validahub", tags: dict[str, Any] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for distributed tracing with comprehensive logging.

    Args:
        operation_name: Name of the operation being traced
        service_name: Name of the service
        tags: Additional tags for the trace

    Returns:
        Decorated function with tracing
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            logger = get_logger(f"{service_name}.{func.__module__}")

            # Get or create trace context
            parent_context = trace_context.get()

            if parent_context:
                # Continue existing trace
                trace_id = parent_context.trace_id
                parent_span_id = parent_context.span_id
            else:
                # Start new trace
                trace_id = get_correlation_id() or generate_span_id()
                parent_span_id = None
                # Set correlation ID if not set
                if not get_correlation_id():
                    set_correlation_id(trace_id)

            # Create new span
            span_id = generate_span_id()

            # Create trace context
            current_context = TraceContext(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                operation_name=operation_name,
                service_name=service_name,
                tags=tags or {},
            )

            # Set context for nested calls
            token = trace_context.set(current_context)

            # Log span start
            logger.info(
                "span_started",
                operation=operation_name,
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                service=service_name,
                function=func.__name__,
                tags=current_context.tags,
            )

            start_time = time.time()
            error_occurred = False
            error_details = None

            try:
                # Execute function
                result = func(*args, **kwargs)

                return result

            except Exception as e:
                error_occurred = True
                error_details = {"error": str(e), "error_type": e.__class__.__name__}

                # Log span error
                logger.error(
                    "span_error",
                    operation=operation_name,
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    service=service_name,
                    **error_details,
                )

                raise

            finally:
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                performance_level = get_performance_level(duration_ms)

                # Log span completion
                log_level = "info"
                if error_occurred:
                    log_level = "error"
                elif performance_level == PerformanceLevel.CRITICAL:
                    log_level = "warning"

                log_data = {
                    "operation": operation_name,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id,
                    "service": service_name,
                    "duration_ms": duration_ms,
                    "performance_level": performance_level.value,
                    "status": "error" if error_occurred else "success",
                }

                if error_details:
                    log_data.update(error_details)

                getattr(logger, log_level)("span_completed", **log_data)

                # Reset context
                trace_context.reset(token)

        return wrapper

    return decorator


def with_performance_logging(
    operation_name: str | None = None, slow_threshold_ms: float = 500, include_args: bool = False
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for performance logging without full tracing overhead.

    Args:
        operation_name: Name of the operation (defaults to function name)
        slow_threshold_ms: Threshold for slow operation warning
        include_args: Whether to include function arguments in logs

    Returns:
        Decorated function with performance logging
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            op_name = operation_name or func.__name__
            logger = get_logger(f"performance.{func.__module__}")

            log_data = {
                "operation": op_name,
                "function": func.__name__,
                "correlation_id": get_correlation_id(),
            }

            if include_args and args:
                log_data["args_count"] = len(args)
            if include_args and kwargs:
                log_data["kwargs_keys"] = list(kwargs.keys())

            start_time = time.time()

            try:
                result = func(*args, **kwargs)

                duration_ms = (time.time() - start_time) * 1000
                log_data["duration_ms"] = duration_ms

                # Determine log level based on performance
                if duration_ms > slow_threshold_ms:
                    logger.warning("slow_operation", **log_data, threshold_ms=slow_threshold_ms)
                else:
                    logger.debug("operation_completed", **log_data)

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                log_data.update(
                    {
                        "duration_ms": duration_ms,
                        "error": str(e),
                        "error_type": e.__class__.__name__,
                    }
                )

                logger.error("operation_failed", **log_data)
                raise

        return wrapper

    return decorator


def measure_operation(operation_name: str) -> "OperationTimer":
    """
    Context manager for measuring operation duration.

    Usage:
        with measure_operation("database_query") as timer:
            # ... perform operation ...
            pass
        print(f"Operation took {timer.duration_ms}ms")

    Args:
        operation_name: Name of the operation being measured

    Returns:
        OperationTimer context manager
    """
    return OperationTimer(operation_name)


class OperationTimer:
    """Context manager for timing operations."""

    def __init__(self, operation_name: str):
        """Initialize timer."""
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
        self.duration_ms = None
        self.logger = get_logger("performance.timer")

    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()

        self.logger.debug(
            "operation_timer_started",
            operation=self.operation_name,
            correlation_id=get_correlation_id(),
        )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and log results."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000

        log_data = {
            "operation": self.operation_name,
            "duration_ms": self.duration_ms,
            "correlation_id": get_correlation_id(),
        }

        if exc_type:
            log_data.update(
                {"status": "failed", "error": str(exc_val), "error_type": exc_type.__name__}
            )
            self.logger.error("operation_timer_failed", **log_data)
        else:
            log_data["status"] = "success"

            # Log based on duration
            if self.duration_ms > 1000:
                self.logger.warning("operation_timer_slow", **log_data)
            else:
                self.logger.info("operation_timer_completed", **log_data)

        return False  # Don't suppress exceptions


def log_method_calls(cls):
    """
    Class decorator that logs all public method calls.

    Usage:
        @log_method_calls
        class MyService:
            def process(self, data):
                return data

    Args:
        cls: Class to decorate

    Returns:
        Decorated class with logged methods
    """
    logger = get_logger(f"{cls.__module__}.{cls.__name__}")

    for name, method in cls.__dict__.items():
        if callable(method) and not name.startswith("_"):
            setattr(cls, name, _log_method(method, cls.__name__, logger))

    return cls


def _log_method(method, class_name, logger):
    """Helper to log individual methods."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()

        logger.debug(
            "method_called",
            class_name=class_name,
            method=method.__name__,
            correlation_id=get_correlation_id(),
        )

        try:
            result = method(self, *args, **kwargs)

            duration_ms = (time.time() - start_time) * 1000

            logger.debug(
                "method_completed",
                class_name=class_name,
                method=method.__name__,
                duration_ms=duration_ms,
                correlation_id=get_correlation_id(),
            )

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            logger.error(
                "method_failed",
                class_name=class_name,
                method=method.__name__,
                duration_ms=duration_ms,
                error=str(e),
                error_type=e.__class__.__name__,
                correlation_id=get_correlation_id(),
            )
            raise

    return wrapper


# Performance monitoring utilities
class PerformanceMonitor:
    """Singleton for collecting performance metrics."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._metrics = {}
            cls._instance.logger = get_logger("performance.monitor")
        return cls._instance

    def record_metric(
        self, metric_name: str, value: float, unit: str = "ms", tags: dict[str, Any] = None
    ):
        """Record a performance metric."""
        if metric_name not in self._metrics:
            self._metrics[metric_name] = []

        metric_data = {"value": value, "unit": unit, "timestamp": time.time(), "tags": tags or {}}

        self._metrics[metric_name].append(metric_data)

        self.logger.debug(
            "metric_recorded",
            metric=metric_name,
            value=value,
            unit=unit,
            tags=tags,
            correlation_id=get_correlation_id(),
        )

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get summary of collected metrics."""
        summary = {}

        for metric_name, values in self._metrics.items():
            if values:
                metric_values = [v["value"] for v in values]
                summary[metric_name] = {
                    "count": len(metric_values),
                    "min": min(metric_values),
                    "max": max(metric_values),
                    "avg": sum(metric_values) / len(metric_values),
                    "last": metric_values[-1],
                }

        return summary

    def clear_metrics(self):
        """Clear all collected metrics."""
        self._metrics.clear()
        self.logger.info("metrics_cleared")


# Global performance monitor instance
performance_monitor = PerformanceMonitor()
