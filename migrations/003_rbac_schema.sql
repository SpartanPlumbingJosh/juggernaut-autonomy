-- Migration: 003_rbac_schema.sql

-- Tool definitions with risk levels
CREATE TABLE IF NOT EXISTS mcp_tool_definitions (
    tool_name VARCHAR(100) PRIMARY KEY,
    description TEXT,
    risk_level VARCHAR(20) DEFAULT 'medium',  -- low, medium, high, critical
    requires_approval BOOLEAN DEFAULT FALSE,
    approval_threshold_usd DECIMAL(10,2),
    rate_limit_per_minute INTEGER DEFAULT 60,
    rate_limit_per_hour INTEGER DEFAULT 500,
    allowed_workers TEXT[] DEFAULT ARRAY['EXECUTOR', 'ANALYST', 'STRATEGIST', 'ORCHESTRATOR', 'WATCHDOG'],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed with current MCP tools
INSERT INTO mcp_tool_definitions (tool_name, risk_level, requires_approval) VALUES
    ('sql_query', 'medium', false),
    ('github_create_pr', 'high', true),
    ('github_merge_pr', 'critical', true),
    ('github_put_file', 'high', true),
    ('railway_redeploy', 'high', true),
    ('email_send', 'high', true),
    ('hq_execute', 'medium', false),
    ('web_search', 'low', false),
    ('fetch_url', 'low', false),
    ('war_room_post', 'medium', false),
    ('calendar_create', 'medium', true),
    ('sheets_write', 'medium', false),
    ('social_post_twitter', 'critical', true),
    ('social_post_facebook', 'critical', true),
    ('storage_upload', 'medium', false),
    ('storage_delete', 'high', true),
    ('puppeteer_healthcheck', 'low', false),
    ('learning_query', 'low', false),
    ('learning_apply', 'medium', false),
    ('experiment_list', 'low', false),
    ('experiment_progress', 'low', false),
    ('opportunity_scan_run', 'medium', false),
    ('code_executor', 'high', true)
ON CONFLICT (tool_name) DO NOTHING;

-- Worker permissions
CREATE TABLE IF NOT EXISTS worker_tool_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id VARCHAR(100) NOT NULL,
    tool_name VARCHAR(100) REFERENCES mcp_tool_definitions(tool_name),
    permission_level VARCHAR(20) DEFAULT 'execute',  -- read, execute, admin
    max_calls_per_day INTEGER,
    requires_approval_override BOOLEAN,
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_until TIMESTAMPTZ,
    granted_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(worker_id, tool_name)
);

-- Budget tracking per worker
CREATE TABLE IF NOT EXISTS worker_budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id VARCHAR(100) NOT NULL UNIQUE,
    budget_type VARCHAR(50) DEFAULT 'usd',
    daily_limit DECIMAL(15,2) DEFAULT 10.00,
    weekly_limit DECIMAL(15,2) DEFAULT 50.00,
    monthly_limit DECIMAL(15,2) DEFAULT 200.00,
    current_daily_usage DECIMAL(15,2) DEFAULT 0,
    current_weekly_usage DECIMAL(15,2) DEFAULT 0,
    current_monthly_usage DECIMAL(15,2) DEFAULT 0,
    hard_stop_enabled BOOLEAN DEFAULT TRUE,
    last_reset_daily TIMESTAMPTZ DEFAULT NOW(),
    last_reset_weekly TIMESTAMPTZ DEFAULT NOW(),
    last_reset_monthly TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default budgets for existing workers
INSERT INTO worker_budgets (worker_id, daily_limit, weekly_limit, monthly_limit) VALUES
    ('EXECUTOR', 20.00, 100.00, 400.00),
    ('ANALYST', 15.00, 75.00, 300.00),
    ('STRATEGIST', 25.00, 125.00, 500.00),
    ('ORCHESTRATOR', 30.00, 150.00, 600.00),
    ('WATCHDOG', 5.00, 25.00, 100.00)
ON CONFLICT (worker_id) DO NOTHING;

