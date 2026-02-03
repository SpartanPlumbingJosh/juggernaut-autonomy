-- Migration: Workers Table
-- Multi-agent coordination and worker management

CREATE TABLE IF NOT EXISTS workers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id VARCHAR(100) NOT NULL UNIQUE,
    worker_type VARCHAR(50) NOT NULL, -- 'executor', 'orchestrator', 'specialist', etc
    status VARCHAR(50) DEFAULT 'offline', -- 'online', 'offline', 'busy', 'idle'
    capabilities JSONB DEFAULT '[]', -- Array of capability strings
    current_task_id UUID, -- Reference to governance_tasks if assigned
    last_heartbeat TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workers_status 
    ON workers(status);
CREATE INDEX IF NOT EXISTS idx_workers_worker_id 
    ON workers(worker_id);
CREATE INDEX IF NOT EXISTS idx_workers_heartbeat 
    ON workers(last_heartbeat DESC);
CREATE INDEX IF NOT EXISTS idx_workers_type 
    ON workers(worker_type);

COMMENT ON TABLE workers IS 'Multi-agent worker registry for L5 coordination';
COMMENT ON COLUMN workers.worker_id IS 'Unique identifier for the worker instance';
COMMENT ON COLUMN workers.status IS 'Current operational status of the worker';
COMMENT ON COLUMN workers.capabilities IS 'Array of capabilities this worker can handle';
COMMENT ON COLUMN workers.last_heartbeat IS 'Last time worker reported being alive';
