-- Migration: Engine Autonomy Restoration (Milestone 5)
-- Autonomous task routing and execution

-- Task assignments (tracks which worker is executing which task)
CREATE TABLE IF NOT EXISTS task_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES governance_tasks(id) ON DELETE CASCADE,
    worker_id UUID REFERENCES workers(id) ON DELETE SET NULL,
    assigned_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'assigned', -- 'assigned', 'running', 'completed', 'failed'
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assignments_task 
    ON task_assignments(task_id, status);
CREATE INDEX IF NOT EXISTS idx_assignments_worker 
    ON task_assignments(worker_id, status);
CREATE INDEX IF NOT EXISTS idx_assignments_status 
    ON task_assignments(status, assigned_at DESC);

-- Worker capabilities (what each worker can do)
CREATE TABLE IF NOT EXISTS worker_capabilities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id UUID REFERENCES workers(id) ON DELETE CASCADE,
    capability VARCHAR(100) NOT NULL,
    proficiency INTEGER DEFAULT 1, -- 1-5 scale
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(worker_id, capability)
);

CREATE INDEX IF NOT EXISTS idx_capabilities_worker 
    ON worker_capabilities(worker_id);
CREATE INDEX IF NOT EXISTS idx_capabilities_capability 
    ON worker_capabilities(capability);

-- Task dependencies (task A must complete before task B)
CREATE TABLE IF NOT EXISTS task_dependencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES governance_tasks(id) ON DELETE CASCADE,
    depends_on_task_id UUID REFERENCES governance_tasks(id) ON DELETE CASCADE,
    dependency_type VARCHAR(50) DEFAULT 'blocks', -- 'blocks', 'requires', 'optional'
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(task_id, depends_on_task_id)
);

CREATE INDEX IF NOT EXISTS idx_dependencies_task 
    ON task_dependencies(task_id);
CREATE INDEX IF NOT EXISTS idx_dependencies_depends 
    ON task_dependencies(depends_on_task_id);

-- Autonomy state (tracks the engine's operational state)
CREATE TABLE IF NOT EXISTS autonomy_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    is_running BOOLEAN DEFAULT FALSE,
    last_loop_at TIMESTAMP,
    tasks_processed INTEGER DEFAULT 0,
    tasks_assigned INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    tasks_failed INTEGER DEFAULT 0,
    loop_duration_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Retry history (tracks task retry attempts)
CREATE TABLE IF NOT EXISTS retry_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES governance_tasks(id) ON DELETE CASCADE,
    assignment_id UUID REFERENCES task_assignments(id) ON DELETE SET NULL,
    retry_number INTEGER NOT NULL,
    retry_reason VARCHAR(200),
    previous_worker_id UUID REFERENCES workers(id) ON DELETE SET NULL,
    new_worker_id UUID REFERENCES workers(id) ON DELETE SET NULL,
    retry_at TIMESTAMP NOT NULL,
    success BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_retry_task 
    ON retry_history(task_id, retry_at DESC);
CREATE INDEX IF NOT EXISTS idx_retry_worker 
    ON retry_history(new_worker_id);

-- Worker health metrics (tracks worker performance)
CREATE TABLE IF NOT EXISTS worker_health_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id UUID REFERENCES workers(id) ON DELETE CASCADE,
    metric_type VARCHAR(50) NOT NULL, -- 'success_rate', 'avg_duration', 'error_count'
    metric_value DECIMAL(10,2) NOT NULL,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_health_worker 
    ON worker_health_metrics(worker_id, metric_type, window_end DESC);

-- Comments for documentation
COMMENT ON TABLE task_assignments IS 'Tracks which worker is executing which task';
COMMENT ON TABLE worker_capabilities IS 'Defines what each worker can do';
COMMENT ON TABLE task_dependencies IS 'Defines task execution order requirements';
COMMENT ON TABLE autonomy_state IS 'Tracks the autonomy engine operational state';
COMMENT ON TABLE retry_history IS 'Logs all task retry attempts';
COMMENT ON TABLE worker_health_metrics IS 'Tracks worker performance over time';

-- Initialize autonomy state
INSERT INTO autonomy_state (is_running, last_loop_at, updated_at)
VALUES (FALSE, NOW(), NOW())
ON CONFLICT DO NOTHING;