-- Tool execution tracking
CREATE TABLE IF NOT EXISTS tool_execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id VARCHAR(100) NOT NULL,
    tool_name VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, success, failed, denied
    parameters JSONB,
    result JSONB,
    error_message TEXT,
    cost_usd DECIMAL(10,4),
    duration_ms INTEGER,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    task_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_exec_worker ON tool_execution_logs(worker_id);
CREATE INDEX IF NOT EXISTS idx_tool_exec_tool ON tool_execution_logs(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_exec_status ON tool_execution_logs(status);
CREATE INDEX IF NOT EXISTS idx_tool_exec_created ON tool_execution_logs(created_at);

-- Function to check if a worker has permission to use a tool
CREATE OR REPLACE FUNCTION check_tool_permission(
    p_worker_id VARCHAR(100),
    p_tool_name VARCHAR(100)
) RETURNS TABLE (
    allowed BOOLEAN,
    reason TEXT,
    requires_approval BOOLEAN,
    permission_level VARCHAR(20),
    daily_calls_remaining INTEGER
) AS $$
DECLARE
    v_tool_def RECORD;
    v_permission RECORD;
    v_budget RECORD;
    v_daily_calls INTEGER;
BEGIN
    -- Get tool definition
    SELECT * INTO v_tool_def FROM mcp_tool_definitions WHERE tool_name = p_tool_name;
    
    IF NOT FOUND THEN
        RETURN QUERY SELECT 
            FALSE, 
            'Tool not found: ' || p_tool_name, 
            FALSE, 
            NULL::VARCHAR(20),
            0;
        RETURN;
    END IF;
    
    -- Check if worker is in allowed_workers array
    IF v_tool_def.allowed_workers IS NOT NULL AND 
       NOT p_worker_id = ANY(v_tool_def.allowed_workers) THEN
        RETURN QUERY SELECT 
            FALSE, 
            'Worker ' || p_worker_id || ' not authorized to use ' || p_tool_name, 
            FALSE, 
            NULL::VARCHAR(20),
            0;
        RETURN;
    END IF;
    
    -- Get specific permission if exists
    SELECT * INTO v_permission 
    FROM worker_tool_permissions 
    WHERE worker_id = p_worker_id AND tool_name = p_tool_name
    AND (valid_until IS NULL OR valid_until > NOW());
    
    -- Get budget info
    SELECT * INTO v_budget
    FROM worker_budgets
    WHERE worker_id = p_worker_id;
    
    -- Count daily calls
    SELECT COUNT(*) INTO v_daily_calls
    FROM tool_execution_logs
    WHERE worker_id = p_worker_id 
    AND tool_name = p_tool_name
    AND started_at > (NOW() - INTERVAL '24 hours');
    
    -- Determine max calls per day
    DECLARE
        v_max_calls INTEGER;
    BEGIN
        IF v_permission.max_calls_per_day IS NOT NULL THEN
            v_max_calls := v_permission.max_calls_per_day;
        ELSE
            -- Default to rate_limit_per_hour * 24 if not specified
            v_max_calls := COALESCE(v_tool_def.rate_limit_per_hour, 100) * 24;
        END IF;
        
        -- Check if over daily limit
        IF v_daily_calls >= v_max_calls THEN
            RETURN QUERY SELECT 
                FALSE, 
                'Daily call limit exceeded for ' || p_tool_name, 
                FALSE, 
                COALESCE(v_permission.permission_level, 'execute'),
                0;
            RETURN;
        END IF;
    END;
    
    -- Check if requires approval
    DECLARE
        v_requires_approval BOOLEAN;
    BEGIN
        IF v_permission.requires_approval_override IS NOT NULL THEN
            v_requires_approval := v_permission.requires_approval_override;
        ELSE
            v_requires_approval := COALESCE(v_tool_def.requires_approval, FALSE);
        END IF;
        
        RETURN QUERY SELECT 
            TRUE, 
            'Permission granted', 
            v_requires_approval, 
            COALESCE(v_permission.permission_level, 'execute'),
            v_max_calls - v_daily_calls;
    END;
END;
$$ LANGUAGE plpgsql;
