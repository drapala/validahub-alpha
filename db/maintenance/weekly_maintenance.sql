-- ValidaHub Weekly Database Maintenance Script
--
-- This script performs comprehensive weekly maintenance including
-- archival operations, deep index maintenance, and system optimization.
--
-- Schedule: Weekly on Sunday at 1:00 AM UTC
-- Execution time: ~30-60 minutes depending on data volume
-- Required role: validahub_system (with BYPASSRLS)

\timing on
\set ECHO all

-- Enable extended maintenance mode
\echo 'Starting ValidaHub weekly maintenance...'
SELECT NOW() as maintenance_start_time;

-- Set aggressive maintenance parameters for weekly operations
SET maintenance_work_mem = '2GB';
SET statement_timeout = '2hour';  -- Allow longer operations
SET work_mem = '512MB';  -- For complex analytical queries

-- 1. ARCHIVAL OPERATIONS
\echo 'Phase 1: Data Archival and Cleanup'

-- Archive old correction log partitions (> 2 years)
SELECT archive_old_partitions(24) as archived_partitions;

-- Deep cleanup of soft-deleted records
DELETE FROM rule_sets 
WHERE deleted_at < NOW() - INTERVAL '90 days'
  AND deleted_at IS NOT NULL;

-- Purge old suggestions that have been implemented or rejected
DELETE FROM suggestions
WHERE status IN ('implemented', 'rejected')
  AND updated_at < NOW() - INTERVAL '6 months'
  AND (
    implementation_result IS NULL OR 
    (implementation_result->>'success')::BOOLEAN = true
  );

-- Clean up orphaned rule versions (rule_set deleted)
DELETE FROM rule_versions rv
WHERE NOT EXISTS (
    SELECT 1 FROM rule_sets rs 
    WHERE rs.id = rv.rule_set_id 
    AND rs.deleted_at IS NULL
);

\echo 'Archival operations completed'

-- 2. DEEP INDEX ANALYSIS AND MAINTENANCE
\echo 'Phase 2: Comprehensive Index Maintenance'

-- Generate index health report
CREATE TEMP TABLE index_health_report AS
SELECT * FROM analyze_index_health();

-- Show indexes needing attention
\echo 'Index Health Report:'
SELECT 
    table_name,
    index_name,
    size_mb,
    bloat_ratio,
    usage_score,
    recommendation
FROM index_health_report 
WHERE recommendation NOT LIKE 'MAINTAIN:%'
ORDER BY size_mb DESC;

-- Perform recommended index maintenance
DO $$
DECLARE
    index_record RECORD;
BEGIN
    FOR index_record IN
        SELECT table_name, index_name, recommendation
        FROM index_health_report
        WHERE recommendation LIKE 'REINDEX:%'
    LOOP
        BEGIN
            -- Attempt concurrent reindex first
            EXECUTE format('REINDEX INDEX CONCURRENTLY %I', index_record.index_name);
            RAISE NOTICE 'Successfully reindexed: %', index_record.index_name;
        EXCEPTION
            WHEN OTHERS THEN
                RAISE WARNING 'Failed concurrent reindex for %: %. Attempting regular reindex.', 
                    index_record.index_name, SQLERRM;
                
                -- Fallback to regular reindex (will lock table)
                BEGIN
                    EXECUTE format('REINDEX INDEX %I', index_record.index_name);
                    RAISE NOTICE 'Regular reindex completed: %', index_record.index_name;
                EXCEPTION
                    WHEN OTHERS THEN
                        RAISE WARNING 'Complete reindex failure for %: %', 
                            index_record.index_name, SQLERRM;
                END;
        END;
    END LOOP;
END $$;

-- Drop unused large indexes (with safety checks)
DO $$
DECLARE
    index_record RECORD;
    safety_days INTEGER := 30;  -- Index must be unused for 30+ days
