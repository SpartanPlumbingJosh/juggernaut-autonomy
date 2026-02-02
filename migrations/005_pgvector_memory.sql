-- Migration: 005_pgvector_memory.sql

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create agent memories table with vector embeddings
CREATE TABLE IF NOT EXISTS agent_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id VARCHAR(100) NOT NULL,
    memory_type VARCHAR(50) NOT NULL,  -- working, episodic, semantic, procedural
    
    -- Content
    content TEXT NOT NULL,
    summary TEXT,
    embedding vector(1536),  -- OpenAI ada-002 dimensions
    
    -- Metadata
    source_type VARCHAR(50),  -- task, conversation, observation, inference
    source_id UUID,
    confidence_score DECIMAL(3,2) DEFAULT 1.0,
    importance_score DECIMAL(3,2) DEFAULT 0.5,
    
    -- Memory lifecycle
    access_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMPTZ,
    decay_factor DECIMAL(3,2) DEFAULT 1.0,
    expires_at TIMESTAMPTZ,
    
    -- Relationships
    parent_memory_id UUID REFERENCES agent_memories(id),
    related_memories UUID[],
    tags TEXT[],
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create vector similarity search index
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON agent_memories 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create standard indexes
CREATE INDEX IF NOT EXISTS idx_memories_worker ON agent_memories(worker_id);
CREATE INDEX IF NOT EXISTS idx_memories_type ON agent_memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_source ON agent_memories(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_memories_tags ON agent_memories USING gin(tags);

-- Create shared knowledge base (cross-agent)
CREATE TABLE IF NOT EXISTS knowledge_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(100) NOT NULL,  -- concept, fact, procedure, person, organization
    name VARCHAR(255) NOT NULL,
    description TEXT,
    embedding vector(1536),
    
    -- Knowledge graph
    properties JSONB DEFAULT '{}',
    
    -- Verification
    verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(100),
    verified_at TIMESTAMPTZ,
    confidence_score DECIMAL(3,2) DEFAULT 0.5,
    
    -- Sources
    source_memories UUID[],
    source_urls TEXT[],
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100)
);

-- Create vector similarity search index for knowledge entities
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding ON knowledge_entities 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create standard indexes for knowledge entities
CREATE INDEX IF NOT EXISTS idx_knowledge_type ON knowledge_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_name ON knowledge_entities(name);

-- Create knowledge relationships table
CREATE TABLE IF NOT EXISTS knowledge_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_entity_id UUID REFERENCES knowledge_entities(id) ON DELETE CASCADE,
    to_entity_id UUID REFERENCES knowledge_entities(id) ON DELETE CASCADE,
    relation_type VARCHAR(100) NOT NULL,  -- is_a, part_of, related_to, causes, etc.
    strength DECIMAL(3,2) DEFAULT 1.0,
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_entity_id, to_entity_id, relation_type)
);

-- Create indexes for knowledge relations
CREATE INDEX IF NOT EXISTS idx_relations_from ON knowledge_relations(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_relations_to ON knowledge_relations(to_entity_id);
CREATE INDEX IF NOT EXISTS idx_relations_type ON knowledge_relations(relation_type);

-- Create knowledge claims table for tracking facts vs opinions
CREATE TABLE IF NOT EXISTS knowledge_claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID REFERENCES knowledge_entities(id),
    claim_type VARCHAR(20) NOT NULL,  -- fact, opinion, inference
    claim_text TEXT NOT NULL,
    confidence_score DECIMAL(3,2) DEFAULT 0.5,
    consensus_level VARCHAR(20) DEFAULT 'unverified',  -- verified, disputed, unverified
    verified_by_agents UUID[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for knowledge claims
CREATE INDEX IF NOT EXISTS idx_claims_entity ON knowledge_claims(entity_id);
CREATE INDEX IF NOT EXISTS idx_claims_type ON knowledge_claims(claim_type);
CREATE INDEX IF NOT EXISTS idx_claims_consensus ON knowledge_claims(consensus_level);

-- Function to search for memories by vector similarity
CREATE OR REPLACE FUNCTION search_memories(
    p_query_embedding vector(1536),
    p_worker_id VARCHAR(100),
    p_memory_types VARCHAR[] DEFAULT NULL,
    p_min_similarity FLOAT DEFAULT 0.7,
    p_limit INTEGER DEFAULT 10
) RETURNS TABLE (
    id UUID,
    worker_id VARCHAR(100),
    memory_type VARCHAR(50),
    content TEXT,
    summary TEXT,
    similarity FLOAT,
    importance_score FLOAT,
    confidence_score FLOAT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.id,
        m.worker_id,
        m.memory_type,
        m.content,
        m.summary,
        1 - (m.embedding <=> p_query_embedding) AS similarity,
        m.importance_score,
        m.confidence_score,
        m.created_at
    FROM agent_memories m
    WHERE m.worker_id = p_worker_id
      AND (p_memory_types IS NULL OR m.memory_type = ANY(p_memory_types))
      AND 1 - (m.embedding <=> p_query_embedding) > p_min_similarity
    ORDER BY similarity DESC, m.importance_score DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to search knowledge entities by vector similarity
CREATE OR REPLACE FUNCTION search_knowledge(
    p_query_embedding vector(1536),
    p_entity_type VARCHAR[] DEFAULT NULL,
    p_min_similarity FLOAT DEFAULT 0.7,
    p_limit INTEGER DEFAULT 10
) RETURNS TABLE (
    id UUID,
    entity_type VARCHAR(100),
    name VARCHAR(255),
    description TEXT,
    similarity FLOAT,
    confidence_score FLOAT,
    verified BOOLEAN,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        k.id,
        k.entity_type,
        k.name,
        k.description,
        1 - (k.embedding <=> p_query_embedding) AS similarity,
        k.confidence_score,
        k.verified,
        k.created_at
    FROM knowledge_entities k
    WHERE (p_entity_type IS NULL OR k.entity_type = ANY(p_entity_type))
      AND 1 - (k.embedding <=> p_query_embedding) > p_min_similarity
    ORDER BY similarity DESC, k.confidence_score DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;
