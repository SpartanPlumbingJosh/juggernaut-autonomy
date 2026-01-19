-- Migration: 005_scaling_events.sql
-- Description: Create scaling_events table for tracking auto-scaling decisions
-- Author: claude-chat-9X4B
-- Date: 2025-01-19

-- Table to track auto-scaling decisions and actions for historical analysis
CREATE TABLE IF NOT EXISTS scaling_events (
    -- Primary key using UUID for distributed system compatibility
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- The scaling action taken (e.g., "scale_up", "scale_down", "no_action")
    action TEXT NOT NULL,
    
    -- Reason for the scaling decision
    reason TEXT NOT NULL,
    
    -- Number of workers before the scaling action
    workers_before INTEGER NOT NULL CHECK (workers_before >= 0),
    
    -- Number of workers after the scaling action
    workers_after INTEGER NOT NULL CHECK (workers_after >= 0),
    
    -- Queue depth at the time of the decision
    queue_depth INTEGER NOT NULL CHECK (queue_depth >= 0),
    
    -- Timestamp when the scaling event occurred
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create index on created_at for efficient time-based queries
CREATE INDEX IF NOT EXISTS idx_scaling_events_created_at 
    ON scaling_events (created_at DESC);

-- Create index on action for filtering by scaling action type
CREATE INDEX IF NOT EXISTS idx_scaling_events_action 
    ON scaling_events (action);

-- Add comment to table for documentation
COMMENT ON TABLE scaling_events IS 'Tracks auto-scaling decisions and actions for historical analysis and performance tuning';
COMMENT ON COLUMN scaling_events.id IS 'Unique identifier for each scaling event';
COMMENT ON COLUMN scaling_events.action IS 'The scaling action taken: scale_up, scale_down, or no_action';
COMMENT ON COLUMN scaling_events.reason IS 'Human-readable reason explaining why the scaling decision was made';
COMMENT ON COLUMN scaling_events.workers_before IS 'Number of active workers before the scaling action';
COMMENT ON COLUMN scaling_events.workers_after IS 'Number of active workers after the scaling action';
COMMENT ON COLUMN scaling_events.queue_depth IS 'Number of pending tasks in the queue at decision time';
COMMENT ON COLUMN scaling_events.created_at IS 'Timestamp when the scaling event was recorded';
