# Database Performance Optimization Guide

**Principle**: Start with the correct minimum; defer enterprise-hardening until the pain justifies it.

This guide provides pragmatic PostgreSQL optimization strategies for ValidaHub's multi-tenant, high-volume correction logging system.

## Core Performance Philosophy

1. **Measure First**: Always use `EXPLAIN ANALYZE` before optimizing
2. **Index for Common Queries**: Optimize for the 95% of queries that run constantly
3. **Multitenancy is Non-Negotiable**: Every query must filter by `tenant_id`
4. **Partitioning When Painful**: Don't partition until tables exceed 100GB
5. **Materialized Views for Aggregations**: Pre-compute expensive analytics

## Query Performance Guidelines

### Essential Query Patterns

Every application query must follow these patterns for optimal performance:

```sql
-- ✅ GOOD: Tenant-scoped with proper indexing
SELECT * FROM correction_logs 
WHERE tenant_id = 't_acme_corp' 
  AND created_at >= NOW() - INTERVAL '7 days'
  AND status = 'pending'
ORDER BY created_at DESC 
LIMIT 100;

-- ❌ BAD: Missing tenant_id (will scan all data)
SELECT * FROM correction_logs 
WHERE status = 'pending'
ORDER BY created_at DESC;

-- ❌ BAD: Functions on indexed columns prevent index usage
SELECT * FROM correction_logs 
WHERE tenant_id = 't_acme_corp'
  AND DATE(created_at) = CURRENT_DATE;  -- Prevents index on created_at

-- ✅ GOOD: Range query uses index effectively
SELECT * FROM correction_logs 
WHERE tenant_id = 't_acme_corp'
  AND created_at >= CURRENT_DATE
  AND created_at < CURRENT_DATE + INTERVAL '1 day';
```

### Index Usage Analysis

Use these queries to verify index effectiveness:

```sql
-- Check index usage for tenant queries
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM correction_logs 
WHERE tenant_id = 't_acme_corp' 
  AND rule_id = 'price_validation'
  AND created_at >= NOW() - INTERVAL '30 days';

-- Look for these good indicators:
-- • Index Scan or Index Only Scan
-- • Low "Buffers: shared hit" numbers
-- • "Planning time" < 1ms, "Execution time" < 100ms

-- Check for unused indexes (candidates for removal)
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes 
WHERE idx_scan = 0 
  AND pg_relation_size(indexrelid) > 1024*1024  -- > 1MB
ORDER BY pg_relation_size(indexrelid) DESC;
```

## Index Strategy by Table

### rule_sets (Low volume, high read frequency)

**Primary Access Patterns:**
- Get active rule set for tenant + channel
- List all rule sets for tenant
- Search by metadata attributes

**Recommended Indexes:**
```sql
-- Already created in migration
CREATE INDEX CONCURRENTLY idx_rule_sets_tenant_channel 
ON rule_sets (tenant_id, channel);

CREATE INDEX CONCURRENTLY idx_rule_sets_tenant_status 
ON rule_sets (tenant_id, status) 
WHERE is_active = true;

-- GIN index for metadata queries
CREATE INDEX CONCURRENTLY idx_rule_sets_metadata_gin 
ON rule_sets USING gin (metadata);
```

**Performance Targets:**
- SELECT by tenant_id + channel: < 1ms
- Metadata queries: < 10ms
- Full tenant list: < 5ms

### rule_versions (Medium volume, version-heavy queries)

**Primary Access Patterns:**
- Get current version for rule set
- Version history queries
- Semantic version range queries

