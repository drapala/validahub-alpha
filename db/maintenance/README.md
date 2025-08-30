# ValidaHub Database Maintenance Scripts

This directory contains production-ready maintenance scripts for ValidaHub's rules engine PostgreSQL database. These scripts are designed for zero-downtime operation and follow best practices for multi-tenant, high-volume systems.

## Overview

The maintenance strategy follows a tiered approach:
- **Daily**: Essential operations during low-traffic periods
- **Weekly**: Comprehensive maintenance including archival and optimization
- **Monthly**: Deep analysis and strategic planning operations

## Prerequisites

### Required PostgreSQL Extensions
```sql
-- Required extensions (install as superuser)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
-- Optional but recommended for better maintenance
-- CREATE EXTENSION IF NOT EXISTS "pg_squeeze";  -- For table compression
```

### Required Database Roles
```sql
-- Create maintenance roles (run as superuser)
CREATE ROLE validahub_system NOLOGIN BYPASSRLS;
CREATE ROLE validahub_maintenance NOLOGIN;

-- Grant necessary permissions
GRANT validahub_system TO validahub_maintenance;
GRANT ALL ON ALL TABLES IN SCHEMA public TO validahub_system;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO validahub_system;
GRANT CREATE ON SCHEMA public TO validahub_system;
```

### Required Metadata Tables
```sql
-- Create maintenance logging table
CREATE TABLE IF NOT EXISTS maintenance_log (
    id SERIAL PRIMARY KEY,
    maintenance_type VARCHAR(50) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create materialized view metadata tracking
CREATE TABLE IF NOT EXISTS materialized_view_metadata (
    view_name VARCHAR(100) PRIMARY KEY,
    last_refreshed TIMESTAMP WITH TIME ZONE,
    records_processed BIGINT,
    refresh_duration_seconds NUMERIC,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Maintenance Schedule

### Daily Maintenance (`daily_maintenance.sql`)

**Schedule**: Every day at 2:00 AM UTC  
**Duration**: 5-15 minutes  
**Impact**: Minimal - uses CONCURRENTLY operations

**Operations Performed**:
- Clean expired ML suggestions
- Update table statistics (ANALYZE)
- Refresh materialized views
- Create new monthly partitions
- Light VACUUM operations
- Performance health checks

**Cron Configuration**:
```bash
# Add to postgres user crontab
0 2 * * * cd /path/to/validahub && psql -d validahub -U validahub_maintenance -f db/maintenance/daily_maintenance.sql >> logs/maintenance_daily.log 2>&1
```

**Docker/Kubernetes**:
```yaml
# CronJob example for Kubernetes
apiVersion: batch/v1
kind: CronJob
metadata:
  name: validahub-daily-maintenance
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: maintenance
            image: postgres:15
            command:
            - psql
            - -d
            - $(DATABASE_URL)
            - -f
            - /scripts/daily_maintenance.sql
```

### Weekly Maintenance (`weekly_maintenance.sql`)

**Schedule**: Every Sunday at 1:00 AM UTC  
**Duration**: 30-60 minutes  
**Impact**: Low - some brief locks during index operations

**Operations Performed**:
- Archive old data partitions
- Deep index analysis and maintenance
- Table reorganization (VACUUM FULL when needed)
- Comprehensive statistics update
- Security and compliance verification
- Backup verification
- Performance regression analysis

**Cron Configuration**:
```bash
# Add to postgres user crontab  
0 1 * * 0 cd /path/to/validahub && psql -d validahub -U validahub_maintenance -f db/maintenance/weekly_maintenance.sql >> logs/maintenance_weekly.log 2>&1
```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Maintenance Duration**
   - Daily: < 15 minutes
   - Weekly: < 60 minutes

2. **Database Size Growth**
   - < 5GB growth per month for typical workloads
   - Partition sizes < 20GB each

3. **Index Health**
   - No unused indexes > 100MB
   - Bloat ratio < 2.0 for active indexes

4. **Query Performance**
   - P95 query time < 100ms
   - Cache hit ratio > 95%

### Alert Configuration

```sql
-- Example alert queries (integrate with your monitoring system)

-- Long-running maintenance
SELECT 
    maintenance_type,
    started_at,
    EXTRACT(EPOCH FROM (NOW() - started_at)) / 60.0 as duration_minutes
FROM maintenance_log 
WHERE completed_at IS NULL 
  AND started_at < NOW() - INTERVAL '2 hours';

