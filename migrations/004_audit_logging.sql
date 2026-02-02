-- Migration: 004_audit_logging.sql

-- Create the audit log table with immutable hash chain
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    actor_type VARCHAR(50) NOT NULL,  -- worker, user, system
    actor_id VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),  -- task, experiment, tool, etc.
    resource_id VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    action_details JSONB,
    ip_address INET,
    user_agent TEXT,
    request_id UUID,
    session_id UUID,
    prev_state JSONB,
    new_state JSONB,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    duration_ms INTEGER,
    cost_usd DECIMAL(10,4),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    -- Immutable hash chain
    prev_hash VARCHAR(64),
    current_hash VARCHAR(64)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor_type, actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);

-- Function to compute hash chain
CREATE OR REPLACE FUNCTION compute_audit_hash()
RETURNS TRIGGER AS $$
DECLARE
    prev_record RECORD;
    hash_input TEXT;
BEGIN
    -- Get the previous record's hash
    SELECT current_hash INTO prev_record 
    FROM audit_log 
    ORDER BY created_at DESC 
    LIMIT 1;
    
    NEW.prev_hash := COALESCE(prev_record.current_hash, 'GENESIS');
    
    -- Compute current hash
    hash_input := NEW.prev_hash || NEW.event_type || NEW.actor_id || 
                  NEW.action || COALESCE(NEW.resource_id, '') || 
                  NEW.created_at::TEXT;
    NEW.current_hash := encode(sha256(hash_input::bytea), 'hex');
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to compute hash on insert
CREATE TRIGGER audit_hash_trigger
    BEFORE INSERT ON audit_log
    FOR EACH ROW
    EXECUTE FUNCTION compute_audit_hash();

-- Function to verify audit log integrity
CREATE OR REPLACE FUNCTION verify_audit_log_integrity()
RETURNS TABLE (
    id UUID,
    created_at TIMESTAMPTZ,
    hash_valid BOOLEAN,
    error_message TEXT
) AS $$
DECLARE
    prev_hash TEXT := 'GENESIS';
    curr_record RECORD;
    computed_hash TEXT;
    hash_input TEXT;
BEGIN
    FOR curr_record IN 
        SELECT * FROM audit_log ORDER BY created_at ASC
    LOOP
        -- Verify previous hash matches
        IF curr_record.prev_hash != prev_hash THEN
            id := curr_record.id;
            created_at := curr_record.created_at;
            hash_valid := FALSE;
            error_message := 'Previous hash mismatch';
            RETURN NEXT;
        END IF;
        
        -- Compute and verify current hash
        hash_input := curr_record.prev_hash || curr_record.event_type || curr_record.actor_id || 
                      curr_record.action || COALESCE(curr_record.resource_id, '') || 
                      curr_record.created_at::TEXT;
        computed_hash := encode(sha256(hash_input::bytea), 'hex');
        
        IF curr_record.current_hash != computed_hash THEN
            id := curr_record.id;
            created_at := curr_record.created_at;
            hash_valid := FALSE;
            error_message := 'Current hash mismatch';
            RETURN NEXT;
        END IF;
        
        -- Update previous hash for next iteration
        prev_hash := curr_record.current_hash;
    END LOOP;
    
    -- Return success if we made it through all records
    id := NULL;
    created_at := NOW();
    hash_valid := TRUE;
    error_message := 'Audit log integrity verified';
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;