**Recommended Indexes:**
```sql
-- Unique constraint for version lookups
CREATE UNIQUE INDEX CONCURRENTLY idx_rule_versions_tenant_set_version 
ON rule_versions (tenant_id, rule_set_id, version);

-- Current version quick access
CREATE INDEX CONCURRENTLY idx_rule_versions_current 
ON rule_versions (tenant_id, rule_set_id, is_current) 
WHERE is_current = true;

-- Semantic version ordering
CREATE INDEX CONCURRENTLY idx_rule_versions_semantic 
ON rule_versions (tenant_id, rule_set_id, major, minor, patch);

-- Published versions (most common query)
CREATE INDEX CONCURRENTLY idx_rule_versions_published 
ON rule_versions (tenant_id, status, published_at) 
WHERE status = 'published';
```

**Performance Targets:**
- Current version lookup: < 1ms
- Version history: < 10ms
- Semantic version range: < 20ms

### correction_logs (High volume, time-series pattern)

**Primary Access Patterns:**
- Recent corrections for tenant + job
- Correction patterns by rule
- Batch operation tracking
- Time-range analytics

**Partitioning Strategy:**
```sql
-- Monthly partitions for optimal performance
-- Each partition ~10GB for 1M+ corrections/month
PARTITION BY RANGE (created_at);

-- Automatic partition creation via maintenance scripts
```

**Recommended Indexes per Partition:**
```sql
-- Primary tenant + time queries
CREATE INDEX idx_correction_logs_tenant_created 
ON correction_logs (tenant_id, created_at DESC);

-- Job-specific lookups
CREATE INDEX idx_correction_logs_job_record 
ON correction_logs (tenant_id, job_id, record_number);

-- Rule effectiveness analysis
CREATE INDEX idx_correction_logs_rule_analysis 
ON correction_logs (tenant_id, rule_id, correction_method, status, created_at);

-- Batch operations
CREATE INDEX idx_correction_logs_batch 
ON correction_logs (tenant_id, correction_batch_id, status);

-- Pending corrections (operational queries)
CREATE INDEX idx_correction_logs_pending 
ON correction_logs (tenant_id, created_at, field_name) 
WHERE status = 'pending';

-- JSONB indexes for flexible queries
CREATE INDEX idx_correction_logs_metadata_gin 
ON correction_logs USING gin (correction_metadata);
```

**Performance Targets:**
- Tenant + time range (7 days): < 50ms
- Job corrections lookup: < 20ms
- Rule effectiveness query: < 100ms
- Batch status check: < 10ms

### suggestions (High volume, ML-heavy queries)

**Primary Access Patterns:**
- High-confidence suggestions for auto-acceptance
- Model performance analysis
- User feedback tracking

**Recommended Indexes:**
```sql
-- High-confidence auto-acceptance candidates
CREATE INDEX idx_suggestions_high_confidence 
ON suggestions (tenant_id, confidence_score, status) 
WHERE confidence_score >= 0.9 AND status = 'pending';

-- Model performance tracking
CREATE INDEX idx_suggestions_model_performance 
ON suggestions (model_name, model_version, status, created_at);

-- User feedback analysis
CREATE INDEX idx_suggestions_feedback 
ON suggestions (tenant_id, status, accepted_at) 
WHERE status IN ('accepted', 'rejected');

-- JSONB queries for ML metadata
CREATE INDEX idx_suggestions_context_gin 
ON suggestions USING gin (context_features);
```

## Performance Thresholds and Actions

### Query Performance SLOs

| Query Type | Target Latency | Action Threshold | Remediation |
|------------|----------------|------------------|-------------|
| Primary key lookup | < 1ms | > 5ms | Check connection pooling, add covering index |
| Tenant + time range | < 50ms | > 200ms | Partition table, optimize index |
| Analytics queries | < 500ms | > 2s | Use materialized views, add aggregation indexes |
| JSONB queries | < 100ms | > 500ms | Optimize GIN indexes, limit result sets |
| Batch operations | < 1s | > 10s | Parallel processing, batch size tuning |

### Database Size Thresholds

