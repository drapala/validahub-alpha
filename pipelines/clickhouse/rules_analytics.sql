-- ValidaHub Rules Analytics Data Warehouse - ClickHouse Schema
-- 
-- This schema implements a Star Schema optimized for rules engine analytics,
-- supporting both real-time queries and historical analysis with pre-aggregated
-- views for business intelligence reporting.
--
-- Architecture:
-- - Fact tables: Store measurable events and metrics
-- - Dimension tables: Store descriptive attributes
-- - Materialized views: Pre-computed aggregations for fast queries
-- - Distributed tables: Scale across ClickHouse cluster
--
-- Data Pipeline: Kafka → ClickHouse (real-time) + S3 → ClickHouse (batch)

-- ============================================================================
-- DIMENSION TABLES
-- ============================================================================

-- Tenant dimension with business context
CREATE TABLE IF NOT EXISTS dim_tenant
(
    tenant_id String,
    tenant_name String,
    business_segment String,
    onboarding_date Date,
    subscription_tier String,
    revenue_tier String, -- 'small', 'medium', 'large', 'enterprise'
    region String,
    is_active UInt8,
    created_at DateTime64(3),
    updated_at DateTime64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (tenant_id)
SETTINGS index_granularity = 8192;

-- Channel/Marketplace dimension
CREATE TABLE IF NOT EXISTS dim_channel
(
    channel_id String,
    channel_name String,
    marketplace_type String, -- 'b2c', 'b2b', 'c2c'
    region String,
    api_version String,
    commission_rate Float32,
    volume_tier String,
    integration_complexity String, -- 'simple', 'medium', 'complex'
    supported_categories Array(String),
    created_at DateTime64(3),
    updated_at DateTime64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (channel_id)
SETTINGS index_granularity = 8192;

-- Rule dimension with metadata and versioning
CREATE TABLE IF NOT EXISTS dim_rule
(
    rule_id String,
    rule_name String,
    rule_type String, -- 'validation', 'transformation', 'suggestion'
    category String, -- 'pricing', 'content', 'images', 'compliance'
    severity String, -- 'error', 'warning', 'info'
    channel_id String,
    ruleset_version String,
    rule_complexity String, -- 'simple', 'medium', 'complex'
    business_impact_tier String, -- 'low', 'medium', 'high', 'critical'
    target_field String,
    condition_type String,
    action_type String,
    created_by String,
    created_at DateTime64(3),
    updated_at DateTime64(3),
    deprecated_at DateTime64(3) DEFAULT NULL,
    is_active UInt8 DEFAULT 1
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (rule_id, ruleset_version)
SETTINGS index_granularity = 8192;

-- Time dimension for efficient time-based queries
CREATE TABLE IF NOT EXISTS dim_date
(
    date Date,
    year UInt16,
    quarter UInt8,
    month UInt8,
    week UInt8,
    day_of_year UInt16,
    day_of_month UInt8,
    day_of_week UInt8,
    is_weekend UInt8,
    is_holiday UInt8,
    business_day UInt8
)
ENGINE = MergeTree()
ORDER BY (date)
SETTINGS index_granularity = 8192;

-- ============================================================================
-- FACT TABLES
-- ============================================================================

-- Core fact table for rule execution events
CREATE TABLE IF NOT EXISTS fact_rule_execution
(
    event_id String,
    tenant_id String,
    channel_id String,
    job_id String,
    ruleset_id String,
    ruleset_version String,
    execution_timestamp DateTime64(3),
    execution_date Date MATERIALIZED toDate(execution_timestamp),
    execution_hour UInt8 MATERIALIZED toHour(execution_timestamp),
    
    -- Execution metrics
    duration_ms UInt32,
    dataset_rows UInt32,
    processed_rows UInt32,
    rules_executed UInt16,
    vectorized_operations UInt16,
    parallel_operations UInt16,
    cache_hits UInt16,
    memory_peak_mb Float32,
    
    -- Result metrics
    error_count UInt32,
    warning_count UInt32,
    suggestion_count UInt32,
    transformation_count UInt32,
    
    -- Performance metrics
    throughput_rows_per_second Float32,
    cpu_usage_percent Float32,
    memory_efficiency Float32,
    cache_hit_rate Float32,
    
    -- Business metrics
    revenue_protected_brl Float64 DEFAULT 0,
    cost_prevented_brl Float64 DEFAULT 0,
    processing_cost_brl Float64 DEFAULT 0,
    
    -- Status and metadata
    execution_status String, -- 'success', 'failed', 'timeout'
    execution_mode String, -- 'vectorized', 'parallel', 'sequential'
    error_type String DEFAULT '',
    trace_id String,
    
    -- Partitioning and optimization
    INDEX idx_tenant_date (tenant_id, execution_date) TYPE minmax,
    INDEX idx_channel_status (channel_id, execution_status) TYPE set(10),
    INDEX idx_duration (duration_ms) TYPE minmax,
    INDEX idx_throughput (throughput_rows_per_second) TYPE minmax
)
ENGINE = MergeTree()
PARTITION BY (toYYYYMM(execution_date), tenant_id)
ORDER BY (execution_date, tenant_id, channel_id, execution_timestamp)
TTL execution_date + INTERVAL 13 MONTH -- 13 months retention
SETTINGS index_granularity = 8192;

-- Individual rule performance fact table
CREATE TABLE IF NOT EXISTS fact_rule_performance
(
    event_id String,
    tenant_id String,
    channel_id String,
    job_id String,
    rule_id String,
    ruleset_version String,
    execution_timestamp DateTime64(3),
    execution_date Date MATERIALIZED toDate(execution_timestamp),
    
    -- Rule-specific metrics
    rule_duration_ms UInt32,
    rows_processed UInt32,
    violations_found UInt32,
    memory_usage_mb Float32,
    cache_operations UInt16,
    
    -- Effectiveness metrics
    precision Float32 DEFAULT 0,
    recall Float32 DEFAULT 0,
    f1_score Float32 DEFAULT 0,
    false_positive_rate Float32 DEFAULT 0,
    true_positive_count UInt32 DEFAULT 0,
    false_positive_count UInt32 DEFAULT 0,
    false_negative_count UInt32 DEFAULT 0,
    
    -- Business impact
    rule_revenue_impact_brl Float64 DEFAULT 0,
    rule_cost_impact_brl Float64 DEFAULT 0,
    time_saved_minutes Float32 DEFAULT 0,
    
    -- Context
    rule_category String,
    rule_complexity String,
    execution_mode String,
    trace_id String,
    
    INDEX idx_rule_date (rule_id, execution_date) TYPE minmax,
    INDEX idx_f1_score (f1_score) TYPE minmax,
    INDEX idx_performance (rule_duration_ms) TYPE minmax
)
ENGINE = MergeTree()
PARTITION BY (toYYYYMM(execution_date), tenant_id)
ORDER BY (execution_date, tenant_id, rule_id, execution_timestamp)
TTL execution_date + INTERVAL 13 MONTH
SETTINGS index_granularity = 8192;

-- Rule effectiveness tracking over time
CREATE TABLE IF NOT EXISTS fact_rule_effectiveness
(
    tenant_id String,
    channel_id String,
    rule_id String,
    ruleset_version String,
    analysis_date Date,
    analysis_timestamp DateTime64(3),
    
    -- Time window for analysis
    analysis_period_hours UInt16,
    jobs_analyzed UInt32,
    total_validations UInt64,
    
    -- Aggregate effectiveness metrics
    avg_precision Float32,
    avg_recall Float32,
    avg_f1_score Float32,
    avg_false_positive_rate Float32,
    
    -- Business metrics
    total_revenue_protected_brl Float64,
    total_cost_prevented_brl Float64,
    avg_revenue_per_validation Float32,
    cost_per_validation_brl Float32,
    roi Float32,
    
    -- Usage patterns
    peak_usage_hour UInt8,
    avg_violations_per_job Float32,
    execution_frequency_per_hour Float32,
    
    -- Quality indicators
    consistency_score Float32, -- How consistent results are
    stability_score Float32,   -- How stable performance is
    business_value_score Float32, -- Overall business value
    
    INDEX idx_effectiveness_date (rule_id, analysis_date) TYPE minmax,
    INDEX idx_f1_trend (avg_f1_score) TYPE minmax,
    INDEX idx_business_value (business_value_score) TYPE minmax
)
ENGINE = ReplacingMergeTree(analysis_timestamp)
PARTITION BY (toYYYYMM(analysis_date), tenant_id)
ORDER BY (analysis_date, tenant_id, rule_id, ruleset_version)
TTL analysis_date + INTERVAL 25 MONTH -- Longer retention for trends
SETTINGS index_granularity = 8192;

-- Compilation events fact table
CREATE TABLE IF NOT EXISTS fact_rule_compilation
(
    event_id String,
    tenant_id String,
    channel_id String,
    ruleset_id String,
    ruleset_version String,
    compilation_timestamp DateTime64(3),
    compilation_date Date MATERIALIZED toDate(compilation_timestamp),
    
    -- Compilation metrics
    compilation_duration_ms UInt32,
    rules_compiled UInt16,
    optimizations_applied UInt16,
    memory_usage_mb Float32,
    execution_plan_phases UInt8,
    vectorized_rules UInt16,
    parallel_rules UInt16,
    
    -- Results
    compilation_status String, -- 'success', 'failed', 'warning'
    error_type String DEFAULT '',
    error_message String DEFAULT '',
    failed_rule_count UInt16 DEFAULT 0,
    
    -- Context
    compilation_mode String,
    compiler_version String,
    triggered_by String, -- 'manual', 'auto', 'deployment'
    actor_id String,
    trace_id String,
    
    INDEX idx_compilation_status (compilation_status) TYPE set(5),
    INDEX idx_duration (compilation_duration_ms) TYPE minmax
)
ENGINE = MergeTree()
PARTITION BY (toYYYYMM(compilation_date), tenant_id)
ORDER BY (compilation_date, tenant_id, ruleset_id, compilation_timestamp)
TTL compilation_date + INTERVAL 6 MONTH -- Shorter retention for compilation events
SETTINGS index_granularity = 8192;

-- ============================================================================
-- AGGREGATION TABLES (Materialized Views)
-- ============================================================================

-- Hourly aggregations for real-time dashboards
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_rules_hourly_stats
(
    tenant_id String,
    channel_id String,
    hour_bucket DateTime,
    date_bucket Date,
    
    -- Execution metrics
    total_executions UInt64,
    successful_executions UInt64,
    failed_executions UInt64,
    avg_duration_ms Float32,
    p95_duration_ms Float32,
    total_rows_processed UInt64,
    avg_throughput_rps Float32,
    
    -- Quality metrics
    total_violations UInt64,
    avg_error_rate Float32,
    avg_cache_hit_rate Float32,
    avg_f1_score Float32,
    
    -- Business metrics
    total_revenue_protected_brl Float64,
    total_cost_prevented_brl Float64,
    net_business_value_brl Float64
)
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(date_bucket)
ORDER BY (date_bucket, tenant_id, channel_id, hour_bucket)
SETTINGS index_granularity = 8192
AS SELECT
    tenant_id,
    channel_id,
    toStartOfHour(execution_timestamp) as hour_bucket,
    toDate(execution_timestamp) as date_bucket,
    
    count(*) as total_executions,
    countIf(execution_status = 'success') as successful_executions,
    countIf(execution_status != 'success') as failed_executions,
    avg(duration_ms) as avg_duration_ms,
    quantile(0.95)(duration_ms) as p95_duration_ms,
    sum(processed_rows) as total_rows_processed,
    avg(throughput_rows_per_second) as avg_throughput_rps,
    
    sum(error_count + warning_count) as total_violations,
    avg((error_count + warning_count) / processed_rows) as avg_error_rate,
    avg(cache_hit_rate) as avg_cache_hit_rate,
    0 as avg_f1_score, -- Will be filled by JOIN with performance table
    
    sum(revenue_protected_brl) as total_revenue_protected_brl,
    sum(cost_prevented_brl) as total_cost_prevented_brl,
    sum(revenue_protected_brl - cost_prevented_brl - processing_cost_brl) as net_business_value_brl
FROM fact_rule_execution
GROUP BY tenant_id, channel_id, hour_bucket, date_bucket;

-- Daily rule performance summary
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_rules_daily_performance
(
    tenant_id String,
    channel_id String,
    rule_id String,
    date_bucket Date,
    
    -- Performance metrics
    execution_count UInt32,
    avg_duration_ms Float32,
    total_violations UInt32,
    avg_precision Float32,
    avg_recall Float32,
    avg_f1_score Float32,
    
    -- Business impact
    total_revenue_impact_brl Float64,
    avg_revenue_per_execution Float32,
    
    -- Trend indicators
    performance_trend String, -- 'improving', 'stable', 'degrading'
    business_value_score Float32
)
ENGINE = ReplacingMergeTree(date_bucket)
PARTITION BY toYYYYMM(date_bucket)
ORDER BY (date_bucket, tenant_id, rule_id)
SETTINGS index_granularity = 8192
AS SELECT
    tenant_id,
    channel_id,
    rule_id,
    execution_date as date_bucket,
    
    count(*) as execution_count,
    avg(rule_duration_ms) as avg_duration_ms,
    sum(violations_found) as total_violations,
    avg(precision) as avg_precision,
    avg(recall) as avg_recall,
    avg(f1_score) as avg_f1_score,
    
    sum(rule_revenue_impact_brl) as total_revenue_impact_brl,
    avg(rule_revenue_impact_brl) as avg_revenue_per_execution,
    
    'stable' as performance_trend, -- Will be computed by external process
    (avg(f1_score) * 0.4 + (sum(rule_revenue_impact_brl) / 1000) * 0.6) as business_value_score
FROM fact_rule_performance
WHERE f1_score > 0 -- Only include rules with effectiveness data
GROUP BY tenant_id, channel_id, rule_id, execution_date;

-- Weekly trend analysis
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_rules_weekly_trends
(
    tenant_id String,
    channel_id String,
    week_start Date,
    
    -- Volume trends
    total_executions UInt64,
    avg_daily_executions Float32,
    execution_growth_rate Float32,
    
    -- Performance trends  
    avg_p95_latency_ms Float32,
    latency_trend String,
    avg_f1_score Float32,
    effectiveness_trend String,
    
    -- Business trends
    total_revenue_impact_brl Float64,
    revenue_growth_rate Float32,
    cost_efficiency_ratio Float32,
    
    -- System health
    avg_error_rate Float32,
    avg_cache_hit_rate Float32,
    system_stability_score Float32
)
ENGINE = ReplacingMergeTree(week_start)
PARTITION BY toYYYYMM(week_start)
ORDER BY (week_start, tenant_id, channel_id)
SETTINGS index_granularity = 8192
AS SELECT
    tenant_id,
    channel_id,
    toMonday(date_bucket) as week_start,
    
    sum(total_executions) as total_executions,
    avg(total_executions) as avg_daily_executions,
    0 as execution_growth_rate, -- Computed by external ETL
    
    avg(p95_duration_ms) as avg_p95_latency_ms,
    'stable' as latency_trend, -- Computed by external ETL
    avg(avg_f1_score) as avg_f1_score,
    'stable' as effectiveness_trend, -- Computed by external ETL
    
    sum(total_revenue_protected_brl) as total_revenue_impact_brl,
    0 as revenue_growth_rate, -- Computed by external ETL
    sum(total_revenue_protected_brl) / sum(total_cost_prevented_brl) as cost_efficiency_ratio,
    
    avg(avg_error_rate) as avg_error_rate,
    avg(avg_cache_hit_rate) as avg_cache_hit_rate,
    (1 - avg(avg_error_rate)) * avg(avg_cache_hit_rate) as system_stability_score
FROM mv_rules_hourly_stats
GROUP BY tenant_id, channel_id, week_start;

-- ============================================================================
-- BUSINESS INTELLIGENCE VIEWS
-- ============================================================================

-- Rule ROI analysis view
CREATE VIEW IF NOT EXISTS view_rule_roi_analysis AS
SELECT
    d.rule_id,
    d.rule_name,
    d.category,
    d.channel_id,
    ch.channel_name,
    
    -- Financial metrics
    sum(p.rule_revenue_impact_brl) as total_revenue_impact,
    sum(p.rule_cost_impact_brl) as total_cost_impact,
    sum(p.rule_revenue_impact_brl - p.rule_cost_impact_brl) as net_value,
    sum(p.rule_revenue_impact_brl) / nullIf(sum(p.rule_cost_impact_brl), 0) as roi,
    
    -- Performance metrics
    avg(p.f1_score) as avg_f1_score,
    avg(p.rule_duration_ms) as avg_duration_ms,
    count(*) as total_executions,
    
    -- Time efficiency
    sum(p.time_saved_minutes) as total_time_saved_minutes,
    sum(p.time_saved_minutes) / 60 as total_time_saved_hours,
    
    -- Last 30 days trend
    sum(if(p.execution_date >= today() - 30, p.rule_revenue_impact_brl, 0)) as revenue_last_30d,
    avg(if(p.execution_date >= today() - 30, p.f1_score, null)) as f1_score_last_30d
    
FROM fact_rule_performance p
JOIN dim_rule d ON p.rule_id = d.rule_id
JOIN dim_channel ch ON p.channel_id = ch.channel_id
WHERE p.execution_date >= today() - 90 -- Last 3 months
GROUP BY d.rule_id, d.rule_name, d.category, d.channel_id, ch.channel_name
HAVING total_executions >= 10 -- Only include rules with sufficient data
ORDER BY roi DESC;

-- Channel performance comparison view
CREATE VIEW IF NOT EXISTS view_channel_performance_comparison AS
SELECT
    ch.channel_name,
    ch.marketplace_type,
    ch.region,
    
    -- Volume metrics
    count(DISTINCT e.job_id) as total_jobs,
    sum(e.processed_rows) as total_rows_processed,
    avg(e.throughput_rows_per_second) as avg_throughput,
    
    -- Quality metrics
    avg(e.cache_hit_rate) as avg_cache_hit_rate,
    sum(e.error_count) / sum(e.processed_rows) as overall_error_rate,
    avg(p.f1_score) as avg_f1_score,
    
    -- Performance metrics
    quantile(0.95)(e.duration_ms) as p95_duration_ms,
    avg(e.memory_efficiency) as avg_memory_efficiency,
    
    -- Business metrics
    sum(e.revenue_protected_brl) as total_revenue_protected,
    sum(e.cost_prevented_brl) as total_cost_prevented,
    sum(e.revenue_protected_brl) / nullIf(sum(e.processing_cost_brl), 0) as cost_efficiency,
    
    -- Reliability metrics
    countIf(e.execution_status = 'success') / count(*) as success_rate,
    avg(e.cpu_usage_percent) as avg_cpu_usage
    
FROM fact_rule_execution e
JOIN dim_channel ch ON e.channel_id = ch.channel_id
LEFT JOIN (
    SELECT 
        tenant_id, channel_id, execution_date,
        avg(f1_score) as f1_score
    FROM fact_rule_performance 
    WHERE f1_score > 0 
    GROUP BY tenant_id, channel_id, execution_date
) p ON e.tenant_id = p.tenant_id 
    AND e.channel_id = p.channel_id 
    AND e.execution_date = p.execution_date
WHERE e.execution_date >= today() - 30 -- Last 30 days
GROUP BY ch.channel_name, ch.marketplace_type, ch.region
ORDER BY total_revenue_protected DESC;

-- ============================================================================
-- INDEXES AND OPTIMIZATIONS
-- ============================================================================

-- Additional indexes for common query patterns
ALTER TABLE fact_rule_execution ADD INDEX IF NOT EXISTS idx_job_id (job_id) TYPE bloom_filter();
ALTER TABLE fact_rule_execution ADD INDEX IF NOT EXISTS idx_revenue (revenue_protected_brl) TYPE minmax;
ALTER TABLE fact_rule_performance ADD INDEX IF NOT EXISTS idx_effectiveness (f1_score) TYPE minmax;

-- Optimize table settings for better performance
ALTER TABLE fact_rule_execution MODIFY SETTING parts_to_delay_insert = 150;
ALTER TABLE fact_rule_execution MODIFY SETTING parts_to_throw_insert = 300;
ALTER TABLE fact_rule_performance MODIFY SETTING parts_to_delay_insert = 150;
ALTER TABLE fact_rule_performance MODIFY SETTING parts_to_throw_insert = 300;

-- ============================================================================
-- DATA RETENTION POLICIES
-- ============================================================================

-- Set up automatic data cleanup for older partitions
-- Raw events: 13 months (already set in TTL)
-- Hourly aggregations: 25 months
ALTER TABLE mv_rules_hourly_stats MODIFY TTL date_bucket + INTERVAL 25 MONTH;

-- Weekly aggregations: 3 years  
ALTER TABLE mv_rules_weekly_trends MODIFY TTL week_start + INTERVAL 36 MONTH;

-- Compilation events: 6 months (already set)

-- ============================================================================
-- SAMPLE DATA FOR TESTING
-- ============================================================================

-- Insert sample dimension data (for development/testing)
/*
INSERT INTO dim_tenant VALUES 
('tenant_mercado_livre', 'Mercado Livre Seller', 'ecommerce', '2024-01-15', 'premium', 'large', 'latam', 1, now(), now()),
('tenant_amazon', 'Amazon Vendor', 'ecommerce', '2024-02-01', 'enterprise', 'enterprise', 'global', 1, now(), now());

INSERT INTO dim_channel VALUES
('mercado_livre', 'Mercado Livre', 'b2c', 'latam', 'v2.1', 0.12, 'high', 'medium', ['electronics', 'fashion', 'home'], now(), now()),
('amazon', 'Amazon Marketplace', 'b2c', 'global', 'v3.0', 0.15, 'high', 'complex', ['all'], now(), now());

INSERT INTO dim_rule VALUES
('R_PRICE_001', 'Price Validation', 'validation', 'pricing', 'error', 'mercado_livre', '1.2.0', 'medium', 'high', 'price', 'range_check', 'assert', 'system', now(), now(), null, 1),
('R_CONTENT_001', 'Content Quality', 'validation', 'content', 'warning', 'mercado_livre', '1.2.0', 'complex', 'medium', 'description', 'ml_analysis', 'suggest', 'system', now(), now(), null, 1);
*/