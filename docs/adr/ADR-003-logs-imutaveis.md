# ADR-003: Logs Imutáveis

- **Status**: Proposed
- **Data**: 2025-08-29
- **Autor**: PM/BI Visionário

## Contexto

ValidaHub precisa de audit logging para:
- Compliance (LGPD, auditoria fiscal)
- Debugging de jobs falhados
- Analytics de uso por tenant
- Rastreabilidade de mudanças em regras

Requisitos:
- Imutabilidade (append-only)
- Structured logging com tenant_id
- Correlação via request_id
- Retenção configurável por tipo de evento

## Decisão

**Fase 1 (MVP)**: PostgreSQL audit_log table
```sql
CREATE TABLE audit_log (
  id uuid PRIMARY KEY,
  tenant_id text NOT NULL,
  actor_id text NOT NULL,
  action text NOT NULL,
  resource_type text NOT NULL,
  resource_id text NOT NULL,
  request_id text NOT NULL,
  timestamp timestamptz NOT NULL DEFAULT now(),
  payload jsonb NOT NULL,
  version text NOT NULL DEFAULT '1.0'
);
```

**Fase 2 (Escala)**: S3 + ClickHouse
- S3 para storage barato de longo prazo
- ClickHouse para analytics rápidos
- Particionamento por tenant/data

## Consequências

### Positivo
- PostgreSQL: simplicidade, transacional com business logic
- Structured logging desde o início
- Evolução natural para analytics stack
- Compliance ready

### Negativo
- PostgreSQL: crescimento da tabela pode impactar performance
- Custos de storage crescentes
- Query analytics limitada em SQL tradicional

## Alternativas Consideradas

### ELK Stack (direto)
- **Prós**: Purpose-built para logging
- **Contras**: Complexidade operacional, custo alto inicial

### AWS CloudWatch
- **Prós**: Serverless, integração AWS
- **Contras**: Lock-in, structured queries limitadas

### Loki + Grafana
- **Prós**: Otimizado para logs, open source
- **Contras**: Curva de aprendizado, menos maduro