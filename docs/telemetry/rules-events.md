# Smart Rules Engine - CloudEvents Specifications

This document defines the CloudEvents 1.0 compliant event schemas for comprehensive observability of ValidaHub's Smart Rules Engine.

## Event Categories

### 1. Rule Compilation Events

#### `rules.compilation.started`
Emitted when rule compilation begins.

```json
{
  "id": "comp_12345",
  "source": "packages/rules/engine/compiler",
  "specversion": "1.0",
  "type": "rules.compilation.started",
  "time": "2024-08-30T14:30:00Z",
  "subject": "ruleset:mercado_livre_v1.2.0",
  "datacontenttype": "application/json",
  "validahub_tenant_id": "tenant_mercado_livre",
  "validahub_trace_id": "trace_456",
  "validahub_actor_id": "user_789",
  "validahub_schema_version": "1",
  "validahub_environment": "production",
  "validahub_service": "rules-engine",
  "data": {
    "ruleset_id": "mercado_livre_v1.2.0",
    "channel": "mercado_livre",
    "version": "1.2.0",
    "rule_count": 45,
    "compilation_mode": "optimized"
  }
}
```

#### `rules.compilation.completed`
Emitted when rule compilation finishes.

```json
{
  "id": "comp_12345_complete",
  "source": "packages/rules/engine/compiler",
  "specversion": "1.0",
  "type": "rules.compilation.completed",
  "time": "2024-08-30T14:30:15Z",
  "subject": "ruleset:mercado_livre_v1.2.0",
  "datacontenttype": "application/json",
  "validahub_tenant_id": "tenant_mercado_livre",
  "validahub_trace_id": "trace_456",
  "validahub_actor_id": "user_789",
  "data": {
    "ruleset_id": "mercado_livre_v1.2.0",
    "channel": "mercado_livre",
    "version": "1.2.0",
    "compilation_duration_ms": 15000,
    "rules_compiled": 45,
    "optimizations_applied": 12,
    "memory_usage_mb": 128.5,
    "compilation_success": true,
    "execution_plan_phases": 3,
    "vectorized_rules": 32,
    "parallel_rules": 8
  }
}
```

#### `rules.compilation.failed`
Emitted when rule compilation fails.

```json
{
  "id": "comp_12345_failed",
  "source": "packages/rules/engine/compiler",
  "specversion": "1.0",
  "type": "rules.compilation.failed",
  "time": "2024-08-30T14:30:05Z",
  "subject": "ruleset:mercado_livre_v1.2.0",
  "datacontenttype": "application/json",
  "validahub_tenant_id": "tenant_mercado_livre",
  "validahub_trace_id": "trace_456",
  "validahub_actor_id": "user_789",
  "data": {
    "ruleset_id": "mercado_livre_v1.2.0",
    "channel": "mercado_livre",
    "version": "1.2.0",
    "compilation_duration_ms": 5000,
    "error_type": "SyntaxError",
    "error_message": "Invalid YAML syntax in rule R_PRICE_001",
    "failed_rule_id": "R_PRICE_001",
    "line_number": 42
  }
}
```

### 2. Rule Execution Events

#### `rules.execution.started`
Emitted when rules engine starts processing a dataset.

```json
{
  "id": "exec_67890",
  "source": "packages/rules/engine/runtime",
  "specversion": "1.0",
  "type": "rules.execution.started",
  "time": "2024-08-30T14:35:00Z",
  "subject": "job:job_12345",
  "datacontenttype": "application/json",
  "validahub_tenant_id": "tenant_mercado_livre",
  "validahub_trace_id": "trace_789",
  "validahub_actor_id": "user_456",
  "data": {
    "job_id": "job_12345",
    "ruleset_id": "mercado_livre_v1.2.0",
    "channel": "mercado_livre",
    "version": "1.2.0",
    "dataset_rows": 10000,
    "dataset_columns": 25,
    "execution_mode": "vectorized",
    "rules_to_execute": 45,
    "estimated_duration_ms": 30000,
    "memory_limit_mb": 1024
  }
}
```

#### `rules.execution.completed`
Emitted when rules engine finishes processing.

