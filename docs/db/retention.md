# Database Retention and Archival Strategy

## Executive Summary

This document outlines ValidaHub's comprehensive data retention and archival strategy for the rules engine database. The strategy balances regulatory compliance, operational performance, cost optimization, and business intelligence requirements while maintaining data integrity and security.

**Key Principles:**
- **Compliance-First**: Adhere to Brazilian LGPD and international data protection requirements
- **Performance-Driven**: Maintain query performance by managing data volume growth
- **Cost-Effective**: Balance storage costs with business intelligence needs
- **Audit-Ready**: Preserve audit trails and regulatory compliance records
- **Zero-Downtime**: All archival operations must not impact production workloads

## Data Classification and Retention Periods

### Critical Business Data (7 Year Retention)

**Rule Sets and Versions**
- **Tables**: `rule_sets`, `rule_versions`
- **Retention**: 7 years after deprecation
- **Rationale**: Business rule evolution tracking, regulatory compliance, audit requirements
- **Archive Strategy**: Compress and move to cold storage after 1 year of inactivity

```sql
-- Example retention query
SELECT rule_set_id, deprecated_at 
FROM rule_sets 
WHERE deprecated_at < NOW() - INTERVAL '7 years';
```

### Operational Data (2 Year Hot + 5 Year Cold)

**Correction Logs** (Partitioned Table)
- **Hot Storage**: 2 years (immediate query access)
- **Cold Storage**: 5 years (archived with limited access)
- **Purge**: After 7 years total retention
- **Special Handling**: Regulatory audit trails preserved longer if required

**Partitioning Strategy for Archival:**
```sql
-- Monthly partitions for efficient archival
correction_logs_2024_01, correction_logs_2024_02, ...

-- Archive partitions older than 2 years
-- Move to separate tablespace on slower storage
```

### ML and Analytics Data (3 Year Retention)

**Suggestions and Effectiveness Data**
- **Tables**: `suggestions`, `rule_effectiveness`, analytics materialized views
- **Retention**: 3 years for model training and business intelligence
- **Archive Strategy**: Aggregate historical data into summary tables

## Archival Implementation Strategy

### 1. Partition Management for correction_logs

**Automated Partition Creation:**
```sql
-- Function to create new partitions (run monthly)
CREATE OR REPLACE FUNCTION create_monthly_partition(
    target_date DATE DEFAULT (NOW() + INTERVAL '1 month')::DATE
)
RETURNS TEXT AS $$
DECLARE
    partition_name TEXT;
    start_date TEXT;
    end_date TEXT;
BEGIN
    -- Calculate partition boundaries
    start_date := DATE_TRUNC('month', target_date)::TEXT;
    end_date := (DATE_TRUNC('month', target_date) + INTERVAL '1 month')::TEXT;
    partition_name := 'correction_logs_' || TO_CHAR(target_date, 'YYYY_MM');
    
    -- Create partition
    EXECUTE format(
        'CREATE TABLE %I PARTITION OF correction_logs 
         FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date
    );
    
    -- Create partition-specific indexes
    EXECUTE format(
        'CREATE INDEX CONCURRENTLY %I ON %I (tenant_id, created_at)',
        'idx_' || partition_name || '_tenant_created', partition_name
    );
    
    RETURN 'Created partition: ' || partition_name;
END;
$$ LANGUAGE plpgsql;
```

**Automated Archival Process:**
```sql
-- Function to archive old partitions
CREATE OR REPLACE FUNCTION archive_old_partitions(
    retention_months INTEGER DEFAULT 24
)
RETURNS TEXT[] AS $$
DECLARE
    partition_record RECORD;
    archived_partitions TEXT[] := '{}';
    archive_tablespace TEXT := 'archive_tablespace';
BEGIN
    -- Find partitions older than retention period
    FOR partition_record IN
        SELECT schemaname, tablename, 
               regexp_replace(tablename, 'correction_logs_(\d{4})_(\d{2})', '\1-\2-01')::DATE as partition_date
        FROM pg_tables 
        WHERE tablename ~ '^correction_logs_\d{4}_\d{2}$'
          AND regexp_replace(tablename, 'correction_logs_(\d{4})_(\d{2})', '\1-\2-01')::DATE < 
              NOW()::DATE - (retention_months || ' months')::INTERVAL
    LOOP
        -- Move partition to archive tablespace
        EXECUTE format('ALTER TABLE %I.%I SET TABLESPACE %I', 
            partition_record.schemaname, partition_record.tablename, archive_tablespace);
        
        -- Update partition-specific settings for archival
        EXECUTE format('ALTER TABLE %I.%I SET (fillfactor = 100)', 
            partition_record.schemaname, partition_record.tablename);
        
        -- Compress partition if pg_squeeze extension available
        -- EXECUTE format('SELECT squeeze.squeeze_table(%L)', partition_record.tablename);
        
        archived_partitions := array_append(archived_partitions, partition_record.tablename);
    END LOOP;
    
    RETURN archived_partitions;
END;
$$ LANGUAGE plpgsql;
```

