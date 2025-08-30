-- ValidaHub Optimized Index Creation Script
-- Creates all performance-critical indexes for multi-tenant correction logging system
-- Run this script after initial table creation to establish optimal query performance

-- ==============================================================================
-- INDEX CREATION STRATEGY
-- ==============================================================================

/*
PRINCIPLES:
1. Tenant isolation is non-negotiable - every index starts with tenant_id
2. Create indexes CONCURRENTLY to avoid blocking production traffic
3. Prioritize compound indexes for common query patterns
4. Use partial indexes for filtered queries (status-specific, date ranges)
5. GIN indexes for JSONB columns with complex queries
6. Monitor index usage and drop unused indexes

PERFORMANCE TARGETS:
- Primary key lookups: < 1ms
- Tenant + time range queries: < 50ms
- Analytics aggregations: < 500ms
- JSONB pattern queries: < 100ms
*/

-- ==============================================================================
-- RULE_SETS TABLE INDEXES
-- ==============================================================================

-- Essential for rule lookup by channel (most common query)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_sets_tenant_channel_performance
ON rule_sets (tenant_id, channel, is_active)
WHERE is_active = true;

-- Rule discovery and listing
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_sets_tenant_active_updated
ON rule_sets (tenant_id, is_active, updated_at DESC)
WHERE is_active = true;

-- Metadata search patterns (marketplace-specific rules)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_sets_metadata_search_gin
ON rule_sets USING gin (metadata jsonb_path_ops);

-- Status-based operations (publishing workflow)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_sets_tenant_status_created
ON rule_sets (tenant_id, status, created_at DESC);

-- Auto-patch policy queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_sets_auto_apply_patches
ON rule_sets (tenant_id, auto_apply_patches, shadow_period_days)
WHERE auto_apply_patches = true;

-- ==============================================================================
-- RULE_VERSIONS TABLE INDEXES  
-- ==============================================================================

-- Critical: Current version lookup (highest frequency query)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_versions_tenant_set_current
ON rule_versions (tenant_id, rule_set_id)
WHERE is_current = true;

-- Version history and comparison queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_versions_tenant_set_semantic
ON rule_versions (tenant_id, rule_set_id, major DESC, minor DESC, patch DESC);

-- Published version queries (active rule evaluation)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_versions_published_performance
ON rule_versions (tenant_id, rule_set_id, published_at DESC)
WHERE status = 'published';

-- Version status workflow queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_versions_tenant_status_created
ON rule_versions (tenant_id, status, created_at DESC);

-- Rule content analysis (complex rule searches)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_versions_rules_content_gin
ON rule_versions USING gin (rules);

-- Performance analysis (slow rule compilation)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_versions_performance_gin
ON rule_versions USING gin (performance_profile);

-- Breaking changes analysis for migration planning
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_versions_breaking_changes_gin
ON rule_versions USING gin (breaking_changes);

-- Compatibility tracking between versions
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_versions_compatibility
ON rule_versions (tenant_id, rule_set_id, compatibility_level, created_at);

-- ==============================================================================
-- CORRECTION_LOGS TABLE INDEXES (HIGH VOLUME - CRITICAL FOR PERFORMANCE)
-- ==============================================================================

-- PRIMARY PATTERN: Recent corrections by tenant (operational queries)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_tenant_time_hot
ON correction_logs (tenant_id, created_at DESC)
WHERE created_at >= NOW() - INTERVAL '7 days';

-- Job-specific correction lookups (CSV processing results)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_job_operations
ON correction_logs (tenant_id, job_id, record_number, field_name);

-- Rule effectiveness analysis (critical for ML and reporting)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_rule_effectiveness
ON correction_logs (tenant_id, rule_id, correction_method, status, created_at DESC);

-- Batch correction operations (bulk apply/reject)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_batch_operations
ON correction_logs (tenant_id, correction_batch_id, status)
WHERE correction_batch_id IS NOT NULL;

-- Pending corrections workflow (user review queue)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_pending_review
ON correction_logs (tenant_id, status, created_at DESC, field_name)
WHERE status = 'pending';

