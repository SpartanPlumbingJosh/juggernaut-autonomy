-- =============================================================================
-- JUGGERNAUT Phase 5: Proactive Systems - Database Migration
-- =============================================================================
-- 
-- This migration adds tables for:
-- - 5.1 Opportunity Scanner (opportunity_scans)
-- - 5.2 Monitoring System (system_metrics, anomaly_events, health_checks)
-- - 5.3 Scheduled Tasks (scheduled_tasks, scheduled_task_runs)
--
-- Run with: Execute queries via Neon SQL over HTTP or psql
-- =============================================================================

-- =============================================================================
-- PHASE 5.1: OPPORTUNITY SCANNER TABLES
-- =============================================================================

-- Table: opportunity_scans - Track scan runs
CREATE TABLE IF NOT EXISTS opportunity_scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_type VARCHAR(50) NOT NULL,
    source VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    opportunities_found INTEGER DEFAULT 0,
    opportunities_qualified INTEGER DEFAULT 0,
    opportunities_duplicates INTEGER DEFAULT 0,
    scan_config JSONB DEFAULT '{}',
    results_summary JSONB DEFAULT '{}',
    error_message TEXT,
    triggered_by VARCHAR(100),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_opportunity_scans_status 
    ON opportunity_scans(status);
CREATE INDEX IF NOT EXISTS idx_opportunity_scans_type_time 
    ON opportunity_scans(scan_type, started_at DESC);

-- =============================================================================
-- PHASE 5.2: MONITORING SYSTEM TABLES
-- =============================================================================

-- Table: system_metrics - Time-series metrics storage
CREATE TABLE IF NOT EXISTS system_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name VARCHAR(100) NOT NULL,
    metric_type VARCHAR(30) NOT NULL CHECK (metric_type IN ('counter', 'gauge', 'histogram', 'summary')),
    value NUMERIC(20, 6) NOT NULL,
    unit VARCHAR(30),
    component VARCHAR(100),
    worker_id VARCHAR(100),
    tags JSONB DEFAULT '{}',
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_metrics_name_time 
    ON system_metrics(metric_name, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_metrics_component 
    ON system_metrics(component, recorded_at DESC);

-- Table: anomaly_events - Detected anomalies
CREATE TABLE IF NOT EXISTS anomaly_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    anomaly_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    component VARCHAR(100) NOT NULL,
    metric_name VARCHAR(100),
    expected_value NUMERIC(20, 6),
    actual_value NUMERIC(20, 6),
    deviation_percent NUMERIC(10, 2),
    description TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'investigating', 'resolved', 'false_positive')),
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),
    resolution_notes TEXT,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_anomaly_events_status 
    ON anomaly_events(status) WHERE status = 'open';
CREATE INDEX IF NOT EXISTS idx_anomaly_events_severity 
    ON anomaly_events(severity, detected_at DESC);

-- Table: health_checks - Component health status
CREATE TABLE IF NOT EXISTS health_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component VARCHAR(100) NOT NULL,
    check_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('healthy', 'degraded', 'unhealthy', 'unknown')),
    response_time_ms INTEGER,
    last_check_at TIMESTAMPTZ DEFAULT NOW(),
    error_message TEXT,
    consecutive_failures INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    UNIQUE(component, check_type)
);

CREATE INDEX IF NOT EXISTS idx_health_checks_component 
    ON health_checks(component);
CREATE INDEX IF NOT EXISTS idx_health_checks_status 
    ON health_checks(status) WHERE status != 'healthy';

-- =============================================================================
-- PHASE 5.3: SCHEDULED TASKS TABLES
-- =============================================================================

-- Table: scheduled_tasks - Task definitions
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    task_type VARCHAR(50) NOT NULL,
    cron_expression VARCHAR(100),
    interval_seconds INTEGER,
    schedule_type VARCHAR(20) DEFAULT 'cron' CHECK (schedule_type IN ('cron', 'interval', 'once')),
    next_run_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    last_run_status VARCHAR(20) CHECK (last_run_status IN ('success', 'failed', 'skipped', 'running')),
    last_run_result JSONB,
    last_run_duration_ms INTEGER,
    consecutive_failures INTEGER DEFAULT 0,
    max_consecutive_failures INTEGER DEFAULT 3,
    enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 5,
    dependencies JSONB DEFAULT '[]',
    config JSONB DEFAULT '{}',
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_next_run 
    ON scheduled_tasks(next_run_at) WHERE enabled = true;
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_type 
    ON scheduled_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_enabled 
    ON scheduled_tasks(enabled) WHERE enabled = true;

