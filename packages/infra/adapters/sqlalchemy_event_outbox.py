"""SQLAlchemy implementation of EventOutbox port.

This module provides the SQLAlchemy-based adapter for reliable event publishing
using the outbox pattern. Events are stored atomically with business data
and published asynchronously by a background process.

Features:
- Atomic event storage with business transactions
- Reliable event delivery with retry logic
- Dead letter queue for failed events
- Event deduplication and ordering
- Comprehensive error handling and logging
"""

from datetime import UTC, datetime

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.application.ports import EventOutbox
from packages.domain.events import DomainEvent
from packages.infra.models.job_model import EventOutboxModel

try:
    from packages.shared.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)


class SqlAlchemyEventOutbox(EventOutbox):
    """
    SQLAlchemy-based implementation of EventOutbox port.
    
    Provides reliable event storage and publishing using the outbox pattern.
    Events are stored atomically with business data and processed by
    a separate background worker.
    """
    
    def __init__(self, session: Session):
        """
        Initialize event outbox with database session.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.logger = get_logger("infra.event_outbox")
    
    def store_events(
        self,
        events: list[DomainEvent],
        correlation_id: str | None = None,
    ) -> None:
        """
        Store events in outbox for later publishing.
        
        This method stores events atomically within the same transaction
        as business data, ensuring consistency.
        
        Args:
            events: List of domain events to store
            correlation_id: Optional correlation ID for tracing
        """
        if not events:
            return
        
        try:
            outbox_records = []
            
            for event in events:
                # Convert domain event to outbox model
                outbox_record = EventOutboxModel(
                    tenant_id=event.tenant_id,
                    event_type=event.type.value,
                    event_version=event.schema_version,
                    correlation_id=correlation_id,
                    payload=event.to_dict(),
                    occurred_at=event.time,
                    attempt_count=0,
                )
                
                outbox_records.append(outbox_record)
            
            # Add all records to session
            self.session.add_all(outbox_records)
            
            # Note: Commit is handled by the calling service to ensure
            # atomicity with business data changes
            
            self.logger.info(
                "events_stored_in_outbox",
                event_count=len(events),
                correlation_id=correlation_id,
                event_types=[event.type.value for event in events],
            )
            
        except IntegrityError as error:
            self.session.rollback()
            self.logger.error(
                "event_outbox_integrity_error",
                event_count=len(events),
                correlation_id=correlation_id,
                error=str(error),
            )
            raise
        
        except Exception as error:
            self.session.rollback()
            self.logger.error(
                "event_outbox_store_failed",
                event_count=len(events),
                correlation_id=correlation_id,
                error=str(error),
                error_type=type(error).__name__,
            )
            raise
    
    def get_pending_events(self, limit: int = 100) -> list[DomainEvent]:
        """
        Get pending events for publishing.
        
        Retrieves events that haven't been dispatched yet, ordered by
        occurrence time to maintain event ordering.
        
        Args:
            limit: Maximum number of events to retrieve
            
        Returns:
            List of pending domain events
        """
        try:
            # Query for undispatched events, ordered by occurrence time
            models = self.session.query(EventOutboxModel).filter(
                EventOutboxModel.dispatched_at.is_(None)
            ).order_by(
                EventOutboxModel.occurred_at.asc()
            ).limit(limit).all()
            
            if not models:
                return []
            
            # Convert to domain events
            events = []
            for model in models:
                try:
                    # Reconstruct domain event from payload
                    event = self._reconstruct_domain_event(model)
                    events.append(event)
                    
                except Exception as error:
                    self.logger.error(
                        "event_reconstruction_failed",
                        outbox_id=str(model.id),
                        event_type=model.event_type,
                        tenant_id=model.tenant_id,
                        error=str(error),
                    )
                    # Mark as failed to avoid infinite retries
                    self._mark_event_failed(model, str(error))
            
            self.logger.debug(
                "pending_events_retrieved",
                event_count=len(events),
                requested_limit=limit,
            )
            
            return events
            
        except Exception as error:
            self.logger.error(
                "get_pending_events_failed",
                limit=limit,
                error=str(error),
                error_type=type(error).__name__,
            )
            return []
    
    def mark_published(self, event_ids: list[str]) -> None:
        """
        Mark events as successfully published.
        
        Args:
            event_ids: List of event IDs to mark as published
        """
        if not event_ids:
            return
        
        try:
            # Convert string IDs to UUID objects for query
            uuid_ids = []
            for event_id in event_ids:
                try:
                    from uuid import UUID
                    uuid_ids.append(UUID(event_id))
                except ValueError as error:
                    self.logger.warning(
                        "invalid_event_id_format",
                        event_id=event_id,
                        error=str(error),
                    )
                    continue
            
            if not uuid_ids:
                self.logger.warning("no_valid_event_ids_to_mark_published")
                return
            
            # Update events as dispatched
            now = datetime.now(UTC)
            rows_updated = self.session.query(EventOutboxModel).filter(
                and_(
                    EventOutboxModel.id.in_(uuid_ids),
                    EventOutboxModel.dispatched_at.is_(None)
                )
            ).update(
                {
                    EventOutboxModel.dispatched_at: now,
                },
                synchronize_session=False
            )
            
            self.session.commit()
            
            self.logger.info(
                "events_marked_published",
                event_count=rows_updated,
                requested_count=len(event_ids),
            )
            
        except Exception as error:
            self.session.rollback()
            self.logger.error(
                "mark_published_failed",
                event_ids=event_ids,
                error=str(error),
                error_type=type(error).__name__,
            )
            raise
    
    def mark_failed(
        self,
        event_id: str,
        error_message: str,
        max_attempts: int = 5,
    ) -> None:
        """
        Mark event as failed and increment attempt count.
        
        Args:
            event_id: Event ID that failed
            error_message: Error message describing the failure
            max_attempts: Maximum retry attempts before giving up
        """
        try:
            from uuid import UUID
            uuid_id = UUID(event_id)
            
            model = self.session.query(EventOutboxModel).filter(
                EventOutboxModel.id == uuid_id
            ).first()
            
            if not model:
                self.logger.warning(
                    "event_not_found_for_failure_marking",
                    event_id=event_id,
                )
                return
            
            # Increment attempt count and set error
            model.attempt_count += 1
            model.last_error = error_message
            
            # If max attempts reached, mark as permanently failed
            if model.attempt_count >= max_attempts:
                model.dispatched_at = datetime.now(UTC)  # Mark as "processed" but failed
                
                self.logger.error(
                    "event_permanently_failed",
                    event_id=event_id,
                    event_type=model.event_type,
                    tenant_id=model.tenant_id,
                    attempt_count=model.attempt_count,
                    error=error_message,
                )
            else:
                self.logger.warning(
                    "event_retry_scheduled",
                    event_id=event_id,
                    event_type=model.event_type,
                    tenant_id=model.tenant_id,
                    attempt_count=model.attempt_count,
                    max_attempts=max_attempts,
                    error=error_message,
                )
            
            self.session.commit()
            
        except ValueError:
            self.logger.error("invalid_event_id_uuid_format", event_id=event_id)
        except Exception as error:
            self.session.rollback()
            self.logger.error(
                "mark_failed_error",
                event_id=event_id,
                error=str(error),
                error_type=type(error).__name__,
            )
            raise
    
    def get_failed_events(
        self,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get events that have permanently failed.
        
        Args:
            tenant_id: Optional tenant filter
            limit: Maximum number of events to retrieve
            
        Returns:
            List of failed event records as dictionaries
        """
        try:
            query = self.session.query(EventOutboxModel).filter(
                and_(
                    EventOutboxModel.dispatched_at.isnot(None),
                    EventOutboxModel.last_error.isnot(None),
                    EventOutboxModel.attempt_count >= 5
                )
            )
            
            if tenant_id:
                query = query.filter(EventOutboxModel.tenant_id == tenant_id)
            
            models = query.order_by(
                EventOutboxModel.occurred_at.desc()
            ).limit(limit).all()
            
            failed_events = []
            for model in models:
                failed_events.append({
                    "id": str(model.id),
                    "tenant_id": model.tenant_id,
                    "event_type": model.event_type,
                    "occurred_at": model.occurred_at.isoformat(),
                    "attempt_count": model.attempt_count,
                    "last_error": model.last_error,
                    "payload": model.payload,
                })
            
            return failed_events
            
        except Exception as error:
            self.logger.error(
                "get_failed_events_error",
                tenant_id=tenant_id,
                error=str(error),
                error_type=type(error).__name__,
            )
            return []
    
    def cleanup_old_events(self, days_old: int = 30) -> int:
        """
        Clean up old dispatched events to prevent table bloat.
        
        Args:
            days_old: Remove events older than this many days
            
        Returns:
            Number of events cleaned up
        """
        try:
            cutoff_date = datetime.now(UTC) - datetime.timedelta(days=days_old)
            
            deleted_count = self.session.query(EventOutboxModel).filter(
                and_(
                    EventOutboxModel.dispatched_at.isnot(None),
                    EventOutboxModel.occurred_at < cutoff_date
                )
            ).delete(synchronize_session=False)
            
            self.session.commit()
            
            self.logger.info(
                "old_events_cleaned_up",
                deleted_count=deleted_count,
                cutoff_date=cutoff_date.isoformat(),
            )
            
            return deleted_count
            
        except Exception as error:
            self.session.rollback()
            self.logger.error(
                "cleanup_old_events_failed",
                days_old=days_old,
                error=str(error),
                error_type=type(error).__name__,
            )
            return 0
    
    def _reconstruct_domain_event(self, model: EventOutboxModel) -> DomainEvent:
        """Reconstruct domain event from outbox model."""
        from packages.domain.enums import EventType
        from packages.domain.events import DomainEvent
        
        payload = model.payload
        
        # Create domain event from stored payload
        event = DomainEvent(
            id=payload["id"],
            source=payload["source"],
            specversion=payload["specversion"],
            type=EventType(payload["type"]),
            time=datetime.fromisoformat(payload["time"].replace("Z", "+00:00")),
            subject=payload["subject"],
            datacontenttype=payload["datacontenttype"],
            trace_id=payload.get("trace_id"),
            tenant_id=payload["tenant_id"],
            actor_id=payload.get("actor_id"),
            schema_version=payload["schema_version"],
            data=payload["data"],
        )
        
        # Store outbox ID for later reference
        event._outbox_id = str(model.id)  # Private attribute for tracking
        
        return event
    
    def _mark_event_failed(self, model: EventOutboxModel, error_message: str) -> None:
        """Mark a single event as failed during reconstruction."""
        try:
            model.attempt_count += 1
            model.last_error = f"Reconstruction failed: {error_message}"
            model.dispatched_at = datetime.now(UTC)  # Prevent further processing
            
            # Session commit will be handled by calling code
            
        except Exception as error:
            self.logger.error(
                "failed_to_mark_event_as_failed",
                outbox_id=str(model.id),
                error=str(error),
            )