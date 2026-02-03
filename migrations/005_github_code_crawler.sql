-- Migration: GitHub Code Crawler (Milestone 4)
-- Code health analysis and automated PR creation

-- Code analysis runs
CREATE TABLE IF NOT EXISTS code_analysis_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository VARCHAR(200) NOT NULL,
    branch VARCHAR(100) DEFAULT 'main',
    commit_sha VARCHAR(40),
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'running', -- 'running', 'completed', 'failed'
    health_score DECIMAL(5,2),
    findings_count INTEGER DEFAULT 0,
    prs_created INTEGER DEFAULT 0,
    tasks_created INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_code_runs_repo 
    ON code_analysis_runs(repository, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_code_runs_status 
    ON code_analysis_runs(status, created_at DESC);

-- Code findings (issues detected)
CREATE TABLE IF NOT EXISTS code_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES code_analysis_runs(id) ON DELETE CASCADE,
    finding_type VARCHAR(50) NOT NULL, -- 'unused_import', 'stale_function', 'contract_mismatch', etc
    severity VARCHAR(20) DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
    file_path VARCHAR(500) NOT NULL,
    line_number INTEGER,
    description TEXT NOT NULL,
    suggestion TEXT,
    auto_fixable BOOLEAN DEFAULT FALSE,
    fixed BOOLEAN DEFAULT FALSE,
    pr_id VARCHAR(100),
    task_id UUID,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_findings_run 
    ON code_findings(run_id, severity);
CREATE INDEX IF NOT EXISTS idx_findings_type 
    ON code_findings(finding_type, fixed);
CREATE INDEX IF NOT EXISTS idx_findings_fixable 
    ON code_findings(auto_fixable, fixed);

-- API contracts (backend vs frontend)
CREATE TABLE IF NOT EXISTS api_contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    endpoint VARCHAR(200) NOT NULL,
    method VARCHAR(10) NOT NULL, -- 'GET', 'POST', 'PUT', 'DELETE'
    backend_schema JSONB,
    frontend_schema JSONB,
    mismatches JSONB,
    mismatch_count INTEGER DEFAULT 0,
    last_validated TIMESTAMP,
    status VARCHAR(50) DEFAULT 'unknown', -- 'valid', 'mismatch', 'unknown'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(endpoint, method)
);

CREATE INDEX IF NOT EXISTS idx_contracts_status 
    ON api_contracts(status, last_validated DESC);
CREATE INDEX IF NOT EXISTS idx_contracts_endpoint 
    ON api_contracts(endpoint);

-- Dependency status
CREATE TABLE IF NOT EXISTS dependency_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    package_name VARCHAR(200) NOT NULL,
    package_manager VARCHAR(20) NOT NULL, -- 'pip', 'npm', 'yarn'
    current_version VARCHAR(50),
    latest_version VARCHAR(50),
    is_outdated BOOLEAN DEFAULT FALSE,
    has_vulnerabilities BOOLEAN DEFAULT FALSE,
    vulnerability_details JSONB,
    vulnerability_count INTEGER DEFAULT 0,
    last_checked TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(package_name, package_manager)
);

CREATE INDEX IF NOT EXISTS idx_deps_outdated 
    ON dependency_status(is_outdated, package_manager);
CREATE INDEX IF NOT EXISTS idx_deps_vulnerable 
    ON dependency_status(has_vulnerabilities, package_manager);

-- Code health metrics (historical tracking)
CREATE TABLE IF NOT EXISTS code_health_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES code_analysis_runs(id) ON DELETE CASCADE,
    metric_type VARCHAR(50) NOT NULL, -- 'staleness', 'contracts', 'dependencies', 'documentation'
    score DECIMAL(5,2) NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metrics_run 
    ON code_health_metrics(run_id, metric_type);
CREATE INDEX IF NOT EXISTS idx_metrics_type 
    ON code_health_metrics(metric_type, created_at DESC);

-- Comments for documentation
COMMENT ON TABLE code_analysis_runs IS 'Code analysis execution history';
COMMENT ON TABLE code_findings IS 'Issues detected during code analysis';
COMMENT ON TABLE api_contracts IS 'API contract validation between backend and frontend';
COMMENT ON TABLE dependency_status IS 'Package dependency health tracking';
COMMENT ON TABLE code_health_metrics IS 'Historical code health metrics';
