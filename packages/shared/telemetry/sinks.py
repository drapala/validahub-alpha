"""
Telemetry sinks for routing events to different destinations.

Sinks are responsible for delivering CloudEvents to various systems:
- ConsoleSink: Development and debugging
- RedisSink: Real-time streaming and notifications  
- S3Sink: Long-term storage for BI and analytics
- PrometheusMetricsSink: Metrics aggregation and alerting
"""

import asyncio
import json
import urllib.parse
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from .envelope import CloudEventEnvelope

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

try:
    from packages.shared.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)


class TelemetrySink(ABC):
    """Abstract base class for telemetry sinks."""
    
    @abstractmethod
    async def emit(self, event: CloudEventEnvelope) -> None:
        """Emit a CloudEvent to this sink."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close sink and cleanup resources."""
        pass


class ConsoleSink(TelemetrySink):
    """
    Console sink for development and debugging.
    
    Outputs structured JSON events to stdout with optional filtering
    and formatting for better development experience.
    """
    
    def __init__(
        self,
        pretty_print: bool = True,
        filter_types: list[str] | None = None,
        max_data_length: int = 1000
    ):
        self.logger = get_logger("telemetry.console_sink")
        self.pretty_print = pretty_print
        self.filter_types = set(filter_types or [])
        self.max_data_length = max_data_length
        self.events_emitted = 0
    
    async def emit(self, event: CloudEventEnvelope) -> None:
        """Emit event to console."""
        # Apply type filtering
        if self.filter_types and event.type not in self.filter_types:
            return
        
        # Prepare event for display
        display_event = self._prepare_for_display(event)
        
        if self.pretty_print:
            output = json.dumps(display_event, indent=2, ensure_ascii=False)
        else:
            output = json.dumps(display_event, ensure_ascii=False)
        
        print(f"📡 CloudEvent: {output}")
        
        self.events_emitted += 1
        
        # Log emission (at debug level to avoid noise)
        self.logger.debug(
            "event_emitted_to_console",
            event_type=event.type,
            event_id=event.id,
            tenant_id=event.validahub_tenant_id
        )
    
    async def close(self) -> None:
        """Console sink has no resources to cleanup."""
        self.logger.info(
            "console_sink_closed",
            total_events_emitted=self.events_emitted
        )
    
    def _prepare_for_display(self, event: CloudEventEnvelope) -> dict[str, Any]:
        """Prepare event for console display with truncation."""
        display_data = event.to_dict()
        
        # Truncate large data payloads for readability
        if "data" in display_data and isinstance(display_data["data"], dict):
            data_str = json.dumps(display_data["data"])
            if len(data_str) > self.max_data_length:
                display_data["data"] = {
                    "_truncated": True,
                    "_original_length": len(data_str),
                    "_preview": data_str[:self.max_data_length],
                }
        
        return display_data


