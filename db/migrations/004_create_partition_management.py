"""Create automated partition management for correction_logs

Revision ID: 004_create_partition_management
Revises: 003_create_correction_logs
Create Date: 2025-01-30 12:00:00.000000

This migration adds automated partition management:
- Auto-creation of future partitions
- Auto-archival/dropping of old partitions
- Monitoring and alerting functions
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_create_partition_management'
down_revision = '003_create_correction_logs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create automated partition management system for correction_logs.
    
    Principle: Hands-off partition management with proactive creation and intelligent archival.
    """
    
    # Create partition management configuration table
    op.create_table(
        'partition_management_config',
        sa.Column('table_name', sa.String(100), primary_key=True, nullable=False),
        sa.Column('partition_interval', sa.String(20), nullable=False, default='monthly',
                  comment='Partition interval: daily, weekly, monthly, yearly'),
        sa.Column('retention_months', sa.Integer, nullable=False, default=12,
                  comment='Number of months to retain partitions'),
        sa.Column('archive_months', sa.Integer, nullable=False, default=6,
                  comment='Months before moving to archive storage'),
        sa.Column('future_partitions', sa.Integer, nullable=False, default=3,
                  comment='Number of future partitions to maintain'),
        sa.Column('is_enabled', sa.Boolean, nullable=False, default=True,
                  comment='Whether auto-management is enabled'),
        sa.Column('last_maintenance_at', sa.TIMESTAMP(timezone=True),
                  comment='Last time maintenance ran'),
        sa.Column('next_maintenance_at', sa.TIMESTAMP(timezone=True),
                  comment='Next scheduled maintenance'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        comment='Configuration for automated partition management'
    )
    
    # Insert configuration for correction_logs
    op.execute("""
        INSERT INTO partition_management_config 
        (table_name, partition_interval, retention_months, archive_months, future_partitions)
        VALUES 
        ('correction_logs', 'monthly', 12, 6, 3)
    """)
    
    # Create partition management log table
    op.create_table(
        'partition_management_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('table_name', sa.String(100), nullable=False),
        sa.Column('action', sa.String(50), nullable=False,
                  comment='Action taken: created, archived, dropped, analyzed'),
        sa.Column('partition_name', sa.String(100), nullable=False),
        sa.Column('partition_start_date', sa.DATE, nullable=False),
        sa.Column('partition_end_date', sa.DATE, nullable=False),
        sa.Column('rows_affected', sa.BigInteger,
                  comment='Number of rows in partition'),
        sa.Column('size_mb', sa.Numeric(10, 2),
                  comment='Partition size in MB'),
        sa.Column('success', sa.Boolean, nullable=False, default=True),
        sa.Column('error_message', sa.Text),
        sa.Column('execution_time_ms', sa.Integer),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        comment='Audit log for partition management operations'
    )
    
    # Create function to automatically create monthly partitions
    op.execute("""
        CREATE OR REPLACE FUNCTION create_monthly_partitions(
            p_table_name TEXT,
            p_months_ahead INTEGER DEFAULT 3
        )
        RETURNS TABLE(partition_name TEXT, created BOOLEAN, message TEXT) 
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_start_date DATE;
            v_end_date DATE;
            v_partition_name TEXT;
            v_sql TEXT;
            v_created_count INTEGER := 0;
            v_start_time TIMESTAMP;
        BEGIN
            v_start_time := clock_timestamp();
            
            -- Loop through the next N months
            FOR i IN 0..p_months_ahead LOOP
                v_start_date := DATE_TRUNC('month', CURRENT_DATE + (i || ' months')::INTERVAL);
                v_end_date := DATE_TRUNC('month', v_start_date + INTERVAL '1 month');
                v_partition_name := p_table_name || '_' || TO_CHAR(v_start_date, 'YYYY_MM');
                
                -- Check if partition exists
                IF NOT EXISTS (
                    SELECT 1 FROM pg_tables 
                    WHERE tablename = v_partition_name
                    AND schemaname = 'public'
                ) THEN
                    -- Create the partition
                    v_sql := FORMAT(
                        'CREATE TABLE %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                        v_partition_name, p_table_name, v_start_date, v_end_date
                    );
                    
                    BEGIN
                        EXECUTE v_sql;
                        
                        -- Add partition comment
                        EXECUTE FORMAT(
                            'COMMENT ON TABLE %I IS %L',
                            v_partition_name,
                            'Auto-created partition for ' || TO_CHAR(v_start_date, 'Month YYYY')
                        );
                        
                        -- Log success
                        INSERT INTO partition_management_log (
                            table_name, action, partition_name, 
                            partition_start_date, partition_end_date,
                            success, execution_time_ms
                        ) VALUES (
                            p_table_name, 'created', v_partition_name,
                            v_start_date, v_end_date,
                            true, EXTRACT(EPOCH FROM (clock_timestamp() - v_start_time)) * 1000
                        );
                        
                        v_created_count := v_created_count + 1;
                        
                        RETURN QUERY SELECT v_partition_name, true::BOOLEAN, 'Created successfully'::TEXT;
                    EXCEPTION
                        WHEN OTHERS THEN
                            -- Log failure
                            INSERT INTO partition_management_log (
                                table_name, action, partition_name,
                                partition_start_date, partition_end_date,
                                success, error_message, execution_time_ms
                            ) VALUES (
                                p_table_name, 'created', v_partition_name,
                                v_start_date, v_end_date,
                                false, SQLERRM, EXTRACT(EPOCH FROM (clock_timestamp() - v_start_time)) * 1000
                            );
                            
                            RETURN QUERY SELECT v_partition_name, false::BOOLEAN, SQLERRM::TEXT;
                    END;
                ELSE
                    RETURN QUERY SELECT v_partition_name, false::BOOLEAN, 'Already exists'::TEXT;
                END IF;
            END LOOP;
            
            -- Update last maintenance timestamp
            UPDATE partition_management_config
            SET last_maintenance_at = NOW(),
                next_maintenance_at = NOW() + INTERVAL '1 day'
            WHERE table_name = p_table_name;
            
            RETURN;
        END;
        $$;
    """)
    
    # Create function to archive old partitions
    op.execute("""
        CREATE OR REPLACE FUNCTION archive_old_partitions(
            p_table_name TEXT,
            p_archive_months INTEGER DEFAULT 6
        )
        RETURNS TABLE(partition_name TEXT, archived BOOLEAN, message TEXT)
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_partition RECORD;
            v_archive_date DATE;
            v_rows_count BIGINT;
            v_size_mb NUMERIC;
            v_archive_table TEXT;
            v_start_time TIMESTAMP;
        BEGIN
            v_start_time := clock_timestamp();
            v_archive_date := DATE_TRUNC('month', CURRENT_DATE - (p_archive_months || ' months')::INTERVAL);
            
            -- Find partitions older than archive date
            FOR v_partition IN
                SELECT 
                    tablename,
                    pg_size_pretty(pg_total_relation_size(tablename::REGCLASS)) as size,
                    pg_total_relation_size(tablename::REGCLASS) / 1024 / 1024.0 as size_mb
                FROM pg_tables
                WHERE tablename LIKE p_table_name || '_%'
                AND schemaname = 'public'
                AND tablename ~ '\\d{4}_\\d{2}$'
                AND TO_DATE(SUBSTRING(tablename FROM '\\d{4}_\\d{2}$'), 'YYYY_MM') < v_archive_date
                ORDER BY tablename
            LOOP
                v_archive_table := 'archive_' || v_partition.tablename;
                
                BEGIN
                    -- Get row count before archiving
                    EXECUTE FORMAT('SELECT COUNT(*) FROM %I', v_partition.tablename) INTO v_rows_count;
                    
                    -- Create archive table (if using separate archive schema)
                    EXECUTE FORMAT(
                        'ALTER TABLE %I RENAME TO %I',
                        v_partition.tablename, v_archive_table
                    );
                    
                    -- Detach from parent table
                    EXECUTE FORMAT(
                        'ALTER TABLE %I NO INHERIT %I',
                        v_archive_table, p_table_name
                    );
                    
                    -- Log archive operation
                    INSERT INTO partition_management_log (
                        table_name, action, partition_name,
                        partition_start_date, partition_end_date,
                        rows_affected, size_mb, success, execution_time_ms
                    ) VALUES (
                        p_table_name, 'archived', v_partition.tablename,
                        TO_DATE(SUBSTRING(v_partition.tablename FROM '\\d{4}_\\d{2}$'), 'YYYY_MM'),
                        TO_DATE(SUBSTRING(v_partition.tablename FROM '\\d{4}_\\d{2}$'), 'YYYY_MM') + INTERVAL '1 month',
                        v_rows_count, v_partition.size_mb, true,
                        EXTRACT(EPOCH FROM (clock_timestamp() - v_start_time)) * 1000
                    );
                    
                    RETURN QUERY SELECT v_partition.tablename::TEXT, true::BOOLEAN, 
                        FORMAT('Archived %s rows, %s', v_rows_count, v_partition.size)::TEXT;
                    
                EXCEPTION
                    WHEN OTHERS THEN
                        -- Log failure
                        INSERT INTO partition_management_log (
                            table_name, action, partition_name,
                            partition_start_date, partition_end_date,
                            success, error_message, execution_time_ms
                        ) VALUES (
                            p_table_name, 'archived', v_partition.tablename,
                            TO_DATE(SUBSTRING(v_partition.tablename FROM '\\d{4}_\\d{2}$'), 'YYYY_MM'),
                            TO_DATE(SUBSTRING(v_partition.tablename FROM '\\d{4}_\\d{2}$'), 'YYYY_MM') + INTERVAL '1 month',
                            false, SQLERRM,
                            EXTRACT(EPOCH FROM (clock_timestamp() - v_start_time)) * 1000
                        );
                        
                        RETURN QUERY SELECT v_partition.tablename::TEXT, false::BOOLEAN, SQLERRM::TEXT;
                END;
            END LOOP;
            
            RETURN;
        END;
        $$;
    """)
    
    # Create function to drop old archived partitions
    op.execute("""
        CREATE OR REPLACE FUNCTION drop_old_partitions(
            p_table_name TEXT,
            p_retention_months INTEGER DEFAULT 12
        )
        RETURNS TABLE(partition_name TEXT, dropped BOOLEAN, message TEXT)
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_partition RECORD;
            v_drop_date DATE;
            v_rows_count BIGINT;
            v_start_time TIMESTAMP;
        BEGIN
            v_start_time := clock_timestamp();
            v_drop_date := DATE_TRUNC('month', CURRENT_DATE - (p_retention_months || ' months')::INTERVAL);
            
            -- Find archived partitions older than retention period
            FOR v_partition IN
                SELECT tablename
                FROM pg_tables
                WHERE tablename LIKE 'archive_' || p_table_name || '_%'
                AND schemaname = 'public'
                AND tablename ~ '\\d{4}_\\d{2}$'
                AND TO_DATE(SUBSTRING(tablename FROM '\\d{4}_\\d{2}$'), 'YYYY_MM') < v_drop_date
                ORDER BY tablename
            LOOP
                BEGIN
                    -- Get row count before dropping
                    EXECUTE FORMAT('SELECT COUNT(*) FROM %I', v_partition.tablename) INTO v_rows_count;
                    
                    -- Drop the archived partition
                    EXECUTE FORMAT('DROP TABLE IF EXISTS %I CASCADE', v_partition.tablename);
                    
                    -- Log drop operation
                    INSERT INTO partition_management_log (
                        table_name, action, partition_name,
                        partition_start_date, partition_end_date,
                        rows_affected, success, execution_time_ms
                    ) VALUES (
                        p_table_name, 'dropped', v_partition.tablename,
                        TO_DATE(SUBSTRING(v_partition.tablename FROM '\\d{4}_\\d{2}$'), 'YYYY_MM'),
                        TO_DATE(SUBSTRING(v_partition.tablename FROM '\\d{4}_\\d{2}$'), 'YYYY_MM') + INTERVAL '1 month',
                        v_rows_count, true,
                        EXTRACT(EPOCH FROM (clock_timestamp() - v_start_time)) * 1000
                    );
                    
                    RETURN QUERY SELECT v_partition.tablename::TEXT, true::BOOLEAN,
                        FORMAT('Dropped %s rows', v_rows_count)::TEXT;
                    
                EXCEPTION
                    WHEN OTHERS THEN
                        RETURN QUERY SELECT v_partition.tablename::TEXT, false::BOOLEAN, SQLERRM::TEXT;
                END;
            END LOOP;
            
            RETURN;
        END;
        $$;
    """)
    
    # Create master maintenance function
    op.execute("""
        CREATE OR REPLACE FUNCTION maintain_partitions()
        RETURNS JSONB
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_config RECORD;
            v_result JSONB := '[]'::JSONB;
            v_operation JSONB;
            v_start_time TIMESTAMP;
        BEGIN
            v_start_time := clock_timestamp();
            
            -- Process each configured table
            FOR v_config IN
                SELECT * FROM partition_management_config
                WHERE is_enabled = true
                AND (next_maintenance_at IS NULL OR next_maintenance_at <= NOW())
            LOOP
                -- Create future partitions
                v_operation := jsonb_build_object(
                    'table', v_config.table_name,
                    'action', 'create_partitions',
                    'results', (
                        SELECT jsonb_agg(row_to_json(t))
                        FROM create_monthly_partitions(v_config.table_name, v_config.future_partitions) t
                    )
                );
                v_result := v_result || v_operation;
                
                -- Archive old partitions
                IF v_config.archive_months > 0 THEN
                    v_operation := jsonb_build_object(
                        'table', v_config.table_name,
                        'action', 'archive_partitions',
                        'results', (
                            SELECT jsonb_agg(row_to_json(t))
                            FROM archive_old_partitions(v_config.table_name, v_config.archive_months) t
                        )
                    );
                    v_result := v_result || v_operation;
                END IF;
                
                -- Drop old archived partitions
                IF v_config.retention_months > 0 THEN
                    v_operation := jsonb_build_object(
                        'table', v_config.table_name,
                        'action', 'drop_partitions',
                        'results', (
                            SELECT jsonb_agg(row_to_json(t))
                            FROM drop_old_partitions(v_config.table_name, v_config.retention_months) t
                        )
                    );
                    v_result := v_result || v_operation;
                END IF;
                
                -- Update next maintenance time
                UPDATE partition_management_config
                SET last_maintenance_at = NOW(),
                    next_maintenance_at = NOW() + INTERVAL '1 day'
                WHERE table_name = v_config.table_name;
            END LOOP;
            
            -- Add summary
            RETURN jsonb_build_object(
                'execution_time_ms', EXTRACT(EPOCH FROM (clock_timestamp() - v_start_time)) * 1000,
                'timestamp', NOW(),
                'operations', v_result
            );
        END;
        $$;
    """)
    
    # Create monitoring function
    op.execute("""
        CREATE OR REPLACE FUNCTION check_partition_health()
        RETURNS TABLE(
            table_name TEXT,
            total_partitions INTEGER,
            future_partitions INTEGER,
            archived_partitions INTEGER,
            total_rows BIGINT,
            total_size_gb NUMERIC,
            oldest_partition DATE,
            newest_partition DATE,
            health_status TEXT,
            alerts JSONB
        )
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_config RECORD;
            v_alerts JSONB;
            v_future_count INTEGER;
            v_archived_count INTEGER;
            v_total_count INTEGER;
            v_total_rows BIGINT;
            v_total_size NUMERIC;
            v_oldest DATE;
            v_newest DATE;
            v_status TEXT;
        BEGIN
            FOR v_config IN
                SELECT * FROM partition_management_config WHERE is_enabled = true
            LOOP
                v_alerts := '[]'::JSONB;
                
                -- Count partitions
                SELECT COUNT(*), SUM(reltuples)::BIGINT, SUM(pg_total_relation_size(oid)) / 1024 / 1024 / 1024.0
                INTO v_total_count, v_total_rows, v_total_size
                FROM pg_class
                WHERE relname LIKE v_config.table_name || '_%'
                AND relkind = 'r';
                
                -- Count future partitions
                SELECT COUNT(*)
                INTO v_future_count
                FROM pg_tables
                WHERE tablename LIKE v_config.table_name || '_%'
                AND tablename ~ '\\d{4}_\\d{2}$'
                AND TO_DATE(SUBSTRING(tablename FROM '\\d{4}_\\d{2}$'), 'YYYY_MM') >= DATE_TRUNC('month', CURRENT_DATE);
                
                -- Count archived partitions
                SELECT COUNT(*)
                INTO v_archived_count
                FROM pg_tables
                WHERE tablename LIKE 'archive_' || v_config.table_name || '_%';
                
                -- Get date range
                SELECT 
                    MIN(TO_DATE(SUBSTRING(tablename FROM '\\d{4}_\\d{2}$'), 'YYYY_MM')),
                    MAX(TO_DATE(SUBSTRING(tablename FROM '\\d{4}_\\d{2}$'), 'YYYY_MM'))
                INTO v_oldest, v_newest
                FROM pg_tables
                WHERE tablename LIKE v_config.table_name || '_%'
                AND tablename ~ '\\d{4}_\\d{2}$';
                
                -- Check health and generate alerts
                v_status := 'healthy';
                
                IF v_future_count < v_config.future_partitions THEN
                    v_alerts := v_alerts || jsonb_build_object(
                        'level', 'warning',
                        'message', FORMAT('Only %s future partitions exist, expected %s', v_future_count, v_config.future_partitions)
                    );
                    v_status := 'warning';
                END IF;
                
                IF v_total_size > 100 THEN
                    v_alerts := v_alerts || jsonb_build_object(
                        'level', 'warning',
                        'message', FORMAT('Total size exceeds 100GB: %.2f GB', v_total_size)
                    );
                END IF;
                
                IF v_config.last_maintenance_at < NOW() - INTERVAL '2 days' THEN
                    v_alerts := v_alerts || jsonb_build_object(
                        'level', 'critical',
                        'message', 'Maintenance has not run in over 2 days'
                    );
                    v_status := 'critical';
                END IF;
                
                RETURN QUERY SELECT
                    v_config.table_name::TEXT,
                    v_total_count,
                    v_future_count,
                    v_archived_count,
                    v_total_rows,
                    v_total_size,
                    v_oldest,
                    v_newest,
                    v_status,
                    v_alerts;
            END LOOP;
            
            RETURN;
        END;
        $$;
    """)
    
    # Add comments
    op.execute("COMMENT ON FUNCTION create_monthly_partitions IS 'Automatically creates future monthly partitions for time-series tables'")
    op.execute("COMMENT ON FUNCTION archive_old_partitions IS 'Moves old partitions to archive storage for cost optimization'")
    op.execute("COMMENT ON FUNCTION drop_old_partitions IS 'Removes archived partitions beyond retention period'")
    op.execute("COMMENT ON FUNCTION maintain_partitions IS 'Master function for automated partition maintenance - run daily via cron/pg_cron'")
    op.execute("COMMENT ON FUNCTION check_partition_health IS 'Monitor partition health and generate alerts for operational issues'")


def downgrade() -> None:
    """Drop partition management system."""
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS check_partition_health()")
    op.execute("DROP FUNCTION IF EXISTS maintain_partitions()")
    op.execute("DROP FUNCTION IF EXISTS drop_old_partitions(TEXT, INTEGER)")
    op.execute("DROP FUNCTION IF EXISTS archive_old_partitions(TEXT, INTEGER)")
    op.execute("DROP FUNCTION IF EXISTS create_monthly_partitions(TEXT, INTEGER)")
    
    # Drop tables
    op.drop_table('partition_management_log')
    op.drop_table('partition_management_config')