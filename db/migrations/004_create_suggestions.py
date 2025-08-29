"""Create suggestions table for ML-driven rule and correction improvements

Revision ID: 004_create_suggestions
Revises: 003_create_correction_logs
Create Date: 2025-01-15 10:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_create_suggestions'
down_revision = '003_create_correction_logs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create suggestions table for ML-driven improvements to rules and corrections.
    
    Principle: Capture ML insights and user feedback to continuously improve validation quality.
    Store both rule suggestions (new rules) and correction suggestions (better corrections).
    """
    
    # Create suggestions table
    op.create_table(
        'suggestions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=False, index=True, comment='Tenant isolation'),
        
        # Suggestion type and context
        sa.Column('suggestion_type', sa.String(50), nullable=False, comment='rule_improvement, new_rule, correction_strategy, field_validation'),
        sa.Column('suggestion_category', sa.String(50), nullable=False, comment='accuracy, performance, coverage, user_experience'),
        sa.Column('target_entity_type', sa.String(50), nullable=False, comment='rule_set, rule_version, correction_log, field'),
        sa.Column('target_entity_id', postgresql.UUID(as_uuid=True), nullable=True, comment='ID of the entity being improved'),
        
        # Context information
        sa.Column('field_name', sa.String(100), nullable=True, comment='Specific field this suggestion applies to'),
        sa.Column('channel', sa.String(50), nullable=True, comment='Marketplace channel context'),
        sa.Column('rule_id', sa.String(100), nullable=True, comment='Specific rule this suggestion improves'),
        
        # ML-generated suggestion content
        sa.Column('title', sa.String(200), nullable=False, comment='Human-readable suggestion title'),
        sa.Column('description', sa.Text, nullable=False, comment='Detailed description of the suggestion'),
        sa.Column('suggested_implementation', postgresql.JSONB, nullable=False, comment='Machine-readable implementation details'),
        
        # Confidence and impact scoring
        sa.Column('confidence_score', sa.Numeric(4, 3), nullable=False, comment='ML confidence (0.000-1.000)'),
        sa.Column('impact_score', sa.Numeric(4, 3), nullable=False, comment='Estimated impact (0.000-1.000)'),
        sa.Column('priority_score', sa.Numeric(4, 3), nullable=False, comment='Combined priority (0.000-1.000)'),
        
        # Evidence and supporting data
        sa.Column('evidence_data', postgresql.JSONB, nullable=False, default={}, comment='Data patterns and statistics supporting the suggestion'),
        sa.Column('sample_violations', postgresql.JSONB, nullable=True, default=[], comment='Sample data violations that would be caught'),
        sa.Column('performance_impact', postgresql.JSONB, nullable=True, default={}, comment='Expected performance impact of implementing'),
        
        # Business impact estimation
        sa.Column('estimated_error_reduction', sa.Numeric(5, 2), nullable=True, comment='Expected % reduction in errors'),
        sa.Column('estimated_efficiency_gain', sa.Numeric(5, 2), nullable=True, comment='Expected % efficiency improvement'),
        sa.Column('affected_record_count', sa.Integer, nullable=True, comment='Number of historical records that would be affected'),
        
        # Status and workflow
        sa.Column('status', sa.String(20), nullable=False, default='generated', comment='generated, reviewed, approved, implemented, rejected'),
        sa.Column('implementation_status', sa.String(20), nullable=True, comment='pending, in_progress, completed, failed'),
        
        # Review and approval workflow
        sa.Column('reviewed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('reviewed_by', sa.String(100), nullable=True),
        sa.Column('review_notes', sa.Text, nullable=True),
        sa.Column('reviewer_rating', sa.Integer, nullable=True, comment='1-5 rating from reviewer'),
        
        sa.Column('approved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('approved_by', sa.String(100), nullable=True),
        sa.Column('rejection_reason', sa.Text, nullable=True),
        
        # Implementation tracking
        sa.Column('implemented_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('implemented_by', sa.String(100), nullable=True),
        sa.Column('implementation_notes', sa.Text, nullable=True),
        sa.Column('implementation_result', postgresql.JSONB, nullable=True, comment='Results and metrics after implementation'),
        
        # ML model metadata
        sa.Column('model_version', sa.String(20), nullable=False, comment='Version of ML model that generated suggestion'),
        sa.Column('training_data_version', sa.String(20), nullable=True, comment='Version of training data used'),
        sa.Column('generation_metadata', postgresql.JSONB, nullable=False, default={}, comment='Model parameters and generation context'),
        
        # Feedback loop for model improvement
        sa.Column('feedback_score', sa.Integer, nullable=True, comment='User feedback score (1-5)'),
        sa.Column('feedback_notes', sa.Text, nullable=True),
        sa.Column('outcome_measured', sa.Boolean, nullable=False, default=False, comment='Whether outcome was measured after implementation'),
        sa.Column('actual_impact', postgresql.JSONB, nullable=True, comment='Measured actual impact vs predicted'),
        
        # Audit fields
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='When suggestion becomes stale and should be regenerated'),
        
        comment='ML-generated suggestions for improving rules and corrections'
    )
    
    # Create indexes for efficient queries
    
    # Primary tenant-based queries with status filtering
    op.create_index(
        'idx_suggestions_tenant_status',
        'suggestions',
        ['tenant_id', 'status', 'priority_score'],
        comment='Query suggestions by tenant and status, ordered by priority'
    )
    
    # Index for high-priority pending suggestions (dashboard queries)
    op.create_index(
        'idx_suggestions_high_priority',
        'suggestions',
        ['tenant_id', 'created_at'],
        postgresql_where=sa.text("status IN ('generated', 'reviewed') AND priority_score >= 0.7"),
        comment='High-priority suggestions needing attention'
    )
    
    # Index for suggestion type and category analysis
    op.create_index(
        'idx_suggestions_type_category',
        'suggestions',
        ['tenant_id', 'suggestion_type', 'suggestion_category', 'confidence_score'],
        comment='Analyze suggestions by type and category'
    )
    
    # Index for field-specific suggestions
    op.create_index(
        'idx_suggestions_field',
        'suggestions',
        ['tenant_id', 'field_name', 'channel', 'status'],
        postgresql_where=sa.text("field_name IS NOT NULL"),
        comment='Field-specific improvement suggestions'
    )
    
    # Index for rule-specific suggestions
    op.create_index(
        'idx_suggestions_rule',
        'suggestions',
        ['tenant_id', 'rule_id', 'suggestion_type', 'status'],
        postgresql_where=sa.text("rule_id IS NOT NULL"),
        comment='Rule-specific improvement suggestions'
    )
    
    # Index for tracking implementation effectiveness
    op.create_index(
        'idx_suggestions_implementation_tracking',
        'suggestions',
        ['tenant_id', 'implemented_at', 'outcome_measured'],
        postgresql_where=sa.text("status = 'implemented'"),
        comment='Track implemented suggestions for effectiveness measurement'
    )
    
    # GIN indexes for JSONB queries
    op.create_index(
        'idx_suggestions_evidence_gin',
        'suggestions',
        ['evidence_data'],
        postgresql_using='gin',
        comment='Query evidence data patterns'
    )
    
    op.create_index(
        'idx_suggestions_implementation_gin',
        'suggestions',
        ['suggested_implementation'],
        postgresql_using='gin',
        comment='Query implementation details'
    )
    
    # Index for model performance analysis
    op.create_index(
        'idx_suggestions_model_version',
        'suggestions',
        ['model_version', 'confidence_score', 'feedback_score'],
        comment='Analyze model performance over time'
    )
    
    # Index for expiration cleanup
    op.create_index(
        'idx_suggestions_expires_at',
        'suggestions',
        ['expires_at'],
        postgresql_where=sa.text("expires_at IS NOT NULL AND status IN ('generated', 'reviewed')"),
        comment='Efficient cleanup of expired suggestions'
    )
    
    # Partial index for suggestions awaiting review
    op.create_index(
        'idx_suggestions_pending_review',
        'suggestions',
        ['tenant_id', 'priority_score', 'created_at'],
        postgresql_where=sa.text("status = 'generated' AND confidence_score >= 0.5"),
        comment='Suggestions with sufficient confidence awaiting review'
    )


def downgrade() -> None:
    """Drop suggestions table and all related indexes."""
    op.drop_table('suggestions')