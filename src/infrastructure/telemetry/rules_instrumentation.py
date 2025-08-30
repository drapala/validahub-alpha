"""
OpenTelemetry instrumentation for ValidaHub Smart Rules Engine.

This module provides comprehensive observability for the rules engine including:
- Distributed tracing with OpenTelemetry
- Prometheus metrics collection
- CloudEvents emission for business intelligence
- Performance monitoring and SLO tracking

Usage:
    from src.infrastructure.telemetry.rules_instrumentation import RulesInstrumentation
    
    instrumentation = RulesInstrumentation()
    
    # Instrument rule compilation
    with instrumentation.trace_compilation("mercado_livre_v1.2.0") as span:
        compiled_ruleset = compile_rules(ruleset)
        
    # Instrument rule execution
    with instrumentation.trace_execution("job_12345", compiled_ruleset) as span:
        result = execute_rules(compiled_ruleset, data)
"""

import asyncio
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import CallbackOptions, Observation
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import AggregationTemporality
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Status, StatusCode

from packages.shared.logging.context import get_correlation_id, get_tenant_id
from packages.shared.telemetry import (
    create_event, create_technical_event, emit_event, get_metrics
)
from src.domain.rules.entities import RuleSet
from src.domain.rules.engine.ir_types import CompiledRuleSet
from src.domain.rules.engine.runtime import ExecutionResult, ExecutionStats


@dataclass
class RulePerformanceMetrics:
    """Performance metrics for individual rule execution."""
    
    rule_id: str
    execution_duration_ms: float
    rows_processed: int
    violations_found: int
    memory_usage_mb: float
    cache_hits: int
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    false_positive_rate: Optional[float] = None


@dataclass
class CompilationMetrics:
    """Metrics collected during rule compilation."""
    
    ruleset_id: str
    compilation_duration_ms: float
    rules_compiled: int
    optimizations_applied: int
    memory_usage_mb: float
    execution_plan_phases: int
    vectorized_rules: int
    parallel_rules: int
    success: bool
    error_message: Optional[str] = None


@dataclass
class ExecutionMetrics:
    """Metrics collected during rule execution."""
    
    job_id: str
    ruleset_id: str
    execution_duration_ms: float
    dataset_rows: int
    processed_rows: int
    rules_executed: int
    vectorized_operations: int
    parallel_operations: int
    cache_hit_rate: float
    memory_peak_mb: float
    throughput_rows_per_second: float
    success: bool
    error_message: Optional[str] = None


