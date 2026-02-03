-- Migration: Self-Heal Workflows (Milestone 2)
-- Adds playbook system for automated diagnosis and repair

-- Self-heal playbooks (reusable diagnosis/repair procedures)
CREATE TABLE IF NOT EXISTS self_heal_playbooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    playbook_type VARCHAR(50) NOT NULL, -- 'diagnosis' or 'repair'
    steps JSONB NOT NULL, -- Array of step definitions
    max_steps INTEGER DEFAULT 10,
    safe_actions_only BOOLEAN DEFAULT true,
    requires_approval BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_playbooks_type 
    ON self_heal_playbooks(playbook_type);
CREATE INDEX IF NOT EXISTS idx_playbooks_name 
    ON self_heal_playbooks(name);

-- Self-heal execution history
CREATE TABLE IF NOT EXISTS self_heal_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    playbook_id UUID REFERENCES self_heal_playbooks(id) ON DELETE CASCADE,
    playbook_name VARCHAR(100) NOT NULL,
    execution_type VARCHAR(50) NOT NULL, -- 'diagnosis', 'repair', 'auto_heal'
    status VARCHAR(50) DEFAULT 'running', -- 'running', 'completed', 'failed', 'stopped'
    trigger_reason TEXT,
    steps_completed INTEGER DEFAULT 0,
    steps_total INTEGER,
    current_step JSONB,
    results JSONB, -- Array of step results
    findings JSONB, -- Diagnosis findings
    actions_taken JSONB, -- Repair actions taken
    verification_result JSONB, -- Post-repair verification
    error_message TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    created_by VARCHAR(100), -- 'system', 'user', or user_id
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_executions_playbook 
    ON self_heal_executions(playbook_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_executions_status 
    ON self_heal_executions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_executions_type 
    ON self_heal_executions(execution_type, created_at DESC);

-- System health snapshots (for trend analysis)
CREATE TABLE IF NOT EXISTS system_health_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_type VARCHAR(50) NOT NULL, -- 'pre_diagnosis', 'post_repair', 'scheduled'
    execution_id UUID REFERENCES self_heal_executions(id) ON DELETE SET NULL,
    metrics JSONB NOT NULL, -- Health metrics at snapshot time
    issues_detected JSONB, -- Array of detected issues
    severity VARCHAR(50), -- 'healthy', 'warning', 'critical'
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_type 
    ON system_health_snapshots(snapshot_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_execution 
    ON system_health_snapshots(execution_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_severity 
    ON system_health_snapshots(severity, created_at DESC);

-- Auto-heal rules (when to trigger automatic healing)
CREATE TABLE IF NOT EXISTS auto_heal_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    condition_type VARCHAR(50) NOT NULL, -- 'error_rate', 'queue_blocked', 'worker_offline', etc
    condition_threshold JSONB NOT NULL, -- Threshold values
    playbook_id UUID REFERENCES self_heal_playbooks(id) ON DELETE CASCADE,
    enabled BOOLEAN DEFAULT true,
    cooldown_minutes INTEGER DEFAULT 30, -- Min time between triggers
    last_triggered_at TIMESTAMP,
    trigger_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auto_heal_rules_enabled 
    ON auto_heal_rules(enabled, condition_type);

-- Comments for documentation
COMMENT ON TABLE self_heal_playbooks IS 'Reusable diagnosis and repair procedures';
COMMENT ON TABLE self_heal_executions IS 'History of self-heal workflow executions';
COMMENT ON TABLE system_health_snapshots IS 'Point-in-time system health metrics';
COMMENT ON TABLE auto_heal_rules IS 'Rules for triggering automatic healing';
