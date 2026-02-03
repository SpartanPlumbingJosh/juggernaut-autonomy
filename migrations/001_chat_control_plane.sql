-- Migration: Chat Control Plane (Milestone 1)
-- Adds streaming event support, budget tracking, and guardrails

-- Add columns to existing chat_sessions table
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS
    current_status VARCHAR(50) DEFAULT 'idle';
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS
    current_budget_used INTEGER DEFAULT 0;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS
    current_budget_max INTEGER DEFAULT 100;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS
    stop_reason VARCHAR(100);
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS
    guardrails_state JSONB DEFAULT '{}';
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS
    mode VARCHAR(50) DEFAULT 'normal';

-- Tool execution timeline
CREATE TABLE IF NOT EXISTS tool_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_id UUID,
    tool_name VARCHAR(100) NOT NULL,
    arguments JSONB,
    result JSONB,
    success BOOLEAN,
    duration_ms INTEGER,
    fingerprint VARCHAR(64),
    error_message TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_executions_session 
    ON tool_executions(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_executions_fingerprint 
    ON tool_executions(fingerprint);
CREATE INDEX IF NOT EXISTS idx_tool_executions_success 
    ON tool_executions(success, created_at DESC);

-- Budget tracking per session
CREATE TABLE IF NOT EXISTS chat_budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    mode VARCHAR(50) NOT NULL,
    max_steps INTEGER DEFAULT 100,
    max_wall_clock_seconds INTEGER DEFAULT 300,
    max_retries_per_fingerprint INTEGER DEFAULT 3,
    max_no_progress_steps INTEGER DEFAULT 5,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_budgets_session 
    ON chat_budgets(session_id);

-- Stream events log (for debugging and replay)
CREATE TABLE IF NOT EXISTS stream_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stream_events_session 
    ON stream_events(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stream_events_type 
    ON stream_events(event_type, created_at DESC);

-- Comments for documentation
COMMENT ON TABLE tool_executions IS 'Timeline of tool executions within chat sessions';
COMMENT ON TABLE chat_budgets IS 'Budget limits and tracking per chat session';
COMMENT ON TABLE stream_events IS 'Log of all streaming events for debugging and replay';