class RedisSink(TelemetrySink):
    """
    Redis sink for real-time event streaming.
    
    Publishes events to Redis streams for real-time consumption by
    dashboards, notifications, and other real-time systems.
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        stream_key_template: str = "validahub:events:{tenant_id}",
        max_stream_length: int = 10000,
        connection_pool_size: int = 10
    ):
        if not REDIS_AVAILABLE:
            raise RuntimeError("Redis not available - install redis[async] package")
        
        self.logger = get_logger("telemetry.redis_sink")
        self.redis_url = redis_url
        self.stream_key_template = stream_key_template
        self.max_stream_length = max_stream_length
        
        # Initialize connection pool
        self.connection_pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=connection_pool_size,
            retry_on_timeout=True
        )
        self.redis_client = redis.Redis(connection_pool=self.connection_pool)
        
        self.events_emitted = 0
        self.connection_errors = 0
    
    async def emit(self, event: CloudEventEnvelope) -> None:
        """Emit event to Redis stream."""
        try:
            # Determine stream key
            stream_key = self.stream_key_template.format(
                tenant_id=event.validahub_tenant_id or "global"
            )
            
            # Prepare event data
            event_data = {
                "event": json.dumps(event.to_dict()),
                "type": event.type,
                "tenant_id": event.validahub_tenant_id or "",
                "emitted_at": datetime.now(UTC).isoformat(),
            }
            
            # Add to Redis stream with length limit
            await self.redis_client.xadd(
                stream_key,
                event_data,
                maxlen=self.max_stream_length,
                approximate=True
            )
            
            self.events_emitted += 1
            
            self.logger.debug(
                "event_emitted_to_redis",
                stream_key=stream_key,
                event_type=event.type,
                event_id=event.id
            )
            
        except redis.RedisError as error:
            self.connection_errors += 1
            self.logger.error(
                "redis_emission_failed",
                event_type=event.type,
                event_id=event.id,
                error=str(error),
                error_type=error.__class__.__name__
            )
            raise
    
    async def close(self) -> None:
        """Close Redis connections."""
        if self.redis_client:
            await self.redis_client.close()
        if self.connection_pool:
            await self.connection_pool.disconnect()
        
        self.logger.info(
            "redis_sink_closed",
            total_events_emitted=self.events_emitted,
            connection_errors=self.connection_errors
        )
    
    async def get_stream_info(self, tenant_id: str) -> dict[str, Any]:
        """Get information about a tenant's event stream."""
        stream_key = self.stream_key_template.format(tenant_id=tenant_id)
        
        try:
            info = await self.redis_client.xinfo_stream(stream_key)
            return {
                "stream_key": stream_key,
                "length": info.get("length", 0),
                "first_entry_id": info.get("first-entry", [None])[0],
                "last_entry_id": info.get("last-entry", [None])[0],
            }
        except redis.ResponseError:
            return {"stream_key": stream_key, "length": 0}


