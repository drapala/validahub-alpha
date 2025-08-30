# Smart Rules Engine Events

## Overview

Este documento define os esquemas de eventos de domínio e integração do Smart Rules Engine, seguindo a especificação CloudEvents 1.0.

## Domain Events

### RuleSetCreatedEvent

Emitido quando um novo RuleSet é criado.

```json
{
  "specversion": "1.0",
  "type": "com.validahub.rules.ruleset.created.v1",
  "source": "https://api.validahub.com/rules",
  "subject": "rules/rulesets/{rule_set_id}",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "time": "2024-01-15T10:30:00Z",
  "datacontenttype": "application/json",
  "data": {
    "rule_set_id": "550e8400-e29b-41d4-a716-446655440001",
    "tenant_id": "t_acme_corp",
    "channel": "mercado_livre",
    "name": "Regras de Validação ML - Janeiro 2024",
    "created_by": "user_123",
    "created_at": "2024-01-15T10:30:00Z",
    "correlation_id": "req_abc123"
  }
}
```

### RuleSetPublishedEvent

Emitido quando uma versão do RuleSet é publicada.

```json
{
  "specversion": "1.0",
  "type": "com.validahub.rules.ruleset.published.v1",
  "source": "https://api.validahub.com/rules",
  "subject": "rules/rulesets/{rule_set_id}/versions/{version}",
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "time": "2024-01-15T11:00:00Z",
  "datacontenttype": "application/json",
  "data": {
    "rule_set_id": "550e8400-e29b-41d4-a716-446655440001",
    "tenant_id": "t_acme_corp",
    "version": "1.0.0",
    "is_current": true,
    "checksum": "sha256:abc123def456",
    "published_by": "user_123",
    "published_at": "2024-01-15T11:00:00Z",
    "rule_count": 25,
    "correlation_id": "req_abc124"
  }
}
```

### RuleSetDeprecatedEvent

Emitido quando uma versão é marcada como deprecated.

```json
{
  "specversion": "1.0",
  "type": "com.validahub.rules.ruleset.deprecated.v1",
  "source": "https://api.validahub.com/rules",
  "subject": "rules/rulesets/{rule_set_id}/versions/{version}",
  "id": "550e8400-e29b-41d4-a716-446655440003",
  "time": "2024-02-01T09:00:00Z",
  "datacontenttype": "application/json",
  "data": {
    "rule_set_id": "550e8400-e29b-41d4-a716-446655440001",
    "tenant_id": "t_acme_corp",
    "version": "0.9.0",
    "reason": "Versão substituída por 1.0.0 com melhorias significativas",
    "deprecated_by": "user_456",
    "deprecated_at": "2024-02-01T09:00:00Z",
    "sunset_date": "2024-03-01T00:00:00Z",
    "correlation_id": "req_def789"
  }
}
```

### RuleVersionCreatedEvent

Emitido quando uma nova versão de regras é criada.

```json
{
  "specversion": "1.0",
  "type": "com.validahub.rules.version.created.v1",
  "source": "https://api.validahub.com/rules",
  "subject": "rules/versions/{rule_version_id}",
  "id": "550e8400-e29b-41d4-a716-446655440004",
  "time": "2024-01-15T10:45:00Z",
  "datacontenttype": "application/json",
  "data": {
    "rule_version_id": "660e8400-e29b-41d4-a716-446655440001",
    "rule_set_id": "550e8400-e29b-41d4-a716-446655440001",
    "tenant_id": "t_acme_corp",
    "version": "1.0.0",
    "status": "draft",
    "rule_count": 25,
    "created_by": "user_123",
    "created_at": "2024-01-15T10:45:00Z",
    "correlation_id": "req_ghi012"
  }
}
```

### RuleValidatedEvent

Emitido quando regras são validadas.

