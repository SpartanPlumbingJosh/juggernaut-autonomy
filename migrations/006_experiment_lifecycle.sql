-- Migration: 006_experiment_lifecycle.sql

-- Create experiment snapshots table for state management
CREATE TABLE IF NOT EXISTS experiment_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL,
    snapshot_type VARCHAR(50) NOT NULL, -- 'pre_experiment', 'post_experiment', 'checkpoint', 'rollback_point'
    snapshot_data JSONB NOT NULL,
    tables_included TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),
    notes TEXT,
    metadata JSONB
);

-- Create index for efficient lookup
CREATE INDEX IF NOT EXISTS idx_snapshot_experiment ON experiment_snapshots(experiment_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_type ON experiment_snapshots(snapshot_type);
CREATE INDEX IF NOT EXISTS idx_snapshot_created ON experiment_snapshots(created_at);

-- Create hypotheses table for experiment tracking
CREATE TABLE IF NOT EXISTS hypotheses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(100),
    expected_outcome TEXT,
    success_criteria TEXT,
    confidence_level DECIMAL(3,2), -- 0.0 to 1.0
    priority VARCHAR(20) DEFAULT 'medium', -- 'critical', 'high', 'medium', 'low'
    status VARCHAR(20) DEFAULT 'draft', -- 'draft', 'active', 'validated', 'rejected', 'archived'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),
    tags TEXT[]
);

-- Create index for efficient lookup
CREATE INDEX IF NOT EXISTS idx_hypothesis_status ON hypotheses(status);
CREATE INDEX IF NOT EXISTS idx_hypothesis_category ON hypotheses(category);
CREATE INDEX IF NOT EXISTS idx_hypothesis_created ON hypotheses(created_at);
CREATE INDEX IF NOT EXISTS idx_hypothesis_tags ON hypotheses USING gin(tags);

-- Create experiment metrics table for tracking KPIs
CREATE TABLE IF NOT EXISTS experiment_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_type VARCHAR(50) NOT NULL, -- 'counter', 'gauge', 'histogram', 'revenue', 'conversion'
    baseline_value DECIMAL(20,5),
    target_value DECIMAL(20,5),
    actual_value DECIMAL(20,5),
    unit VARCHAR(20),
    collection_method VARCHAR(50), -- 'automatic', 'manual', 'calculated'
    collection_query TEXT, -- SQL query used to calculate the metric
    collection_frequency VARCHAR(20), -- 'hourly', 'daily', 'weekly', 'once'
    last_collected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

-- Create index for efficient lookup
CREATE INDEX IF NOT EXISTS idx_metrics_experiment ON experiment_metrics(experiment_id);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON experiment_metrics(metric_name);

-- Create experiment metric history for tracking changes
CREATE TABLE IF NOT EXISTS experiment_metric_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_id UUID NOT NULL REFERENCES experiment_metrics(id),
    value DECIMAL(20,5) NOT NULL,
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT
);

-- Create index for efficient lookup
CREATE INDEX IF NOT EXISTS idx_metric_history_metric ON experiment_metric_history(metric_id);
CREATE INDEX IF NOT EXISTS idx_metric_history_collected ON experiment_metric_history(collected_at);

-- Add hypothesis_id to experiments table
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS hypothesis_id UUID REFERENCES hypotheses(id);
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS lifecycle_state VARCHAR(50) DEFAULT 'created';
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS state_last_changed_at TIMESTAMPTZ;
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS can_rollback BOOLEAN DEFAULT FALSE;
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS rollback_snapshot_id UUID REFERENCES experiment_snapshots(id);

-- Create function to transition experiment state
CREATE OR REPLACE FUNCTION transition_experiment_state(
    p_experiment_id UUID,
    p_new_state VARCHAR(50),
    p_notes TEXT DEFAULT NULL,
    p_actor VARCHAR(100) DEFAULT 'system'
) RETURNS BOOLEAN AS $$
DECLARE
    v_current_state VARCHAR(50);
    v_valid_transition BOOLEAN := FALSE;
BEGIN
    -- Get current state
    SELECT lifecycle_state INTO v_current_state
    FROM experiments
    WHERE id = p_experiment_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Experiment % not found', p_experiment_id;
    END IF;
    
    -- Check if transition is valid
    -- Valid transitions:
    -- created -> preparing -> running -> evaluating -> completed
    --                      -> failed
    --                      -> rolled_back
    IF (v_current_state = 'created' AND p_new_state = 'preparing') OR
       (v_current_state = 'preparing' AND p_new_state = 'running') OR
       (v_current_state = 'running' AND p_new_state = 'evaluating') OR
       (v_current_state = 'evaluating' AND p_new_state = 'completed') OR
       (v_current_state IN ('preparing', 'running', 'evaluating') AND p_new_state = 'failed') OR
       (v_current_state IN ('running', 'evaluating') AND p_new_state = 'rolled_back') THEN
        v_valid_transition := TRUE;
    END IF;
    
    IF NOT v_valid_transition THEN
        RAISE EXCEPTION 'Invalid state transition from % to %', v_current_state, p_new_state;
    END IF;
    
    -- Update experiment state
    UPDATE experiments
    SET lifecycle_state = p_new_state,
        state_last_changed_at = NOW(),
        updated_at = NOW()
    WHERE id = p_experiment_id;
    
    -- Log the transition
    INSERT INTO experiment_state_history (
        experiment_id, from_state, to_state, 
        transitioned_by, notes
    ) VALUES (
        p_experiment_id, v_current_state, p_new_state,
        p_actor, p_notes
    );
    
    RETURN TRUE;
