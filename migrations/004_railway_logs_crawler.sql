-- Migration: Railway Logs Crawler (Milestone 3)
-- Automatic error detection and fingerprinting from Railway logs

-- Railway logs storage
CREATE TABLE IF NOT EXISTS railway_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(100),
    environment_id VARCHAR(100),
    log_level VARCHAR(20), -- 'ERROR', 'CRITICAL', 'WARNING', 'INFO'
    message TEXT,
    timestamp TIMESTAMP,
    raw_log JSONB,
    fingerprint VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_railway_logs_fingerprint 
    ON railway_logs(fingerprint);
CREATE INDEX IF NOT EXISTS idx_railway_logs_level 
    ON railway_logs(log_level, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_railway_logs_timestamp 
    ON railway_logs(timestamp DESC);

-- Error fingerprints (deduplicated errors)
CREATE TABLE IF NOT EXISTS error_fingerprints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fingerprint VARCHAR(64) UNIQUE NOT NULL,
    normalized_message TEXT NOT NULL,
    error_type VARCHAR(100),
    first_seen TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL,
    occurrence_count INTEGER DEFAULT 1,
    sample_log_id UUID REFERENCES railway_logs(id),
    stack_trace TEXT,
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'resolved', 'ignored'
    task_created BOOLEAN DEFAULT FALSE,
    task_id UUID, -- Reference to governance_tasks if created
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_error_fingerprints_fingerprint 
    ON error_fingerprints(fingerprint);
CREATE INDEX IF NOT EXISTS idx_error_fingerprints_status 
    ON error_fingerprints(status, last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_error_fingerprints_count 
    ON error_fingerprints(occurrence_count DESC);

-- Error occurrences (individual instances)
CREATE TABLE IF NOT EXISTS error_occurrences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fingerprint_id UUID REFERENCES error_fingerprints(id) ON DELETE CASCADE,
    log_id UUID REFERENCES railway_logs(id) ON DELETE CASCADE,
    occurred_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_error_occurrences_fingerprint 
    ON error_occurrences(fingerprint_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_occurrences_time 
    ON error_occurrences(occurred_at DESC);

-- Log crawler state (tracks last run)
CREATE TABLE IF NOT EXISTS log_crawler_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    last_run TIMESTAMP,
    last_log_timestamp TIMESTAMP,
    logs_processed INTEGER DEFAULT 0,
    errors_found INTEGER DEFAULT 0,
    tasks_created INTEGER DEFAULT 0,
    run_duration_ms INTEGER,
    status VARCHAR(50) DEFAULT 'idle', -- 'idle', 'running', 'error'
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Alert rules (when to create tasks)
CREATE TABLE IF NOT EXISTS log_alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    rule_type VARCHAR(50) NOT NULL, -- 'new_fingerprint', 'spike', 'sustained', 'critical'
    condition JSONB NOT NULL, -- Rule-specific conditions
    action VARCHAR(50) DEFAULT 'create_task', -- 'create_task', 'send_alert', 'ignore'
    enabled BOOLEAN DEFAULT TRUE,
    last_triggered TIMESTAMP,
    trigger_count INTEGER DEFAULT 0,
    cooldown_minutes INTEGER DEFAULT 30,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_log_alert_rules_enabled 
    ON log_alert_rules(enabled, rule_type);

-- Comments for documentation
COMMENT ON TABLE railway_logs IS 'Raw logs fetched from Railway API';
COMMENT ON TABLE error_fingerprints IS 'Deduplicated error patterns with occurrence tracking';
COMMENT ON TABLE error_occurrences IS 'Individual error instances linked to fingerprints';
COMMENT ON TABLE log_crawler_state IS 'State tracking for log crawler scheduler';
COMMENT ON TABLE log_alert_rules IS 'Rules for triggering alerts and task creation';

-- Insert default alert rules
INSERT INTO log_alert_rules (name, rule_type, condition, action, enabled, cooldown_minutes)
VALUES 
    ('New Error Fingerprint', 'new_fingerprint', '{"threshold": 1}'::jsonb, 'create_task', true, 30),
    ('Error Spike', 'spike', '{"rate_per_minute": 10, "window_minutes": 5}'::jsonb, 'create_task', true, 60),
    ('Sustained Error', 'sustained', '{"duration_minutes": 5, "min_occurrences": 3}'::jsonb, 'create_task', true, 30),
    ('Critical Error', 'critical', '{"level": "CRITICAL"}'::jsonb, 'create_task', true, 15)
ON CONFLICT (name) DO NOTHING;