```json
{
  "id": "exec_67890_complete",
  "source": "packages/rules/engine/runtime",
  "specversion": "1.0",
  "type": "rules.execution.completed",
  "time": "2024-08-30T14:35:25Z",
  "subject": "job:job_12345",
  "datacontenttype": "application/json",
  "validahub_tenant_id": "tenant_mercado_livre",
  "validahub_trace_id": "trace_789",
  "validahub_actor_id": "user_456",
  "data": {
    "job_id": "job_12345",
    "ruleset_id": "mercado_livre_v1.2.0",
    "channel": "mercado_livre",
    "version": "1.2.0",
    "execution_duration_ms": 25000,
    "dataset_rows": 10000,
    "processed_rows": 10000,
    "rules_executed": 45,
    "vectorized_operations": 32,
    "parallel_operations": 8,
    "cache_hit_rate": 0.85,
    "memory_peak_mb": 512.3,
    "validation_results": {
      "error_count": 150,
      "warning_count": 300,
      "suggestion_count": 75,
      "transformation_count": 50
    },
    "performance_metrics": {
      "throughput_rows_per_second": 400,
      "rules_per_second": 1.8,
      "cpu_usage_percent": 65,
      "memory_efficiency": 0.78
    }
  }
}
```

#### `rules.execution.failed`
Emitted when rules engine execution fails.

```json
{
  "id": "exec_67890_failed",
  "source": "packages/rules/engine/runtime",
  "specversion": "1.0",
  "type": "rules.execution.failed",
  "time": "2024-08-30T14:35:15Z",
  "subject": "job:job_12345",
  "datacontenttype": "application/json",
  "validahub_tenant_id": "tenant_mercado_livre",
  "validahub_trace_id": "trace_789",
  "validahub_actor_id": "user_456",
  "data": {
    "job_id": "job_12345",
    "ruleset_id": "mercado_livre_v1.2.0",
    "channel": "mercado_livre",
    "version": "1.2.0",
    "execution_duration_ms": 15000,
    "dataset_rows": 10000,
    "processed_rows": 3500,
    "error_type": "OutOfMemoryError",
    "error_message": "Exceeded memory limit of 1024MB",
    "failed_at_rule": "R_CONTENT_ANALYSIS",
    "memory_peak_mb": 1024.0
  }
}
```

### 3. Rule Performance Events

#### `rules.performance.measured`
Emitted for detailed performance analysis of individual rules.

```json
{
  "id": "perf_12345",
  "source": "packages/rules/engine/runtime",
  "specversion": "1.0",
  "type": "rules.performance.measured",
  "time": "2024-08-30T14:35:25Z",
  "subject": "rule:R_PRICE_001",
  "datacontenttype": "application/json",
  "validahub_tenant_id": "tenant_mercado_livre",
  "validahub_trace_id": "trace_789",
  "validahub_actor_id": "user_456",
  "data": {
    "rule_id": "R_PRICE_001",
    "ruleset_id": "mercado_livre_v1.2.0",
    "channel": "mercado_livre",
    "version": "1.2.0",
    "job_id": "job_12345",
    "execution_duration_ms": 1500,
    "rows_processed": 10000,
    "violations_found": 45,
    "false_positive_rate": 0.02,
    "precision": 0.94,
    "recall": 0.87,
    "f1_score": 0.90,
    "performance_metrics": {
      "throughput_rows_per_ms": 6.67,
      "memory_usage_mb": 32.1,
      "cpu_cycles": 150000,
      "cache_efficiency": 0.92
    },
    "business_impact": {
      "revenue_protected_brl": 2500.00,
      "cost_prevented_brl": 450.00,
      "time_saved_minutes": 15
    }
  }
}
```

### 4. Rule Effectiveness Events

#### `rules.effectiveness.analyzed`
Emitted for business intelligence on rule effectiveness.

```json
{
  "id": "eff_analysis_123",
  "source": "packages/analytics/rules",
  "specversion": "1.0",
  "type": "rules.effectiveness.analyzed",
  "time": "2024-08-30T15:00:00Z",
  "subject": "ruleset:mercado_livre_v1.2.0",
  "datacontenttype": "application/json",
  "validahub_tenant_id": "tenant_mercado_livre",
  "validahub_trace_id": "trace_analytics",
  "data": {
    "ruleset_id": "mercado_livre_v1.2.0",
    "channel": "mercado_livre",
    "version": "1.2.0",
    "analysis_period_days": 7,
    "jobs_analyzed": 150,
    "total_validations": 1500000,
    "effectiveness_metrics": {
      "overall_accuracy": 0.923,
      "precision": 0.891,
      "recall": 0.876,
      "f1_score": 0.883,
      "false_positive_rate": 0.034
    },
    "business_metrics": {
      "total_revenue_protected_brl": 125000.00,
      "average_revenue_per_validation": 0.083,
      "cost_per_validation_brl": 0.012,
      "roi": 6.92,
      "time_saved_hours": 450
    },
    "rule_distribution": {
      "high_impact_rules": 12,
      "medium_impact_rules": 23,
      "low_impact_rules": 10,
      "underperforming_rules": 3
    }
  }
}
```

