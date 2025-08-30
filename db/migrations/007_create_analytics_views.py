"""Create additional materialized views for analytics and reporting

Revision ID: 007_create_analytics_views
Revises: 006_create_rls_policies
Create Date: 2025-01-15 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '007_create_analytics_views'
down_revision = '006_create_rls_policies'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create materialized views for comprehensive analytics and reporting.
    
    Principle: Pre-aggregate common analytical queries for dashboard performance.
    Balance between freshness and query speed with appropriate refresh intervals.
    """
    
    # 1. Daily tenant metrics aggregation
    op.execute("""
        CREATE MATERIALIZED VIEW daily_tenant_metrics AS
        WITH correction_stats AS (
            SELECT 
                tenant_id,
                DATE_TRUNC('day', created_at) as metric_date,
                COUNT(*) as total_corrections,
                COUNT(CASE WHEN status IN ('applied', 'approved') THEN 1 END) as successful_corrections,
                COUNT(CASE WHEN correction_method = 'automatic' THEN 1 END) as auto_corrections,
                COUNT(DISTINCT rule_id) as rules_used,
                COUNT(DISTINCT field_name) as fields_corrected,
                AVG(COALESCE(confidence_score, 0)) as avg_confidence,
                SUM(COALESCE((estimated_impact->>'revenue_impact')::NUMERIC, 0)) as total_revenue_impact
            FROM correction_logs
            WHERE created_at >= NOW() - INTERVAL '365 days'
            GROUP BY tenant_id, DATE_TRUNC('day', created_at)
        ),
        suggestion_stats AS (
            SELECT 
                tenant_id,
                DATE_TRUNC('day', created_at) as metric_date,
                COUNT(*) as suggestions_generated,
                COUNT(CASE WHEN status = 'implemented' THEN 1 END) as suggestions_implemented,
                AVG(confidence_score) as avg_suggestion_confidence,
                COUNT(CASE WHEN priority_score >= 0.7 THEN 1 END) as high_priority_suggestions
            FROM suggestions
            WHERE created_at >= NOW() - INTERVAL '365 days'
            GROUP BY tenant_id, DATE_TRUNC('day', created_at)
        ),
        rule_activity AS (
            SELECT 
                tenant_id,
                DATE_TRUNC('day', updated_at) as metric_date,
                COUNT(*) as rule_updates,
                COUNT(CASE WHEN status = 'published' THEN 1 END) as versions_published
            FROM rule_versions
            WHERE updated_at >= NOW() - INTERVAL '365 days'
            GROUP BY tenant_id, DATE_TRUNC('day', updated_at)
        )
        SELECT 
            COALESCE(cs.tenant_id, ss.tenant_id, ra.tenant_id) as tenant_id,
            COALESCE(cs.metric_date, ss.metric_date, ra.metric_date) as metric_date,
            
            -- Correction metrics
            COALESCE(cs.total_corrections, 0) as total_corrections,
            COALESCE(cs.successful_corrections, 0) as successful_corrections,
            COALESCE(cs.auto_corrections, 0) as auto_corrections,
            COALESCE(cs.rules_used, 0) as rules_used,
            COALESCE(cs.fields_corrected, 0) as fields_corrected,
            COALESCE(cs.avg_confidence, 0) as avg_confidence,
            COALESCE(cs.total_revenue_impact, 0) as total_revenue_impact,
            
            -- Suggestion metrics
            COALESCE(ss.suggestions_generated, 0) as suggestions_generated,
            COALESCE(ss.suggestions_implemented, 0) as suggestions_implemented,
            COALESCE(ss.avg_suggestion_confidence, 0) as avg_suggestion_confidence,
            COALESCE(ss.high_priority_suggestions, 0) as high_priority_suggestions,
            
            -- Rule activity
            COALESCE(ra.rule_updates, 0) as rule_updates,
            COALESCE(ra.versions_published, 0) as versions_published,
            
            -- Calculated KPIs
            CASE 
                WHEN COALESCE(cs.total_corrections, 0) > 0 THEN
                    ROUND(COALESCE(cs.successful_corrections, 0)::NUMERIC / cs.total_corrections::NUMERIC, 4)
                ELSE 0 
            END as correction_success_rate,
            
            CASE 
                WHEN COALESCE(cs.successful_corrections, 0) > 0 THEN
                    ROUND(COALESCE(cs.auto_corrections, 0)::NUMERIC / cs.successful_corrections::NUMERIC, 4)
                ELSE 0 
            END as automation_rate,
            
            CASE 
                WHEN COALESCE(ss.suggestions_generated, 0) > 0 THEN
                    ROUND(COALESCE(ss.suggestions_implemented, 0)::NUMERIC / ss.suggestions_generated::NUMERIC, 4)
                ELSE 0 
            END as suggestion_adoption_rate
            
        FROM correction_stats cs
        FULL OUTER JOIN suggestion_stats ss ON cs.tenant_id = ss.tenant_id AND cs.metric_date = ss.metric_date
        FULL OUTER JOIN rule_activity ra ON COALESCE(cs.tenant_id, ss.tenant_id) = ra.tenant_id 
                                         AND COALESCE(cs.metric_date, ss.metric_date) = ra.metric_date;
    """)
    
    # 2. Channel performance analysis
    op.execute("""
        CREATE MATERIALIZED VIEW channel_performance_metrics AS
        WITH base_metrics AS (
            SELECT 
                cl.tenant_id,
                rs.channel,
                DATE_TRUNC('week', cl.created_at) as metric_week,
                DATE_TRUNC('month', cl.created_at) as metric_month,
                
                COUNT(*) as total_corrections,
                COUNT(CASE WHEN cl.status IN ('applied', 'approved') THEN 1 END) as successful_corrections,
                COUNT(CASE WHEN cl.correction_method = 'automatic' THEN 1 END) as auto_corrections,
                COUNT(DISTINCT cl.rule_id) as unique_rules_triggered,
                COUNT(DISTINCT cl.field_name) as unique_fields_affected,
                
                AVG(COALESCE(cl.confidence_score, 0)) as avg_confidence,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY COALESCE(cl.confidence_score, 0)) as p95_confidence,
                
                SUM(COALESCE((cl.estimated_impact->>'revenue_impact')::NUMERIC, 0)) as total_revenue_impact,
                AVG(COALESCE((cl.correction_metadata->>'processing_time_ms')::NUMERIC, 0)) as avg_processing_time,
                
                -- Error pattern analysis
                COUNT(DISTINCT cl.record_number) as records_with_corrections,
                AVG(COALESCE((cl.correction_metadata->>'error_severity')::NUMERIC, 1)) as avg_error_severity
                
            FROM correction_logs cl
            LEFT JOIN rule_versions rv ON cl.rule_version_id = rv.id
            LEFT JOIN rule_sets rs ON rv.rule_set_id = rs.id
            WHERE cl.created_at >= NOW() - INTERVAL '180 days'
              AND rs.channel IS NOT NULL
            GROUP BY cl.tenant_id, rs.channel, DATE_TRUNC('week', cl.created_at), DATE_TRUNC('month', cl.created_at)
        ),
        channel_rankings AS (
            SELECT 
                *,
                -- Performance score calculation
                ROUND(
                    CASE 
                        WHEN total_corrections > 0 THEN
                            -- Success rate (50%)
                            (successful_corrections::NUMERIC / total_corrections::NUMERIC) * 0.5 +
                            -- Automation rate (30%)
                            (auto_corrections::NUMERIC / GREATEST(successful_corrections::NUMERIC, 1)) * 0.3 +
                            -- Confidence (20%)
                            avg_confidence * 0.2
                        ELSE 0 
                    END, 4
                ) as performance_score,
                
                -- Rank channels within tenant by performance
                ROW_NUMBER() OVER (
                    PARTITION BY tenant_id, metric_month 
                    ORDER BY (successful_corrections::NUMERIC / GREATEST(total_corrections::NUMERIC, 1)) DESC
                ) as channel_rank_by_success,
                
                ROW_NUMBER() OVER (
                    PARTITION BY tenant_id, metric_month 
                    ORDER BY total_revenue_impact DESC
                ) as channel_rank_by_impact
                
            FROM base_metrics
        )
        SELECT 
            tenant_id,
            channel,
            metric_week,
            metric_month,
            total_corrections,
            successful_corrections,
            auto_corrections,
            unique_rules_triggered,
            unique_fields_affected,
            records_with_corrections,
            
            -- Performance metrics
            ROUND(avg_confidence, 4) as avg_confidence,
            ROUND(p95_confidence, 4) as p95_confidence,
            ROUND(avg_processing_time, 2) as avg_processing_time_ms,
            ROUND(avg_error_severity, 2) as avg_error_severity,
            
            -- Business metrics
            ROUND(total_revenue_impact, 2) as total_revenue_impact,
            
            -- Calculated ratios
            ROUND(
                successful_corrections::NUMERIC / GREATEST(total_corrections::NUMERIC, 1), 4
            ) as success_rate,
            
            ROUND(
                auto_corrections::NUMERIC / GREATEST(successful_corrections::NUMERIC, 1), 4
            ) as automation_rate,
            
            ROUND(
                records_with_corrections::NUMERIC / GREATEST(total_corrections::NUMERIC, 1), 4
            ) as correction_density,
            
            performance_score,
            channel_rank_by_success,
            channel_rank_by_impact
            
        FROM channel_rankings;
    """)
    
    # 3. Field-level correction patterns
    op.execute("""
        CREATE MATERIALIZED VIEW field_correction_patterns AS
        WITH field_stats AS (
            SELECT 
                cl.tenant_id,
                cl.field_name,
                rs.channel,
                DATE_TRUNC('month', cl.created_at) as metric_month,
                
                COUNT(*) as total_corrections,
                COUNT(CASE WHEN cl.status IN ('applied', 'approved') THEN 1 END) as successful_corrections,
                COUNT(CASE WHEN cl.correction_method = 'automatic' THEN 1 END) as auto_corrections,
                COUNT(DISTINCT cl.rule_id) as rules_affecting_field,
                
                -- Pattern analysis using JSONB operators
                COUNT(CASE WHEN cl.original_value::text ~ '^[0-9.]+$' THEN 1 END) as numeric_corrections,
                COUNT(CASE WHEN cl.original_value::text ~ '^https?://' THEN 1 END) as url_corrections,
                COUNT(CASE WHEN LENGTH(cl.original_value::text) < 10 THEN 1 END) as short_value_corrections,
                COUNT(CASE WHEN cl.original_value::text = '' OR cl.original_value IS NULL THEN 1 END) as empty_value_corrections,
                
                AVG(COALESCE(cl.confidence_score, 0)) as avg_confidence,
                AVG(LENGTH(cl.original_value::text)) as avg_original_length,
                AVG(LENGTH(cl.corrected_value::text)) as avg_corrected_length,
                
                SUM(COALESCE((cl.estimated_impact->>'revenue_impact')::NUMERIC, 0)) as total_revenue_impact,
                
                -- Most common correction types
                MODE() WITHIN GROUP (ORDER BY cl.correction_type) as most_common_correction_type,
                COUNT(DISTINCT cl.correction_type) as correction_type_variety
                
            FROM correction_logs cl
            LEFT JOIN rule_versions rv ON cl.rule_version_id = rv.id
            LEFT JOIN rule_sets rs ON rv.rule_set_id = rs.id
            WHERE cl.created_at >= NOW() - INTERVAL '180 days'
              AND cl.field_name IS NOT NULL
            GROUP BY cl.tenant_id, cl.field_name, rs.channel, DATE_TRUNC('month', cl.created_at)
        )
        SELECT 
            tenant_id,
            field_name,
            channel,
            metric_month,
            total_corrections,
            successful_corrections,
            auto_corrections,
            rules_affecting_field,
            
            -- Pattern indicators
            numeric_corrections,
            url_corrections,
            short_value_corrections,
            empty_value_corrections,
            
            -- Field characteristics
            ROUND(avg_confidence, 4) as avg_confidence,
            ROUND(avg_original_length, 1) as avg_original_length,
            ROUND(avg_corrected_length, 1) as avg_corrected_length,
            most_common_correction_type,
            correction_type_variety,
            
            -- Business impact
            ROUND(total_revenue_impact, 2) as total_revenue_impact,
            
            -- Performance metrics
            ROUND(
                successful_corrections::NUMERIC / GREATEST(total_corrections::NUMERIC, 1), 4
            ) as field_success_rate,
            
            ROUND(
                auto_corrections::NUMERIC / GREATEST(successful_corrections::NUMERIC, 1), 4
            ) as field_automation_rate,
            
            -- Data quality indicators
            ROUND(
                empty_value_corrections::NUMERIC / GREATEST(total_corrections::NUMERIC, 1), 4
            ) as empty_value_rate,
            
            ROUND(
                short_value_corrections::NUMERIC / GREATEST(total_corrections::NUMERIC, 1), 4
            ) as short_value_rate,
            
            -- Field ranking within tenant
            ROW_NUMBER() OVER (
                PARTITION BY tenant_id, metric_month 
                ORDER BY total_corrections DESC
            ) as field_rank_by_volume,
            
            ROW_NUMBER() OVER (
                PARTITION BY tenant_id, metric_month 
                ORDER BY total_revenue_impact DESC
            ) as field_rank_by_impact
            
        FROM field_stats;
    """)
    
    # Create indexes on materialized views
    op.execute("""
        CREATE UNIQUE INDEX idx_daily_tenant_metrics_unique
        ON daily_tenant_metrics (tenant_id, metric_date);
    """)
    
    op.execute("""
        CREATE INDEX idx_daily_tenant_metrics_recent
        ON daily_tenant_metrics (tenant_id, metric_date DESC)
        WHERE metric_date >= NOW()::DATE - INTERVAL '30 days';
    """)
    
    op.execute("""
        CREATE UNIQUE INDEX idx_channel_performance_unique
        ON channel_performance_metrics (tenant_id, channel, metric_week, metric_month);
    """)
    
    op.execute("""
        CREATE INDEX idx_channel_performance_ranking
        ON channel_performance_metrics (tenant_id, metric_month, performance_score DESC);
    """)
    
    op.execute("""
        CREATE UNIQUE INDEX idx_field_patterns_unique
        ON field_correction_patterns (tenant_id, field_name, channel, metric_month);
    """)
    
    op.execute("""
        CREATE INDEX idx_field_patterns_volume
        ON field_correction_patterns (tenant_id, metric_month, total_corrections DESC);
    """)
    
    # Create refresh functions for all materialized views
    op.execute("""
        CREATE OR REPLACE FUNCTION refresh_all_analytics_views()
        RETURNS VOID AS $$
        BEGIN
            -- Refresh in dependency order
            REFRESH MATERIALIZED VIEW CONCURRENTLY daily_tenant_metrics;
            REFRESH MATERIALIZED VIEW CONCURRENTLY channel_performance_metrics;
            REFRESH MATERIALIZED VIEW CONCURRENTLY field_correction_patterns;
            REFRESH MATERIALIZED VIEW CONCURRENTLY rule_effectiveness;
            
            -- Update statistics
            ANALYZE daily_tenant_metrics;
            ANALYZE channel_performance_metrics;
            ANALYZE field_correction_patterns;
            ANALYZE rule_effectiveness;
            
            -- Log refresh completion
            RAISE NOTICE 'All analytics materialized views refreshed at %', NOW();
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Add table comments
    op.execute("""
        COMMENT ON MATERIALIZED VIEW daily_tenant_metrics IS 
        'Daily aggregated metrics per tenant for dashboard KPIs. Refreshed every 4 hours.';
    """)
    
    op.execute("""
        COMMENT ON MATERIALIZED VIEW channel_performance_metrics IS 
        'Channel-level performance analysis with rankings. Refreshed daily.';
    """)
    
    op.execute("""
        COMMENT ON MATERIALIZED VIEW field_correction_patterns IS 
        'Field-level correction patterns and data quality insights. Refreshed daily.';
    """)


def downgrade() -> None:
    """Drop analytics materialized views and refresh functions."""
    op.execute("DROP FUNCTION IF EXISTS refresh_all_analytics_views() CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS field_correction_patterns CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS channel_performance_metrics CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_tenant_metrics CASCADE")