class S3Sink(TelemetrySink):
    """
    S3 sink for long-term event storage and BI analytics.
    
    Stores events in partitioned NDJSON format optimized for analytics:
    s3://bucket/events/type=job.succeeded/dt=2025-08-29/tenant_id=t_123/events.ndjson
    """
    
    def __init__(
        self,
        bucket_name: str,
        key_template: str = "events/type={event_type}/dt={date}/tenant_id={tenant_id}/{hour}.ndjson",
        aws_region: str = "us-east-1",
        buffer_size: int = 100,
        flush_interval_seconds: int = 60
    ):
        if not S3_AVAILABLE:
            raise RuntimeError("AWS S3 not available - install boto3 package")
        
        self.logger = get_logger("telemetry.s3_sink")
        self.bucket_name = bucket_name
        self.key_template = key_template
        self.buffer_size = buffer_size
        self.flush_interval_seconds = flush_interval_seconds
        
        # Initialize S3 client
        self.s3_client = boto3.client("s3", region_name=aws_region)
        
        # Event buffering for batched uploads
        self.buffer: list[CloudEventEnvelope] = []
        self.last_flush_time = datetime.now(UTC)
        self.flush_lock = asyncio.Lock()
        
        self.events_emitted = 0
        self.upload_errors = 0
        
        # Start background flush task
        self.flush_task = asyncio.create_task(self._background_flush())
    
    async def emit(self, event: CloudEventEnvelope) -> None:
        """Buffer event for batched S3 upload."""
        async with self.flush_lock:
            self.buffer.append(event)
            
            # Flush if buffer is full
            if len(self.buffer) >= self.buffer_size:
                await self._flush_buffer()
    
    async def close(self) -> None:
        """Close S3 sink and flush remaining events."""
        # Cancel background flush task
        if self.flush_task:
            self.flush_task.cancel()
            try:
                await self.flush_task
            except asyncio.CancelledError:
                pass
        
        # Flush remaining events
        if self.buffer:
            await self._flush_buffer()
        
        self.logger.info(
            "s3_sink_closed",
            total_events_emitted=self.events_emitted,
            upload_errors=self.upload_errors
        )
    
    async def _background_flush(self) -> None:
        """Background task to flush events periodically."""
        try:
            while True:
                await asyncio.sleep(self.flush_interval_seconds)
                
                # Check if flush is needed
                now = datetime.now(UTC)
                time_since_flush = (now - self.last_flush_time).total_seconds()
                
                if self.buffer and time_since_flush >= self.flush_interval_seconds:
                    async with self.flush_lock:
                        await self._flush_buffer()
                        
        except asyncio.CancelledError:
            self.logger.debug("background_flush_cancelled")
            raise
    
    async def _flush_buffer(self) -> None:
        """Flush buffered events to S3."""
        if not self.buffer:
            return
        
        try:
            # Group events by partition key
            partitions: dict[str, list[CloudEventEnvelope]] = {}
            
            for event in self.buffer:
                partition_key = self._get_partition_key(event)
                if partition_key not in partitions:
                    partitions[partition_key] = []
                partitions[partition_key].append(event)
            
            # Upload each partition
            upload_tasks = []
            for partition_key, events in partitions.items():
                task = self._upload_partition(partition_key, events)
                upload_tasks.append(task)
            
            # Wait for all uploads
            results = await asyncio.gather(*upload_tasks, return_exceptions=True)
            
            # Check for errors
            successful_uploads = 0
            for result in results:
                if isinstance(result, Exception):
                    self.upload_errors += 1
                    self.logger.error(
                        "s3_upload_failed",
                        error=str(result),
                        error_type=result.__class__.__name__
                    )
                else:
                    successful_uploads += 1
            
            # Clear buffer and update stats
            events_flushed = len(self.buffer)
            self.buffer.clear()
            self.events_emitted += events_flushed
            self.last_flush_time = datetime.now(UTC)
            
            self.logger.debug(
                "s3_buffer_flushed",
                events_flushed=events_flushed,
                partitions=len(partitions),
                successful_uploads=successful_uploads,
                failed_uploads=len(results) - successful_uploads
            )
            
        except Exception as error:
            self.upload_errors += 1
            self.logger.error(
                "s3_flush_failed",
                buffer_size=len(self.buffer),
                error=str(error),
                error_type=error.__class__.__name__
            )
            # Don't clear buffer on error - retry on next flush
            raise
    
    async def _upload_partition(self, partition_key: str, events: list[CloudEventEnvelope]) -> None:
        """Upload events for a single partition."""
        # Create NDJSON content
        ndjson_lines = [event.to_ndjson() for event in events]
        ndjson_content = "".join(ndjson_lines)
        
        try:
            # Upload to S3
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=partition_key,
                    Body=ndjson_content.encode("utf-8"),
                    ContentType="application/x-ndjson",
                    Metadata={
                        "event_count": str(len(events)),
                        "upload_timestamp": datetime.now(UTC).isoformat(),
                    }
                )
            )
            
        except ClientError as error:
            self.logger.error(
                "s3_upload_error",
                partition_key=partition_key,
                event_count=len(events),
                error_code=error.response.get("Error", {}).get("Code"),
                error_message=error.response.get("Error", {}).get("Message")
            )
            raise
    
    def _get_partition_key(self, event: CloudEventEnvelope) -> str:
        """Generate S3 partition key for event."""
        event_time = datetime.fromisoformat(event.time.replace("Z", "+00:00"))
        
        # URL encode event type for safe S3 key
        safe_event_type = urllib.parse.quote_plus(event.type.replace(".", "_"))
        
        return self.key_template.format(
            event_type=safe_event_type,
            date=event_time.strftime("%Y-%m-%d"),
            hour=event_time.strftime("%H"),
            tenant_id=event.validahub_tenant_id or "global"
        )


