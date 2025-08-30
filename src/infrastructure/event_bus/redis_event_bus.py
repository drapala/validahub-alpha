"""Redis-based EventBus implementation with comprehensive logging.

This module implements the EventBus port using Redis Streams
with full logging of event publishing and processing.
"""

import json
import time
from datetime import UTC, datetime
from typing import Any

from src.application.ports import EventBus
from src.infrastructure.logging.utilities import LoggingPort, log_event_publish

from shared.logging.context import get_correlation_id


class InMemoryEventBus(EventBus, LoggingPort):
    """
    In-memory implementation of EventBus for testing.
    Includes comprehensive logging of all event operations.
    """

    def __init__(self):
        """Initialize in-memory event bus with logging."""
        super().__init__(logger_name="infrastructure.event_bus")
        self._events: list[dict[str, Any]] = []
        self._subscribers: dict[str, list[callable]] = {}

        self._logger.info(
            "event_bus_initialized", implementation="in_memory", correlation_id=get_correlation_id()
        )

    def get_component_name(self) -> str:
        """Get component name for logging context."""
        return "EventBus"

    @log_event_publish
    def publish(self, event: "DomainEvent") -> None:
        """
        Publish domain event with detailed logging.

        Args:
            event: Domain event to publish
        """
        start_time = time.time()

        # Extract event metadata
        event_type = getattr(event, "type", "unknown")
        event_id = getattr(event, "id", "unknown")
        tenant_id = getattr(event, "tenant_id", None)
        subject = getattr(event, "subject", None)

        # Convert event to dictionary
        if hasattr(event, "__dict__"):
            event_data = event.__dict__.copy()
        elif hasattr(event, "_asdict"):
            event_data = event._asdict()
        else:
            event_data = {"data": str(event)}

        # Add metadata
        event_record = {
            "id": event_id,
            "type": event_type,
            "tenant_id": tenant_id,
            "subject": subject,
            "timestamp": datetime.now(UTC).isoformat(),
            "correlation_id": get_correlation_id(),
            "data": event_data,
        }

        # Store event
        self._events.append(event_record)

        # Log event stored
        self._logger.debug(
            "event_stored_in_bus",
            event_id=event_id,
            event_type=event_type,
            tenant_id=tenant_id,
            subject=subject,
            event_count=len(self._events),
            correlation_id=get_correlation_id(),
        )

        # Notify subscribers
        subscribers = self._subscribers.get(event_type, [])

        if subscribers:
            self._logger.info(
                "event_dispatching_to_subscribers",
                event_id=event_id,
                event_type=event_type,
                subscriber_count=len(subscribers),
                correlation_id=get_correlation_id(),
            )

            for subscriber in subscribers:
                try:
                    subscriber(event)

                    self._logger.debug(
                        "event_delivered_to_subscriber",
                        event_id=event_id,
                        event_type=event_type,
                        subscriber=(
                            subscriber.__name__
                            if hasattr(subscriber, "__name__")
                            else str(subscriber)
                        ),
                        correlation_id=get_correlation_id(),
                    )

                except Exception as e:
                    self._logger.error(
                        "event_subscriber_failed",
                        event_id=event_id,
                        event_type=event_type,
                        subscriber=(
                            subscriber.__name__
                            if hasattr(subscriber, "__name__")
                            else str(subscriber)
                        ),
                        error=str(e),
                        error_type=e.__class__.__name__,
                        correlation_id=get_correlation_id(),
                    )

        # Calculate total processing time
        duration_ms = (time.time() - start_time) * 1000

        # Log completion with metrics
        self._logger.info(
            "event_processing_completed",
            event_id=event_id,
            event_type=event_type,
            tenant_id=tenant_id,
            subscribers_notified=len(subscribers),
            duration_ms=duration_ms,
            total_events=len(self._events),
            correlation_id=get_correlation_id(),
        )

    def subscribe(self, event_type: str, handler: callable) -> None:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: Type of events to subscribe to
            handler: Callback function to handle events
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        self._subscribers[event_type].append(handler)

        self._logger.info(
            "event_subscription_added",
            event_type=event_type,
            handler=handler.__name__ if hasattr(handler, "__name__") else str(handler),
            total_subscribers=len(self._subscribers[event_type]),
            correlation_id=get_correlation_id(),
        )

    def get_events(self, tenant_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get stored events for monitoring/testing.

        Args:
            tenant_id: Optional tenant filter
            limit: Maximum number of events to return

        Returns:
            List of event records
        """
        start_time = time.time()

        if tenant_id:
            filtered_events = [e for e in self._events if e.get("tenant_id") == tenant_id]
        else:
            filtered_events = self._events

        # Apply limit
        result = filtered_events[-limit:] if len(filtered_events) > limit else filtered_events

        duration_ms = (time.time() - start_time) * 1000

        self._logger.info(
            "event_query_completed",
            tenant_id=tenant_id,
            total_events=len(self._events),
            filtered_events=len(filtered_events),
            returned_events=len(result),
            limit=limit,
            duration_ms=duration_ms,
            correlation_id=get_correlation_id(),
        )

        return result

    def get_stats(self) -> dict[str, Any]:
        """
        Get event bus statistics for monitoring.

        Returns:
            Dictionary with event bus stats
        """
        stats = {
            "total_events": len(self._events),
            "event_types": {},
            "events_by_tenant": {},
            "subscriber_count": sum(len(subs) for subs in self._subscribers.values()),
            "subscribed_types": list(self._subscribers.keys()),
        }

        # Calculate stats
        for event in self._events:
            event_type = event.get("type", "unknown")
            tenant_id = event.get("tenant_id", "unknown")

            stats["event_types"][event_type] = stats["event_types"].get(event_type, 0) + 1
            stats["events_by_tenant"][tenant_id] = stats["events_by_tenant"].get(tenant_id, 0) + 1

        self._logger.info("event_bus_stats", **stats, correlation_id=get_correlation_id())

        return stats


class RedisEventBus(EventBus, LoggingPort):
    """
    Redis Streams based EventBus implementation for production.
    Provides reliable event publishing with persistence and replay capabilities.
    """

    def __init__(self, redis_client, stream_key: str = "validahub:events"):
        """
        Initialize Redis event bus.

        Args:
            redis_client: Redis client instance
            stream_key: Redis stream key for events
        """
        super().__init__(logger_name="infrastructure.redis_event_bus")
        self._redis = redis_client
        self._stream_key = stream_key

        self._logger.info(
            "redis_event_bus_initialized",
            stream_key=stream_key,
            correlation_id=get_correlation_id(),
        )

    def get_component_name(self) -> str:
        """Get component name for logging context."""
        return "RedisEventBus"

    @log_event_publish
    def publish(self, event: "DomainEvent") -> None:
        """
        Publish domain event to Redis Stream.

        Args:
            event: Domain event to publish
        """
        start_time = time.time()

        # Extract event metadata
        event_type = getattr(event, "type", "unknown")
        event_id = getattr(event, "id", "unknown")
        tenant_id = getattr(event, "tenant_id", None)
        subject = getattr(event, "subject", None)

        # Serialize event
        if hasattr(event, "__dict__"):
            event_data = event.__dict__.copy()
        elif hasattr(event, "_asdict"):
            event_data = event._asdict()
        else:
            event_data = {"data": str(event)}

        # Create Redis stream entry
        stream_data = {
            "event_id": event_id,
            "event_type": event_type,
            "tenant_id": tenant_id or "",
            "subject": subject or "",
            "correlation_id": get_correlation_id(),
            "timestamp": datetime.now(UTC).isoformat(),
            "data": json.dumps(event_data),
        }

        try:
            # Add to Redis stream
            message_id = self._redis.xadd(self._stream_key, stream_data)

            duration_ms = (time.time() - start_time) * 1000

            self._logger.info(
                "event_published_to_redis",
                event_id=event_id,
                event_type=event_type,
                tenant_id=tenant_id,
                subject=subject,
                message_id=message_id,
                stream_key=self._stream_key,
                duration_ms=duration_ms,
                correlation_id=get_correlation_id(),
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            self._logger.error(
                "event_publish_to_redis_failed",
                event_id=event_id,
                event_type=event_type,
                tenant_id=tenant_id,
                stream_key=self._stream_key,
                duration_ms=duration_ms,
                error=str(e),
                error_type=e.__class__.__name__,
                correlation_id=get_correlation_id(),
            )
            raise
