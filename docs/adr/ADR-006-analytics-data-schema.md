# ADR-006: Analytics Data Schema (Star Schema)

- **Status**: Proposed
- **Data**: 2025-08-29
- **Autor**: Architecture Decision Architect

## Contexto

ValidaHub está capturando eventos de validação (ADR-004) e anonimizando dados (ADR-005) para criar inteligência de marketplace. Precisamos de schema analítico otimizado para queries de BI, reporting e insights de mercado.

Requisitos analíticos identificados:
- Trends de qualidade por marketplace/categoria ao longo do tempo
- Benchmarking: "Seu catálogo vs média do seu segmento"  
- Insights de preços: distribuições, outliers, oportunidades
- Performance de regras de validação: quais mais corrigem
- ROI tracking: tempo economizado, erros evitados

## Alternativas Consideradas

### Opção A: Tabela Única Desnormalizada
- **Prós**: Queries simples, sem JOINs
- **Contras**: Redundância massiva, dificuldade de evolução

### Opção B: Snowflake Schema 
- **Prós**: Normalização máxima, sem redundância
- **Contras**: JOINs complexos, performance query ruim

### Opção C: Star Schema (escolhido)
- **Prós**: Balance performance/flexibilidade, padrão BI
- **Contras**: Alguma redundância controlada

## Decisão

Implementar **Star Schema** otimizado para analytics de marketplace:

### Fact Tables

```sql
-- Fact: Job Processing (granularidade: 1 job)
CREATE TABLE fact_job_processing (
    job_id uuid PRIMARY KEY,
    tenant_id_hash text,  -- pseudonimizado
    date_key int,         -- YYYYMMDD para partitioning
    marketplace_key int,
    category_key int,
    
    -- Metrics
    total_products int,
    errors_found int,
    errors_fixed int,
    warnings_generated int,
    processing_duration_ms int,
    quality_score_before decimal(3,2),
    quality_score_after decimal(3,2),
    
    -- Dimensions (FKs)
    created_at timestamp,
    updated_at timestamp
);

-- Fact: Product Quality (granularidade: 1 produto anonimo)
CREATE TABLE fact_product_quality (
    product_hash text,    -- consistent hash (ADR-005)
    job_id uuid,
    date_key int,
    marketplace_key int,
    category_key int,
    
    -- Quality Indicators (boolean → int for aggregation)
    has_title int,        -- 0/1
    has_description int,
    has_images int,
    has_valid_price int,
    has_valid_gtin int,
    has_brand int,
    
    -- Price Analysis (bands for privacy)
    price_percentile_band text,  -- "P0-P25", "P25-P50", etc.
    
    -- Error Patterns
    validation_errors jsonb,  -- array of error types
    
    created_at timestamp
);
```

### Dimension Tables

```sql
-- Dimension: Date (standard date dimension)
CREATE TABLE dim_date (
    date_key int PRIMARY KEY,
    full_date date,
    year int,
    quarter int,
    month int,
    month_name text,
    day_of_week int,
    is_weekend boolean,
    is_holiday boolean
);

-- Dimension: Marketplace
CREATE TABLE dim_marketplace (
    marketplace_key serial PRIMARY KEY,
    marketplace_name text,    -- "mercado_livre", "magalu"
    marketplace_display text, -- "Mercado Livre", "Magazine Luiza"
    is_active boolean,
    created_at timestamp
);

-- Dimension: Category (hierarchy)
CREATE TABLE dim_category (
    category_key serial PRIMARY KEY,
    category_l1 text,        -- "Eletrônicos"
    category_l2 text,        -- "Smartphones"  
    category_l3 text,        -- "iPhone"
    category_path text,      -- "Eletrônicos > Smartphones > iPhone"
    is_leaf boolean,
    created_at timestamp
);

-- Dimension: Tenant Segment (for benchmarking)
CREATE TABLE dim_tenant_segment (
    tenant_segment_key serial PRIMARY KEY,
    segment_name text,       -- "small_retailer", "large_distributor"
    product_range text,      -- "1-1K", "1K-10K", "10K+"
    description text,
    is_active boolean
);
```

