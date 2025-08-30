# ADR-004: Foreign Key Constraints and Partition Management Strategy

## Status
Accepted

## Context
ValidaHub is a multi-tenant B2B SaaS platform that processes CSV files for marketplace integrations. The system follows Domain-Driven Design with hexagonal architecture and is designed to scale horizontally.

We need to decide:
1. Whether to use foreign key constraints for relationships between tables
2. How to manage time-series partitioned tables (e.g., `correction_logs`)

### Foreign Key Considerations:
- `tenant_id` references
- `created_by` and `updated_by` user references
- Cross-aggregate references in the domain model
- Partitioned table relationships

## Decision

### Foreign Key Strategy
We will **NOT use foreign key constraints** for cross-service or cross-aggregate references, but **WILL use them** for intra-aggregate relationships.

#### Specific Rules:

1. **No FKs for tenant_id**: Tenant information may reside in a separate service or database
2. **No FKs for user references**: User/auth service is external (JWT-based)
3. **No FKs between aggregates**: Maintains aggregate independence per DDD
4. **Use FKs within aggregates**: For example, between `rule_sets` and `rule_versions` tables
5. **No FKs to partitioned tables**: Foreign keys don't work well with partitioned tables in PostgreSQL

### Partition Management Strategy
We will use **automated partition management** with proactive creation and intelligent archival.

#### Implementation:

1. **Automated Creation**: Monthly partitions created 3 months in advance
2. **Automated Archival**: Move partitions to archive storage after 6 months
3. **Automated Deletion**: Drop archived partitions after 12 months
4. **Health Monitoring**: Daily checks with alerting for missing partitions
5. **Scheduling**: Use pg_cron or SystemD timers for automation

## Consequences

### Positive
- **Service Independence**: Allows microservices to evolve independently
- **Deployment Flexibility**: Services can be deployed/scaled separately
- **Performance**: No cross-database FK checks during high-volume operations
- **Testing**: Easier to test services in isolation
- **Migration Path**: Simpler to extract services later
- **Partition Performance**: Time-series queries remain fast as data grows
- **Automated Maintenance**: No manual intervention needed for partition lifecycle
- **Cost Optimization**: Old data automatically archived/removed

### Negative
- **Data Integrity**: Must enforce referential integrity at application layer
- **Orphaned Data**: Possibility of orphaned records requires cleanup jobs
- **Complexity**: Developers must understand and respect boundaries
- **Monitoring Required**: Partition health must be actively monitored
- **Recovery Complexity**: Partition failures need special handling

## Implementation

### Application-Level Integrity
```python
# Domain layer ensures validity
class RuleSet:
    def __init__(self, tenant_id: TenantId, ...):
        # Validate tenant exists via port
        if not self.tenant_repository.exists(tenant_id):
            raise TenantNotFoundError(tenant_id)
```

### Database-Level Protection
```sql
-- Use CHECK constraints for format validation
ALTER TABLE rule_sets ADD CONSTRAINT check_tenant_id_format 
    CHECK (tenant_id ~ '^t_[a-z0-9_]{1,47}$');

-- Use Row-Level Security for isolation
ALTER TABLE rule_sets ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON rule_sets
    FOR ALL USING (tenant_id = current_setting('app.tenant_id'));
```

### Cleanup Strategy
```sql
-- Daily maintenance removes orphaned records
DELETE FROM rule_sets 
WHERE NOT EXISTS (
    SELECT 1 FROM tenants t WHERE t.id = rule_sets.tenant_id
);
```

### Partition Management
```sql
-- Automated partition lifecycle (Migration 004)
SELECT maintain_partitions();  -- Creates, archives, and drops partitions

-- Health monitoring
SELECT * FROM check_partition_health();  -- Alerts on missing partitions

-- Manual commands via Makefile
make db.partitions.setup    # Initial setup
make db.partitions.check    # Health check
make db.partitions.maintain  # Manual maintenance
make db.partitions.status   # View all partitions
```

### Partition Configuration
```sql
-- Configuration stored in partition_management_config table
UPDATE partition_management_config 
SET retention_months = 12,      -- Total retention period
    archive_months = 6,         -- When to archive
    future_partitions = 3       -- Partitions to pre-create
WHERE table_name = 'correction_logs';
```

## Alternatives Considered

### Foreign Keys
1. **Full FK Constraints**: Rejected due to tight coupling
2. **Hybrid Approach**: Use FKs only for critical relationships - adds complexity
3. **Event-Driven Consistency**: Eventually consistent via events - chosen for cross-aggregate refs

### Partition Management
1. **pg_partman Extension**: More features but adds external dependency
2. **Manual Partitioning**: Rejected due to operational overhead
3. **Application-Level Partitioning**: Rejected - database-native is more efficient
4. **No Partitioning**: Would cause performance degradation at scale

## Migration Scripts
- `002_create_rule_sets_improved.py`: ENUMs, RLS, CHECK constraints
- `003_create_rule_versions.py`: Version integrity with unique partial indexes
- `003_create_correction_logs.py`: Initial partitioned table setup
- `004_create_partition_management.py`: Automated partition lifecycle

## References
- [DDD Aggregate Design](https://martinfowler.com/bliki/DDD_Aggregate.html)
- [Microservices Data Management](https://microservices.io/patterns/data/database-per-service.html)
- [PostgreSQL Partitioning Best Practices](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [pg_cron Documentation](https://github.com/citusdata/pg_cron)
- ValidaHub Architecture Decision Records: ADR-001 (Multi-tenancy), ADR-002 (Event Sourcing)

## Review
- **Author**: Sistema
- **Date**: 2025-01-30
- **Updated**: 2025-01-30 (Added partition management strategy)
- **Reviewers**: Pending