class RulesInstrumentation:
    """
    Comprehensive instrumentation for ValidaHub Rules Engine.
    
    Provides OpenTelemetry tracing, Prometheus metrics, and CloudEvents
    emission for complete observability of rule compilation and execution.
    """
    
    def __init__(self, service_name: str = "validahub-rules-engine"):
        """
        Initialize Rules Engine instrumentation.
        
        Args:
            service_name: Service name for tracing and metrics
        """
        self.service_name = service_name
        
        # Initialize OpenTelemetry
        self._setup_tracing()
        self._setup_metrics()
        
        # Get shared metrics instance
        self.shared_metrics = get_metrics()
        
    def _setup_tracing(self) -> None:
        """Set up OpenTelemetry tracing."""
        self.tracer = trace.get_tracer(
            instrumenting_module_name=__name__,
            instrumenting_library_version="1.0.0"
        )
        
    def _setup_metrics(self) -> None:
        """Set up OpenTelemetry metrics with Prometheus export."""
        # Create Prometheus metric reader
        prometheus_reader = PrometheusMetricReader(
            aggregation_temporality_selector=lambda x: AggregationTemporality.CUMULATIVE
        )
        
        # Initialize meter
        self.meter = metrics.get_meter(
            name=self.service_name,
            version="1.0.0"
        )
        
        # Define histogram metrics
        self.compilation_duration = self.meter.create_histogram(
            name="rules_compilation_duration_ms",
            description="Duration of rule compilation in milliseconds",
            unit="ms"
        )
        
        self.execution_duration = self.meter.create_histogram(
            name="rules_execution_duration_ms", 
            description="Duration of rule execution in milliseconds",
            unit="ms"
        )
        
        self.rule_performance = self.meter.create_histogram(
            name="rules_individual_rule_duration_ms",
            description="Performance of individual rule execution",
            unit="ms"
        )
        
        self.throughput = self.meter.create_histogram(
            name="rules_throughput_rows_per_second",
            description="Rules engine throughput in rows per second",
            unit="rows/s"
        )
        
        # Define counter metrics
        self.compilation_total = self.meter.create_counter(
            name="rules_compilations_total",
            description="Total number of rule compilations"
        )
        
        self.execution_total = self.meter.create_counter(
            name="rules_executions_total", 
            description="Total number of rule executions"
        )
        
        self.violations_total = self.meter.create_counter(
            name="rules_violations_total",
            description="Total number of rule violations found"
        )
        
        # Define gauge metrics
        self.cache_hit_rate = self.meter.create_up_down_counter(
            name="rules_cache_hit_rate",
            description="Current cache hit rate for rule conditions"
        )
        
        self.memory_usage = self.meter.create_up_down_counter(
            name="rules_memory_usage_mb", 
            description="Current memory usage in MB"
        )
        
        # Business intelligence metrics
        self.rule_effectiveness = self.meter.create_histogram(
            name="rules_effectiveness_f1_score",
            description="F1 score measuring rule effectiveness",
            unit="score"
        )
        
        self.business_impact = self.meter.create_histogram(
            name="rules_business_impact_brl",
            description="Business impact in BRL from rule execution",
            unit="brl"
        )
        
    @contextmanager
    def trace_compilation(
        self, 
        ruleset_id: str,
        channel: str,
        version: str,
        tenant_id: Optional[str] = None,
        actor_id: Optional[str] = None
    ):
        """
        Trace rule compilation with comprehensive telemetry.
        
        Args:
            ruleset_id: ID of the ruleset being compiled
            channel: Marketplace channel (e.g., mercado_livre)
            version: Semantic version of the ruleset
            tenant_id: Override auto-detected tenant ID
            actor_id: User/system performing compilation
            
        Usage:
            with instrumentation.trace_compilation("mercado_livre_v1.2.0") as span:
                compiled_ruleset = compiler.compile(ruleset)
                span.set_compilation_result(compiled_ruleset, metrics)
        """
        tenant_id = tenant_id or get_tenant_id()
        trace_id = get_correlation_id()
        start_time = time.perf_counter()
        
        # Start compilation event
        start_event = create_event(
            event_type="rules.compilation.started",
            data={
                "ruleset_id": ruleset_id,
                "channel": channel,
                "version": version,
                "compilation_mode": "optimized"
            },
            subject=f"ruleset:{ruleset_id}",
            source="packages/rules/engine/compiler",
            tenant_id=tenant_id,
            actor_id=actor_id
        )
        
        asyncio.create_task(emit_event(start_event))
        
        # Start tracing span
        with self.tracer.start_as_current_span(
            name=f"rules.compilation",
            attributes={
                "rules.ruleset_id": ruleset_id,
                "rules.channel": channel,
                "rules.version": version,
                "rules.tenant_id": tenant_id,
                "rules.compilation_mode": "optimized"
            }
        ) as span:
            
            compilation_span = CompilationSpan(
                span, ruleset_id, channel, version, tenant_id, actor_id, start_time
            )
            
            try:
                yield compilation_span
                
                # Record successful compilation
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                self.compilation_total.add(
                    1,
                    {
                        "ruleset_id": ruleset_id,
                        "channel": channel, 
                        "version": version,
                        "tenant_id": tenant_id,
                        "status": "success"
                    }
                )
                
                self.compilation_duration.record(
                    duration_ms,
                    {
                        "ruleset_id": ruleset_id,
                        "channel": channel,
                        "version": version,
                        "tenant_id": tenant_id
                    }
                )
                
                span.set_status(Status(StatusCode.OK))
                
            except Exception as error:
                # Record compilation failure
                duration_ms = (time.perf_counter() - start_time) * 1000
                error_message = str(error)
                
                self.compilation_total.add(
                    1,
                    {
                        "ruleset_id": ruleset_id,
                        "channel": channel,
                        "version": version, 
                        "tenant_id": tenant_id,
                        "status": "failed"
                    }
                )
                
                # Emit failure event
                failure_event = create_event(
                    event_type="rules.compilation.failed",
                    data={
                        "ruleset_id": ruleset_id,
                        "channel": channel,
                        "version": version,
                        "compilation_duration_ms": duration_ms,
                        "error_type": error.__class__.__name__,
                        "error_message": error_message
                    },
                    subject=f"ruleset:{ruleset_id}",
                    source="packages/rules/engine/compiler",
                    tenant_id=tenant_id,
                    actor_id=actor_id
                )
                
                asyncio.create_task(emit_event(failure_event))
                
                span.set_status(
                    Status(StatusCode.ERROR, error_message)
                )
                span.set_attribute("error.type", error.__class__.__name__)
                span.set_attribute("error.message", error_message)
                
                raise
                
    @contextmanager 
    def trace_execution(
        self,
        job_id: str,
        ruleset: CompiledRuleSet,
        data: pd.DataFrame,
        tenant_id: Optional[str] = None,
        actor_id: Optional[str] = None
    ):
        """
        Trace rule execution with comprehensive telemetry.
        
        Args:
            job_id: Unique job identifier
            ruleset: Compiled ruleset to execute
            data: DataFrame being processed
            tenant_id: Override auto-detected tenant ID  
            actor_id: User/system performing execution
            
        Usage:
            with instrumentation.trace_execution("job_123", ruleset, data) as span:
                result = engine.execute_rules(ruleset, data)
                span.set_execution_result(result)
        """
        tenant_id = tenant_id or get_tenant_id()
        trace_id = get_correlation_id()
        start_time = time.perf_counter()
        
        # Extract ruleset metadata
        ruleset_id = ruleset.id
        channel = getattr(ruleset, 'channel', 'unknown')
        version = getattr(ruleset, 'version', 'unknown')
        
        # Start execution event
        start_event = create_event(
            event_type="rules.execution.started",
            data={
                "job_id": job_id,
                "ruleset_id": ruleset_id,
                "channel": channel,
                "version": version,
                "dataset_rows": len(data),
                "dataset_columns": len(data.columns),
                "execution_mode": "vectorized",
                "rules_to_execute": len(ruleset.rules),
                "estimated_duration_ms": len(data) * 3  # 3ms per row estimate
            },
            subject=f"job:{job_id}",
            source="packages/rules/engine/runtime",
            tenant_id=tenant_id,
            actor_id=actor_id
        )
        
        asyncio.create_task(emit_event(start_event))
        
        # Start tracing span
        with self.tracer.start_as_current_span(
            name="rules.execution",
            attributes={
                "rules.job_id": job_id,
                "rules.ruleset_id": ruleset_id,
                "rules.channel": channel,
                "rules.version": version,
                "rules.tenant_id": tenant_id,
                "rules.dataset_rows": len(data),
                "rules.dataset_columns": len(data.columns),
                "rules.rules_count": len(ruleset.rules)
            }
        ) as span:
            
            execution_span = ExecutionSpan(
                span, job_id, ruleset_id, channel, version, 
                tenant_id, actor_id, start_time, len(data)
            )
            
            try:
                yield execution_span
                
                # Record successful execution
                duration_ms = (time.perf_counter() - start_time) * 1000
                throughput = len(data) / (duration_ms / 1000) if duration_ms > 0 else 0
                
                self.execution_total.add(
                    1,
                    {
                        "job_id": job_id,
                        "ruleset_id": ruleset_id,
                        "channel": channel,
                        "version": version,
                        "tenant_id": tenant_id,
                        "status": "success"
                    }
                )
                
                self.execution_duration.record(
                    duration_ms,
                    {
                        "ruleset_id": ruleset_id,
                        "channel": channel,
                        "version": version,
                        "tenant_id": tenant_id
                    }
                )
                
                self.throughput.record(
                    throughput,
                    {
                        "ruleset_id": ruleset_id,
                        "channel": channel, 
                        "version": version,
                        "tenant_id": tenant_id
                    }
                )
                
                span.set_status(Status(StatusCode.OK))
                
            except Exception as error:
                # Record execution failure
                duration_ms = (time.perf_counter() - start_time) * 1000
                error_message = str(error)
                
                self.execution_total.add(
                    1,
                    {
                        "job_id": job_id,
                        "ruleset_id": ruleset_id,
                        "channel": channel,
                        "version": version,
                        "tenant_id": tenant_id,
                        "status": "failed"
                    }
                )
                
                # Emit failure event
                failure_event = create_event(
                    event_type="rules.execution.failed",
                    data={
                        "job_id": job_id,
                        "ruleset_id": ruleset_id,
                        "channel": channel,
                        "version": version,
                        "execution_duration_ms": duration_ms,
                        "dataset_rows": len(data),
                        "error_type": error.__class__.__name__,
                        "error_message": error_message
                    },
                    subject=f"job:{job_id}",
                    source="packages/rules/engine/runtime",
                    tenant_id=tenant_id,
                    actor_id=actor_id
                )
                
                asyncio.create_task(emit_event(failure_event))
                
                span.set_status(
                    Status(StatusCode.ERROR, error_message)
                )
                span.set_attribute("error.type", error.__class__.__name__)
                span.set_attribute("error.message", error_message)
                
                raise
                
    def track_rule_performance(
        self,
        metrics: RulePerformanceMetrics,
        tenant_id: Optional[str] = None
    ) -> None:
        """
        Track individual rule performance metrics.
        
        Args:
            metrics: Performance metrics for a specific rule
            tenant_id: Override auto-detected tenant ID
        """
        tenant_id = tenant_id or get_tenant_id()
        
        labels = {
            "rule_id": metrics.rule_id,
            "tenant_id": tenant_id
        }
        
        # Record performance metrics
        self.rule_performance.record(
            metrics.execution_duration_ms,
            labels
        )
        
        if metrics.violations_found > 0:
            self.violations_total.add(
                metrics.violations_found,
                labels
            )
            
        # Track effectiveness metrics
        if metrics.f1_score is not None:
            self.rule_effectiveness.record(
                metrics.f1_score,
                labels
            )
            
        # Emit performance event
        performance_event = create_technical_event(
            event_type="rules.performance.measured",
            technical_data={
                "rule_id": metrics.rule_id,
                "execution_duration_ms": metrics.execution_duration_ms,
                "rows_processed": metrics.rows_processed,
                "violations_found": metrics.violations_found,
                "memory_usage_mb": metrics.memory_usage_mb,
                "cache_hits": metrics.cache_hits
            },
            performance_metrics={
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score,
                "false_positive_rate": metrics.false_positive_rate
            },
            source="packages/rules/engine/runtime"
        )
        
        asyncio.create_task(emit_event(performance_event))
        
    def track_cache_operation(
        self,
        operation: str,
        cache_key: str,
        hit_rate: float,
        time_saved_ms: Optional[float] = None,
        tenant_id: Optional[str] = None
    ) -> None:
        """
        Track cache operations for performance monitoring.
        
        Args:
            operation: Cache operation (hit, miss, eviction)
            cache_key: Unique cache key
            hit_rate: Current cache hit rate
            time_saved_ms: Time saved by cache hit
            tenant_id: Override auto-detected tenant ID
        """
        tenant_id = tenant_id or get_tenant_id()
        
        # Update cache hit rate gauge
        self.cache_hit_rate.add(
            int(hit_rate * 100),  # Convert to percentage
            {
                "tenant_id": tenant_id,
                "operation": operation
            }
        )
        
        # Emit cache operation event (sampled at 1%)
        if hash(cache_key) % 100 == 0:  # 1% sampling
            cache_event = create_event(
                event_type="rules.cache.operation",
                data={
                    "operation": operation,
                    "cache_type": "condition_results",
                    "cache_key": cache_key[:50] + "..." if len(cache_key) > 50 else cache_key,
                    "hit_rate": hit_rate,
                    "time_saved_ms": time_saved_ms
                },
                subject="cache:condition_results",
                source="packages/rules/engine/runtime",
                tenant_id=tenant_id
            )
            
            asyncio.create_task(emit_event(cache_event))
            
    def track_business_impact(
        self,
        ruleset_id: str,
        channel: str,
        revenue_protected_brl: float,
        cost_prevented_brl: float,
        tenant_id: Optional[str] = None
    ) -> None:
        """
        Track business impact metrics for BI analysis.
        
        Args:
            ruleset_id: ID of ruleset generating impact
            channel: Marketplace channel
            revenue_protected_brl: Revenue protected in BRL
            cost_prevented_brl: Cost prevented in BRL
            tenant_id: Override auto-detected tenant ID
        """
        tenant_id = tenant_id or get_tenant_id()
        
        labels = {
            "ruleset_id": ruleset_id,
            "channel": channel,
            "tenant_id": tenant_id
        }
        
        # Record business impact
        self.business_impact.record(revenue_protected_brl, labels)
        
        # Emit business event (100% sampling for business metrics)
        business_event = create_event(
            event_type="rules.business_impact.measured",
            data={
                "ruleset_id": ruleset_id,
                "channel": channel,
                "revenue_protected_brl": revenue_protected_brl,
                "cost_prevented_brl": cost_prevented_brl,
                "roi": revenue_protected_brl / max(cost_prevented_brl, 1.0)
            },
            subject=f"ruleset:{ruleset_id}",
            source="packages/rules/business_intelligence",
            tenant_id=tenant_id
        )
        
        asyncio.create_task(emit_event(business_event))


