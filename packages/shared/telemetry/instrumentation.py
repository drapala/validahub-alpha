"""
Comprehensive instrumentation guide and helpers for ValidaHub telemetry.

This module provides decorators, context managers, and utilities to make
instrumenting ValidaHub code simple and consistent.
"""

import asyncio
import functools
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from .emitter import get_emitter, track_business_event, track_job_lifecycle
from .envelope import create_event, create_technical_event
from .metrics import get_metrics
from .usage_tracker import UserAction, track_feature_usage, track_user_action


def instrument_job_processing(
    job_type: str,
    estimate_revenue_fn: Callable[[str, str], float] | None = None,
    estimate_cost_fn: Callable[[str, str], float] | None = None
):
    """
    Decorator for instrumenting job processing functions.
    
    Usage:
        @instrument_job_processing("validation")
        async def process_validation_job(job_id: str, tenant_id: str):
            # Job processing logic
            return result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract job context (assumes first two args are job_id, tenant_id)
            job_id = str(args[0]) if args else kwargs.get('job_id', 'unknown')
            tenant_id = str(args[1]) if len(args) > 1 else kwargs.get('tenant_id', 'unknown')
            
            start_time = time.time()
            emitter = get_emitter()
            
            # Start job processing span
            with emitter.span(
                f"job.{job_type}.processing",
                tags={
                    "job_id": job_id,
                    "tenant_id": tenant_id,
                    "job_type": job_type,
                },
                emit_event_on_completion=True,
                event_type=f"job.{job_type}.processing"
            ) as span:
                try:
                    # Execute job processing
                    result = await func(*args, **kwargs)
                    
                    # Calculate metrics
                    duration_seconds = time.time() - start_time
                    
                    # Extract result metrics
                    error_count = getattr(result, 'error_count', 0)
                    warning_count = getattr(result, 'warning_count', 0) 
                    total_records = getattr(result, 'total_records', 0)
                    
                    # Estimate business impact
                    revenue_impact = None
                    if estimate_revenue_fn:
                        try:
                            revenue_impact = estimate_revenue_fn(job_id, tenant_id)
                        except Exception:
                            pass
                    
                    cost_impact = None
                    if estimate_cost_fn:
                        try:
                            cost_impact = estimate_cost_fn(job_id, tenant_id)
                        except Exception:
                            pass
                    
                    # Track comprehensive job lifecycle
                    track_job_lifecycle(
                        job_id=job_id,
                        tenant_id=tenant_id,
                        channel=kwargs.get('channel', 'unknown'),
                        job_type=job_type,
                        old_status="running",
                        new_status="succeeded",
                        duration_seconds=duration_seconds,
                        error_count=error_count,
                        warning_count=warning_count,
                        total_records=total_records,
                        revenue_attribution_brl=revenue_impact
                    )
                    
                    # Add success attributes to span
                    span.set_attributes({
                        "success": True,
                        "duration_seconds": duration_seconds,
                        "error_count": error_count,
                        "warning_count": warning_count,
                        "total_records": total_records,
                    })
                    
                    if revenue_impact:
                        span.set_attribute("revenue_impact_brl", revenue_impact)
                    if cost_impact:
                        span.set_attribute("cost_impact_brl", cost_impact)
                    
                    return result
                    
                except Exception as error:
                    # Calculate metrics for failed job
                    duration_seconds = time.time() - start_time
                    
                    # Track failed job lifecycle  
                    track_job_lifecycle(
                        job_id=job_id,
                        tenant_id=tenant_id,
                        channel=kwargs.get('channel', 'unknown'),
                        job_type=job_type,
                        old_status="running",
                        new_status="failed",
                        duration_seconds=duration_seconds
                    )
                    
                    # Add error attributes to span
                    span.set_attributes({
                        "success": False,
                        "error_type": error.__class__.__name__,
                        "error_message": str(error),
                        "duration_seconds": duration_seconds,
                    })
                    
                    raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, convert to async context
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def instrument_api_endpoint(
    endpoint_name: str,
    track_business_metrics: bool = True,
    estimate_revenue_impact: float | None = None
):
    """
    Decorator for instrumenting API endpoints.
    
    Usage:
        @instrument_api_endpoint("submit_job", track_business_metrics=True)
        async def submit_job(request: Request):
            # Endpoint logic
            return response
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            emitter = get_emitter()
            
            # Extract request context
            request = None
            for arg in args:
                if hasattr(arg, 'state') and hasattr(arg.state, 'tenant_id'):
                    request = arg
                    break
            
            tenant_id = getattr(request.state, 'tenant_id', 'unknown') if request else 'unknown'
            user_id = getattr(request.state, 'user_id', 'unknown') if request else 'unknown'
            request_id = getattr(request.state, 'request_id', 'unknown') if request else 'unknown'
            
            # Start API span
            with emitter.span(
                f"api.{endpoint_name}",
                tags={
                    "endpoint": endpoint_name,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "request_id": request_id,
                },
                emit_event_on_completion=True,
                event_type=f"api.{endpoint_name}.completed"
            ) as span:
                try:
                    # Execute endpoint logic
                    response = await func(*args, **kwargs)
                    
                    # Calculate metrics
                    duration_ms = (time.time() - start_time) * 1000
                    status_code = getattr(response, 'status_code', 200)
                    
                    # Track API performance metrics
                    metrics = get_metrics()
                    metrics.histogram(
                        "api_endpoint_duration_ms",
                        duration_ms,
                        {
                            "endpoint": endpoint_name,
                            "status": str(status_code),
                            "tenant_id": tenant_id,
                        }
                    )
                    
                    # Track business metrics if enabled
                    if track_business_metrics and estimate_revenue_impact:
                        track_business_event(
                            event_type=f"api.{endpoint_name}.revenue_attributed",
                            business_data={
                                "endpoint": endpoint_name,
                                "user_id": user_id,
                                "request_id": request_id,
                                "duration_ms": duration_ms,
                            },
                            revenue_impact_brl=estimate_revenue_impact,
                            tenant_id=tenant_id,
                            actor_id=user_id
                        )
                    
                    # Add success attributes
                    span.set_attributes({
                        "success": True,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    })
                    
                    return response
                    
                except Exception as error:
                    # Calculate error metrics
                    duration_ms = (time.time() - start_time) * 1000
                    
                    # Track error metrics
                    metrics = get_metrics()
                    metrics.increment(
                        "api_endpoint_errors_total",
                        1.0,
                        {
                            "endpoint": endpoint_name,
                            "error_type": error.__class__.__name__,
                            "tenant_id": tenant_id,
                        }
                    )
                    
                    # Add error attributes
                    span.set_attributes({
                        "success": False,
                        "error_type": error.__class__.__name__,
                        "error_message": str(error),
                        "duration_ms": duration_ms,
                    })
                    
                    raise
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            # Convert sync function to async
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return asyncio.run(async_wrapper(*args, **kwargs))
            return sync_wrapper
    
    return decorator


