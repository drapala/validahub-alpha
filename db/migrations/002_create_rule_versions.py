"""Create rule_versions table with strict version integrity

Revision ID: 002_create_rule_versions
Revises: 001_create_rule_sets
Create Date: 2025-01-30 11:00:00.000000

This migration creates the rule_versions table with:
- Enforced single current version per rule set
- Version string integrity checks
- Comprehensive audit trail
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_create_rule_versions'
down_revision = '001_create_rule_sets'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create rule_versions table with version management and integrity.
    
    Principle: Immutable versioning with strict integrity constraints.
    """
    
    # Create ENUM for version status
    op.execute("CREATE TYPE version_status AS ENUM ('draft', 'testing', 'published', 'deprecated', 'archived')")
    
    # Create ENUM for version change type
    op.execute("CREATE TYPE version_change_type AS ENUM ('patch', 'minor', 'major')")
    
    # Create rule_versions table
    op.create_table(
        'rule_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False,
                  server_default=sa.text('gen_random_uuid()'),
                  comment='Unique identifier for rule version'),
        
        # Foreign key to rule_sets (intra-aggregate relationship)
        sa.Column('rule_set_id', postgresql.UUID(as_uuid=True), nullable=False,
                  comment='Reference to parent rule set'),
        
        # Multi-tenancy (denormalized for performance)
        sa.Column('tenant_id', sa.String(50), nullable=False, index=True,
                  comment='Denormalized tenant ID for partition efficiency'),
        
        # Version components
        sa.Column('major', sa.Integer, nullable=False,
                  comment='Major version (breaking changes)'),
        sa.Column('minor', sa.Integer, nullable=False,
                  comment='Minor version (new features)'),
        sa.Column('patch', sa.Integer, nullable=False,
                  comment='Patch version (bug fixes)'),
        sa.Column('version', sa.String(20), nullable=False,
                  comment='Full semantic version string (e.g., 1.2.3)'),
        sa.Column('prerelease', sa.String(50), nullable=True,
                  comment='Pre-release identifier (e.g., beta.1, rc.2)'),
        
        # Version metadata
        sa.Column('is_current', sa.Boolean, nullable=False, default=False,
                  comment='Whether this is the current active version'),
        sa.Column('is_latest', sa.Boolean, nullable=False, default=False,
                  comment='Whether this is the latest created version'),
        sa.Column('change_type', postgresql.ENUM('patch', 'minor', 'major',
                                                 name='version_change_type', create_type=False),
                  nullable=True,
                  comment='Type of change from previous version'),
        
        # Status and lifecycle
        sa.Column('status', postgresql.ENUM('draft', 'testing', 'published', 'deprecated', 'archived',
                                           name='version_status', create_type=False),
                  nullable=False, server_default='draft',
                  comment='Version lifecycle status'),
        
        # Rule content (immutable once published)
        sa.Column('mapping_yaml', sa.Text, nullable=False,
                  comment='YAML field mapping rules'),
        sa.Column('ruleset_yaml', sa.Text, nullable=False,
                  comment='YAML validation ruleset'),
        sa.Column('compiled_ir', postgresql.JSONB, nullable=True,
                  comment='Compiled intermediate representation for execution'),
        sa.Column('schema_hash', sa.String(64), nullable=False,
                  comment='SHA-256 hash of mapping + ruleset for integrity'),
        
        # Testing and validation
        sa.Column('test_coverage_percent', sa.Numeric(5, 2), nullable=True,
                  comment='Percentage of rules covered by tests'),
        sa.Column('validation_errors', postgresql.JSONB, nullable=True, server_default='[]',
                  comment='Array of validation errors found during testing'),
        sa.Column('performance_metrics', postgresql.JSONB, nullable=True, server_default='{}',
                  comment='Performance benchmarks for this version'),
        
        # Shadow deployment tracking
        sa.Column('shadow_start_date', sa.DATE, nullable=True,
                  comment='When shadow deployment started'),
        sa.Column('shadow_end_date', sa.DATE, nullable=True,
                  comment='When shadow deployment ended'),
        sa.Column('shadow_metrics', postgresql.JSONB, nullable=True, server_default='{}',
                  comment='Metrics collected during shadow period'),
        
        # Deployment and activation
        sa.Column('published_at', sa.TIMESTAMP(timezone=True), nullable=True,
                  comment='When version was published'),
        sa.Column('activated_at', sa.TIMESTAMP(timezone=True), nullable=True,
                  comment='When version became current'),
        sa.Column('deprecated_at', sa.TIMESTAMP(timezone=True), nullable=True,
                  comment='When version was deprecated'),
        sa.Column('archived_at', sa.TIMESTAMP(timezone=True), nullable=True,
                  comment='When version was archived'),
        
        # Change tracking
        sa.Column('changelog', sa.Text, nullable=True,
                  comment='Human-readable changelog for this version'),
        sa.Column('breaking_changes', postgresql.JSONB, nullable=True, server_default='[]',
                  comment='List of breaking changes if major version'),
        sa.Column('migration_guide', sa.Text, nullable=True,
                  comment='Migration guide from previous version'),
        
        # Audit fields
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('created_by', sa.String(100), nullable=False,
                  comment='User who created this version'),
        sa.Column('published_by', sa.String(100), nullable=True,
                  comment='User who published this version'),
        
        # Event sourcing
        sa.Column('aggregate_version', sa.Integer, nullable=False, default=1,
                  comment='Version of the aggregate for optimistic locking'),
        sa.Column('event_stream_position', sa.BigInteger, nullable=True,
                  comment='Position in event stream'),
        
        comment='Immutable rule version records with comprehensive versioning'
    )
    
    # Add foreign key constraint (intra-aggregate relationship is acceptable)
    op.create_foreign_key(
        'fk_rule_versions_rule_set',
        'rule_versions', 'rule_sets',
        ['rule_set_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # Critical CHECK constraints for data integrity
    
    # Ensure version string matches integer components
    op.create_check_constraint(
        'chk_version_format',
        'rule_versions',
        """
        version ~ '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9\.\-]+)?(\+[a-zA-Z0-9\.\-]+)?$'
        AND 
        CASE 
            WHEN prerelease IS NULL THEN version = (major || '.' || minor || '.' || patch)
            ELSE version = (major || '.' || minor || '.' || patch || '-' || prerelease)
        END
        """
    )
    
    # Ensure version components are non-negative
    op.create_check_constraint(
        'chk_version_components_positive',
        'rule_versions',
        'major >= 0 AND minor >= 0 AND patch >= 0'
    )
    
    # Ensure tenant_id format
    op.create_check_constraint(
        'chk_tenant_id_format',
        'rule_versions',
        "tenant_id ~ '^t_[a-z0-9_]{1,47}$'"
    )
    
    # Ensure schema_hash is valid SHA-256
    op.create_check_constraint(
        'chk_schema_hash_format',
        'rule_versions',
        "schema_hash ~ '^[a-f0-9]{64}$'"
    )
    
    # Ensure test coverage is valid percentage
    op.create_check_constraint(
        'chk_test_coverage_range',
        'rule_versions',
        'test_coverage_percent IS NULL OR (test_coverage_percent >= 0 AND test_coverage_percent <= 100)'
    )
    
    # Ensure status transitions are valid
    op.create_check_constraint(
        'chk_status_timestamps',
        'rule_versions',
        """
        (status != 'published' OR published_at IS NOT NULL) AND
        (status != 'deprecated' OR deprecated_at IS NOT NULL) AND
        (status != 'archived' OR archived_at IS NOT NULL)
        """
    )
    
    # Create indexes for performance
    
    # CRITICAL: Enforce single current version per rule set
    op.create_index(
        'idx_rule_versions_current_unique',
        'rule_versions',
        ['rule_set_id'],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
        comment='Enforce that only one version can be current per rule set'
    )
    
    # Enforce single latest version per rule set
    op.create_index(
        'idx_rule_versions_latest_unique',
        'rule_versions',
        ['rule_set_id'],
        unique=True,
        postgresql_where=sa.text("is_latest = true"),
        comment='Enforce that only one version can be latest per rule set'
    )
    
    # Composite index for tenant queries
    op.create_index(
        'idx_rule_versions_tenant_rule_set',
        'rule_versions',
        ['tenant_id', 'rule_set_id', 'major', 'minor', 'patch'],
        comment='Efficient version lookups by tenant and rule set'
    )
    
    # Index for version queries
    op.create_index(
        'idx_rule_versions_version',
        'rule_versions',
        ['rule_set_id', 'version'],
        unique=True,
        comment='Ensure unique versions per rule set'
    )
    
    # Partial index for published versions
    op.create_index(
        'idx_rule_versions_published',
        'rule_versions',
        ['tenant_id', 'rule_set_id', 'published_at'],
        postgresql_where=sa.text("status = 'published'"),
        comment='Fast lookup of published versions'
    )
    
    # Partial index for shadow deployments
    op.create_index(
        'idx_rule_versions_shadow',
        'rule_versions',
        ['tenant_id', 'shadow_start_date', 'shadow_end_date'],
        postgresql_where=sa.text("status = 'testing' AND shadow_start_date IS NOT NULL"),
        comment='Track active shadow deployments'
    )
    
    # GIN indexes for JSONB columns
    op.create_index(
        'idx_rule_versions_compiled_ir_gin',
        'rule_versions',
        ['compiled_ir'],
        postgresql_using='gin',
        comment='Efficient queries on compiled IR'
    )
    
    op.create_index(
        'idx_rule_versions_metrics_gin',
        'rule_versions',
        ['performance_metrics'],
        postgresql_using='gin',
        comment='Query performance metrics'
    )
    
    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_rule_versions_updated_at
        BEFORE UPDATE ON rule_versions
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)
    
    # Enable Row-Level Security
    op.execute("ALTER TABLE rule_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE rule_versions FORCE ROW LEVEL SECURITY FOR ALL ROLES")
    
    # Create RLS policies
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON rule_versions
        FOR ALL
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
    """)
    
    op.execute("""
        CREATE POLICY system_bypass_policy ON rule_versions
        FOR ALL
        TO validahub_system
        USING (true)
        WITH CHECK (true)
    """)
    
    # Add table comment
    op.execute("""
        COMMENT ON TABLE rule_versions IS 
        'Immutable version records with strict integrity constraints ensuring single current version per rule set'
    """)


def downgrade() -> None:
    """Drop rule_versions table and all related objects."""
    
    # Drop policies
    op.execute("DROP POLICY IF EXISTS system_bypass_policy ON rule_versions")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON rule_versions")
    
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS update_rule_versions_updated_at ON rule_versions")
    
    # Drop table
    op.drop_table('rule_versions')
    
    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS version_status")
    op.execute("DROP TYPE IF EXISTS version_change_type")