-- Failed maintenance jobs
SELECT 
    maintenance_type,
    started_at,
    details->>'error' as error_message
FROM maintenance_log 
WHERE completed_at IS NULL 
  AND started_at < NOW() - INTERVAL '1 day';

-- Storage growth alerts
SELECT * FROM monitor_storage_growth() 
WHERE alert_level IN ('WARNING', 'CRITICAL');
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Maintenance Script Timeout
**Symptoms**: Script stops with timeout error  
**Solution**: 
```sql
-- Increase timeout for specific operations
SET statement_timeout = '4hour';  -- Adjust as needed
```

#### 2. Index Rebuild Failures
**Symptoms**: REINDEX CONCURRENTLY fails  
**Solution**:
```sql
-- Fallback to regular reindex (will lock table)
REINDEX INDEX index_name;
```

#### 3. Partition Creation Failures
**Symptoms**: New partition creation fails  
**Solution**:
```sql
-- Check for existing partition
SELECT tablename FROM pg_tables 
WHERE tablename = 'correction_logs_YYYY_MM';

-- Manual partition creation
CREATE TABLE correction_logs_2024_12 PARTITION OF correction_logs
FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');
```

#### 4. Materialized View Refresh Hangs
**Symptoms**: REFRESH MATERIALIZED VIEW doesn't complete  
**Solution**:
```sql
-- Check for blocking queries
SELECT pid, query, state, query_start 
FROM pg_stat_activity 
WHERE query LIKE '%REFRESH MATERIALIZED VIEW%';

-- Kill if necessary (as superuser)
SELECT pg_terminate_backend(pid);

-- Try non-concurrent refresh
REFRESH MATERIALIZED VIEW view_name;
```

### Performance Optimization

#### Maintenance Window Optimization
```sql
-- Check current load before heavy operations
SELECT COUNT(*) as active_connections
FROM pg_stat_activity 
WHERE state = 'active' 
  AND application_name NOT IN ('maintenance', 'backup');

-- Defer maintenance if load is high
-- (This logic is built into the weekly maintenance script)
```

#### Parallel Operations
```sql
-- Increase parallel workers for maintenance operations
SET max_parallel_workers = 8;
SET max_parallel_workers_per_gather = 4;
SET parallel_setup_cost = 100;
SET parallel_tuple_cost = 0.001;
```

## Customization

### Environment-Specific Adjustments

#### Development Environment
```sql
-- Reduced maintenance for development
-- Skip archival operations
-- Shorter retention periods
-- More frequent statistics updates
```

#### Staging Environment  
```sql
-- Mirror production but with shorter retention
-- Include additional validation checks
-- Performance regression testing
```

#### Production Environment
```sql
-- Full maintenance suite
-- Conservative timeouts
-- Comprehensive monitoring
-- Backup verification
```

### Tenant-Specific Maintenance

For tenants with special requirements:

```sql
-- Example: High-volume tenant optimization
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM daily_tenant_metrics 
        WHERE tenant_id = 'high_volume_tenant' 
          AND total_corrections > 100000
    ) THEN
        -- Special maintenance for high-volume tenants
        PERFORM special_maintenance_for_tenant('high_volume_tenant');
    END IF;
END $$;
```

## Disaster Recovery

### Backup Integration
The maintenance scripts include backup verification checks. Ensure your backup system:

1. **Validates** backup integrity
2. **Tests** recovery procedures monthly
3. **Monitors** backup completion status
4. **Archives** WAL files continuously

### Recovery Testing
```sql
-- Monthly backup recovery test (run in staging)
-- 1. Restore from backup
-- 2. Run maintenance scripts
-- 3. Verify data consistency
-- 4. Test application functionality
```

## Version Compatibility

These scripts are tested with:
- PostgreSQL 13+
- ValidaHub schema versions 1.0+
- Multi-tenant configurations

For updates or issues, refer to the ValidaHub infrastructure team.

## Security Considerations

1. **Access Control**: Scripts run with `validahub_system` role (BYPASSRLS)
2. **Audit Logging**: All operations logged to `maintenance_log`
3. **Data Retention**: Automatic cleanup of sensitive data per LGPD requirements
4. **Encryption**: No plaintext secrets in scripts (use environment variables)

## Contact and Support

For maintenance-related issues:
- Check logs: `/var/log/postgresql/` and application logs
- Monitor database metrics during maintenance windows
- Review `maintenance_log` table for operation history
- Escalate critical issues to on-call DBA