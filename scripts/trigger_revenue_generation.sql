-- Trigger Revenue Generation Immediately
-- This creates tasks to start discovering opportunities and generating revenue ideas
-- Instead of waiting for the 6am scheduled tasks

-- 1. Fix database schema first (prevent NULL created_at)
ALTER TABLE revenue_ideas 
ALTER COLUMN created_at SET DEFAULT NOW();

ALTER TABLE revenue_ideas 
ALTER COLUMN updated_at SET DEFAULT NOW();

-- Update existing NULL values
UPDATE revenue_ideas 
SET created_at = NOW() 
WHERE created_at IS NULL;

UPDATE revenue_ideas 
SET updated_at = NOW() 
WHERE updated_at IS NULL;

-- 2. Create idea generation task (runs immediately)
INSERT INTO governance_tasks (
    id,
    title,
    description,
    task_type,
    status,
    priority,
    payload,
    created_at
) VALUES (
    gen_random_uuid(),
    'Generate Revenue Ideas - Manual Trigger',
    'Discover and generate revenue opportunities using web search and AI analysis. This is a manual trigger to start revenue generation immediately.',
    'idea_generation',
    'pending',
    'high',
    '{"source": "manual_trigger", "limit": 10, "focus": "quick_wins"}',
    NOW()
);

-- 3. Create opportunity scan task
INSERT INTO governance_tasks (
    id,
    title,
    description,
    task_type,
    status,
    priority,
    payload,
    created_at
) VALUES (
    gen_random_uuid(),
    'Opportunity Scan - Manual Trigger',
    'Scan for revenue opportunities across multiple sources',
    'opportunity_scan',
    'pending',
    'high',
    '{"config": {"sources": ["web", "api_marketplaces", "freelance_platforms"], "limit": 20}}',
    NOW()
);

-- 4. Verify scheduled tasks exist
SELECT 
    id,
    name,
    task_type,
    enabled,
    last_run_at,
    next_run_at
FROM scheduled_tasks
WHERE task_type IN ('idea_generation', 'idea_scoring', 'experiment_review', 'portfolio_rebalance')
ORDER BY task_type;

-- 5. Check if any revenue ideas already exist
SELECT 
    COUNT(*) as total_ideas,
    COUNT(*) FILTER (WHERE status = 'approved') as approved,
    COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
    COUNT(*) FILTER (WHERE status = 'pending') as pending
FROM revenue_ideas;

-- 6. Check if any experiments exist
SELECT 
    COUNT(*) as total_experiments,
    COUNT(*) FILTER (WHERE status = 'running') as running,
    COUNT(*) FILTER (WHERE status = 'completed') as completed,
    COUNT(*) FILTER (WHERE status = 'proposed') as proposed
FROM experiments;

-- 7. Check revenue events
SELECT 
    COUNT(*) as total_events,
    SUM(CASE WHEN event_type = 'revenue' THEN amount_cents ELSE 0 END) as total_revenue_cents,
    SUM(CASE WHEN event_type = 'cost' THEN amount_cents ELSE 0 END) as total_cost_cents
FROM revenue_events;