def instrument_feature_usage(
    feature_name: str,
    feature_category: str = "unknown",
    track_revenue: bool = False,
    revenue_attribution: float | None = None
):
    """
    Decorator for instrumenting feature usage.
    
    Usage:
        @instrument_feature_usage("advanced_filtering", "advanced")
        def apply_advanced_filter(user_id: str, tenant_id: str, filters: dict):
            # Feature logic
            return result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract user context
            user_id = kwargs.get('user_id') or (args[0] if args else 'unknown')
            tenant_id = kwargs.get('tenant_id') or (args[1] if len(args) > 1 else 'unknown')
            session_id = kwargs.get('session_id')
            
            # Track feature usage
            track_feature_usage(
                feature_name=feature_name,
                user_id=str(user_id),
                tenant_id=str(tenant_id),
                session_id=session_id,
                usage_context={
                    "feature_category": feature_category,
                    "function_name": func.__name__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                }
            )
            
            # Track user action
            track_user_action(
                UserAction.FEATURE_USED,
                user_id=str(user_id),
                tenant_id=str(tenant_id),
                session_id=session_id,
                context={
                    "feature_name": feature_name,
                    "feature_category": feature_category,
                },
                revenue_impact=revenue_attribution if track_revenue else None
            )
            
            # Execute function
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Track performance metric
                get_metrics().histogram(
                    "feature_usage_duration_ms",
                    duration_ms,
                    {
                        "feature_name": feature_name,
                        "feature_category": feature_category,
                        "tenant_id": str(tenant_id),
                    }
                )
                
                return result
                
            except Exception as error:
                # Track feature error
                get_metrics().increment(
                    "feature_usage_errors_total",
                    1.0,
                    {
                        "feature_name": feature_name,
                        "error_type": error.__class__.__name__,
                        "tenant_id": str(tenant_id),
                    }
                )
                raise
        
        return wrapper
    return decorator


@contextmanager
def track_operation(
    operation_name: str,
    tenant_id: str,
    user_id: str | None = None,
    business_impact: float | None = None,
    emit_events: bool = True
):
    """
    Context manager for tracking custom operations.
    
    Usage:
        with track_operation("data_export", tenant_id="t_123", user_id="u_456"):
            # Operation logic
            export_data()
    """
    start_time = time.time()
    emitter = get_emitter()
    
    # Start operation span
    span_tags = {
        "operation": operation_name,
        "tenant_id": tenant_id,
    }
    if user_id:
        span_tags["user_id"] = user_id
    
    with emitter.span(
        f"operation.{operation_name}",
        tags=span_tags,
        emit_event_on_completion=emit_events,
        event_type=f"operation.{operation_name}.completed"
    ) as span:
        try:
            yield span
            
            # Calculate duration
            duration_seconds = time.time() - start_time
            
            # Track operation metrics
            get_metrics().histogram(
                "operation_duration_seconds",
                duration_seconds,
                {
                    "operation": operation_name,
                    "tenant_id": tenant_id,
                    "success": "true",
                }
            )
            
            # Track business impact if provided
            if business_impact and emit_events:
                track_business_event(
                    event_type=f"operation.{operation_name}.business_impact",
                    business_data={
                        "operation": operation_name,
                        "duration_seconds": duration_seconds,
                        "user_id": user_id,
                    },
                    revenue_impact_brl=business_impact,
                    tenant_id=tenant_id,
                    actor_id=user_id
                )
            
            span.set_attributes({
                "success": True,
                "duration_seconds": duration_seconds,
            })
            
        except Exception as error:
            duration_seconds = time.time() - start_time
            
            # Track error metrics
            get_metrics().increment(
                "operation_errors_total",
                1.0,
                {
                    "operation": operation_name,
                    "error_type": error.__class__.__name__,
                    "tenant_id": tenant_id,
                }
            )
            
            span.set_attributes({
                "success": False,
                "error_type": error.__class__.__name__,
                "error_message": str(error),
                "duration_seconds": duration_seconds,
            })
            
            raise


def track_data_quality_metrics(
    tenant_id: str,
    channel: str,
    validation_results: dict[str, Any],
    job_id: str | None = None
):
    """
    Track comprehensive data quality metrics.
    
    Usage:
        track_data_quality_metrics(
            tenant_id="t_123",
            channel="mercado_livre", 
            validation_results={
                "total_records": 1000,
                "error_count": 50,
                "warning_count": 100,
                "categories": {"pricing": 20, "content": 30}
            }
        )
    """
    emitter = get_emitter()
    
    # Extract metrics from validation results
    total_records = validation_results.get("total_records", 0)
    error_count = validation_results.get("error_count", 0)
    warning_count = validation_results.get("warning_count", 0)
    categories = validation_results.get("categories", {})
    
    # Calculate quality score
    if total_records > 0:
        error_rate = error_count / total_records
        warning_rate = warning_count / total_records
        quality_score = max(0, 100 - (error_rate * 80) - (warning_rate * 20))
    else:
        quality_score = 0
    
    # Track overall quality metrics
    metrics = get_metrics()
    base_tags = {
        "tenant_id": tenant_id,
        "channel": channel,
    }
    
    metrics.gauge("data_quality_score", quality_score, base_tags)
    metrics.histogram("validation_error_rate", error_rate if total_records > 0 else 0, base_tags)
    metrics.histogram("validation_warning_rate", warning_rate if total_records > 0 else 0, base_tags)
    
    # Track category-specific metrics
    for category, count in categories.items():
        category_tags = {**base_tags, "error_category": category}
        metrics.histogram("validation_errors_by_category", count, category_tags)
    
    # Emit data quality event
    if total_records > 0:  # Only emit if there's actual data
        event = create_technical_event(
            event_type="data_quality.measured",
            technical_data={
                "tenant_id": tenant_id,
                "channel": channel,
                "job_id": job_id,
                "quality_score": quality_score,
                "total_records": total_records,
                "error_count": error_count,
                "warning_count": warning_count,
                "error_categories": categories,
            },
            performance_metrics={
                "quality_score": quality_score,
                "error_rate": error_rate,
                "warning_rate": warning_rate,
            },
            source="data_quality.tracker"
        )
        
        asyncio.create_task(emitter.emit_event(event, force_emit=True))


def track_marketplace_intelligence(
    channel: str,
    rule_id: str,
    rule_performance: dict[str, Any],
    business_impact: dict[str, float] | None = None
):
    """
    Track marketplace-specific intelligence metrics.
    
    Usage:
        track_marketplace_intelligence(
            channel="mercado_livre",
            rule_id="pricing_validation_v2",
            rule_performance={
                "accuracy": 0.95,
                "precision": 0.92,
                "recall": 0.88,
                "applications": 1500
            },
            business_impact={
                "revenue_protected_brl": 15000.0,
                "cost_avoided_brl": 3000.0
            }
        )
    """
    emitter = get_emitter()
    
    # Track rule effectiveness metrics
    metrics = get_metrics()
    rule_tags = {
        "channel": channel,
        "rule_id": rule_id,
    }
    
    if "accuracy" in rule_performance:
        metrics.gauge("rule_accuracy", rule_performance["accuracy"], rule_tags)
    if "precision" in rule_performance:
        metrics.gauge("rule_precision", rule_performance["precision"], rule_tags)
    if "recall" in rule_performance:
        metrics.gauge("rule_recall", rule_performance["recall"], rule_tags)
    if "applications" in rule_performance:
        metrics.histogram("rule_applications", rule_performance["applications"], rule_tags)
    
    # Emit marketplace intelligence event
    event_data = {
        "channel": channel,
        "rule_id": rule_id,
        "performance_metrics": rule_performance,
    }
    
    if business_impact:
        event_data["business_impact"] = business_impact
    
    event = create_event(
        event_type="marketplace.intelligence.rule_performance",
        data=event_data,
        subject=f"rule:{rule_id}",
        source="marketplace.intelligence"
    )
    
    asyncio.create_task(emitter.emit_event(event, force_emit=True))


# Convenience function for quick instrumentation
def quick_track(
    event_name: str,
    tenant_id: str,
    user_id: str | None = None,
    data: dict[str, Any] | None = None,
    revenue_impact: float | None = None
):
    """
    Quick tracking function for ad-hoc events.
    
    Usage:
        quick_track(
            "custom_feature_used",
            tenant_id="t_123",
            user_id="u_456",
            data={"feature": "advanced_export", "format": "xlsx"},
            revenue_impact=5.0
        )
    """
    emitter = get_emitter()
    
    if revenue_impact:
        emitter.track_business_event(
            event_type=event_name,
            business_data=data or {},
            revenue_impact_brl=revenue_impact,
            tenant_id=tenant_id,
            actor_id=user_id
        )
    else:
        event = create_event(
            event_type=event_name,
            data=data or {},
            tenant_id=tenant_id,
            actor_id=user_id,
            source="quick.tracker"
        )
        asyncio.create_task(emitter.emit_event(event))