-- ValidaHub Database Maintenance Scripts
-- Comprehensive maintenance procedures for optimal PostgreSQL performance

-- ==============================================================================
-- VACUUM AND ANALYZE OPERATIONS
-- ==============================================================================

-- Comprehensive VACUUM strategy for different table types
-- Principle: Different tables need different maintenance schedules based on write patterns

DO $$
DECLARE
    table_record RECORD;
    partition_record RECORD;
    vacuum_command TEXT;
    analyze_command TEXT;
    table_size BIGINT;
    dead_tuple_ratio NUMERIC;
BEGIN
    RAISE NOTICE 'Starting comprehensive database maintenance at %', NOW();
    
    -- Main tables maintenance (rule_sets, rule_versions, suggestions)
    FOR table_record IN 
        SELECT 
            schemaname,
            tablename,
            n_live_tup,
            n_dead_tup,
            pg_total_relation_size(schemaname||'.'||tablename) as table_size
        FROM pg_stat_user_tables 
        WHERE tablename IN ('rule_sets', 'rule_versions', 'suggestions')
    LOOP
        table_size := table_record.table_size;
        
        -- Calculate dead tuple ratio
        IF table_record.n_live_tup > 0 THEN
            dead_tuple_ratio := table_record.n_dead_tup::NUMERIC / table_record.n_live_tup::NUMERIC;
        ELSE
            dead_tuple_ratio := 0;
        END IF;
        
        RAISE NOTICE 'Processing table: %, size: % MB, dead tuple ratio: %', 
            table_record.tablename, 
            ROUND(table_size / 1024.0 / 1024.0, 2),
            ROUND(dead_tuple_ratio, 4);
        
        -- Decide vacuum strategy based on table characteristics
        IF dead_tuple_ratio > 0.1 OR table_size > 1024*1024*1024 THEN -- > 1GB
            -- Full vacuum for heavily fragmented or large tables
            vacuum_command := 'VACUUM (VERBOSE, ANALYZE) ' || table_record.schemaname || '.' || table_record.tablename;
            RAISE NOTICE 'Executing: %', vacuum_command;
            EXECUTE vacuum_command;
        ELSE
            -- Regular vacuum for smaller/cleaner tables
            vacuum_command := 'VACUUM ' || table_record.schemaname || '.' || table_record.tablename;
            EXECUTE vacuum_command;
            
            -- Separate analyze for better control
            analyze_command := 'ANALYZE ' || table_record.schemaname || '.' || table_record.tablename;
            EXECUTE analyze_command;
        END IF;
    END LOOP;
    
    -- Special handling for partitioned correction_logs table
    RAISE NOTICE 'Processing partitioned correction_logs table';
    
    -- Process each partition separately for optimal performance
    FOR partition_record IN 
        SELECT 
            schemaname,
            tablename,
            n_live_tup,
            n_dead_tup,
            pg_total_relation_size(schemaname||'.'||tablename) as partition_size
        FROM pg_stat_user_tables 
        WHERE tablename LIKE 'correction_logs_%'
        ORDER BY tablename DESC -- Process newest partitions first
    LOOP
        RAISE NOTICE 'Processing partition: %, size: % MB', 
            partition_record.tablename,
            ROUND(partition_record.partition_size / 1024.0 / 1024.0, 2);
        
        -- Aggressive vacuum for correction_logs due to high write volume
        IF partition_record.partition_size > 100*1024*1024 THEN -- > 100MB
            EXECUTE 'VACUUM (VERBOSE, ANALYZE, INDEX_CLEANUP ON) ' || partition_record.schemaname || '.' || partition_record.tablename;
        ELSE
            EXECUTE 'VACUUM ANALYZE ' || partition_record.schemaname || '.' || partition_record.tablename;
        END IF;
    END LOOP;
    
    RAISE NOTICE 'Database maintenance completed at %', NOW();
END $$;

-- ==============================================================================
-- REINDEX OPERATIONS
-- ==============================================================================

-- Rebuild indexes that may be fragmented or bloated
-- Run this monthly or when index bloat is detected

DO $$
DECLARE
    index_record RECORD;
    index_size BIGINT;
    table_size BIGINT;
    bloat_ratio NUMERIC;
