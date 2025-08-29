# ValidaHub Logging Standards & Implementation Guide

## Overview

This document defines the logging standards, patterns, and best practices for the ValidaHub platform. Our logging infrastructure is designed to provide comprehensive observability while maintaining LGPD compliance and supporting multi-tenant isolation.

## Table of Contents
1. [Core Principles](#core-principles)
2. [Logging Architecture](#logging-architecture)
3. [Standard Log Schema](#standard-log-schema)
4. [Implementation Patterns](#implementation-patterns)
5. [Performance Guidelines](#performance-guidelines)
6. [Security & Compliance](#security--compliance)
7. [Monitoring & Alerting](#monitoring--alerting)

## Core Principles

### 1. Structured Logging
All logs MUST be structured JSON with consistent schema:
```python
{
    "timestamp": "2025-08-29T10:30:45.123Z",
    "level": "INFO",
    "event": "job_submitted",
    "service": "validahub",
    "component": "domain.job",
    "tenant_id": "tenant_123",
    "correlation_id": "abc-123-def",
    "duration_ms": 45.2,
    "message": "Job submitted successfully"
}
```

### 2. Multi-Tenant Isolation
Every log entry MUST include `tenant_id` when applicable:
```python
logger.info(
    "operation_completed",
    tenant_id=tenant_id.value,
    resource_id=resource_id,
    correlation_id=get_correlation_id()
)
```

### 3. Correlation Tracking
All logs within a request flow MUST include `correlation_id`:
```python
from shared.logging.context import get_correlation_id

logger.info(
    "processing_started",
    correlation_id=get_correlation_id(),
    ...
)
```

### 4. Performance Metrics
Operations exceeding thresholds MUST log warnings:
- API endpoints: > 500ms
- Database queries: > 100ms
- Use cases: > 500ms
- Domain transitions: > 50ms

## Logging Architecture

### Layer-Specific Loggers

#### Domain Layer
```python
from shared.logging import get_logger

logger = get_logger("domain.job")

# Log state transitions with timing
start_time = time.time()
new_job = replace(self, status=JobStatus.RUNNING)

logger.info(
    "job_state_transition_successful",
    job_id=str(new_job.id.value),
    tenant_id=new_job.tenant_id.value,
    from_status=self.status.value,
    to_status=new_job.status.value,
    transition_duration_ms=(time.time() - start_time) * 1000,
    correlation_id=get_correlation_id()
)
```

#### Application Layer
```python
# Use case with performance breakdown
logger.info(
    "submit_job_use_case_completed",
    tenant_id=request.tenant_id,
    job_id=saved_job.id,
    total_duration_ms=total_duration_ms,
    breakdown={
        "validation_ms": validation_duration_ms,
        "idempotency_check_ms": idempotency_duration_ms,
        "rate_limit_check_ms": rate_limit_duration_ms,
        "job_creation_ms": job_creation_duration_ms,
        "save_ms": save_duration_ms,
        "event_publish_ms": event_publish_duration_ms
    },
    result="success",
    correlation_id=correlation_id
)
```

#### Infrastructure Layer
```python
from src.application.ports.logging import log_repository_query

@log_repository_query(query_type="select", table_name="jobs")
def find_by_id(self, job_id: JobId) -> Optional[Job]:
    # Implementation automatically logged
    pass
```

### Decorators for Consistent Logging

#### Port Operations
```python
from src.application.ports.logging import log_port_operation

@log_port_operation(
    operation_name="save_job",
    log_args=True,
    log_result=False,
    sensitive_args=["password"]
)
def save(self, job: Job) -> Job:
    # Implementation
    pass
```

#### Distributed Tracing
```python
from src.shared.logging.tracing import with_distributed_tracing

@with_distributed_tracing(
    operation_name="process_csv",
    service_name="validahub",
    tags={"job_type": "validation"}
)
def process_csv(self, file_path: str) -> ProcessingResult:
    # Implementation with automatic span tracking
    pass
```

#### Performance Monitoring
```python
from src.shared.logging.tracing import with_performance_logging

@with_performance_logging(
    operation_name="validate_data",
    slow_threshold_ms=200,
    include_args=False
)
def validate_data(self, data: List[Dict]) -> ValidationResult:
    # Implementation with performance tracking
    pass
```

## Standard Log Schema

### Base Fields (Required)
```python
{
    "timestamp": "ISO 8601 timestamp",
    "level": "TRACE|DEBUG|INFO|WARNING|ERROR|CRITICAL",
    "event": "snake_case_event_name",
    "service": "validahub",
    "correlation_id": "request correlation ID"
}
```

### Context Fields (When Applicable)
```python
{
    "tenant_id": "tenant identifier",
    "user_id": "user identifier",
    "job_id": "job identifier",
    "request_id": "HTTP request ID",
    "trace_id": "distributed trace ID",
    "span_id": "span identifier",
    "parent_span_id": "parent span ID"
}
```

### Performance Fields
```python
{
    "duration_ms": 123.45,
    "breakdown": {
        "db_ms": 50.2,
        "cache_ms": 10.3,
        "processing_ms": 62.95
    },
    "performance_level": "fast|normal|slow|critical"
}
```

### Error Fields
```python
{
    "error": "error message",
    "error_type": "ExceptionClassName",
    "stack_trace": "full stack trace (dev only)"
}
```

## Implementation Patterns

### 1. Use Case Pattern
```python
class SubmitJobUseCase:
    def execute(self, request: SubmitJobRequest) -> SubmitJobResponse:
        use_case_start = time.time()
        correlation_id = get_correlation_id()
        
        # Log start
        self._logger.info(
            "submit_job_use_case_started",
            tenant_id=request.tenant_id,
            correlation_id=correlation_id
        )
        
        try:
            # Implementation with step timing
            validation_start = time.time()
            self._validate_request(request)
            validation_duration_ms = (time.time() - validation_start) * 1000
            
            # ... more steps ...
            
            # Log completion with breakdown
            total_duration_ms = (time.time() - use_case_start) * 1000
            self._logger.info(
                "submit_job_use_case_completed",
                tenant_id=request.tenant_id,
                total_duration_ms=total_duration_ms,
                breakdown={...},
                correlation_id=correlation_id
            )
            
        except Exception as e:
            # Log failure
            self._logger.error(
                "submit_job_use_case_failed",
                tenant_id=request.tenant_id,
                error=str(e),
                error_type=e.__class__.__name__,
                correlation_id=correlation_id
            )
            raise
```

### 2. Repository Pattern
```python
class JobRepository:
    @log_repository_query(query_type="select", table_name="jobs")
    def find_by_tenant(self, tenant_id: TenantId) -> List[Job]:
        # Query automatically logged with:
        # - Query type and table
        # - Tenant isolation
        # - Duration and row count
        # - Slow query warnings
        pass
```

### 3. Rate Limiter Pattern
```python
@log_rate_limit_check
def check_and_consume(self, tenant_id: TenantId, resource: str) -> bool:
    # Automatically logs:
    # - Rate limit decisions (allowed/denied)
    # - Remaining tokens
    # - Time until tokens available
    # - Denial rates
    pass
```

### 4. Event Bus Pattern
```python
@log_event_publish
def publish(self, event: DomainEvent) -> None:
    # Automatically logs:
    # - Event metadata (type, ID, tenant)
    # - Publishing duration
    # - Success/failure status
    # - Subscriber notifications
    pass
```

## Performance Guidelines

### Logging Levels by Environment

| Environment | Default Level | Slow Query Threshold | Include Caller Info |
|-------------|--------------|---------------------|-------------------|
| Development | DEBUG        | 50ms                | Yes               |
| Staging     | INFO         | 100ms               | No                |
| Production  | INFO         | 100ms               | No                |

### Performance Thresholds

| Operation Type        | Fast    | Normal  | Slow    | Critical |
|----------------------|---------|---------|---------|----------|
| API Endpoint         | < 50ms  | < 200ms | < 1000ms| >= 1000ms|
| Database Query       | < 20ms  | < 100ms | < 500ms | >= 500ms |
| Use Case Execution   | < 100ms | < 500ms | < 2000ms| >= 2000ms|
| Domain Transition    | < 10ms  | < 50ms  | < 200ms | >= 200ms |
| Event Publishing     | < 10ms  | < 50ms  | < 200ms | >= 200ms |

### When to Log

| Level    | When to Use | Examples |
|----------|------------|----------|
| TRACE    | Detailed debugging | Method entry/exit, variable values |
| DEBUG    | Development info | Validation steps, cache hits/misses |
| INFO     | Normal operations | Request completed, job submitted |
| WARNING  | Potential issues | Slow queries, rate limit approaching |
| ERROR    | Failures | Exception caught, operation failed |
| CRITICAL | System issues | Database down, out of memory |

## Security & Compliance

### LGPD Compliance

1. **Data Sanitization**
```python
# Automatic sanitization via LGPDProcessor
logger.info(
    "user_data_processed",
    email="user@example.com",  # Automatically masked to "u***@example.com"
    cpf="123.456.789-00",      # Automatically masked to "***"
    phone="+5511999999999"     # Automatically masked to "+55***"
)
```

2. **Sensitive Data Handling**
```python
@log_port_operation(
    operation_name="authenticate",
    sensitive_args=["password", "token"]  # These will be redacted
)
```

3. **Audit Logging**
```python
from shared.logging.security import AuditLogger, AuditEventType

audit = AuditLogger("domain.job")
audit.job_lifecycle(
    event_type=AuditEventType.JOB_SUBMITTED,
    job_id=job_id,
    tenant_id=tenant_id,
    actor_id=user_id
)
```

### Security Events

```python
# Log security-relevant events
logger.warning(
    "authentication_failed",
    tenant_id=tenant_id,
    user_id=user_id,
    reason="invalid_credentials",
    ip_address=request.client.host,
    correlation_id=correlation_id
)

# Log authorization violations
logger.error(
    "tenant_isolation_violation_attempted",
    requesting_tenant=requesting_tenant_id,
    resource_tenant=resource_tenant_id,
    resource_id=resource_id,
    correlation_id=correlation_id
)
```

## Monitoring & Alerting

### Key Metrics to Monitor

1. **Error Rates**
```json
{
    "metric": "error_rate",
    "query": "level='ERROR' | count by tenant_id",
    "threshold": "> 1% of requests",
    "action": "Page on-call engineer"
}
```

2. **Performance Degradation**
```json
{
    "metric": "p95_latency",
    "query": "duration_ms | percentile(95) by operation",
    "threshold": "> 2x baseline",
    "action": "Alert team"
}
```

3. **Rate Limiting**
```json
{
    "metric": "rate_limit_denials",
    "query": "event='rate_limit_exceeded' | count by tenant_id",
    "threshold": "> 10 per minute",
    "action": "Notify customer success"
}
```

### Dashboard Queries

```sql
-- Slow queries by tenant
SELECT 
    tenant_id,
    operation,
    COUNT(*) as count,
    AVG(duration_ms) as avg_duration,
    MAX(duration_ms) as max_duration
FROM logs
WHERE 
    event = 'database_query_completed' 
    AND duration_ms > 100
GROUP BY tenant_id, operation
ORDER BY avg_duration DESC;

-- Error distribution
SELECT 
    error_type,
    COUNT(*) as count,
    COUNT(DISTINCT tenant_id) as affected_tenants
FROM logs
WHERE level = 'ERROR'
GROUP BY error_type
ORDER BY count DESC;

-- Use case performance breakdown
SELECT 
    JSON_EXTRACT(breakdown, '$.validation_ms') as validation,
    JSON_EXTRACT(breakdown, '$.save_ms') as save,
    JSON_EXTRACT(breakdown, '$.event_publish_ms') as publish
FROM logs
WHERE event = 'submit_job_use_case_completed';
```

## Testing Logging

### Unit Tests for Logging
```python
def test_job_state_transition_logging(caplog):
    """Test that state transitions are properly logged."""
    job = Job.create(TenantId("tenant_123"))
    
    with caplog.at_level(logging.INFO):
        job.start()
    
    # Verify log entry
    assert "job_state_transition_successful" in caplog.text
    assert "tenant_123" in caplog.text
    assert "from_status" in caplog.text
    assert "to_status" in caplog.text
    assert "duration_ms" in caplog.text
```

### Integration Tests
```python
def test_use_case_performance_logging(client, caplog):
    """Test use case logs performance breakdown."""
    response = client.post("/jobs", json={...})
    
    # Find the completion log
    for record in caplog.records:
        if record.msg == "submit_job_use_case_completed":
            assert "breakdown" in record.__dict__
            assert "total_duration_ms" in record.__dict__
            assert record.total_duration_ms < 500  # SLO check
```

## Migration Guide

### Adding Logging to Existing Code

1. **Identify the layer** (domain, application, infrastructure)
2. **Get appropriate logger**: `logger = get_logger("component.name")`
3. **Add operation timing**: Use `time.time()` at start/end
4. **Include required fields**: tenant_id, correlation_id
5. **Add performance warnings**: Check against thresholds
6. **Test the logging**: Verify in unit tests

### Example Migration
```python
# Before
def process_job(self, job_id: str):
    job = self.repository.get(job_id)
    job.process()
    self.repository.save(job)
    return job

# After
def process_job(self, job_id: str):
    start_time = time.time()
    
    self._logger.info(
        "job_processing_started",
        job_id=job_id,
        correlation_id=get_correlation_id()
    )
    
    try:
        job = self.repository.get(job_id)
        job.process()
        self.repository.save(job)
        
        duration_ms = (time.time() - start_time) * 1000
        self._logger.info(
            "job_processing_completed",
            job_id=job_id,
            tenant_id=job.tenant_id.value,
            duration_ms=duration_ms,
            correlation_id=get_correlation_id()
        )
        
        return job
        
    except Exception as e:
        self._logger.error(
            "job_processing_failed",
            job_id=job_id,
            error=str(e),
            correlation_id=get_correlation_id()
        )
        raise
```

## Checklist for Developers

- [ ] All operations include correlation_id
- [ ] Multi-tenant operations include tenant_id
- [ ] Performance metrics are collected (duration_ms)
- [ ] Slow operations trigger warnings
- [ ] Errors include error type and message
- [ ] Sensitive data is never logged directly
- [ ] Security events are logged appropriately
- [ ] Unit tests verify logging behavior
- [ ] Documentation is updated for new log events