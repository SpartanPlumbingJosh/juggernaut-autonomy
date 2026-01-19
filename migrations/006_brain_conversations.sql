-- Migration: 006_brain_conversations.sql
-- Description: Create brain_conversations table for storing AI conversation history
-- Created: 2026-01-19
-- Task: BRAIN-01

-- =============================================================================
-- BRAIN CONVERSATIONS TABLE
-- Stores conversation history for the Brain service
-- =============================================================================

CREATE TABLE IF NOT EXISTS brain_conversations (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Session identifier for grouping related messages
    session_id VARCHAR(100) NOT NULL,
    
    -- Message role (user, assistant, system)
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    
    -- Message content
    content TEXT NOT NULL,
    
    -- Token count for cost tracking
    token_count INTEGER NOT NULL DEFAULT 0,
    
    -- Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Flexible metadata storage
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Index for fast session lookups (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_brain_conversations_session_id 
    ON brain_conversations (session_id);

-- Composite index for retrieving conversation history in order
CREATE INDEX IF NOT EXISTS idx_brain_conversations_session_created 
    ON brain_conversations (session_id, created_at);

-- Index for time-based queries (cleanup, analytics)
CREATE INDEX IF NOT EXISTS idx_brain_conversations_created_at 
    ON brain_conversations (created_at);

-- GIN index for metadata queries
CREATE INDEX IF NOT EXISTS idx_brain_conversations_metadata 
    ON brain_conversations USING GIN (metadata);

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE brain_conversations IS 'Stores conversation history for the JUGGERNAUT Brain service';
COMMENT ON COLUMN brain_conversations.id IS 'Unique identifier for each message';
COMMENT ON COLUMN brain_conversations.session_id IS 'Groups messages into conversation sessions';
COMMENT ON COLUMN brain_conversations.role IS 'Message role: user, assistant, or system';
COMMENT ON COLUMN brain_conversations.content IS 'The actual message content';
COMMENT ON COLUMN brain_conversations.token_count IS 'Number of tokens in the message for cost tracking';
COMMENT ON COLUMN brain_conversations.created_at IS 'When the message was created';
COMMENT ON COLUMN brain_conversations.metadata IS 'Additional metadata (model, cost, worker_id, etc.)';

-- =============================================================================
-- SAMPLE QUERIES (for reference, not executed)
-- =============================================================================
-- 
-- Get conversation history for a session:
-- SELECT * FROM brain_conversations 
-- WHERE session_id = 'session-123' 
-- ORDER BY created_at ASC;
--
-- Get total tokens for a session:
-- SELECT SUM(token_count) as total_tokens 
-- FROM brain_conversations 
-- WHERE session_id = 'session-123';
--
-- Get recent conversations:
-- SELECT DISTINCT session_id, MAX(created_at) as last_message
-- FROM brain_conversations
-- GROUP BY session_id
-- ORDER BY last_message DESC
-- LIMIT 10;
