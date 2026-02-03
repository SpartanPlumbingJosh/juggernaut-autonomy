-- Tracked Repositories
-- Store repositories configured for code health monitoring

CREATE TABLE IF NOT EXISTS tracked_repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner VARCHAR(100) NOT NULL,
    repo VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    default_branch VARCHAR(100) DEFAULT 'main',
    enabled BOOLEAN DEFAULT TRUE,
    last_analyzed TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(owner, repo)
);

CREATE INDEX IF NOT EXISTS idx_tracked_repos_enabled 
    ON tracked_repositories(enabled, last_analyzed DESC);

-- Insert default repository
INSERT INTO tracked_repositories (owner, repo, display_name, default_branch)
VALUES ('SpartanPlumbingJosh', 'juggernaut-autonomy', 'Juggernaut Autonomy', 'main')
ON CONFLICT (owner, repo) DO NOTHING;
