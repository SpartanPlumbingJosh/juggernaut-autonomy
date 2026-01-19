-- Migration 005: File Storage and Webhook Events
-- Support for R2 storage fallback and webhook event tracking

-- File storage table (fallback when R2 not configured)
CREATE TABLE IF NOT EXISTS file_storage (
    key TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    content_type TEXT DEFAULT 'application/octet-stream',
    size_bytes INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_file_storage_created ON file_storage(created_at);

-- Webhook events table
CREATE TABLE IF NOT EXISTS webhook_events (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    data JSONB NOT NULL,
    headers JSONB,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhook_source ON webhook_events(source);
CREATE INDEX IF NOT EXISTS idx_webhook_processed ON webhook_events(processed);
CREATE INDEX IF NOT EXISTS idx_webhook_created ON webhook_events(created_at);

-- API usage tracking for cost management
CREATE TABLE IF NOT EXISTS api_usage (
    id SERIAL PRIMARY KEY,
    service TEXT NOT NULL,  -- 'openrouter', 'serper', 'twilio', 'resend', etc.
    operation TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd DECIMAL(10,6),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_usage_service ON api_usage(service);
CREATE INDEX IF NOT EXISTS idx_api_usage_created ON api_usage(created_at);

COMMENT ON TABLE file_storage IS 'Fallback file storage when R2 not configured';
COMMENT ON TABLE webhook_events IS 'Incoming webhook events from external services';
COMMENT ON TABLE api_usage IS 'Track API usage for cost management';