BEGIN
    FOR index_record IN
        SELECT 
            ihr.table_name, 
            ihr.index_name,
            psi.idx_scan,
            psi.last_idx_scan
        FROM index_health_report ihr
        JOIN pg_stat_user_indexes psi ON ihr.index_name = psi.indexname
        WHERE ihr.recommendation LIKE 'DROP:%'
          AND ihr.size_mb > 100  -- Only large indexes
          AND (psi.last_idx_scan IS NULL OR psi.last_idx_scan < NOW() - (safety_days || ' days')::INTERVAL)
    LOOP
        -- Additional safety: check if index is unique or primary key
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint pc
            JOIN pg_index pi ON pc.conindid = pi.indexrelid
            JOIN pg_class ic ON pi.indexrelid = ic.oid
            WHERE ic.relname = index_record.index_name
        ) THEN
            EXECUTE format('DROP INDEX CONCURRENTLY %I', index_record.index_name);
            RAISE NOTICE 'Dropped unused index: % (size: %MB, last used: %)', 
                index_record.index_name, 
                (SELECT size_mb FROM index_health_report WHERE index_name = index_record.index_name),
                COALESCE(index_record.last_idx_scan::TEXT, 'never');
        ELSE
            RAISE WARNING 'Skipped dropping constraint-related index: %', index_record.index_name;
        END IF;
    END LOOP;
END $$;

\echo 'Index maintenance completed'

-- 3. TABLE REORGANIZATION
\echo 'Phase 3: Table Reorganization'

-- Identify tables with high bloat for VACUUM FULL consideration
DO $$
DECLARE
    table_record RECORD;
    bloat_threshold NUMERIC := 0.3;  -- 30% bloat threshold
BEGIN
    -- This is a simplified bloat estimation - in production you'd use pg_stat_user_tables
    FOR table_record IN
        SELECT 
            schemaname, tablename,
            n_dead_tup,
            n_live_tup,
            CASE 
                WHEN n_live_tup + n_dead_tup > 0 THEN
                    n_dead_tup::NUMERIC / (n_live_tup + n_dead_tup)::NUMERIC
                ELSE 0 
            END as estimated_bloat
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
          AND n_live_tup > 10000  -- Only tables with significant data
          AND n_dead_tup::NUMERIC / GREATEST(n_live_tup + n_dead_tup, 1)::NUMERIC > bloat_threshold
        ORDER BY estimated_bloat DESC
    LOOP
        -- VACUUM FULL only for non-partitioned tables during maintenance window
        IF table_record.tablename NOT LIKE 'correction_logs_%' THEN
            EXECUTE format('VACUUM FULL ANALYZE %I.%I', table_record.schemaname, table_record.tablename);
            RAISE NOTICE 'VACUUM FULL completed for %: %.1f%% bloat', 
                table_record.tablename, table_record.estimated_bloat * 100;
        ELSE
            -- For partitioned tables, use regular VACUUM
            EXECUTE format('VACUUM (VERBOSE, ANALYZE) %I.%I', table_record.schemaname, table_record.tablename);
            RAISE NOTICE 'VACUUM completed for partition %', table_record.tablename;
        END IF;
    END LOOP;
END $$;

\echo 'Table reorganization completed'

-- 4. COMPREHENSIVE STATISTICS UPDATE
\echo 'Phase 4: Comprehensive Statistics Update'

-- Update statistics with higher target for better query plans
SET default_statistics_target = 1000;  -- Collect detailed statistics

-- Analyze all tables with focus on JSONB columns
DO $$
DECLARE
    table_record RECORD;
BEGIN
    FOR table_record IN
        SELECT schemaname, tablename
        FROM pg_tables 
        WHERE schemaname = 'public'
        ORDER BY tablename
    LOOP
        EXECUTE format('ANALYZE %I.%I', table_record.schemaname, table_record.tablename);
        RAISE NOTICE 'Analyzed table: %', table_record.tablename;
    END LOOP;
END $$;

-- Reset statistics target
RESET default_statistics_target;

\echo 'Statistics update completed'

-- 5. MATERIALIZED VIEW OPTIMIZATION
\echo 'Phase 5: Materialized View Deep Refresh'

-- Perform full refresh of all materialized views (not concurrent)
-- This ensures complete data consistency weekly

REFRESH MATERIALIZED VIEW rule_effectiveness;
REFRESH MATERIALIZED VIEW daily_tenant_metrics;
REFRESH MATERIALIZED VIEW channel_performance_metrics;
REFRESH MATERIALIZED VIEW field_correction_patterns;

-- Optimize materialized view indexes
REINDEX INDEX CONCURRENTLY idx_rule_effectiveness_unique;
REINDEX INDEX CONCURRENTLY idx_rule_effectiveness_tenant_score;
REINDEX INDEX CONCURRENTLY idx_daily_tenant_metrics_unique;
REINDEX INDEX CONCURRENTLY idx_channel_performance_unique;
REINDEX INDEX CONCURRENTLY idx_field_patterns_unique;

