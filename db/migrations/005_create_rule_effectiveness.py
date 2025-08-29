"""Create rule_effectiveness materialized view and supporting functions

Revision ID: 005_create_rule_effectiveness
Revises: 004_create_suggestions
Create Date: 2025-01-15 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_create_rule_effectiveness'
down_revision = '004_create_suggestions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create materialized view and functions for rule effectiveness analysis.
    
    Principle: Pre-aggregate rule performance metrics for fast dashboard queries.
    Materialized view refreshed hourly to balance freshness and performance.
    """
    
    # Create function to calculate rule effectiveness metrics
    op.execute("""
        CREATE OR REPLACE FUNCTION calculate_rule_effectiveness(
            p_tenant_id VARCHAR(50),
            p_rule_id VARCHAR(100),
            p_start_date TIMESTAMP WITH TIME ZONE DEFAULT NOW() - INTERVAL '30 days',
            p_end_date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        ) RETURNS TABLE (
            tenant_id VARCHAR(50),
            rule_id VARCHAR(100),
            rule_version VARCHAR(20),
            channel VARCHAR(50),
            period_start TIMESTAMP WITH TIME ZONE,
            period_end TIMESTAMP WITH TIME ZONE,
            total_evaluations BIGINT,
            total_violations BIGINT,
            total_corrections BIGINT,
            auto_corrections BIGINT,
            manual_corrections BIGINT,
            correction_success_rate NUMERIC(5,4),
            false_positive_rate NUMERIC(5,4),
            avg_correction_confidence NUMERIC(5,4),
            business_impact NUMERIC(12,2),
            performance_score NUMERIC(5,4)
        ) AS $$
        BEGIN
            RETURN QUERY
            WITH rule_evaluations AS (
                -- This would integrate with job execution logs when available
                SELECT 
                    cl.tenant_id,
                    cl.rule_id,
                    rv.version as rule_version,
                    rs.channel,
                    COUNT(*) as evaluations,
                    COUNT(CASE WHEN cl.status IN ('applied', 'approved') THEN 1 END) as violations,
                    COUNT(CASE WHEN cl.correction_method = 'automatic' THEN 1 END) as auto_corr,
                    COUNT(CASE WHEN cl.correction_method = 'manual' THEN 1 END) as manual_corr,
                    AVG(COALESCE(cl.confidence_score, 0)) as avg_confidence,
                    SUM(COALESCE((cl.estimated_impact->>'revenue_impact')::NUMERIC, 0)) as impact
                FROM correction_logs cl
                LEFT JOIN rule_versions rv ON cl.rule_version_id = rv.id
                LEFT JOIN rule_sets rs ON rv.rule_set_id = rs.id
                WHERE cl.tenant_id = p_tenant_id
                  AND cl.rule_id = p_rule_id
                  AND cl.created_at >= p_start_date
                  AND cl.created_at <= p_end_date
                GROUP BY cl.tenant_id, cl.rule_id, rv.version, rs.channel
            ),
            correction_stats AS (
                SELECT 
                    tenant_id,
                    rule_id,
                    rule_version,
                    channel,
                    evaluations as total_evals,
                    violations as total_viol,
                    (auto_corr + manual_corr) as total_corr,
                    auto_corr,
                    manual_corr,
                    CASE 
                        WHEN violations > 0 THEN 
                            ROUND((auto_corr + manual_corr)::NUMERIC / violations::NUMERIC, 4)
                        ELSE 0 
                    END as success_rate,
                    -- Estimate false positive rate based on rejected corrections
                    CASE 
                        WHEN evaluations > 0 THEN
                            ROUND(GREATEST(0, (evaluations - violations)::NUMERIC / evaluations::NUMERIC), 4)
                        ELSE 0
                    END as fp_rate,
                    ROUND(avg_confidence, 4) as avg_conf,
                    ROUND(impact, 2) as biz_impact
                FROM rule_evaluations
            )
            SELECT 
                p_tenant_id,
                p_rule_id,
                COALESCE(cs.rule_version, 'unknown'),
                COALESCE(cs.channel, 'unknown'),
                p_start_date,
                p_end_date,
                COALESCE(cs.total_evals, 0),
                COALESCE(cs.total_viol, 0),
                COALESCE(cs.total_corr, 0),
                COALESCE(cs.auto_corr, 0),
                COALESCE(cs.manual_corr, 0),
                COALESCE(cs.success_rate, 0),
                COALESCE(cs.fp_rate, 0),
                COALESCE(cs.avg_conf, 0),
                COALESCE(cs.biz_impact, 0),
                -- Performance score: weighted combination of metrics
                ROUND(
                    COALESCE(cs.success_rate, 0) * 0.4 + 
                    (1 - COALESCE(cs.fp_rate, 0)) * 0.3 + 
                    COALESCE(cs.avg_conf, 0) * 0.3,
                    4
                ) as performance_score
            FROM correction_stats cs;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create materialized view for rule effectiveness
    op.execute("""
        CREATE MATERIALIZED VIEW rule_effectiveness AS
        WITH base_metrics AS (
            SELECT 
                cl.tenant_id,
                cl.rule_id,
                rv.version as rule_version,
                rs.channel,
                rs.name as rule_set_name,
                rv.rule_set_id,
                
                -- Time buckets for trending
                DATE_TRUNC('day', cl.created_at) as metric_date,
                DATE_TRUNC('week', cl.created_at) as metric_week,
                DATE_TRUNC('month', cl.created_at) as metric_month,
                
                -- Raw counts
                COUNT(*) as total_applications,
                COUNT(CASE WHEN cl.status IN ('applied', 'approved') THEN 1 END) as successful_corrections,
                COUNT(CASE WHEN cl.status = 'rejected' THEN 1 END) as rejected_corrections,
                COUNT(CASE WHEN cl.correction_method = 'automatic' THEN 1 END) as auto_corrections,
                COUNT(CASE WHEN cl.correction_method = 'manual' THEN 1 END) as manual_corrections,
                
                -- Confidence and impact aggregations
                AVG(COALESCE(cl.confidence_score, 0)) as avg_confidence,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY COALESCE(cl.confidence_score, 0)) as median_confidence,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY COALESCE(cl.confidence_score, 0)) as p95_confidence,
                
                -- Business impact metrics
                SUM(COALESCE((cl.estimated_impact->>'revenue_impact')::NUMERIC, 0)) as total_revenue_impact,
                AVG(COALESCE((cl.estimated_impact->>'accuracy_improvement')::NUMERIC, 0)) as avg_accuracy_improvement,
                
                -- Field-level analysis
                COUNT(DISTINCT cl.field_name) as affected_fields,
                
                -- Performance tracking
                AVG(COALESCE((cl.correction_metadata->>'processing_time_ms')::NUMERIC, 0)) as avg_processing_time
                
            FROM correction_logs cl
            LEFT JOIN rule_versions rv ON cl.rule_version_id = rv.id
            LEFT JOIN rule_sets rs ON rv.rule_set_id = rs.id
            WHERE cl.created_at >= NOW() - INTERVAL '90 days'  -- Keep 90 days of data
            GROUP BY 
                cl.tenant_id, cl.rule_id, rv.version, rs.channel, rs.name, rv.rule_set_id,
                DATE_TRUNC('day', cl.created_at),
                DATE_TRUNC('week', cl.created_at),
                DATE_TRUNC('month', cl.created_at)
        ),
        calculated_metrics AS (
            SELECT 
                *,
                -- Effectiveness ratios
                CASE 
                    WHEN total_applications > 0 THEN 
                        ROUND(successful_corrections::NUMERIC / total_applications::NUMERIC, 4)
                    ELSE 0 
                END as success_rate,
                
                CASE 
                    WHEN total_applications > 0 THEN 
                        ROUND(rejected_corrections::NUMERIC / total_applications::NUMERIC, 4)
                    ELSE 0 
                END as rejection_rate,
                
                CASE 
                    WHEN successful_corrections > 0 THEN 
                        ROUND(auto_corrections::NUMERIC / successful_corrections::NUMERIC, 4)
                    ELSE 0 
                END as automation_rate,
                
                -- Quality score based on confidence and success
                ROUND(
                    CASE 
                        WHEN total_applications > 0 THEN
                            (successful_corrections::NUMERIC / total_applications::NUMERIC) * 0.6 +
                            avg_confidence * 0.4
                        ELSE 0 
                    END, 4
                ) as quality_score,
                
                -- Efficiency score based on automation and processing time
                ROUND(
                    CASE 
                        WHEN successful_corrections > 0 AND avg_processing_time > 0 THEN
                            (auto_corrections::NUMERIC / successful_corrections::NUMERIC) * 0.7 +
                            GREATEST(0, (1000 - avg_processing_time) / 1000) * 0.3
                        ELSE 0 
                    END, 4
                ) as efficiency_score,
                
                -- Overall performance score
                ROUND(
                    CASE 
                        WHEN total_applications > 0 THEN
                            -- Success rate (40%)
                            (successful_corrections::NUMERIC / total_applications::NUMERIC) * 0.4 +
                            -- Confidence (30%)
                            avg_confidence * 0.3 +
                            -- Automation rate (20%)
                            (CASE WHEN successful_corrections > 0 THEN auto_corrections::NUMERIC / successful_corrections::NUMERIC ELSE 0 END) * 0.2 +
                            -- Low rejection rate (10%)
                            (1 - LEAST(1, rejected_corrections::NUMERIC / total_applications::NUMERIC)) * 0.1
                        ELSE 0 
                    END, 4
                ) as overall_score
                
            FROM base_metrics
        )
        SELECT 
            tenant_id,
            rule_id,
            rule_version,
            channel,
            rule_set_name,
            rule_set_id,
            metric_date,
            metric_week,
            metric_month,
            
            -- Raw counts
            total_applications,
            successful_corrections,
            rejected_corrections,
            auto_corrections,
            manual_corrections,
            affected_fields,
            
            -- Confidence metrics
            avg_confidence,
            median_confidence,
            p95_confidence,
            
            -- Business impact
            total_revenue_impact,
            avg_accuracy_improvement,
            
            -- Performance metrics
            avg_processing_time,
            success_rate,
            rejection_rate,
            automation_rate,
            quality_score,
            efficiency_score,
            overall_score
            
        FROM calculated_metrics;
    """)
    
    # Create indexes on materialized view for fast queries
    op.execute("""
        CREATE UNIQUE INDEX idx_rule_effectiveness_unique
        ON rule_effectiveness (tenant_id, rule_id, rule_version, channel, metric_date);
    """)
    
    op.execute("""
        CREATE INDEX idx_rule_effectiveness_tenant_score
        ON rule_effectiveness (tenant_id, overall_score DESC, metric_date DESC);
    """)
    
    op.execute("""
        CREATE INDEX idx_rule_effectiveness_channel_performance
        ON rule_effectiveness (tenant_id, channel, metric_month, overall_score DESC);
    """)
    
    op.execute("""
        CREATE INDEX idx_rule_effectiveness_recent
        ON rule_effectiveness (tenant_id, metric_date DESC)
        WHERE metric_date >= NOW()::DATE - INTERVAL '7 days';
    """)
    
    # Create function for top-k analysis by field
    op.execute("""
        CREATE OR REPLACE FUNCTION get_top_correction_patterns(
            p_tenant_id VARCHAR(50),
            p_field_name VARCHAR(100) DEFAULT NULL,
            p_limit INTEGER DEFAULT 10,
            p_days INTEGER DEFAULT 30
        ) RETURNS TABLE (
            field_name VARCHAR(100),
            original_pattern TEXT,
            correction_pattern TEXT,
            frequency BIGINT,
            success_rate NUMERIC(5,4),
            avg_confidence NUMERIC(5,4),
            total_revenue_impact NUMERIC(12,2)
        ) AS $$
        BEGIN
            RETURN QUERY
            WITH pattern_analysis AS (
                SELECT 
                    cl.field_name,
                    LEFT(cl.original_value::TEXT, 100) as orig_pattern,
                    LEFT(cl.corrected_value::TEXT, 100) as corr_pattern,
                    COUNT(*) as freq,
                    COUNT(CASE WHEN cl.status IN ('applied', 'approved') THEN 1 END) as successful,
                    AVG(COALESCE(cl.confidence_score, 0)) as conf,
                    SUM(COALESCE((cl.estimated_impact->>'revenue_impact')::NUMERIC, 0)) as impact
                FROM correction_logs cl
                WHERE cl.tenant_id = p_tenant_id
                  AND cl.created_at >= NOW() - (p_days || ' days')::INTERVAL
                  AND (p_field_name IS NULL OR cl.field_name = p_field_name)
                  AND cl.original_value IS NOT NULL 
                  AND cl.corrected_value IS NOT NULL
                GROUP BY cl.field_name, LEFT(cl.original_value::TEXT, 100), LEFT(cl.corrected_value::TEXT, 100)
                HAVING COUNT(*) >= 2  -- Only patterns that occur multiple times
            )
            SELECT 
                pa.field_name,
                pa.orig_pattern,
                pa.corr_pattern,
                pa.freq,
                ROUND(pa.successful::NUMERIC / pa.freq::NUMERIC, 4) as success_rate,
                ROUND(pa.conf, 4) as avg_confidence,
                ROUND(pa.impact, 2) as total_revenue_impact
            FROM pattern_analysis pa
            ORDER BY pa.freq DESC, success_rate DESC
            LIMIT p_limit;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create function to refresh materialized view with concurrency support
    op.execute("""
        CREATE OR REPLACE FUNCTION refresh_rule_effectiveness()
        RETURNS VOID AS $$
        BEGIN
            -- Use CONCURRENTLY to avoid blocking reads during refresh
            REFRESH MATERIALIZED VIEW CONCURRENTLY rule_effectiveness;
            
            -- Clean up old data (keep only 90 days)
            DELETE FROM rule_effectiveness 
            WHERE metric_date < NOW()::DATE - INTERVAL '90 days';
            
            -- Update statistics for optimal query planning
            ANALYZE rule_effectiveness;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Add comment to materialized view
    op.execute("""
        COMMENT ON MATERIALIZED VIEW rule_effectiveness IS 
        'Pre-aggregated rule performance metrics for fast dashboard queries. Refreshed hourly.';
    """)


def downgrade() -> None:
    """Drop rule effectiveness materialized view and functions."""
    op.execute("DROP FUNCTION IF EXISTS refresh_rule_effectiveness() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS get_top_correction_patterns(VARCHAR, VARCHAR, INTEGER, INTEGER) CASCADE")
    op.execute("DROP FUNCTION IF EXISTS calculate_rule_effectiveness(VARCHAR, VARCHAR, TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE) CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS rule_effectiveness CASCADE")