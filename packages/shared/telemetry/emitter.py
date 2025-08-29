"""
Centralized telemetry emitter for events, metrics, and spans.

This module provides the main interface for emitting telemetry data
from anywhere in the ValidaHub application.
"""

import asyncio
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from .envelope import (
    CloudEventEnvelope,
    create_business_event,
    create_event,
    create_technical_event,
)
from .metrics import BusinessMetrics, MarketplaceIntelligenceMetrics, TechnicalMetrics, get_metrics
from .sinks import TelemetrySink, get_default_sinks
from .spans import get_tracer

try:
    from packages.shared.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)


class TelemetryEmitter:
    """
    Central telemetry emission coordinating events, metrics, and tracing.
    
    This class provides a unified interface for all telemetry data,
    ensuring consistent correlation, sampling, and routing to appropriate sinks.
    """
    
    def __init__(
        self,
        sinks: list[TelemetrySink] | None = None,
        enable_sampling: bool = True,
        success_sample_rate: float = 0.1,  # 10% sampling for successful operations
        error_sample_rate: float = 1.0,    # 100% sampling for errors
    ):
        self.logger = get_logger("telemetry.emitter")
        self.sinks = sinks or get_default_sinks()
        self.enable_sampling = enable_sampling
        self.success_sample_rate = success_sample_rate
        self.error_sample_rate = error_sample_rate
        
        # Metrics collectors
        metrics_collector = get_metrics()
        self.business_metrics = BusinessMetrics(metrics_collector)
        self.technical_metrics = TechnicalMetrics(metrics_collector)
        self.marketplace_metrics = MarketplaceIntelligenceMetrics(metrics_collector)
        
        # Tracing
        self.tracer = get_tracer("validahub.telemetry")
        
        # Internal metrics
        self._events_emitted = 0
        self._metrics_emitted = 0
        self._spans_created = 0
    
    async def emit_event(
        self,
        event: CloudEventEnvelope,
        force_emit: bool = False
    ) -> bool:
        """
        Emit a CloudEvent to all configured sinks.
        
        Args:
            event: CloudEvent to emit
            force_emit: Skip sampling and emit regardless
            
        Returns:
            True if event was emitted, False if sampled out
        """
        # Apply sampling unless forced
        if not force_emit and self.enable_sampling:
            is_error_event = self._is_error_event(event)
            sample_rate = self.error_sample_rate if is_error_event else self.success_sample_rate
            
            if not self._should_sample(sample_rate):
                return False
        
        # Enrich event with telemetry metadata
        enriched_event = self._enrich_event(event)
        
        # Emit to all sinks
        emit_tasks = []
        for sink in self.sinks:
            task = asyncio.create_task(self._emit_to_sink(sink, enriched_event))
            emit_tasks.append(task)
        
        # Wait for all emissions to complete
        results = await asyncio.gather(*emit_tasks, return_exceptions=True)
        
        # Check for failures
        failed_sinks = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_sinks.append(self.sinks[i].__class__.__name__)
                self.logger.error(
                    "sink_emission_failed",
                    sink=self.sinks[i].__class__.__name__,
                    event_type=event.type,
                    event_id=event.id,
                    error=str(result)
                )
        
        # Track emission metrics
        self._events_emitted += 1
        self.technical_metrics.collector.increment(
            "telemetry_events_emitted_total",
            1.0,
            {
                "event_type": event.type,
                "sampled": str(not force_emit).lower(),
                "failed_sinks": str(len(failed_sinks)),
            }
        )
        
        # Log successful emission
        if not failed_sinks:
            self.logger.debug(
                "event_emitted_successfully",
                event_type=event.type,
                event_id=event.id,
                sink_count=len(self.sinks)
            )
        
        return True
    
    def emit_metric(
        self,
        name: str,
        value: int | float,
        metric_type: str = "histogram",
        tags: dict[str, str] | None = None,
        force_emit: bool = False
    ) -> None:
        """
        Emit a metric value.
        
        Args:
            name: Metric name
            value: Metric value
            metric_type: Type of metric (counter, histogram, gauge)
            tags: Optional tags
            force_emit: Skip sampling
        """
        # Apply sampling unless forced
        if not force_emit and self.enable_sampling:
            # Use success rate for metrics (they're generally not errors)
            if not self._should_sample(self.success_sample_rate):
                return
        
        # Emit via metrics collector
        collector = get_metrics()
        tags = tags or {}
        
        if metric_type == "counter":
            collector.increment(name, value, tags)
        elif metric_type == "histogram":
            collector.histogram(name, value, tags)
        elif metric_type == "gauge":
            collector.gauge(name, value, tags)
        else:
            self.logger.warning(f"Unknown metric type: {metric_type}")
            return
        
        self._metrics_emitted += 1
        
        self.logger.debug(
            "metric_emitted",
            name=name,
            value=value,
            metric_type=metric_type,
            tags=tags
        )
    
    @contextmanager
    def span(
        self,
        operation_name: str,
        tags: dict[str, str] | None = None,
        emit_event_on_completion: bool = False,
        event_type: str | None = None
    ):
        """
        Create a tracing span with optional event emission on completion.
        
        Args:
            operation_name: Name of the operation being traced
            tags: Optional span tags
            emit_event_on_completion: Whether to emit an event when span completes
            event_type: CloudEvent type to emit (defaults to 'span.completed')
        """
        span_start_time = time.time()
        
        with self.tracer.start_span(operation_name) as span:
            if tags:
                span.set_attributes(tags)
            
            try:
                self._spans_created += 1
                yield span
                
                # Emit completion event if requested
                if emit_event_on_completion:
                    duration_ms = (time.time() - span_start_time) * 1000
                    completion_event = create_technical_event(
                        event_type or "span.completed",
                        {
                            "operation_name": operation_name,
                            "duration_ms": duration_ms,
                            "success": True,
                        },
                        performance_metrics={"duration_ms": duration_ms},
                        source="packages/shared/telemetry"
                    )
                    
                    # Use asyncio.create_task to emit without blocking
                    asyncio.create_task(self.emit_event(completion_event))
                    
            except Exception as error:
                span.record_exception(error)
                span.set_attribute("error", True)
                
                # Emit error event if requested
                if emit_event_on_completion:
                    duration_ms = (time.time() - span_start_time) * 1000
                    error_event = create_technical_event(
                        "span.failed",
                        {
                            "operation_name": operation_name,
                            "duration_ms": duration_ms,
                            "success": False,
                            "error_type": error.__class__.__name__,
                            "error_message": str(error),
                        },
                        performance_metrics={"duration_ms": duration_ms},
                        source="packages/shared/telemetry"
                    )
                    
                    # Force emit errors
                    asyncio.create_task(self.emit_event(error_event, force_emit=True))
                
                raise
    
    def track_business_event(
        self,
        event_type: str,
        business_data: dict[str, Any],
        revenue_impact_brl: float | None = None,
        cost_impact_brl: float | None = None,
        tenant_id: str | None = None,
        actor_id: str | None = None
    ) -> None:
        """
        Track business events with automatic revenue/cost attribution.
        
        This is a high-level method that combines event emission with
        business metrics tracking for comprehensive BI coverage.
        """
        # Create business event
        event = create_business_event(
            event_type=event_type,
            business_data=business_data,
            revenue_impact=revenue_impact_brl,
            cost_impact=cost_impact_brl,
            tenant_id=tenant_id,
            actor_id=actor_id,
            source="business.tracker"
        )
        
        # Emit event (force emit for business events)
        asyncio.create_task(self.emit_event(event, force_emit=True))
        
        # Track metrics if revenue/cost provided
        if revenue_impact_brl is not None and tenant_id:
            channel = business_data.get("channel", "unknown")
            job_type = business_data.get("job_type", "unknown")
            
            self.business_metrics.track_revenue_attribution(
                amount_brl=revenue_impact_brl,
                tenant_id=tenant_id,
                channel=channel,
                job_type=job_type,
                seller_id=actor_id
            )
        
        if cost_impact_brl is not None and tenant_id:
            channel = business_data.get("channel", "unknown")
            job_type = business_data.get("job_type", "unknown")
            
            self.business_metrics.track_cost_attribution(
                cost_brl=cost_impact_brl,
                tenant_id=tenant_id,
                channel=channel,
                job_type=job_type
            )
    
    def track_job_lifecycle(
        self,
        job_id: str,
        tenant_id: str,
        channel: str,
        job_type: str,
        old_status: str | None,
        new_status: str,
        duration_seconds: float | None = None,
        error_count: int = 0,
        warning_count: int = 0,
        total_records: int = 0,
        revenue_attribution_brl: float | None = None
    ) -> None:
        """
        Track complete job lifecycle with events and metrics.
        
        This method provides comprehensive tracking for job state transitions,
        automatically emitting appropriate events and updating all relevant metrics.
        """
        # Create status transition event
        event_data = {
            "job_id": job_id,
            "old_status": old_status,
            "new_status": new_status,
            "channel": channel,
            "job_type": job_type,
            "error_count": error_count,
            "warning_count": warning_count,
            "total_records": total_records,
        }
        
        if duration_seconds:
            event_data["duration_seconds"] = duration_seconds
        
        # Determine event type based on status
        event_type_map = {
            "queued": "job.submitted",
            "running": "job.started", 
            "succeeded": "job.succeeded",
            "failed": "job.failed",
            "cancelled": "job.cancelled",
            "expired": "job.expired",
            "retrying": "job.retried",
        }
        
        event_type = event_type_map.get(new_status, "job.status_changed")
        
        # Create and emit event
        event = create_event(
            event_type=event_type,
            data=event_data,
            subject=f"job:{job_id}",
            source="job.lifecycle",
            tenant_id=tenant_id
        )
        
        # Force emit job lifecycle events
        asyncio.create_task(self.emit_event(event, force_emit=True))
        
        # Track technical metrics
        self.technical_metrics.track_job_lifecycle(
            job_id=job_id,
            tenant_id=tenant_id,
            channel=channel,
            job_type=job_type,
            status=new_status,
            duration_seconds=duration_seconds,
            error_count=error_count,
            warning_count=warning_count,
            total_records=total_records
        )
        
        # Track business metrics if revenue provided
        if revenue_attribution_brl and new_status == "succeeded":
            self.business_metrics.track_revenue_attribution(
                amount_brl=revenue_attribution_brl,
                tenant_id=tenant_id,
                channel=channel,
                job_type=job_type
            )
    
    def get_stats(self) -> dict[str, Any]:
        """Get telemetry emitter statistics."""
        return {
            "events_emitted": self._events_emitted,
            "metrics_emitted": self._metrics_emitted,
            "spans_created": self._spans_created,
            "sinks_configured": len(self.sinks),
            "sampling_enabled": self.enable_sampling,
            "success_sample_rate": self.success_sample_rate,
            "error_sample_rate": self.error_sample_rate,
        }
    
    async def _emit_to_sink(self, sink: TelemetrySink, event: CloudEventEnvelope) -> None:
        """Emit event to a specific sink."""
        try:
            await sink.emit(event)
        except Exception as error:
            # Log but don't re-raise to prevent one sink failure from affecting others
            self.logger.error(
                "sink_emission_error", 
                sink_type=sink.__class__.__name__,
                event_id=event.id,
                error=str(error)
            )
            raise  # Re-raise so caller can track failed sinks
    
    def _enrich_event(self, event: CloudEventEnvelope) -> CloudEventEnvelope:
        """Enrich event with telemetry metadata."""
        enrichment_data = {
            "_emitted_at": datetime.now(UTC).isoformat(),
            "_emitter_version": "1.0.0",
        }
        
        return event.enrich_for_bi(**enrichment_data)
    
    def _is_error_event(self, event: CloudEventEnvelope) -> bool:
        """Check if event represents an error condition."""
        error_types = ["failed", "error", "exception", "cancelled", "expired"]
        return any(error_type in event.type.lower() for error_type in error_types)
    
    def _should_sample(self, sample_rate: float) -> bool:
        """Determine if event should be sampled based on rate."""
        if sample_rate >= 1.0:
            return True
        if sample_rate <= 0.0:
            return False
        
        import random
        return random.random() < sample_rate


