-- ValidaHub Daily Database Maintenance Script
-- 
-- This script performs essential daily maintenance tasks optimized for
-- ValidaHub's rules engine database with multi-tenant partitioned tables.
-- 
-- Schedule: Daily at 2:00 AM UTC during low-traffic period
-- Execution time: ~5-15 minutes depending on data volume
-- Required role: validahub_system (with BYPASSRLS)

\timing on
\set ECHO all

-- Enable verbose output for monitoring
\echo 'Starting ValidaHub daily maintenance...'
-- Capture start time for accurate duration calculation
SELECT NOW() as maintenance_start_time \gset

-- Set maintenance session parameters
SET maintenance_work_mem = '1GB';
SET statement_timeout = '30min';  -- Allow long operations during maintenance window
SET lock_timeout = '10s';  -- Prevent hanging on lock conflicts during maintenance

-- 1. CLEANUP OPERATIONS
\echo 'Phase 1: Data Cleanup'

-- Remove expired ML suggestions that were never acted upon
DELETE FROM suggestions 
WHERE expires_at < NOW() - INTERVAL '1 day'
  AND status IN ('generated', 'reviewed')
  AND confidence_score < 0.3;  -- Only remove low-confidence expired suggestions

-- Clean up old correction logs marked for deletion (soft delete cleanup)
DELETE FROM correction_logs
WHERE status = 'deleted'
  AND created_at < NOW() - INTERVAL '90 days';

-- Archive old rule versions that are deprecated and unused
-- Using NOT EXISTS instead of NOT IN for better performance
UPDATE rule_versions 
SET status = 'archived'
WHERE deprecated_at < NOW() - INTERVAL '180 days'
  AND status = 'deprecated'
  AND NOT EXISTS (
    SELECT 1
    FROM correction_logs cl
    WHERE cl.rule_version_id = rule_versions.id 
      AND cl.created_at >= NOW() - INTERVAL '30 days'
  );

\echo 'Cleanup completed'

-- 2. STATISTICS UPDATE
\echo 'Phase 2: Statistics Update'

-- Update statistics on main tables for optimal query planning
-- Focus on high-change tables and JSONB columns that need fresh stats

ANALYZE rule_sets;
ANALYZE rule_versions;
ANALYZE suggestions;

-- Analyze recent correction log partitions (last 3 months)
DO $$
DECLARE
    partition_name TEXT;
    partition_record RECORD;
BEGIN
    FOR partition_record IN
        SELECT schemaname, tablename
        FROM pg_tables 
        WHERE tablename ~ '^correction_logs_\d{4}_\d{2}$'
          AND regexp_replace(tablename, 'correction_logs_(\d{4})_(\d{2})', '\1-\2-01')::DATE >= 
              NOW()::DATE - INTERVAL '3 months'
    LOOP
        EXECUTE format('ANALYZE %I.%I', partition_record.schemaname, partition_record.tablename);
        RAISE NOTICE 'Analyzed partition: %', partition_record.tablename;
    END LOOP;
END $$;

-- Update statistics on materialized views
ANALYZE rule_effectiveness;
ANALYZE daily_tenant_metrics;
ANALYZE channel_performance_metrics;
ANALYZE field_correction_patterns;

\echo 'Statistics update completed'

-- 3. INDEX MAINTENANCE
\echo 'Phase 3: Index Maintenance'

-- Reindex indexes based on true bloat calculation (not just size)
-- Uses proper bloat estimation with 25% threshold

DO $$
DECLARE
    index_record RECORD;
    bloat_threshold NUMERIC := 25.0;  -- Reindex if bloat > 25%
    maintenance_start_time TIMESTAMP := :'maintenance_start_time'::TIMESTAMP;
