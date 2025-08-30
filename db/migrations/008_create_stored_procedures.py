"""Create stored procedures for advanced analytics and top-k analysis

Revision ID: 008_create_stored_procedures
Revises: 007_create_analytics_views
Create Date: 2025-01-15 11:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008_create_stored_procedures'
down_revision = '007_create_analytics_views'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create stored procedures for advanced analytics and top-k analysis.
    
    Principle: Encapsulate complex analytical queries in stored procedures for reusability
    and consistent performance. Enable advanced analytics without exposing complex SQL.
    """
    
    # 1. Top-K fields by error volume and impact
    op.execute("""
        CREATE OR REPLACE FUNCTION get_top_error_fields(
            p_tenant_id VARCHAR(50),
            p_channel VARCHAR(50) DEFAULT NULL,
            p_days INTEGER DEFAULT 30,
            p_limit INTEGER DEFAULT 10
        ) RETURNS TABLE (
            field_name VARCHAR(100),
            channel VARCHAR(50),
            total_errors BIGINT,
            unique_error_types BIGINT,
            avg_confidence NUMERIC(5,4),
            total_revenue_impact NUMERIC(12,2),
            improvement_potential NUMERIC(5,4),
            recommended_action TEXT
        ) AS $$
        DECLARE
            analysis_start TIMESTAMP WITH TIME ZONE := NOW() - (p_days || ' days')::INTERVAL;
        BEGIN
            RETURN QUERY
            WITH field_analysis AS (
                SELECT 
                    cl.field_name,
                    COALESCE(rs.channel, 'unknown') as field_channel,
                    COUNT(*) as error_count,
                    COUNT(DISTINCT cl.rule_id) as error_types,
                    AVG(COALESCE(cl.confidence_score, 0)) as confidence,
                    SUM(COALESCE((cl.estimated_impact->>'revenue_impact')::NUMERIC, 0)) as revenue_impact,
                    COUNT(CASE WHEN cl.status IN ('applied', 'approved') THEN 1 END) as successful_fixes,
                    COUNT(CASE WHEN cl.correction_method = 'automatic' THEN 1 END) as auto_fixes,
                    
                    -- Pattern analysis
                    COUNT(CASE WHEN cl.original_value::text = '' OR cl.original_value IS NULL THEN 1 END) as empty_values,
                    AVG(LENGTH(cl.original_value::text)) as avg_length,
                    COUNT(DISTINCT cl.original_value::text) as value_variety
                    
                FROM correction_logs cl
                LEFT JOIN rule_versions rv ON cl.rule_version_id = rv.id
                LEFT JOIN rule_sets rs ON rv.rule_set_id = rs.id
                WHERE cl.tenant_id = p_tenant_id
                  AND cl.created_at >= analysis_start
                  AND (p_channel IS NULL OR rs.channel = p_channel)
                  AND cl.field_name IS NOT NULL
                GROUP BY cl.field_name, rs.channel
            ),
            ranked_fields AS (
                SELECT 
                    *,
                    -- Calculate improvement potential based on automation rate and confidence
                    ROUND(
                        CASE 
                            WHEN error_count > 0 AND successful_fixes > 0 THEN
                                (1.0 - (auto_fixes::NUMERIC / successful_fixes::NUMERIC)) * confidence * 
                                (error_count::NUMERIC / (SELECT SUM(error_count) FROM field_analysis))
                            ELSE 0 
                        END, 4
                    ) as potential,
                    
                    -- Generate recommendations based on patterns
                    CASE 
                        WHEN empty_values::NUMERIC / error_count::NUMERIC > 0.5 THEN 
                            'Implement required field validation'
                        WHEN confidence < 0.5 THEN 
                            'Review and improve rule accuracy'
                        WHEN auto_fixes::NUMERIC / GREATEST(successful_fixes::NUMERIC, 1) < 0.3 THEN 
                            'Increase automation for this field'
                        WHEN value_variety = 1 THEN 
                            'Consider enum or fixed value validation'
                        WHEN avg_length < 5 THEN 
                            'Add minimum length validation'
                        ELSE 
                            'Monitor and optimize existing rules'
                    END as recommendation
                    
                FROM field_analysis
            )
            SELECT 
                rf.field_name,
                rf.field_channel,
                rf.error_count,
                rf.error_types,
                rf.confidence,
                rf.revenue_impact,
                rf.potential,
                rf.recommendation
            FROM ranked_fields rf
            ORDER BY rf.error_count DESC, rf.revenue_impact DESC
            LIMIT p_limit;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 2. Rule performance comparison and benchmarking
    op.execute("""
        CREATE OR REPLACE FUNCTION compare_rule_performance(
            p_tenant_id VARCHAR(50),
            p_rule_id1 VARCHAR(100),
            p_rule_id2 VARCHAR(100),
            p_days INTEGER DEFAULT 30
        ) RETURNS TABLE (
            metric_name TEXT,
            rule1_value NUMERIC,
            rule2_value NUMERIC,
            difference_pct NUMERIC,
            winner TEXT,
            significance TEXT
        ) AS $$
        DECLARE
            analysis_start TIMESTAMP WITH TIME ZONE := NOW() - (p_days || ' days')::INTERVAL;
        BEGIN
            RETURN QUERY
            WITH rule1_stats AS (
                SELECT 
                    COUNT(*) as applications,
                    COUNT(CASE WHEN status IN ('applied', 'approved') THEN 1 END) as successes,
                    COUNT(CASE WHEN correction_method = 'automatic' THEN 1 END) as auto_corrections,
                    AVG(COALESCE(confidence_score, 0)) as avg_confidence,
                    SUM(COALESCE((estimated_impact->>'revenue_impact')::NUMERIC, 0)) as revenue_impact,
                    AVG(COALESCE((correction_metadata->>'processing_time_ms')::NUMERIC, 0)) as avg_processing_time
                FROM correction_logs
                WHERE tenant_id = p_tenant_id 
                  AND rule_id = p_rule_id1 
                  AND created_at >= analysis_start
            ),
            rule2_stats AS (
                SELECT 
                    COUNT(*) as applications,
                    COUNT(CASE WHEN status IN ('applied', 'approved') THEN 1 END) as successes,
                    COUNT(CASE WHEN correction_method = 'automatic' THEN 1 END) as auto_corrections,
                    AVG(COALESCE(confidence_score, 0)) as avg_confidence,
                    SUM(COALESCE((estimated_impact->>'revenue_impact')::NUMERIC, 0)) as revenue_impact,
                    AVG(COALESCE((correction_metadata->>'processing_time_ms')::NUMERIC, 0)) as avg_processing_time
                FROM correction_logs
                WHERE tenant_id = p_tenant_id 
                  AND rule_id = p_rule_id2 
                  AND created_at >= analysis_start
            ),
            comparisons AS (
                SELECT 
                    'Total Applications' as metric,
                    r1.applications as val1,
                    r2.applications as val2
                FROM rule1_stats r1, rule2_stats r2
                
                UNION ALL
                
                SELECT 
                    'Success Rate',
                    CASE WHEN r1.applications > 0 THEN r1.successes::NUMERIC / r1.applications::NUMERIC ELSE 0 END,
                    CASE WHEN r2.applications > 0 THEN r2.successes::NUMERIC / r2.applications::NUMERIC ELSE 0 END
                FROM rule1_stats r1, rule2_stats r2
                
                UNION ALL
                
                SELECT 
                    'Automation Rate',
                    CASE WHEN r1.successes > 0 THEN r1.auto_corrections::NUMERIC / r1.successes::NUMERIC ELSE 0 END,
                    CASE WHEN r2.successes > 0 THEN r2.auto_corrections::NUMERIC / r2.successes::NUMERIC ELSE 0 END
                FROM rule1_stats r1, rule2_stats r2
                
                UNION ALL
                
                SELECT 
                    'Average Confidence',
                    r1.avg_confidence,
                    r2.avg_confidence
                FROM rule1_stats r1, rule2_stats r2
                
                UNION ALL
                
                SELECT 
                    'Revenue Impact',
                    r1.revenue_impact,
                    r2.revenue_impact
                FROM rule1_stats r1, rule2_stats r2
                
                UNION ALL
                
                SELECT 
                    'Processing Time (ms)',
                    r1.avg_processing_time,
                    r2.avg_processing_time
                FROM rule1_stats r1, rule2_stats r2
            )
            SELECT 
                c.metric,
                ROUND(c.val1, 4),
                ROUND(c.val2, 4),
                ROUND(
                    CASE 
                        WHEN c.val1 > 0 THEN ((c.val2 - c.val1) / c.val1) * 100
                        ELSE 0 
                    END, 2
                ) as diff_pct,
                CASE 
                    WHEN c.val2 > c.val1 THEN p_rule_id2
                    WHEN c.val1 > c.val2 THEN p_rule_id1
                    ELSE 'Tie'
                END as winner,
                CASE 
                    WHEN ABS(c.val2 - c.val1) / GREATEST(c.val1, c.val2, 0.001) < 0.05 THEN 'Not Significant'
                    WHEN ABS(c.val2 - c.val1) / GREATEST(c.val1, c.val2, 0.001) < 0.15 THEN 'Moderate'
                    ELSE 'Significant'
                END as significance
            FROM comparisons c;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 3. Tenant health scoring and alerts
    op.execute("""
        CREATE OR REPLACE FUNCTION calculate_tenant_health_score(
            p_tenant_id VARCHAR(50),
            p_days INTEGER DEFAULT 30
        ) RETURNS TABLE (
            tenant_id VARCHAR(50),
            health_score NUMERIC(5,2),
            correction_score NUMERIC(5,2),
            automation_score NUMERIC(5,2),
            quality_score NUMERIC(5,2),
            activity_score NUMERIC(5,2),
            trend_indicator VARCHAR(20),
            priority_issues TEXT[],
            recommendations TEXT[]
        ) AS $$
        DECLARE
            analysis_start TIMESTAMP WITH TIME ZONE := NOW() - (p_days || ' days')::INTERVAL;
            previous_period_start TIMESTAMP WITH TIME ZONE := NOW() - (p_days * 2 || ' days')::INTERVAL;
            issues TEXT[] := '{}';
            recommendations TEXT[] := '{}';
        BEGIN
            RETURN QUERY
            WITH current_metrics AS (
                SELECT 
                    COUNT(*) as total_corrections,
                    COUNT(CASE WHEN status IN ('applied', 'approved') THEN 1 END) as successful_corrections,
                    COUNT(CASE WHEN correction_method = 'automatic' THEN 1 END) as auto_corrections,
                    AVG(COALESCE(confidence_score, 0)) as avg_confidence,
                    COUNT(DISTINCT rule_id) as active_rules,
                    COUNT(DISTINCT field_name) as active_fields,
                    SUM(COALESCE((estimated_impact->>'revenue_impact')::NUMERIC, 0)) as revenue_impact
                FROM correction_logs
                WHERE tenant_id = p_tenant_id AND created_at >= analysis_start
            ),
            previous_metrics AS (
                SELECT 
                    COUNT(*) as total_corrections,
                    COUNT(CASE WHEN status IN ('applied', 'approved') THEN 1 END) as successful_corrections
                FROM correction_logs
                WHERE tenant_id = p_tenant_id 
                  AND created_at >= previous_period_start 
                  AND created_at < analysis_start
            ),
            rule_activity AS (
                SELECT 
                    COUNT(CASE WHEN status = 'published' THEN 1 END) as published_versions,
                    COUNT(*) as total_versions
                FROM rule_versions
                WHERE tenant_id = p_tenant_id AND updated_at >= analysis_start
            ),
            suggestion_metrics AS (
                SELECT 
                    COUNT(*) as suggestions_generated,
                    COUNT(CASE WHEN status = 'implemented' THEN 1 END) as suggestions_implemented
                FROM suggestions
                WHERE tenant_id = p_tenant_id AND created_at >= analysis_start
            )
            SELECT 
                p_tenant_id,
                -- Overall health score (weighted average)
                ROUND(
                    COALESCE(
                        -- Correction success rate (30%)
                        (CASE WHEN cm.total_corrections > 0 THEN cm.successful_corrections::NUMERIC / cm.total_corrections::NUMERIC ELSE 0 END) * 30 +
                        -- Automation rate (25%)
                        (CASE WHEN cm.successful_corrections > 0 THEN cm.auto_corrections::NUMERIC / cm.successful_corrections::NUMERIC ELSE 0 END) * 25 +
                        -- Average confidence (20%)
                        cm.avg_confidence * 20 +
                        -- Activity level (15%)
                        LEAST(1.0, cm.total_corrections::NUMERIC / 100) * 15 +
                        -- Innovation (suggestion adoption) (10%)
                        (CASE WHEN sm.suggestions_generated > 0 THEN sm.suggestions_implemented::NUMERIC / sm.suggestions_generated::NUMERIC ELSE 0 END) * 10,
                        0
                    ), 2
                ) as health_score,
                
                -- Component scores
                ROUND(CASE WHEN cm.total_corrections > 0 THEN (cm.successful_corrections::NUMERIC / cm.total_corrections::NUMERIC) * 100 ELSE 0 END, 2) as correction_score,
                ROUND(CASE WHEN cm.successful_corrections > 0 THEN (cm.auto_corrections::NUMERIC / cm.successful_corrections::NUMERIC) * 100 ELSE 0 END, 2) as automation_score,
                ROUND(cm.avg_confidence * 100, 2) as quality_score,
                ROUND(LEAST(100, (cm.total_corrections::NUMERIC / p_days) * 3), 2) as activity_score,
                
                -- Trend analysis
                CASE 
                    WHEN pm.total_corrections = 0 THEN 'New'
                    WHEN cm.total_corrections > pm.total_corrections * 1.1 THEN 'Improving'
                    WHEN cm.total_corrections < pm.total_corrections * 0.9 THEN 'Declining'
                    ELSE 'Stable'
                END as trend_indicator,
                
                -- Generate issues array based on thresholds
                ARRAY(
                    SELECT issue FROM (
                        SELECT 'Low correction success rate' as issue, 1 as priority
                        WHERE cm.total_corrections > 10 AND cm.successful_corrections::NUMERIC / cm.total_corrections::NUMERIC < 0.8
                        
                        UNION ALL
                        
                        SELECT 'Low automation rate', 2
                        WHERE cm.successful_corrections > 10 AND cm.auto_corrections::NUMERIC / cm.successful_corrections::NUMERIC < 0.3
                        
                        UNION ALL
                        
                        SELECT 'Low average confidence', 3
                        WHERE cm.avg_confidence < 0.6
                        
                        UNION ALL
                        
                        SELECT 'Declining activity', 4
                        WHERE pm.total_corrections > 0 AND cm.total_corrections < pm.total_corrections * 0.7
                        
                        UNION ALL
                        
                        SELECT 'No recent rule updates', 5
                        WHERE ra.published_versions = 0 AND cm.total_corrections > 50
                    ) issues_subq
                    ORDER BY priority
                ) as priority_issues,
                
                -- Generate recommendations
                ARRAY(
                    SELECT recommendation FROM (
                        SELECT 'Review and improve rule accuracy' as recommendation, 1 as priority
                        WHERE cm.avg_confidence < 0.7
                        
                        UNION ALL
                        
                        SELECT 'Increase automation by implementing more auto-correction rules', 2
                        WHERE cm.successful_corrections > 0 AND cm.auto_corrections::NUMERIC / cm.successful_corrections::NUMERIC < 0.5
                        
                        UNION ALL
                        
                        SELECT 'Consider implementing ML-generated suggestions', 3
                        WHERE sm.suggestions_generated > 0 AND sm.suggestions_implemented = 0
                        
                        UNION ALL
                        
                        SELECT 'Update rule sets - no recent publications detected', 4
                        WHERE ra.published_versions = 0 AND cm.total_corrections > 100
                        
                        UNION ALL
                        
                        SELECT 'Monitor data quality - high volume of corrections needed', 5
                        WHERE cm.total_corrections > p_days * 10
                    ) rec_subq
                    ORDER BY priority
                    LIMIT 3
                ) as recommendations
                
            FROM current_metrics cm, previous_metrics pm, rule_activity ra, suggestion_metrics sm;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 4. Data quality trend analysis
    op.execute("""
        CREATE OR REPLACE FUNCTION analyze_data_quality_trends(
            p_tenant_id VARCHAR(50),
            p_field_name VARCHAR(100) DEFAULT NULL,
            p_days INTEGER DEFAULT 90
        ) RETURNS TABLE (
            analysis_period VARCHAR(20),
            period_start DATE,
            period_end DATE,
            total_records_processed BIGINT,
            records_with_errors BIGINT,
            error_rate NUMERIC(6,4),
            top_error_type VARCHAR(100),
            improvement_vs_previous NUMERIC(6,4),
            quality_grade VARCHAR(2),
            trend_direction VARCHAR(10)
        ) AS $$
        BEGIN
            RETURN QUERY
            WITH weekly_periods AS (
                SELECT 
                    generate_series(
                        (NOW() - (p_days || ' days')::INTERVAL)::DATE,
                        NOW()::DATE,
                        '1 week'::INTERVAL
                    )::DATE as period_start
            ),
            period_ranges AS (
                SELECT 
                    period_start,
                    LEAST(period_start + INTERVAL '1 week', NOW()::DATE) as period_end,
                    'Week ' || ROW_NUMBER() OVER (ORDER BY period_start) as period_name
                FROM weekly_periods
            ),
            period_stats AS (
                SELECT 
                    pr.period_name,
                    pr.period_start::DATE,
                    pr.period_end::DATE,
                    
                    -- Estimate total records processed (you'll need to integrate with job execution data)
                    COUNT(DISTINCT cl.record_number, cl.job_id) * 10 as estimated_total_records,
                    COUNT(DISTINCT cl.record_number, cl.job_id) as error_records,
                    COUNT(*) as total_corrections,
                    
                    MODE() WITHIN GROUP (ORDER BY cl.rule_id) as top_error_rule,
                    AVG(COALESCE(cl.confidence_score, 0)) as avg_confidence,
                    
                    LAG(COUNT(DISTINCT cl.record_number, cl.job_id)) OVER (ORDER BY pr.period_start) as prev_error_records
                    
                FROM period_ranges pr
                LEFT JOIN correction_logs cl ON cl.tenant_id = p_tenant_id
                    AND cl.created_at >= pr.period_start
                    AND cl.created_at < pr.period_end
                    AND (p_field_name IS NULL OR cl.field_name = p_field_name)
                GROUP BY pr.period_name, pr.period_start, pr.period_end
                ORDER BY pr.period_start
            )
            SELECT 
                ps.period_name,
                ps.period_start,
                ps.period_end,
                ps.estimated_total_records,
                ps.error_records,
                ROUND(
                    CASE 
                        WHEN ps.estimated_total_records > 0 THEN 
                            ps.error_records::NUMERIC / ps.estimated_total_records::NUMERIC
                        ELSE 0 
                    END, 4
                ) as error_rate,
                ps.top_error_rule,
                ROUND(
                    CASE 
                        WHEN ps.prev_error_records > 0 AND ps.prev_error_records IS NOT NULL THEN
                            (ps.error_records - ps.prev_error_records)::NUMERIC / ps.prev_error_records::NUMERIC
                        ELSE 0 
                    END, 4
                ) as improvement,
                CASE 
                    WHEN ps.estimated_total_records = 0 THEN 'N/A'
                    WHEN ps.error_records::NUMERIC / ps.estimated_total_records::NUMERIC <= 0.01 THEN 'A'
                    WHEN ps.error_records::NUMERIC / ps.estimated_total_records::NUMERIC <= 0.05 THEN 'B'
                    WHEN ps.error_records::NUMERIC / ps.estimated_total_records::NUMERIC <= 0.10 THEN 'C'
                    WHEN ps.error_records::NUMERIC / ps.estimated_total_records::NUMERIC <= 0.20 THEN 'D'
                    ELSE 'F'
                END as quality_grade,
                CASE 
                    WHEN ps.prev_error_records IS NULL THEN 'New'
                    WHEN ps.error_records < ps.prev_error_records * 0.9 THEN 'Improving'
                    WHEN ps.error_records > ps.prev_error_records * 1.1 THEN 'Declining'
                    ELSE 'Stable'
                END as trend
            FROM period_stats ps;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Add comments to procedures
    op.execute("""
        COMMENT ON FUNCTION get_top_error_fields(VARCHAR, VARCHAR, INTEGER, INTEGER) IS 
        'Returns top fields by error volume with improvement recommendations';
    """)
    
    op.execute("""
        COMMENT ON FUNCTION compare_rule_performance(VARCHAR, VARCHAR, VARCHAR, INTEGER) IS 
        'Compares performance metrics between two rules with statistical significance';
    """)
    
    op.execute("""
        COMMENT ON FUNCTION calculate_tenant_health_score(VARCHAR, INTEGER) IS 
        'Calculates comprehensive tenant health score with actionable insights';
    """)
    
    op.execute("""
        COMMENT ON FUNCTION analyze_data_quality_trends(VARCHAR, VARCHAR, INTEGER) IS 
        'Analyzes data quality trends over time with quality grades and trend direction';
    """)


def downgrade() -> None:
    """Drop all stored procedures."""
    op.execute("DROP FUNCTION IF EXISTS analyze_data_quality_trends(VARCHAR, VARCHAR, INTEGER) CASCADE")
    op.execute("DROP FUNCTION IF EXISTS calculate_tenant_health_score(VARCHAR, INTEGER) CASCADE") 
    op.execute("DROP FUNCTION IF EXISTS compare_rule_performance(VARCHAR, VARCHAR, VARCHAR, INTEGER) CASCADE")
    op.execute("DROP FUNCTION IF EXISTS get_top_error_fields(VARCHAR, VARCHAR, INTEGER, INTEGER) CASCADE")