class CompilationSpan:
    """Helper class for managing compilation span context."""
    
    def __init__(
        self, 
        span, 
        ruleset_id: str,
        channel: str, 
        version: str,
        tenant_id: str,
        actor_id: Optional[str],
        start_time: float
    ):
        self.span = span
        self.ruleset_id = ruleset_id
        self.channel = channel
        self.version = version
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.start_time = start_time
        
    def set_compilation_result(
        self, 
        compiled_ruleset: CompiledRuleSet,
        metrics: Optional[CompilationMetrics] = None
    ) -> None:
        """Set compilation result with comprehensive metrics."""
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        
        # Extract metrics from compiled ruleset
        rules_compiled = len(compiled_ruleset.rules)
        execution_plan_phases = len(compiled_ruleset.execution_plan.phases)
        
        # Set span attributes
        self.span.set_attributes({
            "rules.compilation_duration_ms": duration_ms,
            "rules.rules_compiled": rules_compiled,
            "rules.execution_plan_phases": execution_plan_phases,
            "rules.compilation_success": True
        })
        
        # Emit completion event
        completion_event = create_event(
            event_type="rules.compilation.completed",
            data={
                "ruleset_id": self.ruleset_id,
                "channel": self.channel,
                "version": self.version,
                "compilation_duration_ms": duration_ms,
                "rules_compiled": rules_compiled,
                "execution_plan_phases": execution_plan_phases,
                "compilation_success": True
            },
            subject=f"ruleset:{self.ruleset_id}",
            source="packages/rules/engine/compiler",
            tenant_id=self.tenant_id,
            actor_id=self.actor_id
        )
        
        asyncio.create_task(emit_event(completion_event))