-- Table: scheduled_task_runs - Run history
CREATE TABLE IF NOT EXISTS scheduled_task_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES scheduled_tasks(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'running' CHECK (status IN ('running', 'success', 'failed', 'skipped', 'timeout')),
    result JSONB,
    error_message TEXT,
    duration_ms INTEGER,
    triggered_by VARCHAR(100) DEFAULT 'scheduler',
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_scheduled_task_runs_task_id 
    ON scheduled_task_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_task_runs_status 
    ON scheduled_task_runs(status) WHERE status = 'running';
CREATE INDEX IF NOT EXISTS idx_scheduled_task_runs_time 
    ON scheduled_task_runs(started_at DESC);

-- =============================================================================
-- VIEWS FOR REPORTING
-- =============================================================================

-- View: Active scheduled tasks with next run info
CREATE OR REPLACE VIEW v_scheduled_tasks_status AS
SELECT 
    st.id,
    st.name,
    st.task_type,
    st.schedule_type,
    st.next_run_at,
    st.last_run_at,
    st.last_run_status,
    st.consecutive_failures,
    st.enabled,
    st.priority,
    EXTRACT(EPOCH FROM (st.next_run_at - NOW())) as seconds_until_next_run,
    (SELECT COUNT(*) FROM scheduled_task_runs str WHERE str.task_id = st.id AND str.status = 'success') as total_successful_runs,
    (SELECT COUNT(*) FROM scheduled_task_runs str WHERE str.task_id = st.id AND str.status = 'failed') as total_failed_runs
FROM scheduled_tasks st
ORDER BY st.priority DESC, st.next_run_at ASC;

-- View: Recent anomalies summary
CREATE OR REPLACE VIEW v_anomaly_summary AS
SELECT 
    severity,
    component,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE status = 'open') as open_count,
    MAX(detected_at) as latest_detected
FROM anomaly_events
WHERE detected_at > NOW() - INTERVAL '7 days'
GROUP BY severity, component
ORDER BY 
    CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    count DESC;

-- View: System health overview
CREATE OR REPLACE VIEW v_system_health AS
SELECT 
    component,
    check_type,
    status,
    response_time_ms,
    consecutive_failures,
    last_check_at,
    CASE 
        WHEN last_check_at < NOW() - INTERVAL '10 minutes' THEN 'stale'
        ELSE 'current'
    END as freshness
FROM health_checks
ORDER BY 
    CASE status WHEN 'unhealthy' THEN 1 WHEN 'degraded' THEN 2 WHEN 'unknown' THEN 3 ELSE 4 END,
    component;

-- =============================================================================
-- CLEANUP OLD DATA (run periodically)
-- =============================================================================

-- Function to clean up old metrics (keep 30 days)
CREATE OR REPLACE FUNCTION cleanup_old_metrics(days_to_keep INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM system_metrics 
    WHERE recorded_at < NOW() - (days_to_keep || ' days')::INTERVAL;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up old task runs (keep 90 days)
CREATE OR REPLACE FUNCTION cleanup_old_task_runs(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM scheduled_task_runs 
    WHERE started_at < NOW() - (days_to_keep || ' days')::INTERVAL;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- GRANTS (if using specific roles)
-- =============================================================================

-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO juggernaut_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO juggernaut_app;

-- =============================================================================
-- MIGRATION COMPLETE
-- =============================================================================

COMMENT ON TABLE scheduled_tasks IS 'Phase 5.3: Cron-like scheduled task definitions';
COMMENT ON TABLE scheduled_task_runs IS 'Phase 5.3: History of scheduled task executions';
COMMENT ON TABLE system_metrics IS 'Phase 5.2: Time-series system metrics';
COMMENT ON TABLE anomaly_events IS 'Phase 5.2: Detected system anomalies';
COMMENT ON TABLE health_checks IS 'Phase 5.2: Component health check status';
COMMENT ON TABLE opportunity_scans IS 'Phase 5.1: Opportunity scan run history';