class PrometheusMetricsSink(TelemetrySink):
    """
    Prometheus metrics sink for extracting metrics from events.
    
    Analyzes CloudEvents and extracts relevant metrics for Prometheus
    monitoring and alerting.
    """
    
    def __init__(self, enable_histogram_extraction: bool = True):
        self.logger = get_logger("telemetry.prometheus_sink")
        self.enable_histogram_extraction = enable_histogram_extraction
        self.events_processed = 0
        self.metrics_extracted = 0
        
        # Import metrics collector
        from .metrics import get_metrics
        self.metrics_collector = get_metrics()
    
    async def emit(self, event: CloudEventEnvelope) -> None:
        """Extract metrics from CloudEvent."""
        try:
            # Extract basic event metrics
            self._extract_basic_metrics(event)
            
            # Extract event-specific metrics
            await self._extract_event_specific_metrics(event)
            
            self.events_processed += 1
            
        except Exception as error:
            self.logger.error(
                "prometheus_metric_extraction_failed",
                event_type=event.type,
                event_id=event.id,
                error=str(error)
            )
    
    async def close(self) -> None:
        """Prometheus sink has no resources to cleanup."""
        self.logger.info(
            "prometheus_sink_closed",
            events_processed=self.events_processed,
            metrics_extracted=self.metrics_extracted
        )
    
    def _extract_basic_metrics(self, event: CloudEventEnvelope) -> None:
        """Extract basic metrics from all events."""
        tags = {
            "event_type": event.type,
            "source": event.source,
        }
        
        if event.validahub_tenant_id:
            tags["tenant_id"] = event.validahub_tenant_id
        
        # Count events by type
        self.metrics_collector.increment("cloudevents_total", 1.0, tags)
        self.metrics_extracted += 1
    
    async def _extract_event_specific_metrics(self, event: CloudEventEnvelope) -> None:
        """Extract event-specific metrics based on event type."""
        if not event.data:
            return
        
        # Job-related events
        if event.type.startswith("job."):
            await self._extract_job_metrics(event)
        
        # API-related events  
        elif event.type.startswith("api."):
            await self._extract_api_metrics(event)
        
        # Business events
        elif event.data.get("_event_category") == "business":
            await self._extract_business_metrics(event)
    
    async def _extract_job_metrics(self, event: CloudEventEnvelope) -> None:
        """Extract job-specific metrics."""
        data = event.data
        
        base_tags = {
            "tenant_id": event.validahub_tenant_id or "unknown",
            "channel": data.get("channel", "unknown"),
            "job_type": data.get("job_type", "unknown"),
        }
        
        # Job duration metrics
        if "duration_seconds" in data and self.enable_histogram_extraction:
            self.metrics_collector.histogram(
                "job_duration_seconds", 
                data["duration_seconds"], 
                base_tags
            )
            self.metrics_extracted += 1
        
        # Error and warning counts
        if "error_count" in data:
            self.metrics_collector.histogram(
                "job_error_count",
                data["error_count"],
                base_tags
            )
            self.metrics_extracted += 1
        
        if "warning_count" in data:
            self.metrics_collector.histogram(
                "job_warning_count", 
                data["warning_count"],
                base_tags
            )
            self.metrics_extracted += 1
    
    async def _extract_api_metrics(self, event: CloudEventEnvelope) -> None:
        """Extract API-specific metrics."""
        data = event.data
        
        if "duration_ms" in data and self.enable_histogram_extraction:
            tags = {
                "endpoint": data.get("endpoint", "unknown"),
                "method": data.get("method", "unknown"),
                "status": str(data.get("status_code", 0)),
            }
            
            if event.validahub_tenant_id:
                tags["tenant_id"] = event.validahub_tenant_id
            
            self.metrics_collector.histogram(
                "api_request_duration_ms",
                data["duration_ms"],
                tags
            )
            self.metrics_extracted += 1
    
    async def _extract_business_metrics(self, event: CloudEventEnvelope) -> None:
        """Extract business intelligence metrics."""
        data = event.data
        
        base_tags = {
            "tenant_id": event.validahub_tenant_id or "unknown",
        }
        
        # Revenue metrics
        if "_revenue_impact_brl" in data:
            self.metrics_collector.histogram(
                "business_revenue_impact_brl",
                data["_revenue_impact_brl"],
                base_tags
            )
            self.metrics_extracted += 1
        
        # Cost metrics
        if "_cost_impact_brl" in data:
            self.metrics_collector.histogram(
                "business_cost_impact_brl",
                data["_cost_impact_brl"], 
                base_tags
            )
            self.metrics_extracted += 1


def get_default_sinks() -> list[TelemetrySink]:
    """Get default sinks for telemetry emission."""
    sinks = []
    
    # Always include console sink for development
    sinks.append(ConsoleSink(pretty_print=True))
    
    # Add Redis sink if available
    if REDIS_AVAILABLE:
        try:
            sinks.append(RedisSink())
        except Exception as error:
            logger = get_logger("telemetry.sinks")
            logger.warning("redis_sink_unavailable", error=str(error))
    
    # Add Prometheus metrics sink
    sinks.append(PrometheusMetricsSink())
    
    return sinks