BEGIN
    RAISE NOTICE 'Starting index maintenance at %', NOW();
    
    -- Check index bloat and rebuild if necessary
    FOR index_record IN 
        SELECT 
            schemaname,
            indexname,
            tablename,
            pg_total_relation_size(schemaname||'.'||indexname) as idx_size,
            pg_total_relation_size(schemaname||'.'||tablename) as tbl_size
        FROM pg_stat_user_indexes 
        WHERE schemaname = 'public'
        AND tablename IN ('rule_sets', 'rule_versions', 'suggestions', 'correction_logs')
        ORDER BY pg_total_relation_size(schemaname||'.'||indexname) DESC
    LOOP
        index_size := index_record.idx_size;
        table_size := index_record.tbl_size;
        
        -- Estimate bloat ratio (simplified heuristic)
        IF table_size > 0 THEN
            bloat_ratio := index_size::NUMERIC / table_size::NUMERIC;
        ELSE
            bloat_ratio := 0;
        END IF;
        
        RAISE NOTICE 'Index: %, size: % MB, table: %, bloat ratio: %',
            index_record.indexname,
            ROUND(index_size / 1024.0 / 1024.0, 2),
            index_record.tablename,
            ROUND(bloat_ratio, 3);
        
        -- Rebuild indexes that are likely bloated
        -- Skip unique indexes on primary keys to avoid locks
        IF bloat_ratio > 0.3 AND index_size > 50*1024*1024 AND NOT index_record.indexname ~ '_pkey$' THEN
            RAISE NOTICE 'Rebuilding bloated index: %', index_record.indexname;
            EXECUTE 'REINDEX INDEX CONCURRENTLY ' || index_record.schemaname || '.' || index_record.indexname;
        END IF;
    END LOOP;
    
    -- Rebuild GIN indexes separately (they benefit from periodic rebuilds)
    FOR index_record IN
        SELECT DISTINCT
            schemaname,
            indexname
        FROM pg_stat_user_indexes psi
        JOIN pg_indexes pi ON pi.indexname = psi.indexname
        WHERE pi.indexdef LIKE '%USING gin%'
        AND psi.schemaname = 'public'
    LOOP
        RAISE NOTICE 'Rebuilding GIN index: %', index_record.indexname;
        EXECUTE 'REINDEX INDEX CONCURRENTLY ' || index_record.schemaname || '.' || index_record.indexname;
    END LOOP;
    
    RAISE NOTICE 'Index maintenance completed at %', NOW();
END $$;

-- ==============================================================================
-- UPDATE TABLE STATISTICS
-- ==============================================================================

-- Update table statistics for optimal query planning
-- Run this after significant data changes

DO $$
DECLARE
    stats_target INTEGER := 1000; -- Higher than default for better statistics
BEGIN
    RAISE NOTICE 'Updating table statistics with target %', stats_target;
    
    -- Set higher statistics target for key columns
    EXECUTE 'ALTER TABLE rule_sets ALTER COLUMN tenant_id SET STATISTICS ' || stats_target;
    EXECUTE 'ALTER TABLE rule_sets ALTER COLUMN channel SET STATISTICS ' || stats_target;
    EXECUTE 'ALTER TABLE rule_sets ALTER COLUMN metadata SET STATISTICS ' || stats_target;
    
    EXECUTE 'ALTER TABLE rule_versions ALTER COLUMN tenant_id SET STATISTICS ' || stats_target;
    EXECUTE 'ALTER TABLE rule_versions ALTER COLUMN rule_set_id SET STATISTICS ' || stats_target;
    EXECUTE 'ALTER TABLE rule_versions ALTER COLUMN status SET STATISTICS ' || stats_target;
    
    EXECUTE 'ALTER TABLE correction_logs ALTER COLUMN tenant_id SET STATISTICS ' || stats_target;
    EXECUTE 'ALTER TABLE correction_logs ALTER COLUMN rule_id SET STATISTICS ' || stats_target;
    EXECUTE 'ALTER TABLE correction_logs ALTER COLUMN field_name SET STATISTICS ' || stats_target;
    EXECUTE 'ALTER TABLE correction_logs ALTER COLUMN correction_method SET STATISTICS ' || stats_target;
    EXECUTE 'ALTER TABLE correction_logs ALTER COLUMN status SET STATISTICS ' || stats_target;
    
    EXECUTE 'ALTER TABLE suggestions ALTER COLUMN tenant_id SET STATISTICS ' || stats_target;
    EXECUTE 'ALTER TABLE suggestions ALTER COLUMN suggestion_type SET STATISTICS ' || stats_target;
    EXECUTE 'ALTER TABLE suggestions ALTER COLUMN status SET STATISTICS ' || stats_target;
    
    -- Analyze all tables to refresh statistics
    ANALYZE rule_sets, rule_versions, correction_logs, suggestions;
    
    RAISE NOTICE 'Statistics update completed';