| Metric | Green | Yellow | Red | Action Required |
|--------|--------|---------|-----|-----------------|
| Table size | < 10GB | 10-100GB | > 100GB | Consider partitioning |
| Index size | < 2GB | 2-20GB | > 20GB | Analyze index usage, rebuild bloated |
| Dead tuple ratio | < 5% | 5-20% | > 20% | Aggressive VACUUM, tune autovacuum |
| Index bloat | < 30% | 30-50% | > 50% | REINDEX CONCURRENTLY |
| Connection count | < 100 | 100-500 | > 500 | Connection pooling, query optimization |

## Connection Pooling Configuration

### PgBouncer Settings (Recommended)

```ini
[databases]
validahub = host=localhost port=5432 dbname=validahub

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
max_db_connections = 100
max_user_connections = 100

# For tenant isolation
auth_type = trust  # Use application-level auth with RLS
auth_file = /etc/pgbouncer/userlist.txt

# Performance tuning
server_reset_query = SELECT set_tenant_context('')
server_check_query = SELECT 1
server_check_delay = 30
```

### Application Connection Pool

```python
# Example SQLAlchemy configuration
DATABASE_URL = "postgresql://user:pass@pgbouncer:6432/validahub"

engine = create_engine(
    DATABASE_URL,
    pool_size=20,          # Base connections
    max_overflow=30,       # Burst capacity
    pool_pre_ping=True,    # Verify connections
    pool_recycle=3600,     # Recycle hourly
    connect_args={
        "connect_timeout": 5,
        "application_name": "validahub-api",
        "options": "-c statement_timeout=30000"  # 30s timeout
    }
)
```

## Monitoring and Alerting

### Key Metrics to Track

```sql
-- Query performance monitoring
SELECT 
    query_id,
    query,
    calls,
    total_time / calls as avg_time_ms,
    rows / calls as avg_rows,
    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) as hit_percent
FROM pg_stat_statements 
WHERE query LIKE '%correction_logs%' 
  AND calls > 100
ORDER BY total_time DESC 
LIMIT 10;

-- Index usage efficiency
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    idx_tup_read / GREATEST(idx_scan, 1) as tuples_per_scan
FROM pg_stat_user_indexes 
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- Lock contention monitoring
SELECT 
    COUNT(*) as blocked_queries,
    mode,
    locktype,
    relation::regclass as table_name
FROM pg_locks 
WHERE NOT granted 
GROUP BY mode, locktype, relation
ORDER BY blocked_queries DESC;
```

### Automated Alert Thresholds

1. **Query Time > 2s**: Investigate immediately
2. **Connection Count > 80% of max**: Scale horizontally
3. **Dead Tuple Ratio > 15%**: Tune autovacuum
4. **Lock Waits > 30s**: Check for blocking transactions
5. **Partition Size > 50GB**: Create additional partitions

## Disaster Recovery Considerations

### Backup Strategy

```bash
# Daily full backup with compression
pg_dump --host=localhost --port=5432 --username=validahub \
        --format=custom --compress=9 --no-password \
        --file="validahub_$(date +%Y%m%d).backup" validahub

# Continuous WAL archiving for point-in-time recovery
archive_command = 'cp %p /backup/wal/%f'
wal_level = replica
max_wal_senders = 3
```

### Read Replica Configuration

```sql
-- For analytics queries to reduce load on primary
CREATE PUBLICATION validahub_pub FOR ALL TABLES;

-- On replica
CREATE SUBSCRIPTION validahub_sub 
CONNECTION 'host=primary-db port=5432 dbname=validahub user=replication' 
PUBLICATION validahub_pub;
```

## Common Performance Anti-Patterns to Avoid

### ❌ Avoid These Patterns