```json
{
  "specversion": "1.0",
  "type": "com.validahub.rules.validated.v1",
  "source": "https://api.validahub.com/rules",
  "subject": "rules/versions/{rule_version_id}",
  "id": "550e8400-e29b-41d4-a716-446655440005",
  "time": "2024-01-15T10:50:00Z",
  "datacontenttype": "application/json",
  "data": {
    "rule_version_id": "660e8400-e29b-41d4-a716-446655440001",
    "tenant_id": "t_acme_corp",
    "version": "1.0.0",
    "validation_result": true,
    "error_count": 0,
    "warning_count": 2,
    "validated_by": "user_123",
    "validated_at": "2024-01-15T10:50:00Z",
    "validation_duration_ms": 1250,
    "correlation_id": "req_jkl345"
  }
}
```

### RuleSetRolledBackEvent

Emitido quando há rollback para versão anterior.

```json
{
  "specversion": "1.0",
  "type": "com.validahub.rules.ruleset.rolledback.v1",
  "source": "https://api.validahub.com/rules",
  "subject": "rules/rulesets/{rule_set_id}",
  "id": "550e8400-e29b-41d4-a716-446655440006",
  "time": "2024-01-16T14:30:00Z",
  "datacontenttype": "application/json",
  "data": {
    "rule_set_id": "550e8400-e29b-41d4-a716-446655440001",
    "tenant_id": "t_acme_corp",
    "from_version": "1.1.0",
    "to_version": "1.0.0",
    "reason": "Alta taxa de falsos positivos detectada na versão 1.1.0",
    "rolled_back_by": "user_789",
    "rolled_back_at": "2024-01-16T14:30:00Z",
    "correlation_id": "req_mno678"
  }
}
```

## Integration Events

### RulesReadyForJobEvent

Evento de integração indicando que regras estão prontas para serem aplicadas a um job.

```json
{
  "specversion": "1.0",
  "type": "com.validahub.integration.rules.ready.v1",
  "source": "https://api.validahub.com/rules",
  "subject": "jobs/{job_id}",
  "id": "770e8400-e29b-41d4-a716-446655440001",
  "time": "2024-01-15T12:00:00Z",
  "datacontenttype": "application/json",
  "data": {
    "job_id": "880e8400-e29b-41d4-a716-446655440001",
    "tenant_id": "t_acme_corp",
    "rule_set_id": "550e8400-e29b-41d4-a716-446655440001",
    "rule_version": "1.0.0",
    "channel": "mercado_livre",
    "total_rules": 25,
    "cache_key": "rules:compiled:t_acme_corp:mercado_livre:1.0.0:abc123",
    "correlation_id": "req_pqr901"
  }
}
```

### RuleSetAppliedEvent

Evento indicando que um conjunto de regras foi aplicado a um job.

```json
{
  "specversion": "1.0",
  "type": "com.validahub.integration.rules.applied.v1",
  "source": "https://api.validahub.com/jobs",
  "subject": "jobs/{job_id}",
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "time": "2024-01-15T12:05:00Z",
  "datacontenttype": "application/json",
  "data": {
    "job_id": "880e8400-e29b-41d4-a716-446655440001",
    "tenant_id": "t_acme_corp",
    "rule_set_id": "550e8400-e29b-41d4-a716-446655440001",
    "rule_version": "1.0.0",
    "total_rules": 25,
    "rules_passed": 20,
    "rules_failed": 5,
    "rows_processed": 1000,
    "violations_found": 150,
    "evaluation_duration_ms": 3500,
    "correlation_id": "req_stu234"
  }
}
```

### RuleViolationDetectedEvent

Evento emitido quando uma violação de regra é detectada.

