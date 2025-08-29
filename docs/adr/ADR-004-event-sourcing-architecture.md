# ADR-004: Event Sourcing Architecture

- **Status**: Proposed
- **Data**: 2025-08-29
- **Autor**: Architecture Decision Architect

## Contexto

ValidaHub está evoluindo de utilitário CSV para plataforma de inteligência de marketplace. Cada job de validação contém dados valiosos sobre produtos, qualidade de catálogos, padrões de erro e tendências de mercado. Atualmente perdemos essas informações após processar e retornar o CSV corrigido.

Necessidades identificadas:
- Capturar histórico completo de cada validação para analytics
- Preservar dados anonimizados para benchmarking entre tenants  
- Habilitar insights sobre qualidade de catálogos por categoria/marketplace
- Construir dataset para modelos de ML de predição de qualidade

## Alternativas Consideradas

### Opção A: Log-based Analytics (status quo)
- **Prós**: Simples, já implementado
- **Contras**: Logs são temporários, estrutura inconsistente, dificulta queries analíticas

### Opção B: Event Sourcing Completo
- **Prós**: Auditoria completa, replay capability, flexibilidade temporal
- **Contras**: Complexidade alta, overhead de storage, eventual consistency

### Opção C: Hybrid Event Store (escolhido)
- **Prós**: Balance entre auditoria e simplicidade, foco em analytics
- **Contras**: Não permite replay completo do estado

## Decisão

Implementar **Hybrid Event Store** focado em captura de inteligência:

- Event Store para capturar dados estruturados de cada job
- Schema evolutivo com versionamento para compatibilidade
- Particionamento por tenant_id + time-series para performance
- Pipeline ETL → Data Lake → Analytics Schema (star schema)
- Anonimização automática para benchmarking cross-tenant

### Eventos Capturados

```json
// job.validation.started
{
  "job_id": "uuid", "tenant_id": "...", "timestamp": "...",
  "file_metadata": {"rows": 1000, "columns": 12, "size_bytes": 45000},
  "marketplace": "mercado_livre", "category_hint": "eletronicos"
}

// job.validation.completed
{
  "job_id": "uuid", "tenant_id": "...", "timestamp": "...",
  "duration_ms": 8500, "rules_applied": ["price_validation", "gtin_format"],
  "error_summary": {"missing_title": 23, "invalid_gtin": 5, "price_zero": 2},
  "quality_score": 0.89, "improvement_metrics": {"errors_fixed": 30, "warnings": 8}
}

// job.product.analyzed (anonymous)
{
  "anonymous_id": "hash", "category_l1": "Eletrônicos", "marketplace": "ml",
  "quality_indicators": {"title_completeness": 0.9, "image_count": 3, "price_valid": true},
  "common_issues": ["missing_brand", "generic_description"]
}
```

## Rationale / Trade-offs

**Por que Event Store:**
- Cada job vira dataset para analytics sem afetar performance transacional
- Permite análises históricas e detecção de tendências
- Habilita features de inteligência (benchmarking, predições)
- Compliance LGPD com anonimização/pseudonimização

**Trade-offs aceitos:**
- Storage adicional (~30% sobre dados transacionais)
- Complexidade extra no pipeline ETL  
- Latência adicional mínima (eventos async)

## Scope & Boundaries

**In-scope:**
- Event capture para todos os jobs de validação
- Schema evolutivo com backward compatibility
- Pipeline ETL para analytics aggregations
- Anonimização para benchmarking cross-tenant

**Out-of-scope:**
- Event replay para reconstrução de estado (não é CQRS completo)
- Real-time streaming analytics (batch processing inicial)
- Event store para outros agregados além de Job

## Consequências

### Positivo
- Cada job contribui para inteligência coletiva da plataforma
- Dados históricos permitem análises de tendência e sazonalidade
- Base para features de ML/AI futuras
- Compliance LGPD com anonimização built-in
- Monetização via insights premium

### Negativo
- Storage cost aumenta ~30%
- Complexidade operacional do pipeline ETL
- Schema evolution requer versionamento cuidadoso
- Potencial bottleneck no event ingestion em alta escala

### Neutro
- Performance transacional mantida (eventos async)
- Existing jobs API não muda

## Tests & Quality Gates

**RED**: Testes que definem a necessidade
- test_job_events_are_captured_on_completion()
- test_anonymous_product_data_excludes_pii()  
- test_event_schema_evolution_backwards_compatible()
- test_etl_pipeline_aggregates_correctly()

**GREEN**: Implementação mínima
- CloudEvents format para event schema
- S3/MinIO event sink com partitioning
- Basic ETL job (daily batch)
- Anonimization function para product data

**REFACTOR**: Melhorias planejadas
- Real-time streaming com Kafka Streams
- Advanced ML feature engineering
- Cross-marketplace product matching
- Predictive quality scoring

## DDD Anchors

**VO**: EventId, AnonymousProductId, QualityScore
**Aggregate**: Job (emite eventos durante lifecycle)
**Service/Ports**: EventStore, AnonymizationService, AnalyticsETL

## Telemetry & Security

**Metrics/Events**: 
- events.captured.total (by type)
- etl.pipeline.duration, etl.pipeline.errors
- analytics.queries.performance

**Threats/Mitigations**:
- PII leakage → Automated anonymization + schema validation
- Cross-tenant data bleeding → Strict partitioning + access controls
- Event tampering → Immutable event store + cryptographic hashing

## Links

- PR: #TBD
- Commit: TBD
- Issue: #TBD

---

_Supersedes:_ N/A  
_Superseded by:_ N/A