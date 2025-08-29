"""Create correction_logs partitioned table with JSONB optimization

Revision ID: 003_create_correction_logs
Revises: 002_create_rule_versions
Create Date: 2025-01-15 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_create_correction_logs'
down_revision = '002_create_rule_versions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create correction_logs partitioned table for high-volume correction tracking.
    
    Principle: Time-series partitioning for performance with JSONB for flexible correction data.
    Partitioned by month for optimal performance and easier archival.
    """
    
    # Create the main partitioned table
    op.execute("""
        CREATE TABLE correction_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id VARCHAR(50) NOT NULL,
            job_id UUID NOT NULL,
            rule_set_id UUID,
            rule_version_id UUID,
            
            -- Correction metadata
            correction_batch_id UUID NOT NULL DEFAULT gen_random_uuid(),
            record_number INTEGER NOT NULL,
            field_name VARCHAR(100) NOT NULL,
            rule_id VARCHAR(100) NOT NULL,
            
            -- Original and corrected values as JSONB for flexibility
            original_value JSONB,
            corrected_value JSONB,
            correction_type VARCHAR(50) NOT NULL DEFAULT 'value_replacement',
            
            -- Correction details and confidence
            correction_method VARCHAR(50) NOT NULL, -- 'manual', 'automatic', 'ml_suggestion', 'rule_based'
            confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
            correction_metadata JSONB DEFAULT '{}',
            
            -- Status and approval workflow
            status VARCHAR(20) NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'rejected', 'applied', 'reverted'
            applied_at TIMESTAMP WITH TIME ZONE,
            reverted_at TIMESTAMP WITH TIME ZONE,
            approved_by VARCHAR(100),
            rejected_by VARCHAR(100),
            rejection_reason TEXT,
            
            -- Business impact tracking
            estimated_impact JSONB DEFAULT '{}', -- revenue impact, compliance score, etc.
            actual_impact JSONB DEFAULT '{}', -- measured after applying correction
            
            -- Audit and correlation
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            created_by VARCHAR(100) NOT NULL,
            correlation_id VARCHAR(100),
            request_id VARCHAR(100),
            
            -- Performance optimization: include tenant_id and created_at in every query
            CONSTRAINT correction_logs_tenant_partition CHECK (tenant_id IS NOT NULL AND created_at IS NOT NULL)
        ) PARTITION BY RANGE (created_at);
    """)
    
    # Add table comment
    op.execute("COMMENT ON TABLE correction_logs IS 'Partitioned table for tracking all data corrections with full audit trail'")
    
    # Create initial partitions for current and next few months
    # This ensures zero-downtime deployment
    from datetime import datetime, date
    import calendar
    
    current_date = datetime.now()
    
    # Create partitions for current month and next 3 months
    for i in range(4):
        if i == 0:
            partition_date = current_date.replace(day=1)
        else:
            # Calculate next month
            if current_date.month == 12:
                next_year = current_date.year + 1
                next_month = 1
            else:
                next_year = current_date.year
                next_month = current_date.month + 1
            partition_date = date(next_year, next_month, 1)
            current_date = partition_date
        
        # Calculate partition bounds
        start_date = partition_date.strftime('%Y-%m-01')
        if partition_date.month == 12:
            end_date = f"{partition_date.year + 1}-01-01"
        else:
            end_date = f"{partition_date.year}-{partition_date.month + 1:02d}-01"
        
        partition_name = f"correction_logs_{partition_date.strftime('%Y_%m')}"
        
        op.execute(f"""
            CREATE TABLE {partition_name} PARTITION OF correction_logs
            FOR VALUES FROM ('{start_date}') TO ('{end_date}');
        """)
        
        # Add partition-specific comment
        op.execute(f"COMMENT ON TABLE {partition_name} IS 'Correction logs partition for {partition_date.strftime('%B %Y')}'")
    
    # Create indexes on the main table (will be inherited by partitions)
    
    # Primary index for tenant isolation and time-based queries
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_correction_logs_tenant_created 
        ON correction_logs (tenant_id, created_at DESC)
    """)
    
    # Index for job-specific correction lookups
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_correction_logs_job_record 
        ON correction_logs (tenant_id, job_id, record_number)
    """)
    
    # Index for batch operations and rollbacks
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_correction_logs_batch 
        ON correction_logs (tenant_id, correction_batch_id, status)
    """)
    
    # Index for rule effectiveness analysis
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_correction_logs_rule_analysis 
        ON correction_logs (tenant_id, rule_id, correction_method, status, created_at)
    """)
    
    # GIN indexes for JSONB queries
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_correction_logs_metadata_gin 
        ON correction_logs USING gin (correction_metadata)
    """)
    
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_correction_logs_impact_gin 
        ON correction_logs USING gin (estimated_impact)
    """)
    
    # Partial indexes for common filtered queries
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_correction_logs_pending 
        ON correction_logs (tenant_id, created_at, field_name) 
        WHERE status = 'pending'
    """)
    
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_correction_logs_applied 
        ON correction_logs (tenant_id, applied_at, correction_method) 
        WHERE status = 'applied'
    """)
    
    # Index for correlation and request tracking
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_correction_logs_correlation 
        ON correction_logs (correlation_id, request_id) 
        WHERE correlation_id IS NOT NULL
    """)


def downgrade() -> None:
    """Drop correction_logs table and all partitions."""
    op.execute("DROP TABLE IF EXISTS correction_logs CASCADE")