```sql
-- 1. Missing tenant_id filter
SELECT * FROM correction_logs WHERE status = 'pending';

-- 2. Function calls preventing index usage  
SELECT * FROM correction_logs 
WHERE EXTRACT(month FROM created_at) = 12;

-- 3. Leading wildcards in LIKE queries
SELECT * FROM rule_sets WHERE name LIKE '%validation%';

-- 4. Unnecessary JOINs for data that could be denormalized
SELECT cl.*, rv.version, rs.name 
FROM correction_logs cl
JOIN rule_versions rv ON cl.rule_version_id = rv.id  
JOIN rule_sets rs ON rv.rule_set_id = rs.id
WHERE cl.tenant_id = 't_acme'  -- Should denormalize rule info

-- 5. N+1 queries in application code
-- Instead of querying each correction individually:
for correction_id in correction_ids:
    get_correction_details(correction_id)  # N queries
    
-- Batch the query:
SELECT * FROM correction_logs 
WHERE id = ANY($1) AND tenant_id = $2  -- 1 query
```

### ✅ Optimized Alternatives

```sql
-- 1. Always include tenant_id
SELECT * FROM correction_logs 
WHERE tenant_id = 't_acme' AND status = 'pending';

-- 2. Use range queries instead of functions
SELECT * FROM correction_logs 
WHERE created_at >= '2024-12-01' AND created_at < '2025-01-01';

-- 3. Use full-text search for text queries
CREATE INDEX idx_rule_sets_name_fts 
ON rule_sets USING gin (to_tsvector('english', name));

SELECT * FROM rule_sets 
WHERE to_tsvector('english', name) @@ plainto_tsquery('validation');

-- 4. Denormalize frequently-accessed data
ALTER TABLE correction_logs 
ADD COLUMN rule_version TEXT,
ADD COLUMN rule_set_name TEXT;

-- Update via triggers or application logic
-- No JOINs needed for most queries
```

## Performance Testing Strategy

### Synthetic Load Testing

```python
# Example load test for correction logging
import asyncio
import asyncpg
import time
from concurrent.futures import ThreadPoolExecutor

async def insert_corrections(tenant_id, batch_size=1000):
    conn = await asyncpg.connect("postgresql://...")
    
    # Set tenant context
    await conn.execute("SELECT set_tenant_context($1)", tenant_id)
    
    start_time = time.time()
    
    # Batch insert for performance
    corrections = [
        (tenant_id, f"job_{i}", f"rule_{i%100}", "pending", 
         {"confidence": 0.85}, {"value": f"correction_{i}"})
        for i in range(batch_size)
    ]
    
    await conn.executemany("""
        INSERT INTO correction_logs 
        (tenant_id, job_id, rule_id, status, correction_metadata, corrected_value)
        VALUES ($1, $2, $3, $4, $5, $6)
    """, corrections)
    
    elapsed = time.time() - start_time
    print(f"Inserted {batch_size} corrections in {elapsed:.2f}s")
    
    await conn.close()

# Run concurrent load test
async def load_test():
    tasks = []
    for i in range(10):  # 10 concurrent connections
        tasks.append(insert_corrections(f"t_tenant_{i}"))
    
    await asyncio.gather(*tasks)
```

### Performance Regression Testing

```bash
# Before major changes, establish baseline
pgbench -i -s 10 validahub  # Initialize test data
pgbench -c 10 -j 2 -T 60 validahub  # 10 clients, 2 threads, 60 seconds

# Custom test script for ValidaHub queries
cat > correction_queries.sql << EOF
\set tenant_id 't_tenant_' || (random() * 100)::int
\set rule_id 'rule_' || (random() * 1000)::int

SELECT set_tenant_context(:'tenant_id');
SELECT COUNT(*) FROM correction_logs 
WHERE tenant_id = :'tenant_id' 
  AND rule_id = :'rule_id'
  AND created_at >= NOW() - INTERVAL '7 days';
EOF

pgbench -f correction_queries.sql -c 20 -j 4 -T 300 validahub
```

This performance guide provides a foundation for maintaining optimal database performance as ValidaHub scales. Remember: **measure first, optimize based on actual bottlenecks, and always maintain the tenant isolation guarantee**.