# Database Performance Optimization Guide

## Executive Summary

This document provides comprehensive performance optimization strategies for ValidaHub's rules engine database. Based on production-ready PostgreSQL best practices and the specific access patterns of a multi-tenant SaaS platform processing high-volume CSV validation and corrections.

**Performance Targets:**
- Query response time: P95 < 100ms for dashboard queries
- Correction log insertions: > 10,000 rows/second
- Multi-tenant isolation: Zero cross-tenant data leakage
- Materialized view refresh: < 5 minutes for full analytics refresh
- Storage efficiency: > 80% through proper indexing and partitioning

## Index Strategy and Optimization

### Primary Index Design Principles

**1. Tenant-First Indexing Pattern**
All indexes must include `tenant_id` as the first column for multi-tenant isolation:

```sql
-- Correct: Tenant isolation first
CREATE INDEX idx_corrections_tenant_date 
ON correction_logs (tenant_id, created_at DESC);

-- Incorrect: Cross-tenant query possibility  
CREATE INDEX idx_corrections_date_only 
ON correction_logs (created_at DESC);
```

**2. Composite Index Column Ordering**
Follow the selectivity hierarchy: `tenant_id` → high selectivity → low selectivity → sort columns:

```sql
-- Optimal ordering for correction log queries
CREATE INDEX idx_corrections_optimal
ON correction_logs (
    tenant_id,        -- Highest selectivity (tenant isolation)
    rule_id,          -- High selectivity (specific rule)
    status,           -- Medium selectivity (few status values)  
    created_at DESC   -- Sort column last
);
```

### Index Performance Analysis

**Current Index Efficiency Report:**
```sql
-- Query to analyze index usage and effectiveness
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch,
    ROUND(
        CASE 
            WHEN idx_tup_read > 0 THEN (idx_tup_fetch::NUMERIC / idx_tup_read) * 100 
            ELSE 0 
        END, 2
    ) as index_selectivity_pct,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes 
WHERE schemaname = 'public'
ORDER BY idx_tup_read DESC;
```

### Specialized Index Configurations

**1. JSONB GIN Indexes for Flexible Queries**
```sql
-- High-performance JSONB indexing with specific operators
CREATE INDEX CONCURRENTLY idx_rule_versions_rules_advanced_gin
ON rule_versions USING gin (
    rules jsonb_path_ops,  -- More efficient for path queries
    (rules -> 'conditions') -- Index specific JSONB paths
);

-- Enable fast containment queries
CREATE INDEX CONCURRENTLY idx_corrections_metadata_containment  
ON correction_logs USING gin (
    correction_metadata jsonb_ops  -- Better for key existence queries
);
```

**2. Partial Indexes for Common Filtered Queries**
```sql
-- Index only active, non-deprecated rule versions
CREATE INDEX CONCURRENTLY idx_rule_versions_active_optimized
ON rule_versions (tenant_id, rule_set_id, created_at DESC)
WHERE status = 'published' AND deprecated_at IS NULL;

-- Index only pending corrections (hot data)
CREATE INDEX CONCURRENTLY idx_corrections_pending_hot
ON correction_logs (tenant_id, created_at DESC, field_name) 
WHERE status = 'pending' AND created_at >= NOW() - INTERVAL '7 days';
```

**3. Covering Indexes to Reduce Table Lookups**
```sql
-- Include frequently accessed columns in index
CREATE INDEX CONCURRENTLY idx_suggestions_dashboard_covering
ON suggestions (tenant_id, status, priority_score DESC)
INCLUDE (title, confidence_score, created_at, suggestion_type);
```

### Index Maintenance Strategy