END $$;

-- ==============================================================================
-- PARTITION MAINTENANCE
-- ==============================================================================

-- Automatic partition creation and cleanup for time-based partitioned tables
-- Run this daily via cron job

DO $$
DECLARE
    partition_date DATE;
    partition_name TEXT;
    start_date TEXT;
    end_date TEXT;
    old_partition_date DATE;
    old_partition_name TEXT;
    retention_days INTEGER := 730; -- 2 years retention
BEGIN
    RAISE NOTICE 'Starting partition maintenance at %', NOW();
    
    -- Create next month's partition for correction_logs
    partition_date := DATE_TRUNC('month', NOW() + INTERVAL '1 month')::DATE;
    partition_name := 'correction_logs_' || TO_CHAR(partition_date, 'YYYY_MM');
    start_date := TO_CHAR(partition_date, 'YYYY-MM-01');
    
    IF partition_date.month = 12 THEN
        end_date := TO_CHAR(partition_date + INTERVAL '1 year', 'YYYY') || '-01-01';
    ELSE
        end_date := TO_CHAR(partition_date.year, 'FM9999') || '-' || 
                   TO_CHAR(partition_date.month + 1, 'FM00') || '-01';
    END IF;
    
    -- Check if partition already exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = partition_name
    ) THEN
        RAISE NOTICE 'Creating partition: % for period % to %', partition_name, start_date, end_date;
        
        EXECUTE format('CREATE TABLE %I PARTITION OF correction_logs FOR VALUES FROM (%L) TO (%L)',
                      partition_name, start_date, end_date);
        
        -- Add partition-specific optimizations
        EXECUTE format('COMMENT ON TABLE %I IS %L', 
                      partition_name, 
                      'Correction logs partition for ' || TO_CHAR(partition_date, 'Month YYYY'));
    END IF;
    
    -- Drop old partitions beyond retention period
    old_partition_date := DATE_TRUNC('month', NOW() - (retention_days || ' days')::INTERVAL)::DATE;
    old_partition_name := 'correction_logs_' || TO_CHAR(old_partition_date, 'YYYY_MM');
    
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = old_partition_name
    ) THEN
        RAISE NOTICE 'Dropping old partition: % (retention: % days)', old_partition_name, retention_days;
        EXECUTE 'DROP TABLE IF EXISTS ' || old_partition_name || ' CASCADE';
    END IF;
    
    -- Similar logic for rule_effectiveness if it's partitioned
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rule_effectiveness') THEN
        -- Create next month's partition for rule_effectiveness
        partition_name := 'rule_effectiveness_' || TO_CHAR(partition_date, 'YYYY_MM');
        
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = partition_name
        ) THEN
            RAISE NOTICE 'Creating rule_effectiveness partition: %', partition_name;
            
            EXECUTE format('CREATE TABLE %I PARTITION OF rule_effectiveness FOR VALUES FROM (%L) TO (%L)',
                          partition_name, start_date, end_date);
        END IF;
        
        -- Drop old rule_effectiveness partitions (shorter retention - 90 days)
        old_partition_date := DATE_TRUNC('month', NOW() - INTERVAL '90 days')::DATE;
        old_partition_name := 'rule_effectiveness_' || TO_CHAR(old_partition_date, 'YYYY_MM');
        
        IF EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = old_partition_name
        ) THEN
            RAISE NOTICE 'Dropping old rule_effectiveness partition: %', old_partition_name;
            EXECUTE 'DROP TABLE IF EXISTS ' || old_partition_name || ' CASCADE';
        END IF;
    END IF;
    
    RAISE NOTICE 'Partition maintenance completed at %', NOW();
