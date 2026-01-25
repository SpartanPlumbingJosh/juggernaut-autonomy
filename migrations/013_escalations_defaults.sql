-- Migration: Add default values to escalations table columns
-- Date: 2026-01-21
-- Issue: Automatic timeout escalations failing with NULL constraint violations

-- Add default value for level column
ALTER TABLE escalations 
ALTER COLUMN level SET DEFAULT 'high';

-- Add default value for title column  
ALTER TABLE escalations
ALTER COLUMN title SET DEFAULT 'System Escalation';

-- Add default value for source_agent column
ALTER TABLE escalations
ALTER COLUMN source_agent SET DEFAULT 'SYSTEM';

COMMENT ON COLUMN escalations.level IS 'Escalation severity level (defaults to high for system escalations)';
COMMENT ON COLUMN escalations.title IS 'Human-readable title (defaults to System Escalation for automated escalations)';
COMMENT ON COLUMN escalations.source_agent IS 'Agent that created the escalation (defaults to SYSTEM for timeout escalations)';
