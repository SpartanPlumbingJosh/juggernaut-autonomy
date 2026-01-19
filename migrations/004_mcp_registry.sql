-- MCP Registry Table
-- Tracks all MCP servers created by the system
-- Created: 2026-01-19

-- Main registry table
CREATE TABLE IF NOT EXISTS mcp_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    owner_worker_id VARCHAR(100),
    railway_service_id VARCHAR(100),
    railway_deployment_id VARCHAR(100),
    endpoint_url TEXT,
    auth_token VARCHAR(200),
    tools_config JSONB DEFAULT '[]'::jsonb,
    env_vars JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    deployed_at TIMESTAMPTZ,
    last_health_check TIMESTAMPTZ,
    health_status VARCHAR(50) DEFAULT 'unknown',
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_mcp_registry_status 
ON mcp_registry(status);

CREATE INDEX IF NOT EXISTS idx_mcp_registry_owner 
ON mcp_registry(owner_worker_id);

CREATE INDEX IF NOT EXISTS idx_mcp_registry_health 
ON mcp_registry(health_status);

-- Register the main Juggernaut MCP
INSERT INTO mcp_registry (
    name, 
    description, 
    status, 
    endpoint_url,
    auth_token,
    tools_config,
    deployed_at,
    health_status
) VALUES (
    'juggernaut-mcp',
    'Main JUGGERNAUT MCP server for Claude.ai integration',
    'active',
    'https://juggernaut-mcp-production.up.railway.app/mcp/sse',
    'UncQmFYeJRyKufiO72jdazhp9vZXBtEx',
    '[
        {"name": "hq_query", "description": "Query governance database"},
        {"name": "hq_execute", "description": "Execute governance actions"},
        {"name": "fetch_url", "description": "Fetch content from URLs"},
        {"name": "war_room_post", "description": "Post to Slack war-room"},
        {"name": "war_room_history", "description": "Get war-room history"}
    ]'::jsonb,
    NOW(),
    'healthy'
) ON CONFLICT (name) DO UPDATE SET
    endpoint_url = EXCLUDED.endpoint_url,
    status = EXCLUDED.status;

COMMENT ON TABLE mcp_registry IS 'Registry of all MCP servers created and managed by JUGGERNAUT';
COMMENT ON COLUMN mcp_registry.tools_config IS 'JSON array of tool definitions with name, description, and schema';
COMMENT ON COLUMN mcp_registry.env_vars IS 'Environment variables (secrets redacted) for the MCP server';
