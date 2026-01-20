-- GAP-01: Create system_config table for learning application
-- This table stores configuration values including applied learnings patterns
-- Required by core/learning_application.py for apply_learning() functionality

CREATE TABLE IF NOT EXISTS system_config (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL DEFAULT '{}'::jsonb,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index on key for faster lookups
CREATE INDEX IF NOT EXISTS idx_system_config_key ON system_config(key);

-- Create index on updated_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_system_config_updated_at ON system_config(updated_at);

-- Add comment to table
COMMENT ON TABLE system_config IS 'System configuration storage including applied learning patterns';

-- Add comments to columns
COMMENT ON COLUMN system_config.key IS 'Unique configuration key (e.g., success_pattern_code)';
COMMENT ON COLUMN system_config.value IS 'JSONB configuration value';
COMMENT ON COLUMN system_config.description IS 'Human-readable description of this config entry';
COMMENT ON COLUMN system_config.created_at IS 'When this config entry was first created';
COMMENT ON COLUMN system_config.updated_at IS 'When this config entry was last updated';