### Aggregation Tables (Pre-computed)

```sql
-- Daily marketplace quality summary
CREATE TABLE agg_marketplace_quality_daily (
    date_key int,
    marketplace_key int,
    category_key int,
    
    jobs_processed int,
    total_products int,
    avg_quality_score decimal(3,2),
    errors_per_product decimal(4,2),
    most_common_errors jsonb,
    
    PRIMARY KEY (date_key, marketplace_key, category_key)
);

-- Monthly benchmarking data
CREATE TABLE agg_segment_benchmarks_monthly (
    year_month int,         -- YYYYMM
    marketplace_key int,
    category_key int,
    tenant_segment_key int,
    
    median_quality_score decimal(3,2),
    p75_quality_score decimal(3,2),
    p90_quality_score decimal(3,2),
    avg_errors_per_product decimal(4,2),
    
    PRIMARY KEY (year_month, marketplace_key, category_key, tenant_segment_key)
);
```

## Rationale / Trade-offs

**Por que Star Schema:**
- Performance excelente para queries analíticas (poucos JOINs)
- Padrão estabelecido para BI tools (Looker, Tableau, etc.)
- Flexibilidade para novos KPIs sem reestruturação
- Particionamento eficiente por tempo
- Suporte nativo a OLAP cubes

**Trade-offs aceitos:**
- Redundância controlada nas dimensions
- ETL mais complexo que tabela única
- Storage ~20% maior que normalizado
- Necessita refresh das aggregation tables

## Scope & Boundaries

**In-scope:**
- Star schema para marketplace intelligence
- Pre-computed aggregations para performance
- Time-series partitioning para escalabilidade  
- Privacy-safe analytics (sem tenant cross-reference)

**Out-of-scope:**
- Real-time analytics (batch refresh diário inicial)
- OLAP cubes (MDX queries) - pode vir depois
- Advanced ML feature store
- Customer-specific schemas

## Consequências

### Positivo
- Queries de BI 10x+ mais rápidas que schema transacional
- Benchmarking cross-tenant sem privacy concerns
- Base sólida para dashboards e reporting
- Escalável para TBs de dados históricos
- Compatível com ferramentas BI padrão do mercado

### Negativo
- ETL pipeline mais complexa (facts + dimensions + aggregations)
- Storage overhead ~30% vs schema normalizado
- Latência analytics (dados D-1, não real-time)
- Necessita expertise em data modeling

### Neutro
- Não afeta performance transacional (schema separado)
- APIs de cliente permanecem inalteradas

## Tests & Quality Gates

**RED**: Testes de performance e integridade
- test_star_schema_query_performance_benchmarks()
- test_privacy_safe_cross_tenant_aggregations()
- test_etl_idempotency_daily_refresh()
- test_aggregation_accuracy_vs_fact_tables()

**GREEN**: Implementação inicial
- Core fact/dimension tables
- Basic ETL job (diário)  
- Aggregation tables principais
- Privacy validation queries

**REFACTOR**: Otimizações futuras
- Columnar storage (Parquet) para archives
- Incremental ETL para near-real-time
- Advanced indexing strategies
- OLAP cube integration

## DDD Anchors

**VO**: DateKey, QualityScore, PricePercentileBand
**Aggregate**: MarketplaceIntelligence, ProductQualityMetrics
**Service/Ports**: AnalyticsETL, BenchmarkingService, ReportingEngine

## Telemetry & Security

**Metrics/Events:**
- etl.star_schema.refresh.duration, etl.aggregations.rows_processed  
- analytics.query.performance, analytics.dashboard.usage
- privacy.cross_tenant_validation.success

**Threats/Mitigations:**
- Cross-tenant data leakage → Automated privacy validation in ETL
- Performance degradation → Query monitoring + index optimization
- Data inconsistency → ETL idempotency + reconciliation checks
- Storage costs → Automated archival policies + compression

## Links

- PR: #TBD
- Commit: TBD
- Issue: #TBD
- dbt Models: TBD

---

_Supersedes:_ N/A
_Superseded by:_ N/A