"""
Business and technical metrics collection for ValidaHub marketplace intelligence.

This module provides comprehensive metrics that enable ValidaHub to:
1. Track business performance and ROI
2. Monitor technical system health
3. Gather marketplace intelligence
4. Support data-driven product decisions
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

try:
    from opentelemetry import metrics as otel_metrics
    from opentelemetry.metrics import Counter, Gauge, Histogram, UpDownCounter
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    # Mock classes for when OpenTelemetry is not available
    class Counter:
        def add(self, value, attributes=None): pass
    class Histogram:
        def record(self, value, attributes=None): pass
    class Gauge:
        def set(self, value, attributes=None): pass
    class UpDownCounter:
        def add(self, value, attributes=None): pass


class MetricType(Enum):
    """Types of metrics for categorization and routing."""
    BUSINESS = "business"      # Revenue, cost, ROI metrics
    TECHNICAL = "technical"    # Performance, errors, SLOs
    PRODUCT = "product"        # User behavior, feature usage
    MARKETPLACE = "marketplace" # Channel-specific intelligence


@dataclass
class MetricDefinition:
    """
    Definition of a metric with metadata for BI purposes.
    
    This class defines what metrics we collect and how they should
    be interpreted by downstream analytics systems.
    """
    name: str
    description: str
    metric_type: MetricType
    unit: str = ""
    tags: list[str] = field(default_factory=list)
    aggregation_period: str = "1m"  # 1m, 5m, 1h, 1d, etc.
    slo_relevant: bool = False
    business_critical: bool = False
    retention_days: int = 90


class MetricRegistry:
    """
    Central registry of all ValidaHub metrics.
    
    This registry serves as documentation and validation for all metrics
    that flow through the system, ensuring consistency and preventing drift.
    """
    
    def __init__(self):
        self._metrics: dict[str, MetricDefinition] = {}
        self._initialize_core_metrics()
    
    def _initialize_core_metrics(self):
        """Initialize all core ValidaHub metrics."""
        
        # Business Metrics - Revenue & Cost Attribution
        self.register(MetricDefinition(
            name="jobs_revenue_attributed_brl",
            description="Revenue attributed to job processing in BRL",
            metric_type=MetricType.BUSINESS,
            unit="brl",
            tags=["tenant_id", "channel", "job_type"],
            business_critical=True,
            retention_days=365
        ))
        
        self.register(MetricDefinition(
            name="jobs_cost_incurred_brl", 
            description="Infrastructure cost incurred for job processing in BRL",
            metric_type=MetricType.BUSINESS,
            unit="brl",
            tags=["tenant_id", "channel", "job_type"],
            business_critical=True,
            retention_days=365
        ))
        
        self.register(MetricDefinition(
            name="jobs_roi_ratio",
            description="Return on Investment ratio for job processing",
            metric_type=MetricType.BUSINESS,
            unit="ratio",
            tags=["tenant_id", "channel"],
            business_critical=True,
            retention_days=365
        ))
        
        # Technical Metrics - SLO & Performance
        self.register(MetricDefinition(
            name="jobs_submitted_total",
            description="Total number of jobs submitted",
            metric_type=MetricType.TECHNICAL,
            unit="count",
            tags=["tenant_id", "channel", "job_type"],
            slo_relevant=True,
            retention_days=90
        ))
        
        self.register(MetricDefinition(
            name="jobs_success_ratio",
            description="Ratio of successful jobs (SLO: >= 0.99)",
            metric_type=MetricType.TECHNICAL,
            unit="ratio",
            tags=["tenant_id", "channel"],
            slo_relevant=True,
            business_critical=True,
            retention_days=90
        ))
        
        self.register(MetricDefinition(
            name="jobs_duration_seconds",
            description="Job processing duration in seconds (SLO: p95 <= 30s)",
            metric_type=MetricType.TECHNICAL,
            unit="seconds",
            tags=["tenant_id", "channel", "job_type"],
            slo_relevant=True,
            retention_days=90
        ))
        
        self.register(MetricDefinition(
            name="jobs_queue_depth",
            description="Number of jobs waiting in queue",
            metric_type=MetricType.TECHNICAL,
            unit="count",
            tags=["tenant_id", "priority"],
            slo_relevant=True,
            retention_days=30
        ))
        
        # Marketplace Intelligence Metrics
        self.register(MetricDefinition(
            name="validation_errors_by_category",
            description="Validation errors grouped by category for marketplace intelligence",
            metric_type=MetricType.MARKETPLACE,
            unit="count", 
            tags=["tenant_id", "channel", "error_category", "rule_id"],
            retention_days=365
        ))
        
        self.register(MetricDefinition(
            name="marketplace_rule_effectiveness",
            description="Effectiveness of validation rules by marketplace",
            metric_type=MetricType.MARKETPLACE,
            unit="ratio",
            tags=["channel", "rule_id", "rule_version"],
            retention_days=365
        ))
        
        self.register(MetricDefinition(
            name="tenant_data_quality_score",
            description="Overall data quality score per tenant (0-100)",
            metric_type=MetricType.MARKETPLACE,
            unit="score",
            tags=["tenant_id", "channel"],
            business_critical=True,
            retention_days=365
        ))
        
        # Product & User Behavior Metrics
        self.register(MetricDefinition(
            name="user_session_duration_seconds",
            description="Time users spend in ValidaHub dashboard",
            metric_type=MetricType.PRODUCT,
            unit="seconds",
            tags=["tenant_id", "user_role", "feature_area"],
            retention_days=90
        ))
        
        self.register(MetricDefinition(
            name="feature_adoption_ratio",
            description="Ratio of users adopting new features",
            metric_type=MetricType.PRODUCT,
            unit="ratio",
            tags=["tenant_id", "feature_name", "user_segment"],
            business_critical=True,
            retention_days=365
        ))
        
        # Data Quality Metrics
        self.register(MetricDefinition(
            name="csv_data_quality_issues",
            description="Data quality issues found in CSV files",
            metric_type=MetricType.TECHNICAL,
            unit="count",
            tags=["tenant_id", "channel", "issue_type", "severity"],
            retention_days=180
        ))
        
        self.register(MetricDefinition(
            name="rule_engine_accuracy",
            description="Accuracy of validation rule predictions",
            metric_type=MetricType.TECHNICAL,
            unit="ratio",
            tags=["channel", "rule_type", "model_version"],
            slo_relevant=True,
            retention_days=365
        ))
    
    def register(self, metric: MetricDefinition) -> None:
        """Register a new metric definition."""
        self._metrics[metric.name] = metric
    
    def get(self, name: str) -> MetricDefinition | None:
        """Get metric definition by name."""
        return self._metrics.get(name)
    
    def list_by_type(self, metric_type: MetricType) -> list[MetricDefinition]:
        """List all metrics of a specific type."""
        return [m for m in self._metrics.values() if m.metric_type == metric_type]
    
    def list_slo_metrics(self) -> list[MetricDefinition]:
        """List all SLO-relevant metrics."""
        return [m for m in self._metrics.values() if m.slo_relevant]
    
    def list_business_critical(self) -> list[MetricDefinition]:
        """List all business-critical metrics."""
        return [m for m in self._metrics.values() if m.business_critical]


class AbstractMetricsCollector(ABC):
    """Abstract base class for metrics collectors."""
    
    @abstractmethod
    def increment(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        """Increment a counter metric."""
        pass
    
    @abstractmethod
    def histogram(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Record a histogram value."""
        pass
    
    @abstractmethod 
    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Set a gauge value."""
        pass


class OpenTelemetryMetricsCollector(AbstractMetricsCollector):
    """OpenTelemetry-based metrics collector."""
    
    def __init__(self, meter_name: str = "validahub"):
        if not OTEL_AVAILABLE:
            raise RuntimeError("OpenTelemetry not available")
        
        self.meter = otel_metrics.get_meter(meter_name)
        self._counters: dict[str, Counter] = {}
        self._histograms: dict[str, Histogram] = {}
        self._gauges: dict[str, Gauge] = {}
    
    def _get_counter(self, name: str) -> Counter:
        if name not in self._counters:
            self._counters[name] = self.meter.create_counter(name)
        return self._counters[name]
    
    def _get_histogram(self, name: str) -> Histogram:
        if name not in self._histograms:
            self._histograms[name] = self.meter.create_histogram(name)
        return self._histograms[name]
    
    def _get_gauge(self, name: str) -> Gauge:
        if name not in self._gauges:
            self._gauges[name] = self.meter.create_gauge(name)
        return self._gauges[name]
    
    def increment(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        counter = self._get_counter(name)
        counter.add(value, attributes=tags or {})
    
    def histogram(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        hist = self._get_histogram(name)
        hist.record(value, attributes=tags or {})
    
    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        gauge = self._get_gauge(name)
        gauge.set(value, attributes=tags or {})


class InMemoryMetricsCollector(AbstractMetricsCollector):
    """In-memory metrics collector for testing and development."""
    
    def __init__(self):
        self.counters: dict[str, float] = defaultdict(float)
        self.histograms: dict[str, list[float]] = defaultdict(list)
        self.gauges: dict[str, float] = {}
        self.tags_history: dict[str, list[dict[str, str]]] = defaultdict(list)
    
    def increment(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        key = self._make_key(name, tags or {})
        self.counters[key] += value
        self.tags_history[name].append(tags or {})
    
    def histogram(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        key = self._make_key(name, tags or {})
        self.histograms[key].append(value)
        self.tags_history[name].append(tags or {})
    
    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        key = self._make_key(name, tags or {})
        self.gauges[key] = value
        self.tags_history[name].append(tags or {})
    
    def _make_key(self, name: str, tags: dict[str, str]) -> str:
        """Create a unique key for metric + tags combination."""
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}:{tag_str}"
    
    def get_counter_value(self, name: str, tags: dict[str, str] | None = None) -> float:
        """Get current counter value (for testing)."""
        key = self._make_key(name, tags or {})
        return self.counters[key]
    
    def get_histogram_values(self, name: str, tags: dict[str, str] | None = None) -> list[float]:
        """Get all histogram values (for testing)."""
        key = self._make_key(name, tags or {})
        return self.histograms[key].copy()


class BusinessMetrics:
    """
    Business intelligence metrics for ValidaHub marketplace insights.
    
    These metrics directly support business decisions, revenue optimization,
    and strategic planning for marketplace expansion.
    """
    
    def __init__(self, collector: AbstractMetricsCollector):
        self.collector = collector
    
    def track_revenue_attribution(
        self,
        amount_brl: float,
        tenant_id: str,
        channel: str,
        job_type: str,
        seller_id: str | None = None
    ) -> None:
        """Track revenue attributed to job processing."""
        tags = {
            "tenant_id": tenant_id,
            "channel": channel, 
            "job_type": job_type,
        }
        if seller_id:
            tags["seller_id"] = seller_id
        
        self.collector.histogram("jobs_revenue_attributed_brl", amount_brl, tags)
    
    def track_cost_attribution(
        self,
        cost_brl: float,
        tenant_id: str,
        channel: str,
        job_type: str,
        cost_category: str = "processing"
    ) -> None:
        """Track infrastructure costs for job processing."""
        tags = {
            "tenant_id": tenant_id,
            "channel": channel,
            "job_type": job_type,
            "cost_category": cost_category,
        }
        
        self.collector.histogram("jobs_cost_incurred_brl", cost_brl, tags)
    
    def calculate_roi(
        self,
        revenue_brl: float,
        cost_brl: float,
        tenant_id: str,
        channel: str
    ) -> float:
        """Calculate and track ROI ratio."""
        roi = revenue_brl / cost_brl if cost_brl > 0 else 0
        
        tags = {
            "tenant_id": tenant_id,
            "channel": channel,
        }
        
        self.collector.gauge("jobs_roi_ratio", roi, tags)
        return roi
    
    def track_tenant_value(
        self,
        tenant_id: str,
        monthly_revenue_brl: float,
        monthly_cost_brl: float,
        job_count: int,
        data_quality_score: float
    ) -> None:
        """Track comprehensive tenant value metrics."""
        base_tags = {"tenant_id": tenant_id}
        
        # Revenue and cost
        self.collector.gauge("tenant_monthly_revenue_brl", monthly_revenue_brl, base_tags)
        self.collector.gauge("tenant_monthly_cost_brl", monthly_cost_brl, base_tags)
        
        # Volume and quality
        self.collector.gauge("tenant_monthly_jobs", job_count, base_tags)
        self.collector.gauge("tenant_data_quality_score", data_quality_score, base_tags)
        
        # Derived metrics
        if monthly_cost_brl > 0:
            roi = monthly_revenue_brl / monthly_cost_brl
            self.collector.gauge("tenant_monthly_roi", roi, base_tags)
        
        if job_count > 0:
            revenue_per_job = monthly_revenue_brl / job_count
            self.collector.gauge("tenant_revenue_per_job_brl", revenue_per_job, base_tags)


class TechnicalMetrics:
    """
    Technical performance and SLO metrics.
    
    These metrics ensure system reliability, track SLO compliance,
    and identify technical debt and performance bottlenecks.
    """
    
    def __init__(self, collector: AbstractMetricsCollector):
        self.collector = collector
    
    def track_job_lifecycle(
        self,
        job_id: str,
        tenant_id: str,
        channel: str,
        job_type: str,
        status: str,
        duration_seconds: float | None = None,
        error_count: int = 0,
        warning_count: int = 0,
        total_records: int = 0
    ) -> None:
        """Track complete job lifecycle metrics."""
        base_tags = {
            "tenant_id": tenant_id,
            "channel": channel,
            "job_type": job_type,
        }
        
        # Job counts by status
        status_tags = {**base_tags, "status": status}
        self.collector.increment("jobs_total", 1.0, status_tags)
        
        # Success rate calculation
        if status in ["succeeded", "failed"]:
            success_value = 1.0 if status == "succeeded" else 0.0
            self.collector.histogram("jobs_success_ratio", success_value, base_tags)
        
        # Duration tracking (SLO: p95 <= 30s)
        if duration_seconds is not None:
            self.collector.histogram("jobs_duration_seconds", duration_seconds, base_tags)
        
        # Data quality metrics
        if total_records > 0:
            error_rate = error_count / total_records
            warning_rate = warning_count / total_records
            
            quality_tags = {**base_tags, "job_id": job_id}
            self.collector.histogram("jobs_error_rate", error_rate, quality_tags)
            self.collector.histogram("jobs_warning_rate", warning_rate, quality_tags)
    
    def track_api_performance(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        tenant_id: str | None = None
    ) -> None:
        """Track API performance metrics."""
        tags = {
            "endpoint": endpoint,
            "method": method,
            "status": str(status_code),
        }
        if tenant_id:
            tags["tenant_id"] = tenant_id
        
        # Request counts
        self.collector.increment("http_requests_total", 1.0, tags)
        
        # Duration histogram
        self.collector.histogram("http_request_duration_ms", duration_ms, tags)
        
        # Error rates
        if status_code >= 400:
            error_tags = {**tags, "error_type": self._classify_error(status_code)}
            self.collector.increment("http_errors_total", 1.0, error_tags)
    
    def track_queue_metrics(
        self,
        queue_name: str,
        depth: int,
        processing_rate: float,
        tenant_id: str | None = None
    ) -> None:
        """Track queue performance metrics."""
        tags = {"queue": queue_name}
        if tenant_id:
            tags["tenant_id"] = tenant_id
        
        self.collector.gauge("queue_depth", depth, tags)
        self.collector.gauge("queue_processing_rate", processing_rate, tags)
    
    def _classify_error(self, status_code: int) -> str:
        """Classify HTTP error codes for better analytics."""
        if 400 <= status_code < 500:
            return "client_error"
        elif 500 <= status_code < 600:
            return "server_error"
        else:
            return "unknown"


class MarketplaceIntelligenceMetrics:
    """
    Marketplace-specific intelligence metrics.
    
    These metrics provide deep insights into marketplace behavior,
    validation patterns, and opportunities for rule improvements.
    """
    
    def __init__(self, collector: AbstractMetricsCollector):
        self.collector = collector
    
    def track_validation_patterns(
        self,
        channel: str,
        rule_id: str,
        error_category: str,
        severity: str,
        tenant_id: str,
        occurrence_count: int = 1
    ) -> None:
        """Track validation error patterns for marketplace intelligence."""
        tags = {
            "channel": channel,
            "rule_id": rule_id,
            "error_category": error_category,
            "severity": severity,
            "tenant_id": tenant_id,
        }
        
        self.collector.increment("validation_errors_by_category", occurrence_count, tags)
    
    def track_rule_effectiveness(
        self,
        channel: str,
        rule_id: str,
        rule_version: str,
        true_positives: int,
        false_positives: int,
        true_negatives: int,
        false_negatives: int
    ) -> None:
        """Track validation rule effectiveness metrics."""
        total = true_positives + false_positives + true_negatives + false_negatives
        if total == 0:
            return
        
        accuracy = (true_positives + true_negatives) / total
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        
        tags = {
            "channel": channel,
            "rule_id": rule_id,
            "rule_version": rule_version,
        }
        
        self.collector.gauge("rule_accuracy", accuracy, tags)
        self.collector.gauge("rule_precision", precision, tags)
        self.collector.gauge("rule_recall", recall, tags)
    
    def track_marketplace_trends(
        self,
        channel: str,
        trend_type: str,
        trend_value: float,
        period: str = "1d"
    ) -> None:
        """Track marketplace trends and patterns."""
        tags = {
            "channel": channel,
            "trend_type": trend_type,
            "period": period,
        }
        
        self.collector.gauge("marketplace_trends", trend_value, tags)


# Global registry and collectors
_registry = MetricRegistry()
_collector: AbstractMetricsCollector | None = None


def get_metrics() -> AbstractMetricsCollector:
    """Get the global metrics collector."""
    global _collector
    if _collector is None:
        try:
            _collector = OpenTelemetryMetricsCollector()
        except RuntimeError:
            _collector = InMemoryMetricsCollector()
    return _collector


def set_metrics_collector(collector: AbstractMetricsCollector) -> None:
    """Set a custom metrics collector."""
    global _collector
    _collector = collector


def get_registry() -> MetricRegistry:
    """Get the global metrics registry."""
    return _registry