class ExecutionSpan:
    """Helper class for managing execution span context."""
    
    def __init__(
        self,
        span,
        job_id: str,
        ruleset_id: str,
        channel: str,
        version: str,
        tenant_id: str,
        actor_id: Optional[str],
        start_time: float,
        dataset_rows: int
    ):
        self.span = span
        self.job_id = job_id
        self.ruleset_id = ruleset_id
        self.channel = channel
        self.version = version
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.start_time = start_time
        self.dataset_rows = dataset_rows
        
    def set_execution_result(self, result: ExecutionResult) -> None:
        """Set execution result with comprehensive metrics."""
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        throughput = self.dataset_rows / (duration_ms / 1000) if duration_ms > 0 else 0
        
        # Set span attributes
        self.span.set_attributes({
            "rules.execution_duration_ms": duration_ms,
            "rules.processed_rows": result.stats.processed_rows,
            "rules.rules_executed": result.stats.rules_executed,
            "rules.vectorized_operations": result.stats.vectorized_operations,
            "rules.cache_hits": result.stats.cache_hits,
            "rules.error_count": result.stats.error_count,
            "rules.warning_count": result.stats.warning_count,
            "rules.throughput_rows_per_second": throughput
        })
        
        # Emit completion event
        completion_event = create_event(
            event_type="rules.execution.completed",
            data={
                "job_id": self.job_id,
                "ruleset_id": self.ruleset_id,
                "channel": self.channel,
                "version": self.version,
                "execution_duration_ms": duration_ms,
                "dataset_rows": self.dataset_rows,
                "processed_rows": result.stats.processed_rows,
                "rules_executed": result.stats.rules_executed,
                "vectorized_operations": result.stats.vectorized_operations,
                "cache_hit_rate": result.stats.cache_hits / max(result.stats.rules_executed, 1),
                "validation_results": {
                    "error_count": result.stats.error_count,
                    "warning_count": result.stats.warning_count,
                    "suggestion_count": result.stats.suggestion_count,
                    "transformation_count": result.stats.transformation_count
                },
                "performance_metrics": {
                    "throughput_rows_per_second": throughput,
                    "memory_usage_mb": result.stats.memory_usage_mb
                }
            },
            subject=f"job:{self.job_id}",
            source="packages/rules/engine/runtime",
            tenant_id=self.tenant_id,
            actor_id=self.actor_id
        )
        
        asyncio.create_task(emit_event(completion_event))