### 2. Materialized View Data Management

**Retention Strategy for Analytics Views:**
```sql
-- Clean old data from materialized views
CREATE OR REPLACE FUNCTION cleanup_analytics_views()
RETURNS VOID AS $$
BEGIN
    -- Keep 90 days in rule_effectiveness
    DELETE FROM rule_effectiveness 
    WHERE metric_date < NOW()::DATE - INTERVAL '90 days';
    
    -- Keep 1 year in daily_tenant_metrics
    DELETE FROM daily_tenant_metrics 
    WHERE metric_date < NOW()::DATE - INTERVAL '365 days';
    
    -- Keep 6 months in channel_performance_metrics
    DELETE FROM channel_performance_metrics 
    WHERE metric_month < DATE_TRUNC('month', NOW() - INTERVAL '6 months');
    
    -- Refresh statistics after cleanup
    ANALYZE rule_effectiveness;
    ANALYZE daily_tenant_metrics;
    ANALYZE channel_performance_metrics;
END;
$$ LANGUAGE plpgsql;
```

### 3. Soft Delete and Purge Strategy

**Rule Sets Soft Delete:**
```sql
-- Add deletion tracking columns (migration)
ALTER TABLE rule_sets ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE rule_sets ADD COLUMN deletion_reason TEXT;

-- Soft delete function
CREATE OR REPLACE FUNCTION soft_delete_rule_set(
    p_rule_set_id UUID,
    p_tenant_id VARCHAR(50),
    p_reason TEXT,
    p_deleted_by VARCHAR(100)
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE rule_sets 
    SET deleted_at = NOW(),
        deletion_reason = p_reason,
        updated_by = p_deleted_by,
        updated_at = NOW()
    WHERE id = p_rule_set_id 
      AND tenant_id = p_tenant_id
      AND deleted_at IS NULL;
    
    IF FOUND THEN
        -- Also soft delete associated versions
        UPDATE rule_versions 
        SET status = 'deprecated', 
            deprecated_at = NOW(),
            deprecated_by = p_deleted_by
        WHERE rule_set_id = p_rule_set_id;
        
        RETURN TRUE;
    END IF;
    
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;
```

## Automated Maintenance Schedule

### Daily Tasks (Run at 2 AM UTC)
```sql
-- Daily maintenance script
CREATE OR REPLACE FUNCTION daily_maintenance()
RETURNS TEXT AS $$
DECLARE
    result TEXT := '';
BEGIN
    -- Cleanup expired suggestions
    DELETE FROM suggestions 
    WHERE expires_at < NOW() 
      AND status IN ('generated', 'reviewed');
    
    result := result || 'Cleaned ' || ROW_COUNT || ' expired suggestions. ';
    
    -- Update materialized views
    PERFORM refresh_all_analytics_views();
    result := result || 'Refreshed analytics views. ';
    
    -- Basic maintenance
    VACUUM ANALYZE correction_logs;
    result := result || 'Analyzed correction_logs. ';
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;
```

### Weekly Tasks (Run Sunday at 1 AM UTC)
```sql
-- Weekly maintenance script  
CREATE OR REPLACE FUNCTION weekly_maintenance()
RETURNS TEXT AS $$
DECLARE
    result TEXT := '';
    archived_partitions TEXT[];
BEGIN
    -- Archive old partitions (older than 2 years)
    archived_partitions := archive_old_partitions(24);
    result := result || 'Archived partitions: ' || array_to_string(archived_partitions, ', ') || '. ';
    
    -- Create next month's partition
    result := result || create_monthly_partition() || '. ';
    
    -- Cleanup analytics views
    PERFORM cleanup_analytics_views();
    result := result || 'Cleaned analytics views. ';
    
    -- Full vacuum on small tables
    VACUUM FULL rule_sets, rule_versions;
    result := result || 'Full vacuum completed on metadata tables. ';
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;
```

