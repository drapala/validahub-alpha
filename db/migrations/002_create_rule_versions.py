"""Create rule_versions table for semantic versioning and rule definitions

Revision ID: 002_create_rule_versions
Revises: 001_create_rule_sets
Create Date: 2025-01-15 10:15:00.000000

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
    Create rule_versions table with semantic versioning and JSONB rule definitions.
    
    Principle: Immutable published versions with flexible rule definitions stored as JSONB.
    Each version is a complete snapshot of rules for predictable behavior.
    """
    
    # Create rule_versions table
    op.create_table(
        'rule_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('rule_set_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Foreign key to rule_sets'),
        sa.Column('tenant_id', sa.String(50), nullable=False, index=True, comment='Tenant isolation - denormalized for performance'),
        
        # Semantic versioning
        sa.Column('version', sa.String(20), nullable=False, comment='Semantic version (major.minor.patch)'),
        sa.Column('major', sa.Integer, nullable=False, comment='Major version number (breaking changes)'),
        sa.Column('minor', sa.Integer, nullable=False, comment='Minor version number (backward compatible)'),
        sa.Column('patch', sa.Integer, nullable=False, comment='Patch version number (bug fixes)'),
        sa.Column('prerelease', sa.String(20), nullable=True, comment='Pre-release identifier (alpha, beta, rc)'),
        
        # Version status and lifecycle
        sa.Column('status', sa.String(20), nullable=False, default='draft', comment='draft, validated, published, deprecated'),
        sa.Column('is_current', sa.Boolean, nullable=False, default=False, comment='Whether this is the current active version'),
        sa.Column('checksum', sa.String(64), nullable=True, comment='SHA-256 checksum of rules for integrity verification'),
        
        # Rule definitions stored as JSONB for flexibility and performance
        sa.Column('rules', postgresql.JSONB, nullable=False, comment='Array of rule definitions with conditions and actions'),
        sa.Column('rule_count', sa.Integer, nullable=False, default=0, comment='Cached count of rules for quick access'),
        
        # Validation and compilation metadata
        sa.Column('validation_errors', postgresql.JSONB, nullable=True, default=[], comment='Validation errors if status is invalid'),
        sa.Column('compilation_metadata', postgresql.JSONB, nullable=True, default={}, comment='Metadata from rule compilation process'),
        sa.Column('performance_profile', postgresql.JSONB, nullable=True, default={}, comment='Performance metrics and optimization hints'),
        
        # Publishing and deprecation
        sa.Column('published_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='When version was published'),
        sa.Column('deprecated_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='When version was deprecated'),
        sa.Column('sunset_date', sa.TIMESTAMP(timezone=True), nullable=True, comment='When version will be removed'),
        sa.Column('deprecation_reason', sa.Text, nullable=True, comment='Reason for deprecation'),
        
        # Compatibility tracking
        sa.Column('compatibility_level', sa.String(20), nullable=True, comment='major, minor, patch - compatibility with previous version'),
        sa.Column('migration_notes', sa.Text, nullable=True, comment='Notes for migrating from previous versions'),
        sa.Column('breaking_changes', postgresql.JSONB, nullable=True, default=[], comment='List of breaking changes from previous version'),
        
        # Audit fields
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(100), nullable=False, comment='User who created the version'),
        sa.Column('published_by', sa.String(100), nullable=True, comment='User who published the version'),
        sa.Column('deprecated_by', sa.String(100), nullable=True, comment='User who deprecated the version'),
        
        # Event sourcing support
        sa.Column('version_number', sa.Integer, nullable=False, default=1, comment='Entity version for optimistic locking'),
        
        comment='Rule versions - immutable snapshots of rule definitions with semantic versioning'
    )
    
    # Foreign key constraint with proper cascading
    op.create_foreign_key(
        'fk_rule_versions_rule_set_id',
        'rule_versions', 'rule_sets',
        ['rule_set_id'], ['id'],
        ondelete='CASCADE',
        comment='Cascade delete when rule set is deleted'
    )
    
    # Essential indexes for multi-tenant queries and versioning
    # Composite index for tenant isolation and version queries
    op.create_index(
        'idx_rule_versions_tenant_set_version',
        'rule_versions',
        ['tenant_id', 'rule_set_id', 'version'],
        unique=True,
        comment='Enforce unique versions per rule set and enable efficient lookups'
    )
    
    # Index for finding current versions across tenants
    op.create_index(
        'idx_rule_versions_current',
        'rule_versions',
        ['tenant_id', 'rule_set_id', 'is_current'],
        postgresql_where=sa.text("is_current = true"),
        comment='Quick access to current versions'
    )
    
    # Index for version ordering and compatibility checks
    op.create_index(
        'idx_rule_versions_semantic',
        'rule_versions',
        ['tenant_id', 'rule_set_id', 'major', 'minor', 'patch'],
        comment='Enable semantic version ordering and range queries'
    )
    
    # Index for published versions (common query for active rules)
    op.create_index(
        'idx_rule_versions_published',
        'rule_versions',
        ['tenant_id', 'status', 'published_at'],
        postgresql_where=sa.text("status = 'published'"),
        comment='Efficient queries for published versions'
    )
    
    # GIN indexes on JSONB columns for rule queries
    op.create_index(
        'idx_rule_versions_rules_gin',
        'rule_versions',
        ['rules'],
        postgresql_using='gin',
        comment='Enable complex queries on rule definitions'
    )
    
    op.create_index(
        'idx_rule_versions_breaking_changes_gin',
        'rule_versions',
        ['breaking_changes'],
        postgresql_using='gin',
        comment='Query breaking changes for compatibility analysis'
    )
    
    # Partial index for active (non-deprecated) versions
    op.create_index(
        'idx_rule_versions_active',
        'rule_versions',
        ['tenant_id', 'rule_set_id', 'status', 'created_at'],
        postgresql_where=sa.text("deprecated_at IS NULL"),
        comment='Optimized queries for active versions'
    )


def downgrade() -> None:
    """Drop rule_versions table and all related indexes."""
    op.drop_table('rule_versions')