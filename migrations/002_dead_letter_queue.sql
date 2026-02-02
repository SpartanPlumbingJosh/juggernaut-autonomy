-- Migration: 002_dead_letter_queue.sql

-- Create the dead letter queue table for permanently failed tasks
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_task_id UUID REFERENCES governance_tasks(id),
    task_snapshot JSONB NOT NULL,  -- Full task state at failure
    failure_reason TEXT NOT NULL,
    failure_count INTEGER DEFAULT 1,
    first_failure_at TIMESTAMPTZ DEFAULT NOW(),
    last_failure_at TIMESTAMPTZ DEFAULT NOW(),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, retrying, resolved, abandoned
    resolution_notes TEXT,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_dlq_status ON dead_letter_queue(status);
CREATE INDEX IF NOT EXISTS idx_dlq_original_task ON dead_letter_queue(original_task_id);
CREATE INDEX IF NOT EXISTS idx_dlq_failure_reason ON dead_letter_queue(failure_reason);

-- Add a column to governance_tasks to track if a task has been moved to DLQ
ALTER TABLE governance_tasks ADD COLUMN IF NOT EXISTS moved_to_dlq BOOLEAN DEFAULT FALSE;
ALTER TABLE governance_tasks ADD COLUMN IF NOT EXISTS dlq_id UUID REFERENCES dead_letter_queue(id);

-- Create a function to move a task to the dead letter queue
CREATE OR REPLACE FUNCTION move_to_dlq(
    p_task_id UUID,
    p_failure_reason TEXT
) RETURNS UUID AS $$
DECLARE
    v_task_data JSONB;
    v_dlq_id UUID;
BEGIN
    -- Get the task data
    SELECT row_to_json(t)::jsonb INTO v_task_data
    FROM governance_tasks t
    WHERE id = p_task_id;
    
    IF v_task_data IS NULL THEN
        RAISE EXCEPTION 'Task with ID % not found', p_task_id;
    END IF;
    
    -- Check if task is already in DLQ
    SELECT dlq_id INTO v_dlq_id
    FROM governance_tasks
    WHERE id = p_task_id AND moved_to_dlq = TRUE;
    
    IF v_dlq_id IS NOT NULL THEN
        -- Update existing DLQ entry
        UPDATE dead_letter_queue
        SET failure_count = failure_count + 1,
            last_failure_at = NOW(),
            failure_reason = p_failure_reason
        WHERE id = v_dlq_id;
        
        RETURN v_dlq_id;
    END IF;
    
    -- Insert into DLQ
    INSERT INTO dead_letter_queue (
        original_task_id,
        task_snapshot,
        failure_reason
    ) VALUES (
        p_task_id,
        v_task_data,
        p_failure_reason
    ) RETURNING id INTO v_dlq_id;
    
    -- Update the original task
    UPDATE governance_tasks
    SET moved_to_dlq = TRUE,
        dlq_id = v_dlq_id,
        status = 'failed',
        completion_evidence = jsonb_build_object(
            'moved_to_dlq', true,
            'dlq_reason', p_failure_reason,
            'dlq_at', NOW()::text
        )
    WHERE id = p_task_id;
    
    RETURN v_dlq_id;
END;
$$ LANGUAGE plpgsql;
