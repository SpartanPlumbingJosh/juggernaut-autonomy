-- Migration 017: Fix research_findings schema for task completion
-- Addresses Blocker 2: Missing confidence column causing research task failures

-- research_findings table appears to exist but is missing in migrations
-- This migration ensures it exists with correct schema

-- Create table if it doesn't exist (defensive)
CREATE TABLE IF NOT EXISTS research_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES governance_tasks(id) ON DELETE CASCADE,
    topic VARCHAR(200) NOT NULL DEFAULT 'Research',
    query TEXT NOT NULL,
    summary TEXT NOT NULL,
    sources JSONB DEFAULT '[]',
    findings JSONB DEFAULT '{}',
    confidence DECIMAL(3,2) DEFAULT 0.5,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add confidence column if it doesn't exist (for existing tables)
ALTER TABLE research_findings ADD COLUMN IF NOT EXISTS confidence DECIMAL(3,2) DEFAULT 0.5;

-- Remove confidence_score if it exists (was incorrect fallback column name)
-- This is safe because we just added/ensured confidence exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'research_findings' 
        AND column_name = 'confidence_score'
    ) THEN
        -- Copy data from confidence_score to confidence if needed
        EXECUTE 'UPDATE research_findings SET confidence = confidence_score WHERE confidence IS NULL AND confidence_score IS NOT NULL';
        -- Drop the incorrect column
        EXECUTE 'ALTER TABLE research_findings DROP COLUMN confidence_score';
    END IF;
END $$;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_research_findings_task_id ON research_findings(task_id);
CREATE INDEX IF NOT EXISTS idx_research_findings_topic ON research_findings(topic);
CREATE INDEX IF NOT EXISTS idx_research_findings_created_at ON research_findings(created_at DESC);

-- Add comment
COMMENT ON TABLE research_findings IS 'Research task outputs with sources and confidence scores';
COMMENT ON COLUMN research_findings.confidence IS 'Confidence score 0.0-1.0 for research quality';