**Monitoring Index Health:**
```sql
-- Function to identify bloated or unused indexes
CREATE OR REPLACE FUNCTION analyze_index_health()
RETURNS TABLE (
    table_name TEXT,
    index_name TEXT,
    size_mb NUMERIC,
    bloat_ratio NUMERIC,
    usage_score NUMERIC,
    recommendation TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH index_stats AS (
        SELECT 
            schemaname||'.'||tablename as full_table_name,
            indexname,
            pg_relation_size(indexrelid) / 1024 / 1024.0 as size_mb,
            idx_tup_read,
            idx_tup_fetch,
            idx_scan
        FROM pg_stat_user_indexes
        WHERE schemaname = 'public'
    ),
    index_analysis AS (
        SELECT 
            *,
            CASE 
                WHEN idx_scan > 0 AND idx_tup_read > 0 THEN
                    (idx_tup_fetch::NUMERIC / idx_tup_read) * LOG(idx_scan + 1)
                ELSE 0 
            END as usage_score,
            -- Estimate bloat based on size vs usage patterns
            CASE 
                WHEN size_mb > 100 AND idx_scan < 10 THEN size_mb / GREATEST(idx_scan, 1)
                ELSE 1.0
            END as estimated_bloat
        FROM index_stats
    )
    SELECT 
        ia.full_table_name,
        ia.indexname,
        ROUND(ia.size_mb, 2),
        ROUND(ia.estimated_bloat, 2),
        ROUND(ia.usage_score, 2),
        CASE 
            WHEN ia.size_mb > 50 AND ia.idx_scan = 0 THEN 'DROP: Unused large index'
            WHEN ia.estimated_bloat > 10 THEN 'REINDEX: High bloat detected'
            WHEN ia.usage_score < 1 AND ia.size_mb > 10 THEN 'REVIEW: Low usage efficiency'
            WHEN ia.usage_score > 100 THEN 'OPTIMIZE: High-value index'
            ELSE 'MAINTAIN: Normal operation'
        END
    FROM index_analysis ia
    ORDER BY ia.usage_score DESC, ia.size_mb DESC;
END;
$$ LANGUAGE plpgsql;
```

## Query Optimization Patterns

### 1. Tenant-Scoped Query Patterns

**Optimal Multi-Tenant Query Structure:**
```sql
-- Template for all tenant queries
SELECT /* columns */
FROM table_name t
WHERE t.tenant_id = $1  -- Always first filter
  AND /* additional conditions */
ORDER BY /* order clauses */
LIMIT /* reasonable limit */;

-- Example: Get recent corrections for a tenant
EXPLAIN (ANALYZE, BUFFERS) 
SELECT 
    cl.field_name,
    cl.correction_type,
    cl.confidence_score,
    cl.created_at
FROM correction_logs cl
WHERE cl.tenant_id = 't_acme_corp'
  AND cl.created_at >= NOW() - INTERVAL '7 days'
  AND cl.status = 'applied'
ORDER BY cl.created_at DESC
LIMIT 100;
```

### 2. JSONB Query Optimization

**Efficient JSONB Query Patterns:**
```sql
-- Optimized JSONB containment queries
SELECT rv.id, rv.version, rv.rules
FROM rule_versions rv
WHERE rv.tenant_id = 't_acme_corp'
  AND rv.rules @> '{"field": "price", "type": "range"}'::jsonb
  AND rv.status = 'published';

-- Using GIN indexes for path queries  
SELECT cl.correction_metadata->'processing_time_ms' as processing_time
FROM correction_logs cl
WHERE cl.tenant_id = 't_acme_corp'
  AND cl.correction_metadata ? 'processing_time_ms'  -- Key existence check
  AND (cl.correction_metadata->>'processing_time_ms')::NUMERIC > 1000;

-- Optimized aggregations on JSONB fields
SELECT 
    cl.field_name,
    AVG((cl.estimated_impact->>'revenue_impact')::NUMERIC) as avg_impact
FROM correction_logs cl
WHERE cl.tenant_id = 't_acme_corp'
  AND cl.estimated_impact ? 'revenue_impact'
GROUP BY cl.field_name;
```

## Partitioning Performance Optimization

### Partition Pruning Optimization

**Query Patterns for Optimal Partition Elimination:**
```sql
-- Excellent: Partition pruning with exact date range
SELECT COUNT(*) 
FROM correction_logs
WHERE tenant_id = 't_acme_corp'
  AND created_at >= '2024-01-01'::DATE
  AND created_at < '2024-02-01'::DATE;

-- Good: Partition pruning with relative dates
SELECT * 
FROM correction_logs
WHERE tenant_id = 't_acme_corp'
  AND created_at >= DATE_TRUNC('month', NOW())
  AND status = 'pending';

-- Poor: Forces scan of all partitions
SELECT * 
FROM correction_logs
WHERE tenant_id = 't_acme_corp'
  AND EXTRACT(YEAR FROM created_at) = 2024;  -- Function prevents pruning
```