BEGIN
    -- Check for bloated indexes using proper bloat estimation
    FOR index_record IN
        WITH bloat_stats AS (
            SELECT 
                schemaname,
                tablename,
                indexname,
                pg_relation_size(indexrelid) as current_size,
                -- Estimate ideal size based on table stats
                CASE WHEN relpages > 0 THEN
                    ROUND((
                        -- Base calculation for B-tree indexes
                        CASE WHEN am.amname = 'btree' THEN
                            reltuples * (
                                -- Average key size estimation
                                8 + -- page overhead
                                COALESCE((
                                    SELECT sum(CASE 
                                        WHEN atttypid = 'text'::regtype THEN 32  -- Average text field
                                        WHEN atttypid = 'uuid'::regtype THEN 16
                                        WHEN atttypid = 'bigint'::regtype THEN 8
                                        WHEN atttypid = 'integer'::regtype THEN 4
                                        WHEN atttypid = 'timestamp'::regtype THEN 8
                                        WHEN atttypid = 'timestamptz'::regtype THEN 8
                                        ELSE 8 -- Default size
                                    END)
                                    FROM pg_attribute pa
                                    JOIN pg_index pgi ON pgi.indrelid = pa.attrelid
                                    WHERE pgi.indexrelid = psi.indexrelid
                                      AND pa.attnum = ANY(pgi.indkey)
                                ), 16) -- Default if cannot determine
                            ) / 8192 -- Page size
                        -- GIN indexes (JSONB) - different calculation
                        WHEN am.amname = 'gin' THEN
                            reltuples * 0.1 -- Rough estimate: 10% of rows contribute to index size
                        ELSE reltuples * 0.05 -- Conservative estimate for other types
                        END
                    ) * 8192) -- Convert pages back to bytes
                ELSE 0 END as estimated_ideal_size
            FROM pg_stat_user_indexes psi
            JOIN pg_class pc ON psi.relid = pc.oid
            JOIN pg_index pi ON psi.indexrelid = pi.indexrelid
            JOIN pg_am am ON pc.relam = am.oid
            WHERE psi.idx_scan > 1000  -- Only maintain actively used indexes
              AND psi.schemaname = 'public'
              AND pg_relation_size(psi.indexrelid) > 100 * 1024 * 1024  -- > 100MB
        )
        SELECT 
            schemaname,
            tablename,
            indexname,
            current_size,
            estimated_ideal_size,
            CASE WHEN estimated_ideal_size > 0 THEN
                ROUND((current_size::NUMERIC - estimated_ideal_size) / estimated_ideal_size * 100, 2)
            ELSE 0 END as bloat_percentage
        FROM bloat_stats
        WHERE estimated_ideal_size > 0
          AND ((current_size::NUMERIC - estimated_ideal_size) / estimated_ideal_size * 100) > bloat_threshold
    LOOP
        -- Reindex bloated indexes concurrently to avoid blocking
        BEGIN
            EXECUTE format('REINDEX INDEX CONCURRENTLY %I.%I', 
                index_record.schemaname, index_record.indexname);
            RAISE NOTICE 'Reindexed bloated index: % (%.1f%% bloat, %.1f MB -> estimated %.1f MB)', 
                index_record.indexname, 
                index_record.bloat_percentage,
                index_record.current_size / 1024.0 / 1024.0,
                index_record.estimated_ideal_size / 1024.0 / 1024.0;
        EXCEPTION 
            WHEN OTHERS THEN
                RAISE WARNING 'Failed to reindex %: %', index_record.indexname, SQLERRM;
                -- Enhanced error logging - insert failure into maintenance_log
                INSERT INTO maintenance_log (
                    maintenance_type,
                    started_at,
                    completed_at,
                    status,
                    error_message,
                    details
                ) VALUES (
                    'index_reindex_failure',
                    maintenance_start_time,
                    NOW(),
                    'failed',
                    SQLERRM,
                    jsonb_build_object(
                        'index_name', index_record.indexname,
                        'schema_name', index_record.schemaname,
                        'table_name', index_record.tablename,
                        'bloat_percentage', index_record.bloat_percentage,
                        'current_size_mb', index_record.current_size / 1024.0 / 1024.0
                    )
                ) ON CONFLICT DO NOTHING;
        END;
    END LOOP;
END $$;

\echo 'Index maintenance completed'

-- 4. MATERIALIZED VIEW REFRESH
\echo 'Phase 4: Materialized View Refresh'

-- Refresh materialized views with intelligent strategy based on size and usage
SELECT smart_refresh_materialized_views() as refresh_report;

-- Special handling for rule_effectiveness (most critical for performance)
-- Force refresh if data is stale (>6 hours old)
DO $$
DECLARE
    last_refresh TIMESTAMP;
    hours_since_refresh NUMERIC;