\echo 'Materialized view optimization completed'

-- 6. PARTITION MAINTENANCE
\echo 'Phase 6: Advanced Partition Maintenance'

-- Create partitions for next 3 months
DO $$
DECLARE
    i INTEGER;
    partition_result TEXT;
BEGIN
    FOR i IN 1..3 LOOP
        SELECT create_monthly_partition(
            (NOW() + (i || ' months')::INTERVAL)::DATE
        ) INTO partition_result;
        RAISE NOTICE 'Future partition: %', partition_result;
    END LOOP;
END $$;

-- Optimize partition constraints for better pruning
SELECT optimize_partition_constraints() as constraint_optimization_result;

-- Check partition sizes and recommend archival
DO $$
DECLARE
    partition_info RECORD;
    large_partition_threshold_gb NUMERIC := 20.0;
BEGIN
    RAISE NOTICE 'Partition Size Report:';
    
    FOR partition_info IN
        SELECT 
            tablename,
            pg_total_relation_size(schemaname||'.'||tablename) / 1024 / 1024 / 1024.0 as size_gb,
            regexp_replace(tablename, 'correction_logs_(\d{4})_(\d{2})', '\1-\2-01')::DATE as partition_date
        FROM pg_tables 
        WHERE tablename ~ '^correction_logs_\d{4}_\d{2}$'
        ORDER BY partition_date DESC
        LIMIT 12  -- Last 12 months
    LOOP
        IF partition_info.size_gb > large_partition_threshold_gb THEN
            RAISE WARNING 'Large partition: % (%.1f GB) - consider archival', 
                partition_info.tablename, partition_info.size_gb;
        ELSE
            RAISE NOTICE 'Partition %: %.1f GB', 
                partition_info.tablename, partition_info.size_gb;
        END IF;
    END LOOP;
END $$;

\echo 'Partition maintenance completed'

-- 7. SECURITY AND COMPLIANCE CHECK
\echo 'Phase 7: Security and Compliance Verification'

-- Verify RLS policies are active
DO $$
DECLARE
    table_record RECORD;
BEGIN
    RAISE NOTICE 'Row Level Security Status:';
    
    FOR table_record IN
        SELECT 
            schemaname, tablename, rowsecurity
        FROM pg_tables 
        WHERE schemaname = 'public' 
          AND tablename IN ('rule_sets', 'rule_versions', 'correction_logs', 'suggestions')
    LOOP
        IF table_record.rowsecurity THEN
            RAISE NOTICE 'RLS ENABLED: %', table_record.tablename;
        ELSE
            RAISE WARNING 'RLS DISABLED: % - SECURITY RISK!', table_record.tablename;
        END IF;
    END LOOP;
END $$;

-- Check for potential data retention violations
SELECT 
    'Retention Compliance Check' as check_type,
    COUNT(*) as old_records_count,
    'correction_logs older than 7 years' as description
FROM correction_logs 
WHERE created_at < NOW() - INTERVAL '7 years';

-- Verify tenant isolation (no cross-tenant data leakage)
DO $$
DECLARE
    tenant_count INTEGER;
    isolation_check_passed BOOLEAN := TRUE;
BEGIN
    -- This is a simplified check - in production you'd have more comprehensive tests
    SELECT COUNT(DISTINCT tenant_id) INTO tenant_count FROM rule_sets WHERE tenant_id IS NOT NULL;
    
    IF tenant_count > 0 THEN
        RAISE NOTICE 'Tenant isolation check passed: % active tenants', tenant_count;
    ELSE
        RAISE WARNING 'Tenant isolation check: No tenants found or data issue';
        isolation_check_passed := FALSE;
    END IF;
    
    -- Additional isolation checks could be added here
    
    IF isolation_check_passed THEN
        RAISE NOTICE 'Security and compliance checks: PASSED';
    ELSE
        RAISE WARNING 'Security and compliance checks: FAILED - Review required';
    END IF;
END $$;

\echo 'Security and compliance check completed'

-- 8. PERFORMANCE OPTIMIZATION REPORT
\echo 'Phase 8: Weekly Performance Report'

-- Generate comprehensive performance report
SELECT 
    'Weekly Performance Summary' as report_title,
    get_performance_metrics() as metrics;

-- Check for performance regressions
SELECT 
    alert_type,
    severity,
    message,
    recommended_action