# Global instrumentation instance
_instrumentation: Optional[RulesInstrumentation] = None


def get_rules_instrumentation() -> RulesInstrumentation:
    """Get or create the global rules instrumentation instance."""
    global _instrumentation
    if _instrumentation is None:
        _instrumentation = RulesInstrumentation()
    return _instrumentation


# Convenience functions for easy instrumentation
def trace_compilation(
    ruleset_id: str,
    channel: str,
    version: str,
    tenant_id: Optional[str] = None,
    actor_id: Optional[str] = None
):
    """Convenience function for tracing rule compilation."""
    return get_rules_instrumentation().trace_compilation(
        ruleset_id, channel, version, tenant_id, actor_id
    )


def trace_execution(
    job_id: str,
    ruleset: CompiledRuleSet,
    data: pd.DataFrame,
    tenant_id: Optional[str] = None,
    actor_id: Optional[str] = None
):
    """Convenience function for tracing rule execution."""
    return get_rules_instrumentation().trace_execution(
        job_id, ruleset, data, tenant_id, actor_id
    )


def track_rule_performance(
    metrics: RulePerformanceMetrics,
    tenant_id: Optional[str] = None
) -> None:
    """Convenience function for tracking rule performance."""
    get_rules_instrumentation().track_rule_performance(metrics, tenant_id)


def track_cache_operation(
    operation: str,
    cache_key: str,
    hit_rate: float,
    time_saved_ms: Optional[float] = None,
    tenant_id: Optional[str] = None
) -> None:
    """Convenience function for tracking cache operations."""
    get_rules_instrumentation().track_cache_operation(
        operation, cache_key, hit_rate, time_saved_ms, tenant_id
    )


def track_business_impact(
    ruleset_id: str,
    channel: str, 
    revenue_protected_brl: float,
    cost_prevented_brl: float,
    tenant_id: Optional[str] = None
) -> None:
    """Convenience function for tracking business impact."""
    get_rules_instrumentation().track_business_impact(
        ruleset_id, channel, revenue_protected_brl, cost_prevented_brl, tenant_id
    )