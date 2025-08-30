# ADR-005: Index Strategy and Configuration Management

## Status
Accepted

## Context
ValidaHub is a read-heavy analytical system processing high volumes of CSV corrections with multi-tenant isolation. We need a comprehensive indexing strategy that balances read performance with write overhead while maintaining flexibility for threshold adjustments.

### Key Challenges:
1. Multi-tenant data isolation requiring tenant_id in every query
2. High-volume time-series data in correction_logs
3. Complex JSONB queries for metadata and ML features
4. Balance between read optimization and write performance
5. Hardcoded thresholds in partial indexes

## Decision

### Index Creation Strategy

#### 1. **Separation of Concerns**
- **Migrations**: Create tables, constraints, and critical indexes only
- **Index Script**: Comprehensive performance optimization indexes
- **Rationale**: Clean separation between schema definition and performance tuning

#### 2. **Index Design Principles**
```sql
-- Every index starts with tenant_id for isolation
CREATE INDEX idx_name ON table (tenant_id, other_columns);

-- Use CONCURRENTLY to avoid blocking
CREATE INDEX CONCURRENTLY idx_name ON table (...);

-- Partial indexes for filtered queries
CREATE INDEX idx_name ON table (...) WHERE condition;

-- GIN for JSONB columns
CREATE INDEX idx_name ON table USING gin (jsonb_column);
```

#### 3. **Configuration Management**
Create a configuration table for dynamic thresholds:

```sql
CREATE TABLE index_thresholds (
    id SERIAL PRIMARY KEY,
    index_name VARCHAR(100) UNIQUE NOT NULL,
    threshold_name VARCHAR(100) NOT NULL,
    threshold_value NUMERIC NOT NULL,
    threshold_unit VARCHAR(50),
    description TEXT,
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by VARCHAR(100)
);

-- Example entries
INSERT INTO index_thresholds VALUES
('idx_suggestions_high_confidence', 'min_confidence', 0.95, 'score', 'Auto-apply threshold'),
('idx_ml_metrics_slow', 'max_inference_ms', 100, 'milliseconds', 'Slow model detection'),
('idx_corrections_high_impact', 'min_impact_score', 0.8, 'score', 'High business impact');
```

#### 4. **Dynamic Index Recreation**
Function to rebuild partial indexes with new thresholds:

```sql
CREATE OR REPLACE FUNCTION rebuild_threshold_index(
    p_index_name TEXT,
    p_threshold_value NUMERIC
) RETURNS VOID AS $$
DECLARE
    v_index_def TEXT;
BEGIN
    -- Get current index definition
    SELECT pg_get_indexdef(indexrelid) INTO v_index_def
    FROM pg_stat_user_indexes
    WHERE indexname = p_index_name;
    
    -- Drop old index
    EXECUTE FORMAT('DROP INDEX CONCURRENTLY IF EXISTS %I', p_index_name);
    
    -- Create new index with updated threshold
    -- (Implementation specific to each index pattern)
    EXECUTE v_index_def; -- Simplified, needs threshold injection
END;
$$ LANGUAGE plpgsql;
```

### Index Lifecycle Management

#### 1. **Monitoring**
- Use `analyze_index_usage()` function weekly
- Track index bloat with `check_index_bloat()`
- Monitor slow queries via pg_stat_statements

#### 2. **Maintenance Windows**
- Create new indexes with CONCURRENTLY during business hours
- Drop unused indexes during maintenance windows
- Rebuild bloated indexes monthly

#### 3. **Write Performance Protection**
```sql
-- Monitor write performance impact
CREATE VIEW write_performance_metrics AS
SELECT 
    schemaname,
    tablename,
    n_tup_ins + n_tup_upd + n_tup_del as total_writes,
    (SELECT COUNT(*) FROM pg_indexes WHERE tablename = t.tablename) as index_count,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as table_size
FROM pg_stat_user_tables t
ORDER BY total_writes DESC;
```

## Consequences

### Positive
- **Performance**: Optimized read queries with sub-50ms response times
- **Flexibility**: Thresholds can be adjusted without code changes
- **Monitoring**: Comprehensive index usage tracking
- **Separation**: Clean separation between schema and performance tuning

### Negative
- **Complexity**: Two-phase deployment (migrations then indexes)
- **Write Overhead**: Many indexes increase write latency
- **Maintenance**: Requires active monitoring and tuning
- **Storage**: Indexes can consume significant disk space

## Implementation

### Phase 1: Initial Deployment
```bash
# Run migrations to create tables
alembic upgrade head

# Run comprehensive index creation
psql -f db/scripts/create_indexes.sql

# Load initial thresholds
psql -f db/scripts/load_index_thresholds.sql
```

### Phase 2: Monitoring Setup
```bash
# Schedule weekly analysis
SELECT cron.schedule('analyze-indexes', '0 2 * * 0', 
    'SELECT analyze_index_usage()');

# Schedule daily threshold checks
SELECT cron.schedule('check-thresholds', '0 3 * * *',
    'SELECT verify_threshold_effectiveness()');
```

### Phase 3: Optimization Loop
1. Collect metrics for 1 week
2. Identify unused indexes via `analyze_index_usage()`
3. Identify slow queries needing new indexes
4. Adjust thresholds based on actual data distribution
5. Rebuild affected partial indexes
6. Repeat monthly

## Alternatives Considered

1. **All Indexes in Migrations**: Rejected - mixes concerns, harder to optimize
2. **Application-Level Indexing**: Rejected - database-native is more efficient
3. **Fixed Thresholds**: Rejected - lacks flexibility for changing requirements
4. **Index Advisor Tools**: Considered - can supplement but not replace strategy

## Migration Path

### From Current State:
1. Migration `005_create_suggestions_complete.py` includes all columns
2. Remove index creation from future migrations
3. Consolidate all performance indexes in `create_indexes.sql`
4. Implement threshold configuration table
5. Convert hardcoded thresholds to configuration-driven

## References
- [PostgreSQL Index Types](https://www.postgresql.org/docs/current/indexes-types.html)
- [Index Design Best Practices](https://www.postgresql.org/docs/current/indexes-design.html)
- [Multi-Tenant Index Strategies](https://www.citusdata.com/blog/2016/10/03/designing-your-saas-database-for-high-scalability/)
- ValidaHub ADRs: ADR-004 (Foreign Keys & Partitions)

## Review
- **Author**: Sistema
- **Date**: 2025-01-30
- **Reviewers**: Pending