"""
OpenTelemetry tracing spans for distributed tracing.
"""

import time
from contextlib import contextmanager
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.trace import Span, Status, StatusCode, Tracer
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    
    # Mock classes when OpenTelemetry is not available
    class Span:
        def set_attributes(self, attributes): pass
        def set_attribute(self, key, value): pass
        def record_exception(self, exception): pass
        def set_status(self, status): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
    
    class Tracer:
        def start_span(self, name): return MockSpan(name)
    
    class Status:
        ERROR = "ERROR"
        OK = "OK"
    
    class StatusCode:
        ERROR = "ERROR" 
        OK = "OK"


class MockSpan(Span):
    """Mock span for when OpenTelemetry is not available."""
    def __init__(self, name: str):
        self.name = name


class TracingSpan:
    """Wrapper for OpenTelemetry spans with ValidaHub-specific features."""
    
    def __init__(self, span: Span, operation_name: str):
        self.span = span
        self.operation_name = operation_name
        self.start_time = time.time()
    
    def set_attributes(self, attributes: dict[str, Any]) -> None:
        """Set multiple attributes on the span."""
        if OTEL_AVAILABLE:
            self.span.set_attributes(attributes)
    
    def set_attribute(self, key: str, value: Any) -> None:
        """Set a single attribute on the span.""" 
        if OTEL_AVAILABLE:
            self.span.set_attribute(key, value)
    
    def record_exception(self, exception: Exception) -> None:
        """Record an exception on the span."""
        if OTEL_AVAILABLE:
            self.span.record_exception(exception)
            self.span.set_status(Status(StatusCode.ERROR))
    
    def set_success(self) -> None:
        """Mark span as successful."""
        if OTEL_AVAILABLE:
            self.span.set_status(Status(StatusCode.OK))
    
    def set_error(self, error_message: str) -> None:
        """Mark span as failed with error message."""
        if OTEL_AVAILABLE:
            self.span.set_attribute("error.message", error_message)
            self.span.set_status(Status(StatusCode.ERROR))
    
    def get_duration_ms(self) -> float:
        """Get span duration in milliseconds."""
        return (time.time() - self.start_time) * 1000


def get_tracer(name: str = "validahub") -> Tracer:
    """Get OpenTelemetry tracer."""
    if OTEL_AVAILABLE:
        return trace.get_tracer(name)
    else:
        return Tracer()


@contextmanager
def trace_operation(
    operation_name: str,
    attributes: dict[str, Any] | None = None,
    tracer_name: str = "validahub"
):
    """
    Context manager for tracing operations.
    
    Usage:
        with trace_operation("job.processing", {"job_id": "123"}):
            # Do work
            pass
    """
    tracer = get_tracer(tracer_name)
    
    with tracer.start_span(operation_name) as span:
        wrapped_span = TracingSpan(span, operation_name)
        
        if attributes:
            wrapped_span.set_attributes(attributes)
        
        try:
            yield wrapped_span
            wrapped_span.set_success()
        except Exception as error:
            wrapped_span.record_exception(error)
            raise