BEGIN
    -- Check when rule_effectiveness was last refreshed
    -- This would integrate with a metadata table in production
    SELECT GREATEST(
        COALESCE(MAX(metric_date), NOW() - INTERVAL '1 day')
    ) INTO last_refresh
    FROM rule_effectiveness;
    
    hours_since_refresh := EXTRACT(EPOCH FROM (NOW() - last_refresh)) / 3600.0;
    
    IF hours_since_refresh > 6 THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY rule_effectiveness;
        RAISE NOTICE 'Force refreshed rule_effectiveness (stale for % hours)', 
            ROUND(hours_since_refresh, 1);
    ELSE
        RAISE NOTICE 'rule_effectiveness is fresh (refreshed % hours ago)', 
            ROUND(hours_since_refresh, 1);
    END IF;
END $$;

\echo 'Materialized view refresh completed'

-- 5. PARTITION MANAGEMENT
\echo 'Phase 5: Partition Management'

-- Create next month's partition for correction_logs if not exists
SELECT create_monthly_partition() as partition_creation_result;

-- Check partition sizes and alert if approaching limits
DO $$
DECLARE
    partition_record RECORD;
    size_threshold_gb NUMERIC := 10.0;  -- Alert if partition > 10GB
BEGIN
    FOR partition_record IN
        SELECT 
            tablename,
            pg_total_relation_size(schemaname||'.'||tablename) / 1024 / 1024 / 1024.0 as size_gb
        FROM pg_tables 
        WHERE tablename ~ '^correction_logs_\d{4}_\d{2}$'
          AND pg_total_relation_size(schemaname||'.'||tablename) > size_threshold_gb * 1024 * 1024 * 1024
    LOOP
        RAISE WARNING 'Large partition detected: % (%.1f GB)', 
            partition_record.tablename, partition_record.size_gb;
    END LOOP;
END $$;

\echo 'Partition management completed'

-- 6. VACUUM OPERATIONS
\echo 'Phase 6: Vacuum Operations'

-- Perform targeted vacuum operations on high-churn tables
-- Use VACUUM (not VACUUM FULL) to avoid blocking operations

-- Vacuum rule_versions (frequent updates during development)
VACUUM (VERBOSE, ANALYZE) rule_versions;

-- Vacuum suggestions table (frequent inserts/deletes)
VACUUM (VERBOSE, ANALYZE) suggestions;

-- Vacuum recent correction log partitions (last 2 months)
DO $$
DECLARE
    partition_record RECORD;
BEGIN
    FOR partition_record IN
        SELECT schemaname, tablename
        FROM pg_tables 
        WHERE tablename ~ '^correction_logs_\d{4}_\d{2}$'
          AND regexp_replace(tablename, 'correction_logs_(\d{4})_(\d{2})', '\1-\2-01')::DATE >= 
              NOW()::DATE - INTERVAL '2 months'
    LOOP
        EXECUTE format('VACUUM (VERBOSE, ANALYZE) %I.%I', 
            partition_record.schemaname, partition_record.tablename);
        RAISE NOTICE 'Vacuumed partition: %', partition_record.tablename;
    END LOOP;
END $$;

\echo 'Vacuum operations completed'

-- 7. PERFORMANCE MONITORING
\echo 'Phase 7: Performance Health Check'

-- Generate performance report
SELECT 
    'Performance Report' as report_type,
    get_performance_metrics() as current_metrics;

-- Check for performance alerts
SELECT * FROM check_performance_alerts();

-- Log maintenance completion with accurate duration calculation
INSERT INTO maintenance_log (
    maintenance_type,
    started_at,
    completed_at,
    status,
    details
) VALUES (
    'daily_maintenance',
    :'maintenance_start_time'::TIMESTAMP,
    NOW(),
    'completed',
    jsonb_build_object(
        'phases_completed', ARRAY['cleanup', 'statistics', 'indexes', 'materialized_views', 'partitions', 'vacuum', 'monitoring'],
        'total_duration_minutes', ROUND(EXTRACT(EPOCH FROM (NOW() - :'maintenance_start_time'::TIMESTAMP)) / 60.0, 2)
    )
) ON CONFLICT DO NOTHING;

-- Final status report with accurate duration
\echo 'Daily maintenance completed successfully'
SELECT 
    NOW() as maintenance_end_time,
    ROUND(EXTRACT(EPOCH FROM (NOW() - :'maintenance_start_time'::TIMESTAMP)) / 60.0, 2) as duration_minutes;

-- Reset session parameters
RESET maintenance_work_mem;
RESET statement_timeout;

\timing off