-- FIX-11: Add source references to learnings and opportunities
-- This migration enables L2-02 References and Sourcing capability
--
-- Sources track where information comes from:
-- - For learnings: which task/worker/scan identified this insight
-- - For opportunities: which data source or scan identified this opportunity

-- Add source column to learnings table (if not exists)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'learnings' AND column_name = 'source'
    ) THEN
        ALTER TABLE learnings ADD COLUMN source VARCHAR(500);
        COMMENT ON COLUMN learnings.source IS 'Source reference describing where this learning originated (task, scan, external data)';
    END IF;
END $$;

-- Add source_description column to opportunities table (if not exists)
-- Note: source_id already exists as UUID FK, we add description for human-readable source
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'opportunities' AND column_name = 'source_description'
    ) THEN
        ALTER TABLE opportunities ADD COLUMN source_description VARCHAR(500);
        COMMENT ON COLUMN opportunities.source_description IS 'Human-readable description of the data source that identified this opportunity';
    END IF;
END $$;

-- Create index on learnings.source for faster source-based queries
CREATE INDEX IF NOT EXISTS idx_learnings_source ON learnings(source) WHERE source IS NOT NULL;

-- Create index on opportunities.source_description for faster lookups
CREATE INDEX IF NOT EXISTS idx_opportunities_source_desc ON opportunities(source_description) WHERE source_description IS NOT NULL;

-- Verify columns were added
SELECT 'learnings.source' as column_added 
WHERE EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'learnings' AND column_name = 'source')
UNION ALL
SELECT 'opportunities.source_description' as column_added 
WHERE EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'opportunities' AND column_name = 'source_description');