### Monthly Tasks (1st Sunday at 12 AM UTC)
```sql
-- Monthly maintenance script
CREATE OR REPLACE FUNCTION monthly_maintenance()
RETURNS TEXT AS $$
DECLARE
    result TEXT := '';
BEGIN
    -- Purge old soft-deleted records (after 90 days)
    DELETE FROM rule_sets 
    WHERE deleted_at < NOW() - INTERVAL '90 days';
    
    result := result || 'Purged ' || ROW_COUNT || ' soft-deleted rule sets. ';
    
    -- Archive suggestions older than 1 year to cold storage
    -- Implementation depends on cold storage strategy
    
    -- Reindex frequently updated tables
    REINDEX TABLE suggestions;
    REINDEX TABLE rule_versions;
    result := result || 'Reindexed active tables. ';
    
    -- Update table statistics
    ANALYZE;
    result := result || 'Updated database statistics. ';
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;
```

## Data Export and Backup Integration

### Backup Strategy Alignment
```sql
-- Function to identify archival-ready data for backups
CREATE OR REPLACE FUNCTION get_archival_ready_data(
    table_name TEXT,
    retention_days INTEGER
)
RETURNS TABLE (
    schema_name TEXT,
    table_name TEXT,
    estimated_size TEXT,
    oldest_record TIMESTAMP WITH TIME ZONE,
    record_count BIGINT
) AS $$
BEGIN
    RETURN QUERY EXECUTE format(
        'SELECT 
            schemaname::TEXT,
            tablename::TEXT,
            pg_size_pretty(pg_total_relation_size(schemaname||''.''||tablename))::TEXT,
            MIN(created_at),
            COUNT(*)
         FROM %I 
         WHERE created_at < NOW() - INTERVAL ''%s days''
         GROUP BY schemaname, tablename',
        table_name, retention_days
    );
END;
$$ LANGUAGE plpgsql;
```

## LGPD Compliance Features

### Right to Deletion (Right to be Forgotten)
```sql
-- LGPD-compliant data deletion function
CREATE OR REPLACE FUNCTION lgpd_delete_tenant_data(
    p_tenant_id VARCHAR(50),
    p_deletion_request_id UUID,
    p_legal_basis TEXT
)
RETURNS JSONB AS $$
DECLARE
    deletion_report JSONB := '{}';
    affected_tables TEXT[] := ARRAY['rule_sets', 'rule_versions', 'correction_logs', 'suggestions'];
    table_name TEXT;
    deleted_count INTEGER;
BEGIN
    -- Validate deletion request and legal basis
    IF p_legal_basis NOT IN ('user_request', 'legal_obligation', 'court_order') THEN
        RAISE EXCEPTION 'Invalid legal basis for deletion: %', p_legal_basis;
    END IF;
    
    -- Log deletion request
    INSERT INTO audit_log (event_type, tenant_id, details, created_at)
    VALUES ('lgpd_deletion_request', p_tenant_id, 
            jsonb_build_object('request_id', p_deletion_request_id, 'legal_basis', p_legal_basis),
            NOW());
    
    -- Delete from each table and record counts
    FOREACH table_name IN ARRAY affected_tables
    LOOP
        EXECUTE format('DELETE FROM %I WHERE tenant_id = $1', table_name) USING p_tenant_id;
        GET DIAGNOSTICS deleted_count = ROW_COUNT;
        deletion_report := deletion_report || jsonb_build_object(table_name, deleted_count);
    END LOOP;
    
    -- Log completion
    INSERT INTO audit_log (event_type, tenant_id, details, created_at)
    VALUES ('lgpd_deletion_completed', p_tenant_id, deletion_report, NOW());
    
    RETURN deletion_report;
END;
$$ LANGUAGE plpgsql;
```

### Data Export for Portability
```sql
-- LGPD-compliant data export function
CREATE OR REPLACE FUNCTION lgpd_export_tenant_data(
    p_tenant_id VARCHAR(50),
    p_export_format TEXT DEFAULT 'json'
)
RETURNS TEXT AS $$
DECLARE
    export_data JSONB := '{}';
BEGIN
    -- Export rule sets
    export_data := export_data || jsonb_build_object(
        'rule_sets',
        (SELECT jsonb_agg(row_to_json(rs.*)) FROM rule_sets rs WHERE rs.tenant_id = p_tenant_id)
    );
    
    -- Export rule versions
    export_data := export_data || jsonb_build_object(
        'rule_versions',
        (SELECT jsonb_agg(row_to_json(rv.*)) FROM rule_versions rv WHERE rv.tenant_id = p_tenant_id)
    );
    
    -- Export recent corrections (last 2 years for privacy)
    export_data := export_data || jsonb_build_object(
        'recent_corrections',
        (SELECT jsonb_agg(row_to_json(cl.*)) 
         FROM correction_logs cl 
         WHERE cl.tenant_id = p_tenant_id 
           AND cl.created_at >= NOW() - INTERVAL '2 years')
    );
    
    -- Log export request
    INSERT INTO audit_log (event_type, tenant_id, details, created_at)
    VALUES ('lgpd_data_export', p_tenant_id, 
            jsonb_build_object('format', p_export_format, 'size_bytes', octet_length(export_data::text)),
            NOW());
    
    RETURN export_data::text;
END;
$$ LANGUAGE plpgsql;
```