## Memory and Configuration Tuning

### PostgreSQL Configuration for Rules Engine Workload

**Recommended postgresql.conf Settings:**
```ini
# Memory Configuration
shared_buffers = 4GB                    # 25% of total RAM
work_mem = 256MB                        # For complex JSONB operations  
maintenance_work_mem = 1GB              # For REINDEX and VACUUM operations
effective_cache_size = 12GB             # 75% of total RAM

# Connection Management
max_connections = 200                   # Balance between concurrency and resources
shared_preload_libraries = 'pg_stat_statements'

# Query Planner
default_statistics_target = 100         # Better statistics for JSONB columns
random_page_cost = 1.1                  # SSD-optimized
seq_page_cost = 1.0                     # SSD-optimized

# Checkpoints and WAL
checkpoint_timeout = 10min              # Longer intervals for better performance
checkpoint_completion_target = 0.9      # Spread out checkpoint I/O
wal_buffers = 64MB                      # High write volume optimization
max_wal_size = 4GB                      # Allow larger WAL for bulk operations

# Background Writer
bgwriter_delay = 50ms                   # More frequent background writes
bgwriter_lru_maxpages = 1000           # Clean more pages per round
bgwriter_lru_multiplier = 10.0         # Aggressive background cleaning

# Autovacuum Tuning
autovacuum_max_workers = 6              # More workers for partitioned tables
autovacuum_naptime = 30s                # More frequent autovacuum checks
autovacuum_vacuum_scale_factor = 0.1    # Vacuum when 10% of table changes
autovacuum_analyze_scale_factor = 0.05  # Analyze when 5% of table changes

# Logging for Performance Monitoring
log_min_duration_statement = 1000       # Log queries > 1 second
log_checkpoints = on                    # Monitor checkpoint performance
log_connections = on                    # Monitor connection patterns
log_disconnections = on
log_lock_waits = on                     # Identify contention
```

### Connection Pooling Configuration

**PgBouncer Optimization for Multi-Tenant Workload:**
```ini
# pgbouncer.ini optimized for ValidaHub
[databases]
validahub = host=localhost port=5432 dbname=validahub

[pgbouncer]
pool_mode = transaction                 # Efficient for short transactions
max_client_conn = 1000                  # High concurrent user support
default_pool_size = 20                  # Connections per database
min_pool_size = 5                       # Always keep minimum connections
reserve_pool_size = 5                   # Emergency connections
max_db_connections = 100                # Total connections to PostgreSQL

# Performance optimizations
query_timeout = 300                     # 5 minute query timeout
query_wait_timeout = 120                # 2 minute wait timeout
client_idle_timeout = 3600              # 1 hour idle timeout
server_idle_timeout = 600               # 10 minute server idle

# Logging and monitoring
log_connections = 1
log_disconnections = 1
stats_period = 60                       # Stats collection interval
```

## Maintenance Scripts and Automation

**Create maintenance scripts directory:**
```bash
mkdir -p /Users/drapala/WebstormProjects/validahub-alpha/db/maintenance
```

### Daily Maintenance Script
```sql
-- Daily maintenance function
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

## Performance Checklist

### Pre-Deployment Performance Validation
- [ ] All queries include tenant_id in WHERE clause
- [ ] Indexes follow tenant-first pattern
- [ ] JSONB queries use appropriate GIN indexes
- [ ] Materialized views have optimal refresh schedules  
- [ ] Partition pruning works for time-range queries
- [ ] Connection pooling configured correctly
- [ ] pg_stat_statements enabled for monitoring

### Production Performance Monitoring
- [ ] Query response time monitoring (< 100ms P95)
- [ ] Index usage analysis (monthly)
- [ ] Partition growth monitoring
- [ ] Cache hit ratio monitoring (> 95%)
- [ ] Connection pool utilization
- [ ] Materialized view refresh performance
- [ ] Storage growth rate analysis

**Expected Performance Improvements:**
- 60-80% faster dashboard queries with optimized indexes
- 90% reduction in full-table scans through partitioning
- 50% improvement in concurrent write throughput
- 95%+ cache hit ratio with proper memory configuration
- Sub-second materialized view refreshes for most views