EXCEPTION
    WHEN OTHERS THEN
        RAISE;
END;
$$ LANGUAGE plpgsql;

-- Create experiment state history table
CREATE TABLE IF NOT EXISTS experiment_state_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL,
    from_state VARCHAR(50) NOT NULL,
    to_state VARCHAR(50) NOT NULL,
    transitioned_at TIMESTAMPTZ DEFAULT NOW(),
    transitioned_by VARCHAR(100),
    notes TEXT
);

-- Create index for efficient lookup
CREATE INDEX IF NOT EXISTS idx_state_history_experiment ON experiment_state_history(experiment_id);
CREATE INDEX IF NOT EXISTS idx_state_history_to ON experiment_state_history(to_state);
CREATE INDEX IF NOT EXISTS idx_state_history_transitioned ON experiment_state_history(transitioned_at);

-- Create function to create experiment snapshot
CREATE OR REPLACE FUNCTION create_experiment_snapshot(
    p_experiment_id UUID,
    p_snapshot_type VARCHAR(50),
    p_tables TEXT[] DEFAULT NULL,
    p_notes TEXT DEFAULT NULL,
    p_created_by VARCHAR(100) DEFAULT 'system'
) RETURNS UUID AS $$
DECLARE
    v_snapshot_id UUID;
    v_snapshot_data JSONB := '{}'::JSONB;
    v_table TEXT;
    v_query TEXT;
    v_result JSONB;
    v_tables_to_snapshot TEXT[];
BEGIN
    -- Determine which tables to snapshot
    IF p_tables IS NULL THEN
        -- Default tables to snapshot
        v_tables_to_snapshot := ARRAY[
            'experiments',
            'experiment_tasks',
            'experiment_metrics'
        ];
    ELSE
        v_tables_to_snapshot := p_tables;
    END IF;
    
    -- Snapshot experiment data
    SELECT row_to_json(e)::JSONB INTO v_result
    FROM experiments e
    WHERE id = p_experiment_id;
    
    IF v_result IS NULL THEN
        RAISE EXCEPTION 'Experiment % not found', p_experiment_id;
    END IF;
    
    v_snapshot_data := jsonb_set(v_snapshot_data, '{experiment}', v_result);
    
    -- Snapshot related tables
    FOREACH v_table IN ARRAY v_tables_to_snapshot
    LOOP
        CASE v_table
            WHEN 'experiment_tasks' THEN
                v_query := format(
                    'SELECT COALESCE(jsonb_agg(t), ''[]''::jsonb) FROM experiment_tasks t WHERE experiment_id = %L',
                    p_experiment_id
                );
            WHEN 'experiment_metrics' THEN
                v_query := format(
                    'SELECT COALESCE(jsonb_agg(m), ''[]''::jsonb) FROM experiment_metrics m WHERE experiment_id = %L',
                    p_experiment_id
                );
            WHEN 'experiment_metric_history' THEN
                v_query := format(
                    'SELECT COALESCE(jsonb_agg(h), ''[]''::jsonb) FROM experiment_metric_history h ' ||
                    'JOIN experiment_metrics m ON h.metric_id = m.id ' ||
                    'WHERE m.experiment_id = %L',
                    p_experiment_id
                );
            ELSE
                -- Skip unknown tables
                CONTINUE;
        END CASE;
        
        EXECUTE v_query INTO v_result;
        v_snapshot_data := jsonb_set(v_snapshot_data, ('{'|| v_table || '}')::text[], v_result);
    END LOOP;
    
    -- Create snapshot record
    INSERT INTO experiment_snapshots (
        experiment_id, snapshot_type, snapshot_data,
        tables_included, created_by, notes
    ) VALUES (
        p_experiment_id, p_snapshot_type, v_snapshot_data,
        v_tables_to_snapshot, p_created_by, p_notes
    ) RETURNING id INTO v_snapshot_id;
    
    -- If this is a rollback snapshot, update the experiment
    IF p_snapshot_type = 'rollback_point' THEN
        UPDATE experiments
        SET can_rollback = TRUE,
            rollback_snapshot_id = v_snapshot_id
        WHERE id = p_experiment_id;
    END IF;
    
    RETURN v_snapshot_id;
EXCEPTION
    WHEN OTHERS THEN
        RAISE;
END;
$$ LANGUAGE plpgsql;