# Global emitter instance
_emitter: TelemetryEmitter | None = None


def get_emitter() -> TelemetryEmitter:
    """Get the global telemetry emitter."""
    global _emitter
    if _emitter is None:
        _emitter = TelemetryEmitter()
    return _emitter


def set_emitter(emitter: TelemetryEmitter) -> None:
    """Set a custom telemetry emitter."""
    global _emitter
    _emitter = emitter


# Convenience functions for common operations
async def emit_event(event: CloudEventEnvelope, force_emit: bool = False) -> bool:
    """Emit a CloudEvent using the global emitter."""
    return await get_emitter().emit_event(event, force_emit)


def emit_metric(
    name: str,
    value: int | float,
    metric_type: str = "histogram",
    tags: dict[str, str] | None = None,
    force_emit: bool = False
) -> None:
    """Emit a metric using the global emitter."""
    get_emitter().emit_metric(name, value, metric_type, tags, force_emit)


def emit_span(
    operation_name: str,
    tags: dict[str, str] | None = None,
    emit_event_on_completion: bool = False,
    event_type: str | None = None
):
    """Create a span using the global emitter."""
    return get_emitter().span(operation_name, tags, emit_event_on_completion, event_type)


def track_business_event(
    event_type: str,
    business_data: dict[str, Any],
    revenue_impact_brl: float | None = None,
    cost_impact_brl: float | None = None,
    tenant_id: str | None = None,
    actor_id: str | None = None
) -> None:
    """Track business event using the global emitter."""
    get_emitter().track_business_event(
        event_type, business_data, revenue_impact_brl, cost_impact_brl, tenant_id, actor_id
    )


def track_job_lifecycle(
    job_id: str,
    tenant_id: str,
    channel: str,
    job_type: str,
    old_status: str | None,
    new_status: str,
    duration_seconds: float | None = None,
    error_count: int = 0,
    warning_count: int = 0,
    total_records: int = 0,
    revenue_attribution_brl: float | None = None
) -> None:
    """Track job lifecycle using the global emitter."""
    get_emitter().track_job_lifecycle(
        job_id, tenant_id, channel, job_type, old_status, new_status,
        duration_seconds, error_count, warning_count, total_records, revenue_attribution_brl
    )