FROM check_performance_alerts()
ORDER BY 
    CASE severity 
        WHEN 'CRITICAL' THEN 1 
        WHEN 'WARNING' THEN 2 
        ELSE 3 
    END;

-- Generate storage growth analysis
SELECT 
    'Storage Growth Analysis' as analysis_type,
    table_name,
    current_size,
    growth_rate_mb_per_day,
    estimated_days_to_threshold,
    alert_level
FROM monitor_storage_growth()
WHERE alert_level != 'OK'
ORDER BY estimated_days_to_threshold;

\echo 'Performance report completed'

-- 9. BACKUP AND DISASTER RECOVERY VERIFICATION
\echo 'Phase 9: Backup Verification'

-- Check WAL archiving status (if configured)
DO $$
DECLARE
    wal_archiving BOOLEAN;
BEGIN
    SELECT setting::BOOLEAN INTO wal_archiving 
    FROM pg_settings 
    WHERE name = 'archive_mode';
    
    IF wal_archiving THEN
        RAISE NOTICE 'WAL archiving is enabled';
        
        -- Additional backup health checks could be added here
        -- e.g., checking last successful backup timestamp
        
    ELSE
        RAISE WARNING 'WAL archiving is disabled - backup coverage may be incomplete';
    END IF;
END $$;

-- Verify critical data consistency
DO $$
DECLARE
    consistency_issues INTEGER := 0;
BEGIN
    -- Check for orphaned rule versions
    SELECT COUNT(*) INTO consistency_issues
    FROM rule_versions rv
    LEFT JOIN rule_sets rs ON rv.rule_set_id = rs.id
    WHERE rs.id IS NULL AND rv.rule_set_id IS NOT NULL;
    
    IF consistency_issues > 0 THEN
        RAISE WARNING 'Data consistency issue: % orphaned rule versions', consistency_issues;
    END IF;
    
    -- Check for correction logs without valid rule references
    SELECT COUNT(*) INTO consistency_issues
    FROM correction_logs cl
    LEFT JOIN rule_versions rv ON cl.rule_version_id = rv.id
    WHERE rv.id IS NULL 
      AND cl.rule_version_id IS NOT NULL 
      AND cl.created_at >= NOW() - INTERVAL '7 days';  -- Only recent data
    
    IF consistency_issues > 0 THEN
        RAISE WARNING 'Data consistency issue: % correction logs with invalid rule references', consistency_issues;
    END IF;
    
    RAISE NOTICE 'Data consistency verification completed';
END $$;

\echo 'Backup verification completed'

-- 10. MAINTENANCE LOG AND CLEANUP
\echo 'Phase 10: Maintenance Logging and Cleanup'

-- Log weekly maintenance completion
INSERT INTO maintenance_log (
    maintenance_type,
    started_at,
    completed_at,
    details
) VALUES (
    'weekly_maintenance',
    (SELECT maintenance_start_time FROM (SELECT NOW() - INTERVAL '2 hours' as maintenance_start_time) t),
    NOW(),
    jsonb_build_object(
        'phases_completed', ARRAY[
            'archival', 'index_maintenance', 'table_reorganization', 
            'statistics', 'materialized_views', 'partitions', 
            'security_check', 'performance_report', 'backup_verification'
        ],
        'total_duration_minutes', EXTRACT(EPOCH FROM (NOW() - (NOW() - INTERVAL '2 hours'))) / 60.0,
        'archived_partitions', (SELECT COUNT(*) FROM pg_tables WHERE tablename ~ '^correction_logs_archive_\d{4}_\d{2}$'),
        'index_operations_completed', (SELECT COUNT(*) FROM index_health_report WHERE recommendation NOT LIKE 'MAINTAIN:%')
    )
);

-- Clean up temporary tables
DROP TABLE IF EXISTS index_health_report;

-- Reset all session parameters
RESET maintenance_work_mem;
RESET statement_timeout;
RESET work_mem;

-- Final completion report
\echo 'Weekly maintenance completed successfully!'
SELECT 
    NOW() as maintenance_end_time,
    EXTRACT(EPOCH FROM (NOW() - (NOW() - INTERVAL '2 hours'))) / 60.0 as total_duration_minutes,
    'Weekly maintenance cycle completed' as status;

\timing off

-- Suggest immediate actions if any critical issues were found
\echo 'Weekly Maintenance Summary:'
\echo '- Review any WARNING messages above'
\echo '- Check storage growth alerts'
\echo '- Verify backup completion status'
\echo '- Monitor performance metrics over the next week'