-- Applied corrections audit trail
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_applied_audit
ON correction_logs (tenant_id, applied_at DESC, correction_method, created_by)
WHERE status = 'applied';

-- Confidence-based filtering (auto-apply thresholds)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_high_confidence
ON correction_logs (tenant_id, confidence_score DESC, status)
WHERE confidence_score >= 0.8 AND status = 'pending';

-- Field-specific correction patterns (data quality insights)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_field_patterns
ON correction_logs (tenant_id, field_name, correction_method, created_at DESC);

-- JSONB indexes for flexible correction metadata queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_metadata_gin
ON correction_logs USING gin (correction_metadata);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_impact_analysis_gin  
ON correction_logs USING gin (estimated_impact);

-- Correlation and request tracking for debugging
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_correlation_tracking
ON correction_logs (correlation_id, request_id, created_at DESC)
WHERE correlation_id IS NOT NULL;

-- Performance monitoring (slow corrections)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_processing_performance
ON correction_logs (tenant_id, (correction_metadata->>'processing_time_ms')::int DESC)
WHERE (correction_metadata->>'processing_time_ms')::int > 1000;

-- Reversion tracking (rollback operations)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_reverted
ON correction_logs (tenant_id, reverted_at DESC, created_by)
WHERE reverted_at IS NOT NULL;

-- ==============================================================================
-- SUGGESTIONS TABLE INDEXES (ML-HEAVY QUERIES)
-- ==============================================================================

-- High-confidence suggestions for auto-acceptance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_suggestions_auto_accept_candidates
ON suggestions (tenant_id, confidence_score DESC, model_version)
WHERE confidence_score >= 0.9 AND status = 'pending';

-- Job-specific suggestion retrieval
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_suggestions_job_processing
ON suggestions (tenant_id, job_id, record_number, field_name);

-- Model performance analysis (A/B testing)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_suggestions_model_comparison
ON suggestions (model_name, model_version, confidence_score, status, created_at DESC);

-- User feedback analysis for model improvement
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_suggestions_feedback_analysis
ON suggestions (tenant_id, status, accepted_at DESC)
WHERE status IN ('accepted', 'rejected');

-- Field-specific suggestion patterns
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_suggestions_field_intelligence
ON suggestions (tenant_id, field_name, suggestion_type, confidence_score DESC);

-- Batch suggestion processing
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_suggestions_batch_processing
ON suggestions (tenant_id, batch_id, status)
WHERE batch_id IS NOT NULL;

-- ML algorithm metadata queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_suggestions_algorithm_gin
ON suggestions USING gin (algorithm_metadata);

-- Context feature analysis for model training
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_suggestions_context_features_gin
ON suggestions USING gin (context_features);

-- Alternative suggestions analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_suggestions_alternatives_gin
ON suggestions USING gin (alternative_suggestions);

-- Performance monitoring (slow ML inference)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_suggestions_inference_performance
ON suggestions (tenant_id, model_inference_time_ms DESC, created_at)
WHERE model_inference_time_ms > 500;

-- Business impact tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_suggestions_business_impact
ON suggestions (tenant_id, (business_impact->>'revenue_impact')::numeric DESC)
WHERE (business_impact->>'revenue_impact')::numeric > 0;

-- ==============================================================================
-- RULE_EFFECTIVENESS MATERIALIZED VIEW INDEXES
-- ==============================================================================

-- Time-series analysis (primary dashboard query)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_effectiveness_time_series
ON rule_effectiveness (tenant_id, metric_date DESC, overall_score DESC);

-- Rule performance ranking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_effectiveness_performance_ranking
ON rule_effectiveness (tenant_id, overall_score DESC, quality_score DESC, metric_date DESC);

-- Channel-specific effectiveness
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_effectiveness_channel_analysis
ON rule_effectiveness (tenant_id, channel, metric_month, automation_rate DESC);

-- Recent performance for alerts
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_effectiveness_recent_alerts
ON rule_effectiveness (tenant_id, metric_date DESC, success_rate)
WHERE metric_date >= CURRENT_DATE - INTERVAL '7 days' AND success_rate < 0.8;

-- Rule evolution tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_effectiveness_rule_evolution
ON rule_effectiveness (tenant_id, rule_id, metric_week DESC);

