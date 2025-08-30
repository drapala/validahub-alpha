"""Create rule_sets table with enhanced type safety and security

Revision ID: 001_create_rule_sets
Revises: None
Create Date: 2025-01-30 10:00:00.000000

Initial migration creating rule_sets table with:
- PostgreSQL ENUM for status field
- Row-Level Security setup
- CHECK constraints for data integrity
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_create_rule_sets'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create rule_sets table with enhanced type safety and security.
    
    Principle: Defense in depth - multiple layers of data integrity and security.
    """
    
    # Create ENUM type for rule set status
    op.execute("CREATE TYPE rule_set_status AS ENUM ('draft', 'published', 'deprecated', 'archived')")
    
    # Create ENUM type for marketplace channels (extensible list)
    op.execute("""
        CREATE TYPE marketplace_channel AS ENUM (
            'mercado_livre',
            'mercado_livre_classic',
            'mercado_livre_premium',
            'magalu',
            'amazon_br',
            'amazon_mx',
            'shopee',
            'b2w',
            'via_varejo',
            'carrefour',
            'custom'
        )
    """)
    
    # Create rule_sets table with comprehensive metadata
    op.create_table(
        'rule_sets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False,
                  server_default=sa.text('gen_random_uuid()'),
                  comment='Unique identifier for rule set'),
        
        # Multi-tenancy foundation
        sa.Column('tenant_id', sa.String(50), nullable=False, index=True,
                  comment='Tenant isolation key (pattern: t_[a-z0-9_]{1,47})'),
        
        # Core business fields with type safety
        sa.Column('channel', postgresql.ENUM('mercado_livre', 'mercado_livre_classic', 'mercado_livre_premium',
                                             'magalu', 'amazon_br', 'amazon_mx', 'shopee', 'b2w',
                                             'via_varejo', 'carrefour', 'custom',
                                             name='marketplace_channel', create_type=False),
                  nullable=False,
                  comment='Marketplace channel with enforced values'),
        
        sa.Column('name', sa.String(100), nullable=False,
                  comment='Human-readable rule set name'),
        sa.Column('description', sa.Text, nullable=True,
                  comment='Optional detailed description'),
        sa.Column('current_version', sa.String(20), nullable=True,
                  comment='Current semantic version (e.g., 1.2.3)'),
        
        # Status and lifecycle with ENUM
        sa.Column('status', postgresql.ENUM('draft', 'published', 'deprecated', 'archived',
                                           name='rule_set_status', create_type=False),
                  nullable=False, server_default='draft',
                  comment='Lifecycle status with database-enforced values'),
        
        sa.Column('is_active', sa.Boolean, nullable=False, default=True,
                  comment='Whether rule set is active'),
        sa.Column('auto_apply_patches', sa.Boolean, nullable=False, default=True,
                  comment='Auto-apply patch version updates'),
        sa.Column('shadow_period_days', sa.Integer, nullable=False, default=7,
                  comment='Days to test minor versions before activation'),
        
        # Metadata as JSONB for flexibility
        sa.Column('metadata', postgresql.JSONB, nullable=False, server_default='{}',
                  comment='Flexible metadata including tags, configuration'),
        
        # Audit fields following ValidaHub patterns
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('created_by', sa.String(100), nullable=False,
                  comment='User who created the rule set'),
        sa.Column('updated_by', sa.String(100), nullable=False,
                  comment='User who last updated the rule set'),
        
        # Event sourcing support
        sa.Column('version', sa.Integer, nullable=False, default=1,
                  comment='Aggregate version for optimistic locking'),
        sa.Column('event_stream_position', sa.BigInteger, nullable=True,
                  comment='Position in event stream for replay'),
        
        comment='Rule sets aggregate root - manages validation rules for marketplace channels'
    )
    
    # Add CHECK constraints for data integrity
    op.create_check_constraint(
        'check_tenant_id_format',
        'rule_sets',
        "tenant_id ~ '^t_[a-z0-9_]{1,47}$'"
    )
    
    op.create_check_constraint(
        'check_version_format',
        'rule_sets',
        "current_version IS NULL OR current_version ~ '^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$'"
    )
    
    op.create_check_constraint(
        'check_shadow_period_range',
        'rule_sets',
        'shadow_period_days BETWEEN 0 AND 30'
    )
    
    op.create_check_constraint(
        'check_version_positive',
        'rule_sets',
        'version > 0'
    )
    
    # Create essential indexes for multi-tenant performance
    op.create_index(
        'idx_rule_sets_tenant_channel',
        'rule_sets',
        ['tenant_id', 'channel'],
        unique=False,  # Changed from unique to allow multiple rule sets per channel
        comment='Query rule sets by tenant and channel'
    )
    
    op.create_index(
        'idx_rule_sets_tenant_status',
        'rule_sets',
        ['tenant_id', 'status'],
        comment='Query rule sets by tenant and status'
    )
    
    # GIN index on JSONB metadata for flexible queries
    op.create_index(
        'idx_rule_sets_metadata_gin',
        'rule_sets',
        ['metadata'],
        postgresql_using='gin',
        comment='Enable efficient queries on metadata fields'
    )
    
    # Partial indexes for common query patterns
    op.create_index(
        'idx_rule_sets_active',
        'rule_sets',
        ['tenant_id', 'channel', 'updated_at'],
        postgresql_where=sa.text("is_active = true AND status != 'archived'"),
        comment='Optimized index for active, non-archived rule sets'
    )
    
    op.create_index(
        'idx_rule_sets_published',
        'rule_sets',
        ['tenant_id', 'channel', 'current_version'],
        postgresql_where=sa.text("status = 'published'"),
        comment='Fast lookup of published rule sets'
    )
    
    # Create updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    # Attach trigger to rule_sets table
    op.execute("""
        CREATE TRIGGER update_rule_sets_updated_at
        BEFORE UPDATE ON rule_sets
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)
    
    # Enable Row-Level Security for multi-tenant isolation
    op.execute("ALTER TABLE rule_sets ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE rule_sets FORCE ROW LEVEL SECURITY FOR ALL ROLES")
    
    # Create RLS policy for tenant isolation
    # Note: In production, you'd create separate policies for different roles
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON rule_sets
        FOR ALL
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
    """)
    
    # Create a bypass policy for system maintenance
    op.execute("""
        CREATE POLICY system_bypass_policy ON rule_sets
        FOR ALL
        TO validahub_system
        USING (true)
        WITH CHECK (true)
    """)
    
    # Add comments for documentation
    op.execute("COMMENT ON TABLE rule_sets IS 'Multi-tenant rule sets with versioning, status management, and event sourcing support'")
    op.execute("COMMENT ON POLICY tenant_isolation_policy ON rule_sets IS 'Ensures complete data isolation between tenants'")
    op.execute("COMMENT ON POLICY system_bypass_policy ON rule_sets IS 'Allows system maintenance operations to bypass RLS'")


def downgrade() -> None:
    """Drop rule_sets table and all related objects."""
    
    # Drop policies first (must be done before dropping table)
    op.execute("DROP POLICY IF EXISTS system_bypass_policy ON rule_sets")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON rule_sets")
    
    # Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS update_rule_sets_updated_at ON rule_sets")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    
    # Drop table (indexes and constraints are dropped automatically)
    op.drop_table('rule_sets')
    
    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS rule_set_status")
    op.execute("DROP TYPE IF EXISTS marketplace_channel")