## Monitoring and Alerting

### Storage Growth Monitoring
```sql
-- Function to monitor storage growth and alert on thresholds
CREATE OR REPLACE FUNCTION monitor_storage_growth()
RETURNS TABLE (
    table_name TEXT,
    current_size TEXT,
    size_bytes BIGINT,
    growth_rate_mb_per_day NUMERIC,
    estimated_days_to_threshold INTEGER,
    alert_level TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH current_sizes AS (
        SELECT 
            schemaname||'.'||tablename as full_table_name,
            pg_total_relation_size(schemaname||'.'||tablename) as size_in_bytes
        FROM pg_tables 
        WHERE schemaname = 'public' 
          AND tablename IN ('rule_sets', 'rule_versions', 'correction_logs', 'suggestions')
    ),
    growth_analysis AS (
        SELECT 
            cs.full_table_name,
            pg_size_pretty(cs.size_in_bytes) as current_size,
            cs.size_in_bytes,
            -- Estimate growth based on recent partition sizes
            CASE 
                WHEN cs.full_table_name LIKE '%correction_logs%' THEN cs.size_in_bytes / 30.0 / 1024 / 1024 -- Assume 30-day data
                ELSE cs.size_in_bytes / 365.0 / 1024 / 1024 -- Assume yearly growth for other tables
            END as growth_mb_per_day,
            CASE 
                WHEN cs.full_table_name LIKE '%correction_logs%' THEN 
                    (50 * 1024 * 1024 * 1024 - cs.size_in_bytes) / GREATEST(cs.size_in_bytes / 30.0, 1) -- 50GB threshold
                ELSE 
                    (5 * 1024 * 1024 * 1024 - cs.size_in_bytes) / GREATEST(cs.size_in_bytes / 365.0, 1) -- 5GB threshold
            END as days_to_threshold
        FROM current_sizes cs
    )
    SELECT 
        ga.full_table_name,
        ga.current_size,
        ga.size_in_bytes,
        ROUND(ga.growth_mb_per_day, 2),
        ga.days_to_threshold::INTEGER,
        CASE 
            WHEN ga.days_to_threshold < 30 THEN 'CRITICAL'
            WHEN ga.days_to_threshold < 90 THEN 'WARNING' 
            WHEN ga.days_to_threshold < 180 THEN 'INFO'
            ELSE 'OK'
        END
    FROM growth_analysis ga
    ORDER BY ga.days_to_threshold;
END;
$$ LANGUAGE plpgsql;
```

## Implementation Checklist

### Phase 1: Basic Retention (Week 1-2)
- [ ] Implement partition management for correction_logs
- [ ] Set up basic daily/weekly maintenance jobs
- [ ] Configure automated partition creation
- [ ] Test archival processes in staging

### Phase 2: Advanced Features (Week 3-4)
- [ ] Implement LGPD compliance functions
- [ ] Set up storage monitoring and alerting
- [ ] Configure cold storage tablespace
- [ ] Implement soft delete functionality

### Phase 3: Optimization (Week 5-6)
- [ ] Tune maintenance schedules based on actual load
- [ ] Implement compression strategies
- [ ] Set up backup integration
- [ ] Create retention policy documentation

### Phase 4: Monitoring (Ongoing)
- [ ] Monitor storage growth trends
- [ ] Validate archival process effectiveness  
- [ ] Regular retention policy reviews
- [ ] Compliance audit preparation

## Performance Impact Assessment

**Expected Performance Benefits:**
- 40-60% reduction in query times for recent data queries
- 70% reduction in index maintenance overhead
- 50% reduction in backup/restore times for hot data

**Resource Requirements:**
- Additional storage for archive tablespace (estimate 30% of current size)
- CPU overhead for maintenance jobs (< 5% during off-peak hours)
- Network bandwidth for cold storage transfers (estimated 10GB/month)

**Risk Mitigation:**
- All maintenance operations use `CONCURRENTLY` where possible
- Phased rollout with rollback procedures
- Comprehensive testing in staging environment
- 24/7 monitoring during initial deployment