-- ==============================================================================
-- COVERING INDEXES FOR INDEX-ONLY SCANS
-- ==============================================================================

-- Correction logs summary queries (avoid table access)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_summary_covering
ON correction_logs (tenant_id, rule_id, created_at DESC) 
INCLUDE (status, correction_method, confidence_score);

-- Suggestion summary for dashboards
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_suggestions_summary_covering
ON suggestions (tenant_id, created_at DESC) 
INCLUDE (status, confidence_score, suggestion_type, model_name);

-- Rule version summary for API responses
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rule_versions_api_covering
ON rule_versions (tenant_id, rule_set_id, is_current) 
INCLUDE (version, status, published_at, rule_count)
WHERE is_current = true;

-- ==============================================================================
-- SPECIALIZED INDEXES FOR ANALYTICS AND REPORTING
-- ==============================================================================

-- Time-bucketed aggregation support
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_hourly_buckets
ON correction_logs (tenant_id, date_trunc('hour', created_at), rule_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_daily_buckets
ON correction_logs (tenant_id, date_trunc('day', created_at), correction_method);

-- Top-K pattern analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_pattern_frequency
ON correction_logs (tenant_id, field_name, left(original_value::text, 50), left(corrected_value::text, 50))
WHERE original_value IS NOT NULL AND corrected_value IS NOT NULL;

-- Compliance reporting (user activity tracking)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_user_activity
ON correction_logs (tenant_id, created_by, date_trunc('day', created_at));

-- Revenue impact analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_correction_logs_revenue_impact
ON correction_logs (tenant_id, (estimated_impact->>'revenue_impact')::numeric DESC, created_at DESC)
WHERE (estimated_impact->>'revenue_impact')::numeric > 0;

-- ==============================================================================
-- PARTITION-SPECIFIC OPTIMIZATIONS
-- ==============================================================================

-- For each monthly partition of correction_logs, create optimized local indexes
DO $$
DECLARE
    partition_name TEXT;
BEGIN
    -- Loop through existing partitions
    FOR partition_name IN 
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name LIKE 'correction_logs_%' 
        AND table_schema = 'public'
    LOOP
        -- Create partition-optimized indexes
        EXECUTE format('
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_%I_tenant_time_local
            ON %I (tenant_id, created_at DESC)
        ', partition_name, partition_name);
        
        EXECUTE format('
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_%I_rule_local
            ON %I (tenant_id, rule_id, status) 
        ', partition_name, partition_name);
        
        RAISE NOTICE 'Created local indexes for partition: %', partition_name;
    END LOOP;
END $$;

-- ==============================================================================
-- INDEX MAINTENANCE AND MONITORING
-- ==============================================================================

-- Function to monitor index usage and identify candidates for removal
CREATE OR REPLACE FUNCTION analyze_index_usage()
RETURNS TABLE (
    schema_name TEXT,
    table_name TEXT,
    index_name TEXT,
    index_size TEXT,
    scans BIGINT,
    tuples_read BIGINT,
    tuples_fetched BIGINT,
    usage_efficiency NUMERIC,
    recommendation TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH index_stats AS (
        SELECT 
            schemaname,
            tablename,
            indexname,
            pg_size_pretty(pg_relation_size(indexrelid)) as size,
            idx_scan,
            idx_tup_read,
            idx_tup_fetch,
            CASE 
                WHEN idx_scan > 0 THEN 
                    ROUND((idx_tup_fetch::NUMERIC / idx_tup_read::NUMERIC) * 100, 2)
                ELSE 0 
            END as efficiency
        FROM pg_stat_user_indexes 
        WHERE schemaname = 'public'
    )
    SELECT 
        schemaname,
        tablename,
        indexname,
        size,
        idx_scan,
        idx_tup_read,
        idx_tup_fetch,
        efficiency,
        CASE 
            WHEN idx_scan = 0 AND pg_relation_size(schemaname||'.'||indexname) > 10485760 THEN 'CONSIDER_DROP - Unused index > 10MB'
            WHEN efficiency < 1 THEN 'REVIEW_SELECTIVITY - Low efficiency'
            WHEN idx_scan > 1000 AND efficiency > 80 THEN 'HIGH_VALUE - Keep'
            WHEN idx_scan < 10 THEN 'LOW_USAGE - Monitor'
            ELSE 'NORMAL'
        END
    FROM index_stats
    ORDER BY idx_scan DESC, pg_relation_size(schemaname||'.'||indexname) DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to identify missing indexes based on query patterns
CREATE OR REPLACE FUNCTION suggest_missing_indexes()
RETURNS TABLE (
    table_name TEXT,
    suggested_index TEXT,
    reason TEXT,
    estimated_benefit TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH slow_queries AS (
        SELECT 
            query,
            calls,
            total_time,
            mean_time,
            rows
        FROM pg_stat_statements
        WHERE mean_time > 100  -- Queries slower than 100ms
        AND calls > 10         -- Called more than 10 times
        AND query ~ '(correction_logs|suggestions|rule_versions|rule_sets)'
        ORDER BY total_time DESC
        LIMIT 20
    )
    SELECT 
        'correction_logs'::TEXT,
        'Consider index on (tenant_id, field_name, status, created_at)'::TEXT,
        'Many queries filter by tenant + field + status'::TEXT,
        'Could improve 15+ queries averaging 150ms'::TEXT
    WHERE EXISTS (
        SELECT 1 FROM slow_queries 
        WHERE query ~ 'field_name.*status' OR query ~ 'status.*field_name'
    )
    
    UNION ALL
    
    SELECT 
        'suggestions'::TEXT,
        'Consider index on (tenant_id, model_name, created_at DESC)'::TEXT,
        'Model performance queries are frequent'::TEXT,
        'Could improve analytics queries by 50%'::TEXT
    WHERE EXISTS (
        SELECT 1 FROM slow_queries 
        WHERE query ~ 'model_name' AND query ~ 'suggestions'
    );
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- INDEX HEALTH CHECK AND MAINTENANCE
-- ==============================================================================

-- Check for bloated indexes that need rebuilding
SELECT 
    'Index Health Check' as check_type,
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(schemaname||'.'||indexname)) as index_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    ROUND(
        pg_relation_size(schemaname||'.'||indexname)::NUMERIC / 
        NULLIF(pg_relation_size(schemaname||'.'||tablename), 0) * 100, 2
    ) as index_to_table_ratio
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND pg_relation_size(schemaname||'.'||indexname) > 104857600  -- > 100MB
ORDER BY pg_relation_size(schemaname||'.'||indexname) DESC;

-- ==============================================================================
-- USAGE INSTRUCTIONS
-- ==============================================================================

/*
DEPLOYMENT CHECKLIST:

1. PRE-DEPLOYMENT:
   - Verify sufficient disk space (indexes ~30% of table size)
   - Check current database load (avoid peak hours)
   - Backup database before large index operations

2. DEPLOYMENT:
   - Run this script during low-traffic periods
   - Monitor connection count and lock waits
   - Script uses CONCURRENTLY - safe for production

3. POST-DEPLOYMENT:
   - Run ANALYZE on all tables to update statistics
   - Monitor query performance for 24-48 hours
   - Use analyze_index_usage() to verify effectiveness

4. MAINTENANCE:
   - Weekly: Check index usage with analyze_index_usage()
   - Monthly: Review slow queries with suggest_missing_indexes()
   - Quarterly: Rebuild indexes with high bloat ratio

MONITORING QUERIES:

-- Check index creation progress
SELECT 
    command, 
    pid, 
    NOW() - query_start as duration,
    query
FROM pg_stat_activity 
WHERE query LIKE '%CREATE INDEX%' 
  AND state = 'active';

-- Verify new indexes are being used
SELECT * FROM analyze_index_usage() 
WHERE table_name IN ('correction_logs', 'suggestions', 'rule_versions', 'rule_sets')
ORDER BY scans DESC;

-- Check for missing indexes
SELECT * FROM suggest_missing_indexes();

ROLLBACK PLAN:
- Individual indexes can be dropped safely with:
  DROP INDEX CONCURRENTLY idx_name;
- Monitor performance impact before dropping multiple indexes
- Keep usage statistics to recreate if needed
*/