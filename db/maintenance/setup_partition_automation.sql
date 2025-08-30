-- ValidaHub Partition Automation Setup
-- 
-- This script sets up automated partition management using pg_cron
-- Run this after installing pg_cron extension
--
-- Installation:
-- 1. Install pg_cron extension: CREATE EXTENSION pg_cron;
-- 2. Run this script to schedule automated maintenance
-- 3. Monitor via check_partition_health() function

-- Ensure pg_cron is installed (uncomment if needed)
-- CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule daily partition maintenance at 3 AM UTC
-- This creates future partitions and archives/drops old ones
SELECT cron.schedule(
    'partition-maintenance-daily',
    '0 3 * * *',  -- Daily at 3 AM
    $$SELECT maintain_partitions();$$
);

-- Schedule hourly health checks during business hours
SELECT cron.schedule(
    'partition-health-check',
    '0 9-18 * * 1-5',  -- Every hour 9 AM - 6 PM on weekdays
    $$
    DO $$
    DECLARE
        v_health RECORD;
        v_alert_count INTEGER;
    BEGIN
        -- Check partition health
        FOR v_health IN SELECT * FROM check_partition_health() LOOP
            -- Count critical alerts
            SELECT COUNT(*)
            INTO v_alert_count
            FROM jsonb_array_elements(v_health.alerts) AS alert
            WHERE alert->>'level' = 'critical';
            
            -- Log critical issues
            IF v_alert_count > 0 THEN
                RAISE WARNING 'CRITICAL: Partition health issue for %: %',
                    v_health.table_name, v_health.alerts;
                    
                -- Insert into maintenance log for alerting
                INSERT INTO partition_management_log (
                    table_name, action, partition_name,
                    partition_start_date, partition_end_date,
                    success, error_message
                ) VALUES (
                    v_health.table_name, 'health_check', 'system',
                    CURRENT_DATE, CURRENT_DATE,
                    false, v_health.alerts::TEXT
                );
            END IF;
        END LOOP;
    END $$;
    $$
);

-- Schedule weekly partition analysis (Sundays at 4 AM)
SELECT cron.schedule(
    'partition-analysis-weekly',
    '0 4 * * 0',  -- Sunday at 4 AM
    $$
    DO $$
    DECLARE
        v_partition RECORD;
    BEGIN
        -- Analyze all correction_logs partitions for query optimization
        FOR v_partition IN
            SELECT tablename
            FROM pg_tables
            WHERE tablename LIKE 'correction_logs_%'
            AND schemaname = 'public'
        LOOP
            EXECUTE FORMAT('ANALYZE %I', v_partition.tablename);
        END LOOP;
        
        -- Log completion
        INSERT INTO partition_management_log (
            table_name, action, partition_name,
            partition_start_date, partition_end_date,
            success
        ) VALUES (
            'correction_logs', 'analyzed', 'all_partitions',
            CURRENT_DATE, CURRENT_DATE,
            true
        );
    END $$;
    $$
);

-- View scheduled jobs
SELECT * FROM cron.job;

-- Manual execution commands (for testing)
COMMENT ON FUNCTION maintain_partitions() IS 
'Automated partition maintenance. Manual execution: SELECT maintain_partitions();';

COMMENT ON FUNCTION check_partition_health() IS 
'Check partition health status. Manual execution: SELECT * FROM check_partition_health();';

-- Create helper view for monitoring
CREATE OR REPLACE VIEW partition_status AS
SELECT 
    tablename as partition_name,
    pg_size_pretty(pg_total_relation_size(tablename::regclass)) as size,
    pg_total_relation_size(tablename::regclass) / 1024 / 1024.0 as size_mb,
    (SELECT COUNT(*) FROM pg_class WHERE relname = tablename)::BIGINT as estimated_rows,
    TO_DATE(SUBSTRING(tablename FROM '\d{4}_\d{2}$'), 'YYYY_MM') as partition_month,
    CASE 
        WHEN tablename LIKE 'archive_%' THEN 'archived'
        WHEN TO_DATE(SUBSTRING(tablename FROM '\d{4}_\d{2}$'), 'YYYY_MM') < DATE_TRUNC('month', CURRENT_DATE) THEN 'historical'
        WHEN TO_DATE(SUBSTRING(tablename FROM '\d{4}_\d{2}$'), 'YYYY_MM') = DATE_TRUNC('month', CURRENT_DATE) THEN 'current'
        ELSE 'future'
    END as status
FROM pg_tables
WHERE tablename LIKE '%correction_logs_%'
AND schemaname = 'public'
ORDER BY partition_month DESC;

COMMENT ON VIEW partition_status IS 'Real-time view of all correction_logs partitions and their status';

-- Create alerting function for integration with monitoring systems
CREATE OR REPLACE FUNCTION get_partition_alerts()
RETURNS TABLE(
    severity TEXT,
    table_name TEXT,
    message TEXT,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE sql
AS $$
    SELECT 
        CASE 
            WHEN error_message LIKE '%CRITICAL%' THEN 'critical'
            WHEN error_message LIKE '%WARNING%' THEN 'warning'
            ELSE 'info'
        END as severity,
        table_name,
        COALESCE(error_message, action || ' completed') as message,
        jsonb_build_object(
            'partition', partition_name,
            'rows', rows_affected,
            'size_mb', size_mb,
            'execution_ms', execution_time_ms
        ) as details,
        created_at
    FROM partition_management_log
    WHERE created_at > NOW() - INTERVAL '24 hours'
    AND (NOT success OR error_message IS NOT NULL)
    ORDER BY created_at DESC;
$$;

-- Alternative: SystemD timer setup (if pg_cron not available)
-- Save this as /etc/systemd/system/validahub-partition-maintenance.service
/*
[Unit]
Description=ValidaHub Partition Maintenance
After=postgresql.service

[Service]
Type=oneshot
User=postgres
ExecStart=/usr/bin/psql -d validahub -c "SELECT maintain_partitions();"
StandardOutput=journal
StandardError=journal
*/

-- And corresponding timer: /etc/systemd/system/validahub-partition-maintenance.timer
/*
[Unit]
Description=Run ValidaHub Partition Maintenance daily
Requires=validahub-partition-maintenance.service

[Timer]
OnCalendar=daily
AccuracySec=1h
Persistent=true

[Install]
WantedBy=timers.target
*/

-- Quick test to verify everything works
DO $$
BEGIN
    RAISE NOTICE 'Testing partition management...';
    
    -- Test creating partitions
    PERFORM create_monthly_partitions('correction_logs', 1);
    
    -- Test health check
    PERFORM * FROM check_partition_health();
    
    RAISE NOTICE 'Partition management setup completed successfully!';
    RAISE NOTICE 'Run "SELECT * FROM partition_status;" to view current partitions';
    RAISE NOTICE 'Run "SELECT * FROM check_partition_health();" to check health';
    RAISE NOTICE 'Run "SELECT maintain_partitions();" to manually trigger maintenance';
END $$;