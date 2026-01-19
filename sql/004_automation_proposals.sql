-- Migration: Create automation_proposals table
-- L4-04: Build propose new automations capability

-- Create enum for proposal status
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'proposal_status') THEN
        CREATE TYPE proposal_status AS ENUM (
            'pending',      -- Awaiting review
            'approved',     -- Approved for implementation
            'rejected',     -- Rejected by reviewer
            'implemented',  -- Implementation complete
            'archived'      -- No longer active
        );
    END IF;
END $$;

-- Create enum for proposal type
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'proposal_type') THEN
        CREATE TYPE proposal_type AS ENUM (
            'workflow',     -- New workflow automation
            'tool',         -- New tool integration
            'strategy',     -- New strategy/approach
            'optimization', -- Improvement to existing
            'integration'   -- New system integration
        );
    END IF;
END $$;

-- Create automation_proposals table
CREATE TABLE IF NOT EXISTS automation_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Proposal identification
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    proposal_type proposal_type NOT NULL,
    
    -- Detection context
    detected_pattern TEXT,               -- What repetitive pattern was detected
    pattern_occurrences INTEGER DEFAULT 0, -- How many times pattern seen
    source_task_ids UUID[],              -- Tasks that triggered this proposal
    
    -- Implementation plan
    rationale TEXT NOT NULL,             -- Why this automation is proposed
    implementation_plan TEXT NOT NULL,    -- How to implement it
    estimated_effort VARCHAR(50),        -- low/medium/high
    estimated_impact VARCHAR(50),        -- low/medium/high
    risk_assessment TEXT,                -- Potential risks
    
    -- Status tracking
    status proposal_status NOT NULL DEFAULT 'pending',
    proposed_by VARCHAR(100) NOT NULL,   -- Worker that created proposal
    reviewed_by VARCHAR(100),            -- Who approved/rejected
    review_notes TEXT,                   -- Feedback from reviewer
    
    -- Implementation tracking
    implementation_task_id UUID,         -- Link to governance_task for implementation
    implemented_by VARCHAR(100),         -- Worker that implemented
    implementation_evidence TEXT,        -- PR link, deployment, etc.
    
    -- Metrics (post-implementation)
    time_saved_hours DECIMAL(10,2),      -- Estimated time saved
    success_metrics JSONB,               -- Custom metrics
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    implemented_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_automation_proposals_status 
    ON automation_proposals(status);

CREATE INDEX IF NOT EXISTS idx_automation_proposals_type 
    ON automation_proposals(proposal_type);

CREATE INDEX IF NOT EXISTS idx_automation_proposals_created 
    ON automation_proposals(created_at DESC);

-- Create trigger to update updated_at
CREATE OR REPLACE FUNCTION update_automation_proposals_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_automation_proposals_updated_at 
    ON automation_proposals;

CREATE TRIGGER trigger_update_automation_proposals_updated_at
    BEFORE UPDATE ON automation_proposals
    FOR EACH ROW
    EXECUTE FUNCTION update_automation_proposals_updated_at();

-- Add comment for documentation
COMMENT ON TABLE automation_proposals IS 
    'L4-04: Stores proposals for new automations detected by the engine. Tracks proposal -> approval -> implementation lifecycle.';
