-- Migration: 007_cost_tracking.sql

-- Create API cost tracking table
CREATE TABLE IF NOT EXISTS api_cost_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service VARCHAR(100) NOT NULL,
    cost_usd DECIMAL(10,4) NOT NULL,
    worker_id VARCHAR(100) NOT NULL,
    request_id UUID,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_cost_service ON api_cost_tracking(service);
CREATE INDEX IF NOT EXISTS idx_cost_worker ON api_cost_tracking(worker_id);
CREATE INDEX IF NOT EXISTS idx_cost_created ON api_cost_tracking(created_at);

-- Create worker budgets table if not exists (may already be created in RBAC schema)
CREATE TABLE IF NOT EXISTS worker_budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id VARCHAR(100) NOT NULL UNIQUE,
    budget_type VARCHAR(50) DEFAULT 'usd',
    daily_limit DECIMAL(15,2) DEFAULT 50.00,
    weekly_limit DECIMAL(15,2) DEFAULT 250.00,
    monthly_limit DECIMAL(15,2) DEFAULT 1000.00,
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

-- Insert default budgets for existing workers if not already done
INSERT INTO worker_budgets (worker_id, daily_limit, weekly_limit, monthly_limit)
VALUES
    ('EXECUTOR', 20.00, 100.00, 400.00),
    ('ANALYST', 15.00, 75.00, 300.00),
    ('STRATEGIST', 25.00, 125.00, 500.00),
    ('ORCHESTRATOR', 30.00, 150.00, 600.00),
    ('WATCHDOG', 5.00, 25.00, 100.00)
ON CONFLICT (worker_id) DO NOTHING;

-- Create service budget limits table
CREATE TABLE IF NOT EXISTS service_budget_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service VARCHAR(100) NOT NULL UNIQUE,
    daily_limit DECIMAL(15,2) DEFAULT 20.00,
    weekly_limit DECIMAL(15,2) DEFAULT 100.00,
    monthly_limit DECIMAL(15,2) DEFAULT 400.00,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default service budget limits
INSERT INTO service_budget_limits (service, daily_limit, weekly_limit, monthly_limit)
VALUES
    ('openrouter', 20.00, 100.00, 400.00),
    ('anthropic', 15.00, 75.00, 300.00),
    ('openai', 15.00, 75.00, 300.00)
ON CONFLICT (service) DO NOTHING;

-- Create cost alerts table
CREATE TABLE IF NOT EXISTS cost_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(50) NOT NULL, -- 'daily_limit', 'weekly_limit', 'monthly_limit', 'service_limit', 'worker_limit'
    service VARCHAR(100),
    worker_id VARCHAR(100),
    threshold_usd DECIMAL(15,2) NOT NULL,
    current_usage_usd DECIMAL(15,2) NOT NULL,
    percentage DECIMAL(5,2) NOT NULL,
    alerted_at TIMESTAMPTZ DEFAULT NOW(),
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMPTZ
);

-- Create index for cost alerts
CREATE INDEX IF NOT EXISTS idx_cost_alerts_type ON cost_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_service ON cost_alerts(service);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_worker ON cost_alerts(worker_id);

-- Function to check and create cost alerts
CREATE OR REPLACE FUNCTION check_cost_alerts()
RETURNS TABLE (
    alert_id UUID,
    alert_type VARCHAR(50),
    service VARCHAR(100),
    worker_id VARCHAR(100),
    threshold_usd DECIMAL(15,2),
    current_usage_usd DECIMAL(15,2),
    percentage DECIMAL(5,2)
) AS $$
DECLARE
    alert_threshold DECIMAL(5,2) := 0.8; -- Alert at 80% of limit
    v_alert_id UUID;
    v_percentage DECIMAL(5,2);
BEGIN
    -- Check overall daily limit
    SELECT 
        SUM(cost_usd) INTO current_usage_usd
    FROM api_cost_tracking
    WHERE created_at > NOW() - INTERVAL '24 hours';
    
    SELECT 
        AVG(daily_limit) INTO threshold_usd
    FROM worker_budgets;
    
    IF threshold_usd IS NULL THEN
        threshold_usd := 50.00; -- Default
    END IF;
    
    v_percentage := CASE WHEN threshold_usd > 0 THEN current_usage_usd / threshold_usd ELSE 0 END;
    
    IF v_percentage >= alert_threshold THEN
        INSERT INTO cost_alerts (
            alert_type, threshold_usd, current_usage_usd, percentage
        ) VALUES (
            'daily_limit', threshold_usd, current_usage_usd, v_percentage
        )
        ON CONFLICT DO NOTHING
        RETURNING id INTO v_alert_id;
        
        IF v_alert_id IS NOT NULL THEN
            alert_id := v_alert_id;
            alert_type := 'daily_limit';
            service := NULL;
            worker_id := NULL;
            RETURN NEXT;
        END IF;
    END IF;
    
    -- Check service-specific limits
    FOR service, threshold_usd IN 
        SELECT service, daily_limit FROM service_budget_limits
    LOOP
        SELECT 
            SUM(cost_usd) INTO current_usage_usd
        FROM api_cost_tracking
        WHERE service = service
          AND created_at > NOW() - INTERVAL '24 hours';
        
        IF current_usage_usd IS NULL THEN
            current_usage_usd := 0;
        END IF;
        
        v_percentage := CASE WHEN threshold_usd > 0 THEN current_usage_usd / threshold_usd ELSE 0 END;
        
        IF v_percentage >= alert_threshold THEN
            INSERT INTO cost_alerts (
                alert_type, service, threshold_usd, current_usage_usd, percentage
            ) VALUES (
                'service_limit', service, threshold_usd, current_usage_usd, v_percentage
            )
            ON CONFLICT DO NOTHING
            RETURNING id INTO v_alert_id;
            
            IF v_alert_id IS NOT NULL THEN
                alert_id := v_alert_id;
                alert_type := 'service_limit';
                worker_id := NULL;
                RETURN NEXT;
            END IF;
        END IF;
    END LOOP;
    
    -- Check worker-specific limits
    FOR worker_id, threshold_usd IN 
        SELECT worker_id, daily_limit FROM worker_budgets
    LOOP
        SELECT 
            SUM(cost_usd) INTO current_usage_usd
        FROM api_cost_tracking
        WHERE worker_id = worker_id
          AND created_at > NOW() - INTERVAL '24 hours';
        
        IF current_usage_usd IS NULL THEN
            current_usage_usd := 0;
        END IF;
        
        v_percentage := CASE WHEN threshold_usd > 0 THEN current_usage_usd / threshold_usd ELSE 0 END;
        
        IF v_percentage >= alert_threshold THEN
            INSERT INTO cost_alerts (
                alert_type, worker_id, threshold_usd, current_usage_usd, percentage
            ) VALUES (
                'worker_limit', worker_id, threshold_usd, current_usage_usd, v_percentage
            )
            ON CONFLICT DO NOTHING
            RETURNING id INTO v_alert_id;
            
            IF v_alert_id IS NOT NULL THEN
                alert_id := v_alert_id;
                alert_type := 'worker_limit';
                service := NULL;
                RETURN NEXT;
            END IF;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