```json
{
  "specversion": "1.0",
  "type": "com.validahub.integration.violation.detected.v1",
  "source": "https://api.validahub.com/validation",
  "subject": "jobs/{job_id}/violations",
  "id": "770e8400-e29b-41d4-a716-446655440003",
  "time": "2024-01-15T12:03:00Z",
  "datacontenttype": "application/json",
  "data": {
    "job_id": "880e8400-e29b-41d4-a716-446655440001",
    "tenant_id": "t_acme_corp",
    "rule_id": "product_title_length",
    "rule_version": "1.0.0",
    "field": "title",
    "severity": "error",
    "row_number": 42,
    "column_name": "product_title",
    "original_value": "TV",
    "expected_format": "minimum 10 characters",
    "message": "Título do produto muito curto",
    "violation_details": {
      "actual_length": 2,
      "minimum_length": 10,
      "maximum_length": 200
    },
    "correlation_id": "req_vwx567"
  }
}
```

### RuleEvaluationEvent

Evento detalhado de avaliação de uma regra individual.

```json
{
  "specversion": "1.0",
  "type": "com.validahub.integration.rule.evaluated.v1",
  "source": "https://api.validahub.com/validation",
  "subject": "jobs/{job_id}/evaluations",
  "id": "770e8400-e29b-41d4-a716-446655440004",
  "time": "2024-01-15T12:02:30Z",
  "datacontenttype": "application/json",
  "data": {
    "job_id": "880e8400-e29b-41d4-a716-446655440001",
    "tenant_id": "t_acme_corp",
    "rule_id": "price_range",
    "rule_version": "1.0.0",
    "field": "price",
    "value": 999999.99,
    "passed": false,
    "severity": "warning",
    "message": "Preço fora do intervalo esperado",
    "evaluation_context": {
      "row_index": 100,
      "product_category": "electronics",
      "marketplace": "mercado_livre"
    },
    "evaluation_duration_ms": 0.5,
    "correlation_id": "req_yzab890"
  }
}
```

## Event Schemas

### Common Event Properties

Todos os eventos seguem o padrão CloudEvents 1.0 com as seguintes propriedades comuns:

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| specversion | string | Yes | CloudEvents version (sempre "1.0") |
| type | string | Yes | Tipo do evento no formato reverse-DNS |
| source | URI | Yes | URI identificando a origem do evento |
| subject | string | No | Contexto do evento dentro da origem |
| id | string | Yes | Identificador único do evento |
| time | timestamp | Yes | Timestamp RFC3339 quando o evento ocorreu |
| datacontenttype | string | Yes | Tipo do conteúdo (sempre "application/json") |
| data | object | Yes | Payload específico do evento |

### Data Schema Validation

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "RuleSetCreatedEvent",
  "type": "object",
  "required": ["rule_set_id", "tenant_id", "channel", "name", "created_by", "created_at"],
  "properties": {
    "rule_set_id": {
      "type": "string",
      "format": "uuid"
    },
    "tenant_id": {
      "type": "string",
      "pattern": "^t_[a-z0-9_]{1,47}$"
    },
    "channel": {
      "type": "string",
      "enum": ["mercado_livre", "magalu", "americanas", "shopee", "amazon"]
    },
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 100
    },
    "created_by": {
      "type": "string"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "correlation_id": {
      "type": "string"
    }
  }
}
```

## Event Routing

### Topics e Subscriptions

| Event Type | Topic | Subscribers |
|------------|-------|-------------|
| RuleSetCreatedEvent | rules.created | Audit Service, Analytics |
| RuleSetPublishedEvent | rules.published | Job Service, Cache Service |
| RuleViolationDetectedEvent | violations.detected | Corrections Service, Analytics |
| RuleSetAppliedEvent | rules.applied | Metrics Service, Billing |

### Retry Policy

```yaml
retry_policy:
  max_attempts: 3
  initial_delay: 1s
  max_delay: 10s
  multiplier: 2
  dead_letter_queue: dlq.{topic_name}
```

### Event Ordering

- Eventos do mesmo agregado mantêm ordem (partition key = aggregate_id)
- Eventos entre agregados são eventualmente consistentes
- Use correlation_id para rastrear fluxos relacionados