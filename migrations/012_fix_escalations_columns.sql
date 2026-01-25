-- Migration: Fix missing columns in escalations table
-- Date: 2026-01-21
-- Issue: SQL errors from missing escalated_by and reason columns

-- Add missing escalated_by column
ALTER TABLE escalations 
ADD COLUMN IF NOT EXISTS escalated_by TEXT;

-- Add missing reason column  
ALTER TABLE escalations
ADD COLUMN IF NOT EXISTS reason TEXT;

-- Add index for better query performance
CREATE INDEX IF NOT EXISTS idx_escalations_escalated_by 
ON escalations(escalated_by);

COMMENT ON COLUMN escalations.escalated_by IS 'Worker ID that initiated the escalation';
COMMENT ON COLUMN escalations.reason IS 'Reason for escalation';
