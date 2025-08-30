"""Create complete suggestions table with ML-powered correction recommendations

Revision ID: 005_create_suggestions_complete
Revises: 004_create_partition_management
Create Date: 2025-01-30 14:00:00.000000

This migration creates the complete suggestions table with all columns
referenced in the index creation script, including ML metadata and business impact tracking.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_create_suggestions_complete'
down_revision = '004_create_partition_management'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create suggestions table for ML-powered correction recommendations.
    
    Principle: Intelligent suggestions with comprehensive tracking for model improvement.
    """
    
    # Create ENUM for suggestion status
    op.execute("CREATE TYPE suggestion_status AS ENUM ('generated', 'reviewed', 'accepted', 'rejected', 'expired', 'applied')")
    
    # Create ENUM for suggestion source
    op.execute("CREATE TYPE suggestion_source AS ENUM ('ml_model', 'rule_engine', 'user_feedback', 'historical_pattern', 'external_api')")
    
    # Create ENUM for model types
    op.execute("CREATE TYPE ml_model_type AS ENUM ('transformer', 'random_forest', 'gradient_boost', 'neural_network', 'ensemble', 'rule_based')")
    
    # Create suggestions table
    op.create_table(
        'suggestions',
        # Primary identifiers
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False,
                  server_default=sa.text('gen_random_uuid()'),
                  comment='Unique identifier for suggestion'),
        sa.Column('tenant_id', sa.String(50), nullable=False, index=True,
                  comment='Tenant isolation key'),
        
        # Job and record context
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False,
                  comment='Related job ID for context'),
        sa.Column('record_number', sa.Integer, nullable=False,
                  comment='Specific record within the job'),
        sa.Column('field_name', sa.String(100), nullable=False,
                  comment='Field being suggested for correction'),
        sa.Column('rule_id', sa.String(100), nullable=True,
                  comment='Associated rule that triggered suggestion'),
        
        # Suggestion content
        sa.Column('original_value', postgresql.JSONB, nullable=False,
                  comment='Original value before correction'),
        sa.Column('suggested_value', postgresql.JSONB, nullable=False,
                  comment='Primary suggested correction'),
        sa.Column('alternative_suggestions', postgresql.JSONB, nullable=True, server_default='[]',
                  comment='Array of alternative suggestions with scores'),
        
        # ML Model metadata
        sa.Column('model_name', sa.String(100), nullable=False,
                  comment='Name/version of the ML model used'),
        sa.Column('model_type', postgresql.ENUM('transformer', 'random_forest', 'gradient_boost', 
                                                'neural_network', 'ensemble', 'rule_based',
                                                name='ml_model_type', create_type=False),
                  nullable=False,
                  comment='Type of ML model used'),
        sa.Column('model_version', sa.String(50), nullable=False,
                  comment='Specific version of the model'),
        sa.Column('confidence_score', sa.Numeric(5, 4), nullable=False,
                  sa.CheckConstraint('confidence_score >= 0 AND confidence_score <= 1'),
                  comment='Confidence score between 0 and 1'),
        
        # Algorithm and feature metadata
        sa.Column('algorithm_metadata', postgresql.JSONB, nullable=True, server_default='{}',
                  comment='Algorithm-specific metadata (hyperparameters, thresholds)'),
        sa.Column('context_features', postgresql.JSONB, nullable=True, server_default='{}',
                  comment='Features used for this prediction'),
        sa.Column('feature_importance', postgresql.JSONB, nullable=True, server_default='{}',
                  comment='Feature importance scores for explainability'),
        
        # Batch processing
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='Batch processing identifier for bulk operations'),
        sa.Column('batch_position', sa.Integer, nullable=True,
                  comment='Position within the batch'),
        
        # Status and lifecycle
        sa.Column('status', postgresql.ENUM('generated', 'reviewed', 'accepted', 'rejected', 
                                           'expired', 'applied',
                                           name='suggestion_status', create_type=False),
                  nullable=False, server_default='generated',
                  comment='Current status of the suggestion'),
        sa.Column('source', postgresql.ENUM('ml_model', 'rule_engine', 'user_feedback', 
                                           'historical_pattern', 'external_api',
                                           name='suggestion_source', create_type=False),
                  nullable=False,
                  comment='Source that generated this suggestion'),
        
        # Explanation and reasoning
        sa.Column('explanation', sa.Text, nullable=True,
                  comment='Human-readable explanation of the suggestion'),
        sa.Column('reasoning_path', postgresql.JSONB, nullable=True, server_default='[]',
                  comment='Step-by-step reasoning for audit trail'),
        
        # User interaction
        sa.Column('reviewed_at', sa.TIMESTAMP(timezone=True), nullable=True,
                  comment='When suggestion was reviewed'),
        sa.Column('reviewed_by', sa.String(100), nullable=True,
                  comment='User who reviewed the suggestion'),
        sa.Column('accepted_at', sa.TIMESTAMP(timezone=True), nullable=True,
                  comment='When suggestion was accepted'),
        sa.Column('accepted_by', sa.String(100), nullable=True,
                  comment='User who accepted the suggestion'),
        sa.Column('rejected_at', sa.TIMESTAMP(timezone=True), nullable=True,
                  comment='When suggestion was rejected'),
        sa.Column('rejected_by', sa.String(100), nullable=True,
                  comment='User who rejected the suggestion'),
        sa.Column('rejection_reason', sa.Text, nullable=True,
                  comment='Reason for rejection'),
        sa.Column('user_feedback', postgresql.JSONB, nullable=True, server_default='{}',
                  comment='Structured user feedback for model improvement'),
        
        # Performance metrics
        sa.Column('model_inference_time_ms', sa.Integer, nullable=True,
                  comment='Time taken for model inference in milliseconds'),
        sa.Column('total_processing_time_ms', sa.Integer, nullable=True,
                  comment='Total processing time including pre/post processing'),
        sa.Column('cache_hit', sa.Boolean, nullable=False, server_default='false',
                  comment='Whether this was served from cache'),
        
        # Business impact
        sa.Column('business_impact', postgresql.JSONB, nullable=True, server_default='{}',
                  comment='Estimated business impact (revenue, compliance score, etc.)'),
        sa.Column('priority_score', sa.Numeric(5, 2), nullable=True,
                  comment='Priority score for suggestion review'),
        sa.Column('compliance_flags', postgresql.JSONB, nullable=True, server_default='[]',
                  comment='Compliance issues this suggestion addresses'),
        
        # Expiration and validity
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True,
                  comment='When this suggestion expires'),
        sa.Column('valid_until', sa.TIMESTAMP(timezone=True), nullable=True,
                  comment='Suggestion validity period'),
        
        # Training feedback loop
        sa.Column('used_for_training', sa.Boolean, nullable=False, server_default='false',
                  comment='Whether this suggestion was used for model training'),
        sa.Column('training_weight', sa.Numeric(3, 2), nullable=True, server_default='1.0',
                  comment='Weight for training purposes'),
        sa.Column('training_batch_id', sa.String(100), nullable=True,
                  comment='Training batch identifier'),
        
        # Audit fields
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('correlation_id', sa.String(100), nullable=True,
                  comment='Correlation ID for distributed tracing'),
        sa.Column('request_id', sa.String(100), nullable=True,
                  comment='Original request ID'),
        
        comment='ML-powered suggestions for data corrections with comprehensive tracking'
    )
    
    # Add CHECK constraints
    op.create_check_constraint(
        'chk_suggestion_lifecycle',
        'suggestions',
        """
        (status = 'generated' AND accepted_at IS NULL AND rejected_at IS NULL) OR
        (status = 'accepted' AND accepted_at IS NOT NULL) OR
        (status = 'rejected' AND rejected_at IS NOT NULL) OR
        (status IN ('reviewed', 'expired', 'applied'))
        """
    )
    
    op.create_check_constraint(
        'chk_confidence_valid',
        'suggestions',
        'confidence_score >= 0 AND confidence_score <= 1'
    )
    
    op.create_check_constraint(
        'chk_priority_valid',
        'suggestions',
        'priority_score IS NULL OR (priority_score >= 0 AND priority_score <= 100)'
    )
    
    op.create_check_constraint(
        'chk_training_weight_valid',
        'suggestions',
        'training_weight IS NULL OR (training_weight >= 0 AND training_weight <= 1)'
    )
    
    # Create indexes matching the index creation script
    
    # Primary access pattern: tenant + job
    op.create_index(
        'idx_suggestions_tenant_job',
        'suggestions',
        ['tenant_id', 'job_id', 'record_number']
    )
    
    # Model performance analysis
    op.create_index(
        'idx_suggestions_model_performance',
        'suggestions',
        ['tenant_id', 'model_name', 'confidence_score', 'created_at']
    )
    
    # Batch processing
    op.create_index(
        'idx_suggestions_batch',
        'suggestions',
        ['tenant_id', 'batch_id', 'batch_position'],
        postgresql_where=sa.text("batch_id IS NOT NULL")
    )
    
    # High confidence suggestions for auto-apply
    op.create_index(
        'idx_suggestions_high_confidence',
        'suggestions',
        ['tenant_id', 'confidence_score', 'status'],
        postgresql_where=sa.text("confidence_score >= 0.95 AND status = 'generated'")
    )
    
    # Accepted suggestions for learning
    op.create_index(
        'idx_suggestions_accepted',
        'suggestions',
        ['tenant_id', 'accepted_at', 'model_name'],
        postgresql_where=sa.text("status = 'accepted'")
    )
    
    # Training feedback loop
    op.create_index(
        'idx_suggestions_training',
        'suggestions',
        ['training_batch_id', 'used_for_training'],
        postgresql_where=sa.text("used_for_training = true")
    )
    
    # GIN indexes for JSONB columns
    op.create_index(
        'idx_suggestions_algorithm_metadata_gin',
        'suggestions',
        ['algorithm_metadata'],
        postgresql_using='gin'
    )
    
    op.create_index(
        'idx_suggestions_context_features_gin',
        'suggestions',
        ['context_features'],
        postgresql_using='gin'
    )
    
    op.create_index(
        'idx_suggestions_alternatives_gin',
        'suggestions',
        ['alternative_suggestions'],
        postgresql_using='gin'
    )
    
    op.create_index(
        'idx_suggestions_business_impact_gin',
        'suggestions',
        ['business_impact'],
        postgresql_using='gin'
    )
    
    # Performance monitoring
    op.create_index(
        'idx_suggestions_slow_inference',
        'suggestions',
        ['model_name', 'model_inference_time_ms'],
        postgresql_where=sa.text("model_inference_time_ms > 100")
    )
    
    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_suggestions_updated_at
        BEFORE UPDATE ON suggestions
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)
    
    # Enable Row-Level Security
    op.execute("ALTER TABLE suggestions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE suggestions FORCE ROW LEVEL SECURITY FOR ALL ROLES")
    
    # Create RLS policies
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON suggestions
        FOR ALL
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
    """)
    
    op.execute("""
        CREATE POLICY system_bypass_policy ON suggestions
        FOR ALL
        TO validahub_system
        USING (true)
        WITH CHECK (true)
    """)
    
    # Add table comment
    op.execute("""
        COMMENT ON TABLE suggestions IS 
        'Complete ML-powered suggestion system with comprehensive tracking for model improvement and business impact analysis'
    """)


def downgrade() -> None:
    """Drop suggestions table and all related objects."""
    
    # Drop policies
    op.execute("DROP POLICY IF EXISTS system_bypass_policy ON suggestions")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON suggestions")
    
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS update_suggestions_updated_at ON suggestions")
    
    # Drop table
    op.drop_table('suggestions')
    
    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS suggestion_status")
    op.execute("DROP TYPE IF EXISTS suggestion_source")
    op.execute("DROP TYPE IF EXISTS ml_model_type")