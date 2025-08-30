"""Create Row Level Security (RLS) policies for tenant isolation

Revision ID: 006_create_rls_policies
Revises: 005_create_rule_effectiveness
Create Date: 2025-01-15 11:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006_create_rls_policies'
down_revision = '005_create_rule_effectiveness'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Enable Row Level Security (RLS) for complete tenant isolation.
    
    Principle: Defense in depth - RLS ensures tenant isolation even if application queries miss tenant_id filters.
    Critical for multi-tenant security compliance.
    """
    
    # Enable RLS on all tables
    tables = ['rule_sets', 'rule_versions', 'correction_logs', 'suggestions']
    
    for table in tables:
        # Enable RLS
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        
        # Create policy for tenant isolation
        # Users can only access rows from their own tenant
        op.execute(f"""
            CREATE POLICY tenant_isolation_policy ON {table}
            FOR ALL 
            USING (tenant_id = current_setting('app.current_tenant_id', true))
        """)
        
        # Create bypass policy for superusers and system processes
        op.execute(f"""
            CREATE POLICY bypass_rls_policy ON {table}
            FOR ALL 
            TO validahub_admin, validahub_system
            USING (true)
        """)
    
    # Create specialized policies for correction_logs (partitioned table)
    # Additional security for high-volume audit data
    op.execute("""
        CREATE POLICY correction_logs_read_policy ON correction_logs
        FOR SELECT
        USING (
            tenant_id = current_setting('app.current_tenant_id', true)
            AND created_at >= NOW() - INTERVAL '2 years'  -- Limit historical access
        )
    """)
    
    op.execute("""
        CREATE POLICY correction_logs_insert_policy ON correction_logs
        FOR INSERT
        WITH CHECK (
            tenant_id = current_setting('app.current_tenant_id', true)
            AND created_by = current_setting('app.current_user_id', true)
        )
    """)
    
    op.execute("""
        CREATE POLICY correction_logs_update_policy ON correction_logs
        FOR UPDATE
        USING (
            tenant_id = current_setting('app.current_tenant_id', true)
            AND status IN ('pending', 'approved')  -- Only allow updates on specific statuses
        )
        WITH CHECK (
            tenant_id = current_setting('app.current_tenant_id', true)
        )
    """)
    
    # Create database roles for different access patterns
    # Application service role
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'validahub_app') THEN
                CREATE ROLE validahub_app NOLOGIN;
            END IF;
        END $$;
    """)
    
    # Read-only analytics role
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'validahub_analytics') THEN
                CREATE ROLE validahub_analytics NOLOGIN;
            END IF;
        END $$;
    """)
    
    # Admin role for system operations
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'validahub_admin') THEN
                CREATE ROLE validahub_admin NOLOGIN BYPASSRLS;
            END IF;
        END $$;
    """)
    
    # System role for automated processes
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'validahub_system') THEN
                CREATE ROLE validahub_system NOLOGIN BYPASSRLS;
            END IF;
        END $$;
    """)
    
    # Grant appropriate permissions
    for table in tables:
        # Application role - full CRUD within tenant
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO validahub_app")
        
        # Analytics role - read-only access with RLS
        op.execute(f"GRANT SELECT ON {table} TO validahub_analytics")
        
        # Admin role - full access without RLS restrictions
        op.execute(f"GRANT ALL ON {table} TO validahub_admin")
        
        # System role - full access for migrations and maintenance
        op.execute(f"GRANT ALL ON {table} TO validahub_system")
    
    # Special permissions for materialized view
    op.execute("GRANT SELECT ON rule_effectiveness TO validahub_app, validahub_analytics, validahub_admin")
    op.execute("GRANT ALL ON rule_effectiveness TO validahub_system")  # Needs refresh permissions
    
    # Create security functions
    op.execute("""
        CREATE OR REPLACE FUNCTION set_tenant_context(tenant_id TEXT, user_id TEXT DEFAULT NULL)
        RETURNS VOID AS $$
        BEGIN
            -- Validate tenant_id format
            IF tenant_id !~ '^t_[a-z0-9_]{1,47}$' THEN
                RAISE EXCEPTION 'Invalid tenant_id format: %', tenant_id;
            END IF;
            
            -- Set session variables for RLS
            PERFORM set_config('app.current_tenant_id', tenant_id, false);
            
            IF user_id IS NOT NULL THEN
                PERFORM set_config('app.current_user_id', user_id, false);
            END IF;
            
            -- Log security context change
            RAISE NOTICE 'Tenant context set to: %', tenant_id;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
    """)
    
    op.execute("""
        CREATE OR REPLACE FUNCTION clear_tenant_context()
        RETURNS VOID AS $$
        BEGIN
            -- Clear session variables
            PERFORM set_config('app.current_tenant_id', '', false);
            PERFORM set_config('app.current_user_id', '', false);
            
            RAISE NOTICE 'Tenant context cleared';
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
    """)
    
    op.execute("""
        CREATE OR REPLACE FUNCTION get_current_tenant()
        RETURNS TEXT AS $$
        BEGIN
            RETURN current_setting('app.current_tenant_id', true);
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
    """)
    
    # Create audit function for RLS violations
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_rls_violation()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Log potential security violations
            RAISE WARNING 'Potential RLS violation: table=%, operation=%, user=%, tenant=%', 
                TG_TABLE_NAME, TG_OP, current_user, current_setting('app.current_tenant_id', true);
            
            -- You could also write to an audit log table here
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Add comments for security documentation
    op.execute("""
        COMMENT ON FUNCTION set_tenant_context(TEXT, TEXT) IS 
        'Sets tenant context for RLS policies. Must be called before database operations.';
    """)
    
    op.execute("""
        COMMENT ON FUNCTION clear_tenant_context() IS 
        'Clears tenant context. Should be called at end of request lifecycle.';
    """)
    
    op.execute("""
        COMMENT ON FUNCTION get_current_tenant() IS 
        'Returns current tenant ID from session context.';
    """)


def downgrade() -> None:
    """Disable RLS and drop all policies and security functions."""
    
    # Drop security functions
    op.execute("DROP FUNCTION IF EXISTS audit_rls_violation() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS get_current_tenant() CASCADE") 
    op.execute("DROP FUNCTION IF EXISTS clear_tenant_context() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS set_tenant_context(TEXT, TEXT) CASCADE")
    
    # Disable RLS and drop policies
    tables = ['rule_sets', 'rule_versions', 'correction_logs', 'suggestions']
    
    for table in tables:
        op.execute(f"DROP POLICY IF EXISTS bypass_rls_policy ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    
    # Drop specialized correction_logs policies
    op.execute("DROP POLICY IF EXISTS correction_logs_update_policy ON correction_logs")
    op.execute("DROP POLICY IF EXISTS correction_logs_insert_policy ON correction_logs")
    op.execute("DROP POLICY IF EXISTS correction_logs_read_policy ON correction_logs")
    
    # Note: We don't drop roles in downgrade to avoid breaking existing connections
    # Roles should be managed separately in production