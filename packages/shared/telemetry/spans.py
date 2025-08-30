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
    class MockSpanType:
        def set_attributes(self, attributes: dict[str, Any]) -> None: pass
        def set_attribute(self, key: str, value: Any) -> None: pass
        def record_exception(self, exception: Exception) -> None: pass
        def set_status(self, status: Any) -> None: pass
        def __enter__(self) -> "MockSpanType": return self
        def __exit__(self, *args: Any) -> None: pass
    
    class MockTracerType:
        def start_span(self, name: str) -> "MockSpan": return MockSpan(name)
    
    class MockStatus:
        ERROR = "ERROR"
        OK = "OK"
    
    class MockStatusCode:
        ERROR = "ERROR" 
        OK = "OK"
    
    # Assign mock types to the expected names
    Span = MockSpanType  # type: ignore
    Status = MockStatus  # type: ignore  
    StatusCode = MockStatusCode  # type: ignore
    Tracer = MockTracerType  # type: ignore


class MockSpan(MockSpanType):
    """Mock span for when OpenTelemetry is not available."""
    def __init__(self, name: str):
        self.name = name


class TracingSpan:
    """Wrapper for OpenTelemetry spans with ValidaHub-specific features."""
    
    def __init__(self, span: Any, operation_name: str) -> None:
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


def get_tracer(name: str = "validahub") -> Tracer | MockTracerType:
    """Get OpenTelemetry tracer."""
    if OTEL_AVAILABLE:
        return trace.get_tracer(name)
    else:
        return MockTracerType()


@contextmanager
def trace_operation(
    operation_name: str,
    attributes: dict[str, Any] | None = None,
    tracer_name: str = "validahub"
) -> Any:
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