END $$;

-- ==============================================================================
-- MATERIALIZED VIEW REFRESH
-- ==============================================================================

-- Refresh materialized views with optimal concurrency
-- Run this hourly for rule_effectiveness

DO $$
DECLARE
    refresh_start TIMESTAMP WITH TIME ZONE;
    refresh_duration INTERVAL;
BEGIN
    refresh_start := NOW();
    RAISE NOTICE 'Starting materialized view refresh at %', refresh_start;
    
    -- Check if rule_effectiveness materialized view exists
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'rule_effectiveness' 
        AND table_type = 'MATERIALIZED VIEW'
    ) THEN
        -- Use concurrent refresh to avoid blocking reads
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY rule_effectiveness;
            
            refresh_duration := NOW() - refresh_start;
            RAISE NOTICE 'rule_effectiveness refreshed successfully in %', refresh_duration;
            
        EXCEPTION WHEN OTHERS THEN
            RAISE WARNING 'Concurrent refresh failed, falling back to regular refresh: %', SQLERRM;
            -- Fall back to regular refresh if concurrent fails
            REFRESH MATERIALIZED VIEW rule_effectiveness;
        END;
        
        -- Update statistics after refresh
        ANALYZE rule_effectiveness;
    END IF;
    
    RAISE NOTICE 'Materialized view refresh completed at %', NOW();
END $$;

-- ==============================================================================
-- CONNECTION AND LOCK MONITORING
-- ==============================================================================

-- Monitor database connections and long-running queries
-- Run this to check database health

SELECT 
    'Database Health Check' as check_type,
    NOW() as check_time;

-- Current connection count by database and user
SELECT 
    'Active Connections' as metric,
    datname,
    usename,
    COUNT(*) as connection_count,
    MAX(NOW() - backend_start) as longest_connection_age
FROM pg_stat_activity 
WHERE state = 'active'
GROUP BY datname, usename
ORDER BY connection_count DESC;

-- Long-running queries (> 30 minutes)
SELECT 
    'Long Running Queries' as metric,
    NOW() - query_start as duration,
    state,
    usename,
    datname,
    LEFT(query, 100) as query_preview
FROM pg_stat_activity 
WHERE NOW() - query_start > INTERVAL '30 minutes'
  AND state != 'idle'
ORDER BY duration DESC;

-- Lock contention analysis
SELECT 
    'Lock Contention' as metric,
    blocked_locks.pid as blocked_pid,
    blocked_activity.usename as blocked_user,
    blocking_locks.pid as blocking_pid,
    blocking_activity.usename as blocking_user,
    blocked_activity.query as blocked_statement,
    blocking_activity.query as blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.DATABASE IS NOT DISTINCT FROM blocked_locks.DATABASE
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.GRANTED;

-- Table and index sizes
SELECT 
    'Table Sizes' as metric,
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- ==============================================================================
-- MAINTENANCE SCHEDULING RECOMMENDATIONS
-- ==============================================================================

/*
RECOMMENDED MAINTENANCE SCHEDULE:

1. DAILY (via cron at 2 AM):
   - Partition maintenance (create future, drop old)
   - Quick VACUUM on smaller tables
   - Connection monitoring

2. HOURLY:
   - Materialized view refresh (rule_effectiveness)
   - Statistics update for heavily-used tables

3. WEEKLY (Sunday 3 AM):
   - Comprehensive VACUUM ANALYZE on all tables
   - Index bloat analysis and selective rebuild

4. MONTHLY:
   - Full REINDEX of all indexes
   - Deep statistics update
   - Performance analysis and optimization review

5. ON-DEMAND (when performance issues detected):
   - Lock contention analysis
   - Query performance investigation
   - Emergency index rebuilds

EXAMPLE CRON CONFIGURATION:
# Daily maintenance at 2 AM
0 2 * * * psql -d validahub -f /path/to/daily_maintenance.sql

# Hourly materialized view refresh
0 * * * * psql -d validahub -c "SELECT refresh_rule_effectiveness();"

# Weekly full maintenance at 3 AM on Sunday
0 3 * * 0 psql -d validahub -f /path/to/weekly_maintenance.sql
*/