### 5. Rule Cache Events

#### `rules.cache.operation`
Emitted for cache operations tracking.

```json
{
  "id": "cache_op_456",
  "source": "packages/rules/engine/runtime",
  "specversion": "1.0",
  "type": "rules.cache.operation",
  "time": "2024-08-30T14:35:10Z",
  "subject": "cache:condition_results",
  "datacontenttype": "application/json",
  "validahub_tenant_id": "tenant_mercado_livre",
  "validahub_trace_id": "trace_789",
  "data": {
    "operation": "hit",
    "cache_type": "condition_results",
    "cache_key": "rule_R_PRICE_001_hash_abc123",
    "ruleset_id": "mercado_livre_v1.2.0",
    "job_id": "job_12345",
    "cache_size": 1024,
    "hit_rate": 0.85,
    "time_saved_ms": 150
  }
}
```

### 6. Rule Version Events

#### `rules.version.deployed`
Emitted when a new rule version is deployed.

```json
{
  "id": "deploy_789",
  "source": "packages/rules/deployment",
  "specversion": "1.0",
  "type": "rules.version.deployed",
  "time": "2024-08-30T13:00:00Z",
  "subject": "ruleset:mercado_livre_v1.2.0",
  "datacontenttype": "application/json",
  "validahub_tenant_id": "tenant_mercado_livre",
  "validahub_trace_id": "trace_deploy",
  "validahub_actor_id": "user_admin",
  "data": {
    "ruleset_id": "mercado_livre_v1.2.0",
    "channel": "mercado_livre",
    "previous_version": "1.1.5",
    "new_version": "1.2.0",
    "deployment_type": "gradual_rollout",
    "rollout_percentage": 10,
    "rules_added": 3,
    "rules_modified": 7,
    "rules_removed": 1,
    "backwards_compatible": true,
    "estimated_impact": {
      "accuracy_improvement": 0.02,
      "performance_impact": -0.05,
      "memory_usage_change_mb": 15.2
    }
  }
}
```

## Event Routing and Processing

### Event Sinks Configuration

1. **Real-time Processing**: Redis Streams for immediate alerting
2. **Analytics Pipeline**: S3 (NDJSON) → Kafka → ClickHouse
3. **Monitoring**: Prometheus metrics extraction
4. **Audit Trail**: PostgreSQL event store

### Sampling Strategy

- **Success Events**: 10% sampling for performance events
- **Error Events**: 100% capture
- **Business Impact Events**: 100% capture
- **Cache Events**: 1% sampling for operational visibility

### Event Correlation

All events include:
- `validahub_tenant_id`: Multi-tenant isolation
- `validahub_trace_id`: Request correlation
- `validahub_actor_id`: User/system attribution
- `job_id`: Job lifecycle tracking (when applicable)
- `ruleset_id`: Rule version tracking

## Schema Evolution

### Version Compatibility
- Events follow semantic versioning via `validahub_schema_version`
- Backward compatibility guaranteed within major versions
- Schema registry validates all event structures

### Required Fields Evolution
New required fields introduced only in major version updates with migration path provided.

## Business Intelligence Integration

### Key Metrics Extracted
- Rule execution performance (latency, throughput, accuracy)
- Business impact (revenue protection, cost savings)
- System efficiency (cache hit rates, memory usage)
- Quality metrics (precision, recall, F1 score)

### Data Retention
- Raw events: 90 days in S3
- Aggregated metrics: Permanent retention
- Audit events: 7 years for compliance

## SLO Monitoring

Events support monitoring of:
- **F1 Score SLO**: ≥ 0.5 (Alert threshold)
- **P95 Latency SLO**: ≤ 800ms (Alert threshold)
- **Cache Hit Rate SLO**: ≥ 0.9 (Alert threshold)
- **Accuracy SLO**: ≥ 0.85
- **Availability SLO**: ≥ 99.5%