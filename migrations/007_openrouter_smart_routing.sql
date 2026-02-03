-- Migration: OpenRouter Smart Routing (Milestone 6)
-- Intelligent model selection and cost optimization

-- Routing policies (defines model selection rules)
CREATE TABLE IF NOT EXISTS routing_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    policy_config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_policies_name 
    ON routing_policies(name);
CREATE INDEX IF NOT EXISTS idx_policies_active 
    ON routing_policies(is_active);

-- Model selections (tracks which model was used for each task)
CREATE TABLE IF NOT EXISTS model_selections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES governance_tasks(id) ON DELETE CASCADE,
    policy_name VARCHAR(50),
    selected_model VARCHAR(100) NOT NULL,
    selected_provider VARCHAR(50) NOT NULL,
    estimated_cost DECIMAL(10,4),
    actual_cost DECIMAL(10,4),
    tokens_used INTEGER,
    response_time_ms INTEGER,
    success BOOLEAN,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_selections_task 
    ON model_selections(task_id);
CREATE INDEX IF NOT EXISTS idx_selections_model 
    ON model_selections(selected_model, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_selections_policy 
    ON model_selections(policy_name, created_at DESC);

-- Model performance (aggregated performance metrics)
CREATE TABLE IF NOT EXISTS model_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    avg_response_time_ms INTEGER,
    total_cost DECIMAL(10,2) DEFAULT 0,
    avg_tokens_used INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_performance_model 
    ON model_performance(model_name, window_end DESC);
CREATE INDEX IF NOT EXISTS idx_performance_window 
    ON model_performance(window_start, window_end);

-- Cost budgets (budget tracking and enforcement)
CREATE TABLE IF NOT EXISTS cost_budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_type VARCHAR(50) NOT NULL,
    budget_period VARCHAR(20) NOT NULL,
    budget_amount DECIMAL(10,2) NOT NULL,
    spent_amount DECIMAL(10,2) DEFAULT 0,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    alert_threshold DECIMAL(5,2) DEFAULT 0.80,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_budgets_period 
    ON cost_budgets(budget_period, period_start DESC);
CREATE INDEX IF NOT EXISTS idx_budgets_active 
    ON cost_budgets(is_active, budget_period);

-- Comments for documentation
COMMENT ON TABLE routing_policies IS 'Model selection policies for different task types';
COMMENT ON TABLE model_selections IS 'Tracks which model was used for each task';
COMMENT ON TABLE model_performance IS 'Aggregated performance metrics per model';
COMMENT ON TABLE cost_budgets IS 'Budget tracking and enforcement';

-- Insert default routing policies
INSERT INTO routing_policies (name, description, policy_config)
VALUES 
    (
        'normal',
        'Balanced cost and performance for general tasks',
        '{
            "models": [
                {"provider": "openai", "model": "gpt-4o-mini", "priority": 1},
                {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022", "priority": 2}
            ],
            "max_cost_per_task": 0.10,
            "max_tokens": 4000,
            "temperature": 0.7
        }'::jsonb
    ),
    (
        'deep_research',
        'Maximum intelligence for complex analysis',
        '{
            "models": [
                {"provider": "openai", "model": "gpt-4o", "priority": 1},
                {"provider": "anthropic", "model": "claude-3-opus-20240229", "priority": 2}
            ],
            "max_cost_per_task": 1.00,
            "max_tokens": 8000,
            "temperature": 0.7
        }'::jsonb
    ),
    (
        'code',
        'Specialized for code analysis and debugging',
        '{
            "models": [
                {"provider": "openai", "model": "gpt-4o", "priority": 1},
                {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022", "priority": 2}
            ],
            "max_cost_per_task": 0.50,
            "max_tokens": 6000,
            "temperature": 0.3
        }'::jsonb
    ),
    (
        'ops',
        'Ultra-cheap for simple operational tasks',
        '{
            "models": [
                {"provider": "openai", "model": "gpt-3.5-turbo", "priority": 1},
                {"provider": "anthropic", "model": "claude-3-haiku-20240307", "priority": 2}
            ],
            "max_cost_per_task": 0.01,
            "max_tokens": 2000,
            "temperature": 0.5
        }'::jsonb
    )
ON CONFLICT (name) DO NOTHING;

-- Insert default daily budget
INSERT INTO cost_budgets (budget_type, budget_period, budget_amount, period_start, period_end)
VALUES (
    'total',
    'daily',
    10.00,
    DATE_TRUNC('day', NOW()),
    DATE_TRUNC('day', NOW() + INTERVAL '1 day')
)
ON CONFLICT DO NOTHING;
