"""
ValidaHub Telemetry SDK

Comprehensive observability and business intelligence framework that transforms
raw operational data into strategic assets for marketplace intelligence.

Features:
- CloudEvents 1.0 compliant event emission
- Business and technical metrics collection
- Structured logging with correlation
- OpenTelemetry instrumentation
- Cost and revenue attribution
- Data quality monitoring
"""

from .emitter import TelemetryEmitter, emit_event, emit_metric, emit_span
from .envelope import CloudEventEnvelope, create_event
from .metrics import BusinessMetrics, TechnicalMetrics, get_metrics
from .sinks import ConsoleSink, PrometheusMetricsSink, RedisSink, S3Sink
from .spans import TracingSpan, get_tracer
from .validators import validate_cloudevents, validate_metrics

__version__ = "1.0.0"

# Re-export main interfaces
__all__ = [
    # Event handling
    "CloudEventEnvelope",
    "create_event", 
    "emit_event",
    
    # Metrics
    "BusinessMetrics",
    "TechnicalMetrics", 
    "get_metrics",
    "emit_metric",
    
    # Tracing
    "TracingSpan",
    "get_tracer",
    "emit_span",
    
    # Sinks
    "ConsoleSink",
    "RedisSink", 
    "S3Sink",
    "PrometheusMetricsSink",
    
    # Utilities
    "TelemetryEmitter",
    "validate_cloudevents",
    "validate_metrics",
]