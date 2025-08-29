"""Create rule_sets table with multi-tenancy and versioning

Revision ID: 001_create_rule_sets
Revises: 
Create Date: 2025-01-15 10:00:00.000000

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
    Create rule_sets table following ValidaHub patterns.
    
    Principle: Multi-tenancy is non-negotiable - tenant_id is the foundation of security and scale.
    All rules are scoped by tenant for complete isolation.
    """
    
    # Create rule_sets table with comprehensive metadata
    op.create_table(
        'rule_sets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False, index=True, comment='Tenant isolation key (pattern: t_[a-z0-9_]{1,47})'),
        sa.Column('channel', sa.String(50), nullable=False, comment='Marketplace channel (mercado_livre, magalu, etc.)'),
        sa.Column('name', sa.String(100), nullable=False, comment='Human-readable rule set name'),
        sa.Column('description', sa.Text, nullable=True, comment='Optional detailed description'),
        sa.Column('current_version', sa.String(20), nullable=True, comment='Current semantic version (e.g., 1.2.3)'),
        
        # Status and lifecycle
        sa.Column('status', sa.String(20), nullable=False, default='draft', comment='draft, published, deprecated'),
        sa.Column('is_active', sa.Boolean, nullable=False, default=True, comment='Whether rule set is active'),
        sa.Column('auto_apply_patches', sa.Boolean, nullable=False, default=True, comment='Auto-apply patch version updates'),
        sa.Column('shadow_period_days', sa.Integer, nullable=False, default=7, comment='Days to test minor versions before activation'),
        
        # Metadata as JSONB for flexibility
        sa.Column('metadata', postgresql.JSONB, nullable=True, default={}, comment='Flexible metadata including tags, configuration'),
        
        # Audit fields following ValidaHub patterns
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(100), nullable=False, comment='User who created the rule set'),
        sa.Column('updated_by', sa.String(100), nullable=False, comment='User who last updated the rule set'),
        
        # Event sourcing support
        sa.Column('version', sa.Integer, nullable=False, default=1, comment='Aggregate version for optimistic locking'),
        sa.Column('event_stream_position', sa.BigInteger, nullable=True, comment='Position in event stream for replay'),
        
        comment='Rule sets aggregate root - manages validation rules for marketplace channels'
    )
    
    # Create essential indexes for multi-tenant performance
    # Tenant isolation is critical - tenant_id must be in every query
    op.create_index(
        'idx_rule_sets_tenant_channel',
        'rule_sets', 
        ['tenant_id', 'channel'],
        unique=True,
        comment='Enforce one active rule set per tenant per channel'
    )
    
    op.create_index(
        'idx_rule_sets_tenant_status',
        'rule_sets',
        ['tenant_id', 'status'],
        comment='Query active rule sets by tenant'
    )
    
    # GIN index on JSONB metadata for flexible queries
    op.create_index(
        'idx_rule_sets_metadata_gin',
        'rule_sets',
        ['metadata'],
        postgresql_using='gin',
        comment='Enable efficient queries on metadata fields'
    )
    
    # Partial index for active rule sets only (common query pattern)
    op.create_index(
        'idx_rule_sets_active',
        'rule_sets',
        ['tenant_id', 'channel', 'updated_at'],
        postgresql_where=sa.text("is_active = true"),
        comment='Optimized index for active rule sets'
    )


def downgrade() -> None:
    """Drop rule_sets table and all related indexes."""
    op.drop_table('rule_sets')