-- Create function to rollback experiment
CREATE OR REPLACE FUNCTION rollback_experiment(
    p_experiment_id UUID,
    p_snapshot_id UUID DEFAULT NULL,
    p_actor VARCHAR(100) DEFAULT 'system',
    p_notes TEXT DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    v_snapshot_id UUID;
    v_snapshot_data JSONB;
    v_experiment_data JSONB;
    v_tasks JSONB;
    v_metrics JSONB;
    v_task JSONB;
    v_metric JSONB;
    v_task_id UUID;
    v_metric_id UUID;
BEGIN
    -- Get snapshot ID if not provided
    IF p_snapshot_id IS NULL THEN
        SELECT rollback_snapshot_id INTO v_snapshot_id
        FROM experiments
        WHERE id = p_experiment_id AND can_rollback = TRUE;
        
        IF v_snapshot_id IS NULL THEN
            RAISE EXCEPTION 'No rollback snapshot available for experiment %', p_experiment_id;
        END IF;
    ELSE
        v_snapshot_id := p_snapshot_id;
    END IF;
    
    -- Get snapshot data
    SELECT snapshot_data INTO v_snapshot_data
    FROM experiment_snapshots
    WHERE id = v_snapshot_id AND experiment_id = p_experiment_id;
    
    IF v_snapshot_data IS NULL THEN
        RAISE EXCEPTION 'Snapshot % not found for experiment %', v_snapshot_id, p_experiment_id;
    END IF;
    
    -- Extract data from snapshot
    v_experiment_data := v_snapshot_data->'experiment';
    v_tasks := v_snapshot_data->'experiment_tasks';
    v_metrics := v_snapshot_data->'experiment_metrics';
    
    -- Create a new snapshot of current state before rollback
    PERFORM create_experiment_snapshot(
        p_experiment_id,
        'pre_rollback',
        NULL,
        'Auto-created before rollback',
        p_actor
    );
    
    -- Rollback experiment tasks (delete current and recreate from snapshot)
    DELETE FROM experiment_tasks WHERE experiment_id = p_experiment_id;
    
    IF v_tasks IS NOT NULL AND jsonb_array_length(v_tasks) > 0 THEN
        FOR i IN 0..jsonb_array_length(v_tasks)-1
        LOOP
            v_task := v_tasks->i;
            v_task_id := (v_task->>'id')::UUID;
            
            -- Insert task from snapshot
            INSERT INTO experiment_tasks (
                id, experiment_id, title, description,
                task_type, status, priority, assigned_worker,
                completion_evidence, created_at, updated_at
            ) VALUES (
                v_task_id,
                p_experiment_id,
                v_task->>'title',
                v_task->>'description',
                v_task->>'task_type',
                v_task->>'status',
                v_task->>'priority',
                v_task->>'assigned_worker',
                (v_task->'completion_evidence')::JSONB,
                (v_task->>'created_at')::TIMESTAMPTZ,
                NOW()
            );
        END LOOP;
    END IF;
    
    -- Rollback experiment metrics (update to snapshot values)
    IF v_metrics IS NOT NULL AND jsonb_array_length(v_metrics) > 0 THEN
        FOR i IN 0..jsonb_array_length(v_metrics)-1
        LOOP
            v_metric := v_metrics->i;
            v_metric_id := (v_metric->>'id')::UUID;
            
            -- Update or insert metric
            INSERT INTO experiment_metrics (
                id, experiment_id, metric_name, metric_type,
                baseline_value, target_value, actual_value,
                unit, collection_method, collection_query,
                collection_frequency, last_collected_at,
                created_at, updated_at
            ) VALUES (
                v_metric_id,
                p_experiment_id,
                v_metric->>'metric_name',
                v_metric->>'metric_type',
                (v_metric->>'baseline_value')::DECIMAL,
                (v_metric->>'target_value')::DECIMAL,
                (v_metric->>'actual_value')::DECIMAL,
                v_metric->>'unit',
                v_metric->>'collection_method',
                v_metric->>'collection_query',
                v_metric->>'collection_frequency',
                (v_metric->>'last_collected_at')::TIMESTAMPTZ,
                (v_metric->>'created_at')::TIMESTAMPTZ,
                NOW()
            )
            ON CONFLICT (id) DO UPDATE SET
                metric_name = EXCLUDED.metric_name,
                metric_type = EXCLUDED.metric_type,
                baseline_value = EXCLUDED.baseline_value,
                target_value = EXCLUDED.target_value,
                actual_value = EXCLUDED.actual_value,
                unit = EXCLUDED.unit,
                collection_method = EXCLUDED.collection_method,
                collection_query = EXCLUDED.collection_query,
                collection_frequency = EXCLUDED.collection_frequency,
                updated_at = NOW();
        END LOOP;
    END IF;
    
    -- Transition experiment state to rolled_back
    PERFORM transition_experiment_state(
        p_experiment_id,
        'rolled_back',
        p_notes,
        p_actor
    );
    
    RETURN TRUE;
EXCEPTION
    WHEN OTHERS THEN
        RAISE;
END;
$$ LANGUAGE plpgsql;
