-- Migration: 014_add_experiment_type_and_research_topic.sql
-- Add missing columns that code expects but schema doesn't have

-- Add experiment_type to experiments table
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS experiment_type VARCHAR(50);

-- Create index for efficient filtering
CREATE INDEX IF NOT EXISTS idx_experiments_type ON experiments(experiment_type);

-- Add topic to research_findings table
ALTER TABLE research_findings ADD COLUMN IF NOT EXISTS topic VARCHAR(200) NOT NULL DEFAULT 'Research';

-- Create index for efficient search
CREATE INDEX IF NOT EXISTS idx_research_findings_topic ON research_findings(topic);

-- Update existing NULL values if any
UPDATE experiments SET experiment_type = 'revenue' WHERE experiment_type IS NULL AND name ILIKE '%revenue%';
UPDATE experiments SET experiment_type = 'domain_flip' WHERE experiment_type IS NULL AND name ILIKE '%domain%';
UPDATE experiments SET experiment_type = 'rollback_test' WHERE experiment_type IS NULL AND name ILIKE '%rollback%';
UPDATE experiments SET experiment_type = 'test' WHERE experiment_type IS NULL AND experiment_type IS NULL;
