"""
CloudEvents envelope builder for ValidaHub domain events.

Provides a fluent interface for creating CloudEvents 1.0 compliant events
with ValidaHub-specific extensions for multi-tenancy and correlation.
"""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from packages.shared.logging.context import get_correlation_id, get_tenant_id


@dataclass(frozen=True)
class CloudEventEnvelope:
    """
    CloudEvents 1.0 compliant event envelope with ValidaHub extensions.
    
    This class represents the complete event structure that will be
    emitted to various sinks (Redis, S3, etc.) and consumed by BI systems.
    """
    
    # CloudEvents 1.0 standard attributes
    id: str
    source: str
    specversion: str = "1.0"
    type: str = ""
    time: str = ""
    subject: str = ""
    datacontenttype: str = "application/json"
    
    # ValidaHub extensions (prefixed with validahub_ per CloudEvents spec)
    validahub_tenant_id: str = ""
    validahub_trace_id: str | None = None
    validahub_actor_id: str | None = None
    validahub_schema_version: str = "1"
    validahub_environment: str = "development"
    validahub_service: str = "api"
    
    # Event payload
    data: dict[str, Any] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        
        # Remove None values to keep events clean
        return {k: v for k, v in result.items() if v is not None}
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    def to_ndjson(self) -> str:
        """Convert to NDJSON format for S3 storage."""
        return self.to_json() + "\n"
    
    def validate(self) -> bool:
        """Validate CloudEvents compliance."""
        required_fields = ["id", "source", "specversion", "type"]
        
        for field in required_fields:
            value = getattr(self, field)
            if not value:
                raise ValueError(f"CloudEvent missing required field: {field}")
        
        if self.specversion != "1.0":
            raise ValueError(f"Unsupported CloudEvents version: {self.specversion}")
        
        if not self.validahub_tenant_id:
            raise ValueError("ValidaHub events must include tenant_id")
        
        return True
    
    def enrich_for_bi(self, **additional_data) -> 'CloudEventEnvelope':
        """
        Enrich event with additional business intelligence data.
        
        This method is used to add calculated metrics, derived dimensions,
        and other BI-relevant data without modifying the core event.
        """
        enriched_data = self.data.copy() if self.data else {}
        enriched_data.update(additional_data)
        
        # Add BI metadata
        enriched_data["_bi_enriched_at"] = datetime.now(UTC).isoformat()
        enriched_data["_bi_version"] = "1.0"
        
        return CloudEventEnvelope(
            **{**asdict(self), "data": enriched_data}
        )


class CloudEventBuilder:
    """
    Fluent builder for CloudEvents with auto-injection of context.
    
    Usage:
        event = (CloudEventBuilder("job.submitted")
                .from_source("apps/api")
                .with_subject("job:12345")
                .with_data({"job_id": "12345", "status": "queued"})
                .with_actor("seller_123")
                .build())
    """
    
    def __init__(self, event_type: str):
        self.event_type = event_type
        self.event_id = str(uuid4())
        self.timestamp = datetime.now(UTC).isoformat()
        self.source = "packages/domain"
        self.subject = ""
        self.data = {}
        
        # Auto-inject context
        self.tenant_id = get_tenant_id() or ""
        self.trace_id = get_correlation_id()
        self.actor_id = None
        
    def from_source(self, source: str) -> 'CloudEventBuilder':
        """Set event source (e.g., 'apps/api', 'packages/domain')."""
        self.source = source
        return self
    
    def with_id(self, event_id: str) -> 'CloudEventBuilder':
        """Set custom event ID (use sparingly)."""
        self.event_id = event_id
        return self
    
    def with_subject(self, subject: str) -> 'CloudEventBuilder':
        """Set event subject (e.g., 'job:12345', 'tenant:abc')."""
        self.subject = subject
        return self
    
    def with_data(self, data: dict[str, Any]) -> 'CloudEventBuilder':
        """Set event data payload."""
        self.data = data.copy()
        return self
    
    def with_tenant(self, tenant_id: str) -> 'CloudEventBuilder':
        """Override auto-detected tenant ID."""
        self.tenant_id = tenant_id
        return self
    
    def with_actor(self, actor_id: str) -> 'CloudEventBuilder':
        """Set actor ID (user/seller who triggered the event)."""
        self.actor_id = actor_id
        return self
    
    def with_trace(self, trace_id: str) -> 'CloudEventBuilder':
        """Override auto-detected trace ID."""
        self.trace_id = trace_id
        return self
    
    def merge_data(self, additional_data: dict[str, Any]) -> 'CloudEventBuilder':
        """Merge additional data into existing payload."""
        self.data.update(additional_data)
        return self
    
    def build(self) -> CloudEventEnvelope:
        """Build the final CloudEvent envelope."""
        event = CloudEventEnvelope(
            id=self.event_id,
            source=self.source,
            type=self.event_type,
            time=self.timestamp,
            subject=self.subject,
            validahub_tenant_id=self.tenant_id,
            validahub_trace_id=self.trace_id,
            validahub_actor_id=self.actor_id,
            data=self.data,
        )
        
        # Validate before returning
        event.validate()
        return event


# Convenience functions
def create_event(
    event_type: str,
    data: dict[str, Any],
    subject: str = "",
    source: str = "packages/domain",
    tenant_id: str | None = None,
    actor_id: str | None = None,
) -> CloudEventEnvelope:
    """
    Quick event creation with sensible defaults.
    
    Args:
        event_type: CloudEvent type (e.g., 'job.submitted')
        data: Event payload
        subject: Event subject (e.g., 'job:12345')
        source: Event source
        tenant_id: Override auto-detected tenant
        actor_id: Actor who triggered the event
    
    Returns:
        Ready-to-emit CloudEvent envelope
    """
    builder = (CloudEventBuilder(event_type)
              .from_source(source)
              .with_subject(subject)
              .with_data(data))
    
    if tenant_id:
        builder = builder.with_tenant(tenant_id)
    if actor_id:
        builder = builder.with_actor(actor_id)
    
    return builder.build()


def create_business_event(
    event_type: str,
    business_data: dict[str, Any],
    revenue_impact: float | None = None,
    cost_impact: float | None = None,
    **kwargs
) -> CloudEventEnvelope:
    """
    Create event enriched with business intelligence data.
    
    This function automatically adds business context that's crucial
    for revenue attribution, cost analysis, and marketplace intelligence.
    """
    # Add business intelligence metadata
    bi_metadata = {
        "_event_category": "business",
        "_revenue_impact_brl": revenue_impact,
        "_cost_impact_brl": cost_impact,
        "_marketplace_context": True,
    }
    
    # Remove None values
    bi_metadata = {k: v for k, v in bi_metadata.items() if v is not None}
    
    # Merge with business data
    enriched_data = {**business_data, **bi_metadata}
    
    return create_event(event_type, enriched_data, **kwargs)


def create_technical_event(
    event_type: str,
    technical_data: dict[str, Any],
    performance_metrics: dict[str, int | float] | None = None,
    **kwargs
) -> CloudEventEnvelope:
    """
    Create event enriched with technical performance data.
    
    Used for system performance monitoring, SLO tracking, and
    technical debt identification.
    """
    # Add technical metadata  
    tech_metadata = {
        "_event_category": "technical",
        "_performance_metrics": performance_metrics or {},
        "_slo_relevant": True,
    }
    
    # Merge with technical data
    enriched_data = {**technical_data, **tech_metadata}
    
    return create_event(event_type, enriched_data, **kwargs)