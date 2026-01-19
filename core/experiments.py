"""
JUGGERNAUT Experimentation Framework (Phase 4)

Provides L4 capabilities for designing, executing, analyzing experiments,
managing rollbacks, and extracting learnings for self-improvement.

Functions:
- Phase 4.1: Experiment Design (templates, creation)
- Phase 4.2: Experiment Execution (start, pause, checkpoints)
- Phase 4.3: Experiment Analysis (results, success criteria)
- Phase 4.4: Rollback System (snapshots, auto-rollback)
- Phase 4.5: Self-Improvement (learnings extraction)
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

# Configure logging
logger = logging.getLogger(__name__)

# Database configuration
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
NEON_CONNECTION_STRING = "postgresql://neondb_owner:npg_OYkCRU4aze2l@ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"


def _execute_sql(query: str, return_results: bool = True) -> Dict[str, Any]:
    """Execute SQL query against Neon database."""
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": NEON_CONNECTION_STRING
    }
    response = httpx.post(
        NEON_ENDPOINT,
        json={"query": query},
        headers=headers,
        timeout=30.0
    )
    result = response.json()
    
    if return_results and "rows" in result:
        return {"success": True, "rows": result["rows"], "rowCount": result.get("rowCount", 0)}
    return {"success": True, "rowCount": result.get("rowCount", 0)}


def _escape_string(value: str) -> str:
    """Escape single quotes for SQL."""
    if value is None:
        return "NULL"
    return value.replace("'", "''")


# =============================================================================
# PHASE 4.1: EXPERIMENT DESIGN
# =============================================================================

def create_experiment_template(
    name: str,
    description: str,
    experiment_type: str,
    category: str,
    default_hypothesis: str,
    default_success_criteria: Dict[str, Any],
    default_failure_criteria: Optional[Dict[str, Any]] = None,
    default_budget_limit: float = 100.0,
    default_max_iterations: int = 10,
    config_schema: Optional[Dict[str, Any]] = None,
    required_tools: Optional[List[str]] = None,
    estimated_duration_days: int = 7,
    risk_level: str = "low",
    created_by: str = "SYSTEM"
) -> Dict[str, Any]:
    """
    Create a reusable experiment template.
    
    Templates provide blueprints for common experiment types, reducing
    setup time and ensuring consistency.
    
    Args:
        name: Template name (e.g., "digital_product_launch")
        description: What this template is for
        experiment_type: Category (revenue, cost_reduction, optimization, etc.)
        category: Business area (digital_products, domain, saas, etc.)
        default_hypothesis: Starting hypothesis text
        default_success_criteria: JSONB of success conditions
        default_failure_criteria: Optional JSONB of failure conditions
        default_budget_limit: Default budget cap
        default_max_iterations: Default iteration limit
        config_schema: JSON Schema for experiment config validation
        required_tools: List of tool names needed for this experiment
        estimated_duration_days: Expected duration
        risk_level: low, medium, high
        created_by: Worker/user creating the template
    
    Returns:
        Dict with template_id and creation status
    """
    template_id = str(uuid.uuid4())
    
    query = f"""
    INSERT INTO experiment_templates (
        id, name, description, experiment_type, category,
        default_hypothesis, default_success_criteria, default_failure_criteria,
        default_budget_limit, default_max_iterations, config_schema,
        required_tools, estimated_duration_days, risk_level,
        usage_count, created_by
    ) VALUES (
        '{template_id}',
        '{_escape_string(name)}',
        '{_escape_string(description)}',
        '{_escape_string(experiment_type)}',
        '{_escape_string(category)}',
        '{_escape_string(default_hypothesis)}',
        '{json.dumps(default_success_criteria)}'::jsonb,
        {f"'{json.dumps(default_failure_criteria)}'::jsonb" if default_failure_criteria else "NULL"},
        {default_budget_limit},
        {default_max_iterations},
        {f"'{json.dumps(config_schema)}'::jsonb" if config_schema else "'{}'::jsonb"},
        {f"'{json.dumps(required_tools)}'::jsonb" if required_tools else "'[]'::jsonb"},
        {estimated_duration_days},
        '{_escape_string(risk_level)}',
        0,
        '{_escape_string(created_by)}'
    )
    RETURNING id
    """
    
    result = _execute_sql(query)
    return {
        "success": True,
        "template_id": template_id,
        "message": f"Template '{name}' created successfully"
    }


def list_experiment_templates(
    category: Optional[str] = None,
    experiment_type: Optional[str] = None,
    risk_level: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List available experiment templates with optional filtering.
    
    Args:
        category: Filter by business category
        experiment_type: Filter by experiment type
        risk_level: Filter by risk level
    
    Returns:
        List of template dictionaries
    """
    conditions = []
    if category:
        conditions.append(f"category = '{_escape_string(category)}'")
    if experiment_type:
        conditions.append(f"experiment_type = '{_escape_string(experiment_type)}'")
    if risk_level:
        conditions.append(f"risk_level = '{_escape_string(risk_level)}'")
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    query = f"""
    SELECT id, name, description, experiment_type, category,
           default_budget_limit, default_max_iterations,
           risk_level, usage_count, last_used_at, created_at
    FROM experiment_templates
    {where_clause}
    ORDER BY usage_count DESC, created_at DESC
    """
    
    result = _execute_sql(query)
    return result.get("rows", [])


def create_experiment(
    name: str,
    hypothesis: str,
    success_criteria: Dict[str, Any],
    experiment_type: str = "revenue",
    description: Optional[str] = None,
    failure_criteria: Optional[Dict[str, Any]] = None,
    budget_limit: float = 50.0,
    max_iterations: int = 10,
    cost_per_iteration: Optional[float] = None,
    scheduled_end: Optional[datetime] = None,
    owner_worker: str = "ORCHESTRATOR",
    template_id: Optional[str] = None,
    parent_experiment_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    config: Optional[Dict[str, Any]] = None,
    created_by: str = "SYSTEM"
) -> Dict[str, Any]:
    """
    Create a new experiment.
    
    This is the main experiment creation function. Experiments track hypotheses,
    success criteria, budget, and progress toward proving/disproving the hypothesis.
    
    Args:
        name: Experiment name
        hypothesis: What you're testing (e.g., "AI prompts sell better at $9 than $19")
        success_criteria: JSONB conditions for success (e.g., {"revenue": {">=": 100}})
        experiment_type: Type (revenue, cost_reduction, optimization, growth)
        description: Detailed description
        failure_criteria: Optional conditions that indicate failure
        budget_limit: Maximum spend on this experiment
        max_iterations: Maximum iterations before concluding
        cost_per_iteration: Expected cost per iteration
        scheduled_end: When the experiment should end
        owner_worker: Worker responsible for this experiment
        template_id: If using a template
        parent_experiment_id: If this is a sub-experiment
        tags: List of tags for categorization
        config: Experiment-specific configuration
        created_by: Who created this experiment
    
    Returns:
        Dict with experiment_id and creation status
    """
    experiment_id = str(uuid.uuid4())
    
    # Update template usage count if using a template
    if template_id:
        _execute_sql(f"""
        UPDATE experiment_templates 
        SET usage_count = usage_count + 1, last_used_at = NOW()
        WHERE id = '{template_id}'
        """)
    
    scheduled_end_str = f"'{scheduled_end.isoformat()}'" if scheduled_end else "NULL"
    
    query = f"""
    INSERT INTO experiments (
        id, name, description, experiment_type, status,
        hypothesis, success_criteria, failure_criteria,
        budget_limit, budget_spent, cost_per_iteration,
        max_iterations, current_iteration,
        scheduled_end, owner_worker, template_id,
        parent_experiment_id, tags, config, created_by
    ) VALUES (
        '{experiment_id}',
        '{_escape_string(name)}',
        {f"'{_escape_string(description)}'" if description else "NULL"},
        '{_escape_string(experiment_type)}',
        'draft',
        '{_escape_string(hypothesis)}',
        '{json.dumps(success_criteria)}'::jsonb,
        {f"'{json.dumps(failure_criteria)}'::jsonb" if failure_criteria else "NULL"},
        {budget_limit},
        0,
        {cost_per_iteration if cost_per_iteration else "NULL"},
        {max_iterations},
        0,
        {scheduled_end_str},
        '{_escape_string(owner_worker)}',
        {f"'{template_id}'" if template_id else "NULL"},
        {f"'{parent_experiment_id}'" if parent_experiment_id else "NULL"},
        '{json.dumps(tags or [])}'::jsonb,
        '{json.dumps(config or {})}'::jsonb,
        '{_escape_string(created_by)}'
    )
    RETURNING id
    """
    
    result = _execute_sql(query)
    
    # Log the creation
    log_experiment_event(experiment_id, "created", f"Experiment '{name}' created", created_by)
    
    return {
        "success": True,
        "experiment_id": experiment_id,
        "message": f"Experiment '{name}' created in draft status"
    }


def get_experiment(experiment_id: str) -> Optional[Dict[str, Any]]:
    """Get experiment details by ID."""
    query = f"SELECT * FROM experiments WHERE id = '{experiment_id}'"
    result = _execute_sql(query)
    rows = result.get("rows", [])
    return rows[0] if rows else None


def list_experiments(
    status: Optional[str] = None,
    experiment_type: Optional[str] = None,
    owner_worker: Optional[str] = None,
    tags: Optional[List[str]] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    List experiments with filtering.
    
    Args:
        status: Filter by status (draft, running, paused, completed, failed)
        experiment_type: Filter by type
        owner_worker: Filter by owner
        tags: Filter by any matching tags
        limit: Maximum results
    
    Returns:
        List of experiment dictionaries
    """
    conditions = []
    if status:
        conditions.append(f"status = '{_escape_string(status)}'")
    if experiment_type:
        conditions.append(f"experiment_type = '{_escape_string(experiment_type)}'")
    if owner_worker:
        conditions.append(f"owner_worker = '{_escape_string(owner_worker)}'")
    if tags:
        tags_json = json.dumps(tags)
        conditions.append(f"tags ?| array{tags}")
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    query = f"""
    SELECT id, name, experiment_type, status, hypothesis,
           budget_limit, budget_spent, current_iteration, max_iterations,
           owner_worker, tags, start_date, scheduled_end, created_at
    FROM experiments
    {where_clause}
    ORDER BY created_at DESC
    LIMIT {limit}
    """
    
    result = _execute_sql(query)
    return result.get("rows", [])


# =============================================================================
# PHASE 4.2: EXPERIMENT EXECUTION
# =============================================================================

def start_experiment(experiment_id: str, started_by: str = "SYSTEM") -> Dict[str, Any]:
    """
    Start an experiment (move from draft to running).
    
    Creates an initial rollback snapshot before starting.
    
    Args:
        experiment_id: Experiment to start
        started_by: Who is starting it
    
    Returns:
        Dict with status
    """
    # Check current status
    experiment = get_experiment(experiment_id)
    if not experiment:
        return {"success": False, "error": "Experiment not found"}
    
    if experiment["status"] not in ["draft", "paused"]:
        return {"success": False, "error": f"Cannot start experiment in {experiment['status']} status"}
    
    # Create rollback snapshot before starting
    create_rollback_snapshot(experiment_id, "pre_start", started_by)
    
    # Update status to running
    query = f"""
    UPDATE experiments
    SET status = 'running',
        start_date = COALESCE(start_date, NOW()),
        updated_at = NOW()
    WHERE id = '{experiment_id}'
    """
    _execute_sql(query)
    
    log_experiment_event(experiment_id, "started", "Experiment started", started_by)
    
    return {"success": True, "message": "Experiment started"}


def pause_experiment(experiment_id: str, reason: str, paused_by: str = "SYSTEM") -> Dict[str, Any]:
    """
    Pause a running experiment.
    
    Args:
        experiment_id: Experiment to pause
        reason: Why it's being paused
        paused_by: Who paused it
    
    Returns:
        Dict with status
    """
    query = f"""
    UPDATE experiments
    SET status = 'paused',
        updated_at = NOW()
    WHERE id = '{experiment_id}' AND status = 'running'
    """
    result = _execute_sql(query)
    
    if result.get("rowCount", 0) > 0:
        log_experiment_event(experiment_id, "paused", f"Paused: {reason}", paused_by)
        return {"success": True, "message": "Experiment paused"}
    return {"success": False, "error": "Could not pause experiment"}


def resume_experiment(experiment_id: str, resumed_by: str = "SYSTEM") -> Dict[str, Any]:
    """Resume a paused experiment."""
    query = f"""
    UPDATE experiments
    SET status = 'running',
        updated_at = NOW()
    WHERE id = '{experiment_id}' AND status = 'paused'
    """
    result = _execute_sql(query)
    
    if result.get("rowCount", 0) > 0:
        log_experiment_event(experiment_id, "resumed", "Experiment resumed", resumed_by)
        return {"success": True, "message": "Experiment resumed"}
    return {"success": False, "error": "Could not resume experiment"}


def increment_iteration(
    experiment_id: str,
    iteration_notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Increment the experiment iteration counter.
    
    Automatically concludes the experiment if max_iterations is reached.
    
    Args:
        experiment_id: Experiment to increment
        iteration_notes: Optional notes about this iteration
    
    Returns:
        Dict with new iteration number and status
    """
    # Get current state
    experiment = get_experiment(experiment_id)
    if not experiment:
        return {"success": False, "error": "Experiment not found"}
    
    new_iteration = (experiment.get("current_iteration") or 0) + 1
    max_iterations = experiment.get("max_iterations")
    
    # Check if we've hit max iterations
    if max_iterations and new_iteration >= max_iterations:
        query = f"""
        UPDATE experiments
        SET current_iteration = {new_iteration},
            status = 'completed',
            end_date = NOW(),
            conclusion = 'Max iterations reached',
            updated_at = NOW()
        WHERE id = '{experiment_id}'
        """
        _execute_sql(query)
        log_experiment_event(experiment_id, "completed", "Max iterations reached", "SYSTEM")
        return {
            "success": True,
            "iteration": new_iteration,
            "status": "completed",
            "message": "Experiment completed - max iterations reached"
        }
    
    # Normal iteration increment
    query = f"""
    UPDATE experiments
    SET current_iteration = {new_iteration},
        updated_at = NOW()
    WHERE id = '{experiment_id}'
    """
    _execute_sql(query)
    
    if iteration_notes:
        log_experiment_event(experiment_id, "iteration", f"Iteration {new_iteration}: {iteration_notes}", "SYSTEM")
    
    return {
        "success": True,
        "iteration": new_iteration,
        "status": "running"
    }


def record_experiment_cost(
    experiment_id: str,
    amount: float,
    description: str,
    cost_type: str = "api"
) -> Dict[str, Any]:
    """
    Record a cost against an experiment's budget.
    
    Automatically pauses experiment if budget is exhausted.
    
    Args:
        experiment_id: Experiment to record cost for
        amount: Cost amount
        description: What the cost was for
        cost_type: Type of cost (api, infrastructure, marketing, etc.)
    
    Returns:
        Dict with new budget status
    """
    # Update budget spent
    query = f"""
    UPDATE experiments
    SET budget_spent = COALESCE(budget_spent, 0) + {amount},
        updated_at = NOW()
    WHERE id = '{experiment_id}'
    RETURNING budget_spent, budget_limit
    """
    result = _execute_sql(query)
    
    if not result.get("rows"):
        return {"success": False, "error": "Experiment not found"}
    
    row = result["rows"][0]
    budget_spent = float(row["budget_spent"])
    budget_limit = float(row["budget_limit"]) if row["budget_limit"] else None
    
    # Also record in cost_events for tracking
    _execute_sql(f"""
    INSERT INTO cost_events (cost_type, category, amount, description, experiment_id)
    VALUES ('{cost_type}', 'experiment', {amount}, '{_escape_string(description)}', '{experiment_id}')
    """)
    
    # Check budget exhaustion
    if budget_limit and budget_spent >= budget_limit:
        pause_experiment(experiment_id, "Budget exhausted", "SYSTEM")
        return {
            "success": True,
            "budget_spent": budget_spent,
            "budget_limit": budget_limit,
            "budget_exhausted": True,
            "message": "Budget exhausted - experiment paused"
        }
    
    # Warning at 80% budget
    if budget_limit and budget_spent >= budget_limit * 0.8:
        log_experiment_event(
            experiment_id, "warning",
            f"Budget 80% consumed: ${budget_spent:.2f} of ${budget_limit:.2f}",
            "SYSTEM"
        )
    
    return {
        "success": True,
        "budget_spent": budget_spent,
        "budget_limit": budget_limit,
        "budget_remaining": (budget_limit - budget_spent) if budget_limit else None
    }


def create_variant(
    experiment_id: str,
    name: str,
    description: Optional[str] = None,
    is_control: bool = False,
    traffic_percentage: int = 50,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a variant for A/B testing within an experiment.
    
    Args:
        experiment_id: Parent experiment
        name: Variant name (e.g., "Control", "Treatment A")
        description: What this variant tests
        is_control: Is this the control group?
        traffic_percentage: Percentage of traffic to send to this variant
        config: Variant-specific configuration
    
    Returns:
        Dict with variant_id
    """
    variant_id = str(uuid.uuid4())
    
    query = f"""
    INSERT INTO experiment_variants (
        id, experiment_id, name, description, is_control,
        traffic_percentage, config, sample_size, conversions,
        revenue_generated, status
    ) VALUES (
        '{variant_id}',
        '{experiment_id}',
        '{_escape_string(name)}',
        {f"'{_escape_string(description)}'" if description else "NULL"},
        {is_control},
        {traffic_percentage},
        '{json.dumps(config or {})}'::jsonb,
        0, 0, 0, 'active'
    )
    RETURNING id
    """
    
    result = _execute_sql(query)
    
    return {
        "success": True,
        "variant_id": variant_id,
        "message": f"Variant '{name}' created"
    }


def update_variant_metrics(
    variant_id: str,
    sample_size_delta: int = 0,
    conversions_delta: int = 0,
    revenue_delta: float = 0.0
) -> Dict[str, Any]:
    """
    Update variant metrics (for A/B test tracking).
    
    Args:
        variant_id: Variant to update
        sample_size_delta: Number to add to sample size
        conversions_delta: Number to add to conversions
        revenue_delta: Amount to add to revenue
    
    Returns:
        Dict with updated metrics
    """
    query = f"""
    UPDATE experiment_variants
    SET sample_size = sample_size + {sample_size_delta},
        conversions = conversions + {conversions_delta},
        revenue_generated = revenue_generated + {revenue_delta},
        updated_at = NOW()
    WHERE id = '{variant_id}'
    RETURNING sample_size, conversions, revenue_generated
    """
    
    result = _execute_sql(query)
    if result.get("rows"):
        return {"success": True, "metrics": result["rows"][0]}
    return {"success": False, "error": "Variant not found"}


def create_checkpoint(
    experiment_id: str,
    checkpoint_name: str,
    state_snapshot: Dict[str, Any],
    metrics_at_checkpoint: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
    created_by: str = "SYSTEM"
) -> Dict[str, Any]:
    """
    Create a checkpoint to save experiment state.
    
    Checkpoints allow resuming experiments from a known good state.
    
    Args:
        experiment_id: Experiment to checkpoint
        checkpoint_name: Name for this checkpoint
        state_snapshot: Current state to save
        metrics_at_checkpoint: Current metrics
        notes: Additional notes
        created_by: Who created the checkpoint
    
    Returns:
        Dict with checkpoint_id
    """
    checkpoint_id = str(uuid.uuid4())
    
    # Get current iteration
    experiment = get_experiment(experiment_id)
    iteration = experiment.get("current_iteration", 0) if experiment else 0
    
    query = f"""
    INSERT INTO experiment_checkpoints (
        id, experiment_id, checkpoint_name, iteration_number,
        state_snapshot, metrics_at_checkpoint, notes, created_by
    ) VALUES (
        '{checkpoint_id}',
        '{experiment_id}',
        '{_escape_string(checkpoint_name)}',
        {iteration},
        '{json.dumps(state_snapshot)}'::jsonb,
        {f"'{json.dumps(metrics_at_checkpoint)}'::jsonb" if metrics_at_checkpoint else "NULL"},
        {f"'{_escape_string(notes)}'" if notes else "NULL"},
        '{_escape_string(created_by)}'
    )
    """
    
    _execute_sql(query)
    log_experiment_event(experiment_id, "checkpoint", f"Checkpoint '{checkpoint_name}' created", created_by)
    
    return {
        "success": True,
        "checkpoint_id": checkpoint_id,
        "iteration": iteration
    }


def get_checkpoints(experiment_id: str) -> List[Dict[str, Any]]:
    """Get all checkpoints for an experiment."""
    query = f"""
    SELECT id, checkpoint_name, iteration_number, 
           metrics_at_checkpoint, notes, created_at, created_by
    FROM experiment_checkpoints
    WHERE experiment_id = '{experiment_id}'
    ORDER BY created_at DESC
    """
    result = _execute_sql(query)
    return result.get("rows", [])


def get_latest_checkpoint(experiment_id: str) -> Optional[Dict[str, Any]]:
    """Get the most recent checkpoint for an experiment."""
    query = f"""
    SELECT * FROM experiment_checkpoints
    WHERE experiment_id = '{experiment_id}'
    ORDER BY created_at DESC
    LIMIT 1
    """
    result = _execute_sql(query)
    rows = result.get("rows", [])
    return rows[0] if rows else None


# =============================================================================
# PHASE 4.3: EXPERIMENT ANALYSIS
# =============================================================================

def record_result(
    experiment_id: str,
    metric_name: str,
    metric_value: float,
    metric_type: str = "numeric",
    variant_id: Optional[str] = None,
    iteration: Optional[int] = None,
    raw_data: Optional[Dict[str, Any]] = None,
    source: str = "manual",
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Record an experiment result/metric.
    
    Args:
        experiment_id: Experiment this result belongs to
        metric_name: Name of the metric (e.g., "revenue", "conversions")
        metric_value: The value
        metric_type: Type (numeric, percentage, currency, count)
        variant_id: If A/B testing, which variant
        iteration: Which iteration (defaults to current)
        raw_data: Additional raw data
        source: Where this data came from
        notes: Additional notes
    
    Returns:
        Dict with result_id
    """
    result_id = str(uuid.uuid4())
    
    # Get current iteration if not specified
    if iteration is None:
        experiment = get_experiment(experiment_id)
        iteration = experiment.get("current_iteration", 0) if experiment else 0
    
    query = f"""
    INSERT INTO experiment_results (
        id, experiment_id, variant_id, iteration,
        metric_name, metric_value, metric_type,
        raw_data, source, notes
    ) VALUES (
        '{result_id}',
        '{experiment_id}',
        {f"'{variant_id}'" if variant_id else "NULL"},
        {iteration},
        '{_escape_string(metric_name)}',
        {metric_value},
        '{_escape_string(metric_type)}',
        {f"'{json.dumps(raw_data)}'::jsonb" if raw_data else "NULL"},
        '{_escape_string(source)}',
        {f"'{_escape_string(notes)}'" if notes else "NULL"}
    )
    """
    
    _execute_sql(query)
    
    return {
        "success": True,
        "result_id": result_id,
        "metric": metric_name,
        "value": metric_value
    }


def get_result_summary(
    experiment_id: str,
    metric_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get aggregated results for an experiment.
    
    Args:
        experiment_id: Experiment to analyze
        metric_name: Optional filter by metric
    
    Returns:
        Dict with aggregated statistics
    """
    metric_filter = f"AND metric_name = '{_escape_string(metric_name)}'" if metric_name else ""
    
    query = f"""
    SELECT 
        metric_name,
        metric_type,
        COUNT(*) as data_points,
        MIN(metric_value) as min_value,
        MAX(metric_value) as max_value,
        AVG(metric_value) as avg_value,
        SUM(metric_value) as total_value,
        STDDEV(metric_value) as stddev
    FROM experiment_results
    WHERE experiment_id = '{experiment_id}' {metric_filter}
    GROUP BY metric_name, metric_type
    ORDER BY metric_name
    """
    
    result = _execute_sql(query)
    return {
        "success": True,
        "experiment_id": experiment_id,
        "metrics": result.get("rows", [])
    }


def evaluate_success_criteria(experiment_id: str) -> Dict[str, Any]:
    """
    Evaluate if an experiment has met its success criteria.
    
    Compares actual results against defined success_criteria.
    
    Args:
        experiment_id: Experiment to evaluate
    
    Returns:
        Dict with success status and details
    """
    experiment = get_experiment(experiment_id)
    if not experiment:
        return {"success": False, "error": "Experiment not found"}
    
    success_criteria = experiment.get("success_criteria", {})
    failure_criteria = experiment.get("failure_criteria", {})
    
    # Get latest metric values
    query = f"""
    SELECT DISTINCT ON (metric_name)
        metric_name, metric_value
    FROM experiment_results
    WHERE experiment_id = '{experiment_id}'
    ORDER BY metric_name, timestamp DESC
    """
    result = _execute_sql(query)
    
    # Build metric lookup
    metrics = {row["metric_name"]: float(row["metric_value"]) for row in result.get("rows", [])}
    
    # Evaluate success criteria
    success_results = {}
    all_success_met = True
    
    for metric_name, conditions in success_criteria.items():
        actual = metrics.get(metric_name)
        if actual is None:
            success_results[metric_name] = {"met": False, "reason": "No data"}
            all_success_met = False
            continue
        
        met = True
        for operator, target in conditions.items():
            target = float(target)
            if operator == ">=":
                met = met and actual >= target
            elif operator == ">":
                met = met and actual > target
            elif operator == "<=":
                met = met and actual <= target
            elif operator == "<":
                met = met and actual < target
            elif operator == "==":
                met = met and actual == target
        
        success_results[metric_name] = {
            "met": met,
            "actual": actual,
            "target": conditions
        }
        if not met:
            all_success_met = False
    
    # Evaluate failure criteria
    failure_results = {}
    any_failure_met = False
    
    for metric_name, conditions in (failure_criteria or {}).items():
        actual = metrics.get(metric_name)
        if actual is None:
            continue
        
        met = True
        for operator, target in conditions.items():
            target = float(target)
            if operator == ">=":
                met = met and actual >= target
            elif operator == ">":
                met = met and actual > target
            elif operator == "<=":
                met = met and actual <= target
            elif operator == "<":
                met = met and actual < target
        
        if met:
            any_failure_met = True
            failure_results[metric_name] = {
                "triggered": True,
                "actual": actual,
                "threshold": conditions
            }
    
    return {
        "success": True,
        "experiment_id": experiment_id,
        "success_criteria_met": all_success_met,
        "failure_criteria_triggered": any_failure_met,
        "success_details": success_results,
        "failure_details": failure_results,
        "current_metrics": metrics,
        "recommendation": (
            "SUCCESS - All criteria met" if all_success_met
            else "FAIL - Failure criteria triggered" if any_failure_met
            else "ONGOING - Continue experiment"
        )
    }


def compare_variants(experiment_id: str) -> Dict[str, Any]:
    """
    Compare A/B test variants for an experiment.
    
    Args:
        experiment_id: Experiment with variants to compare
    
    Returns:
        Dict with variant comparison data
    """
    query = f"""
    SELECT id, name, is_control, traffic_percentage,
           sample_size, conversions, revenue_generated,
           CASE WHEN sample_size > 0 
                THEN (conversions::float / sample_size * 100)
                ELSE 0 END as conversion_rate
    FROM experiment_variants
    WHERE experiment_id = '{experiment_id}'
    ORDER BY is_control DESC, created_at
    """
    
    result = _execute_sql(query)
    variants = result.get("rows", [])
    
    if len(variants) < 2:
        return {
            "success": True,
            "message": "Need at least 2 variants for comparison",
            "variants": variants
        }
    
    # Find control
    control = next((v for v in variants if v.get("is_control")), variants[0])
    control_rate = float(control.get("conversion_rate", 0))
    
    # Calculate lift vs control
    comparisons = []
    for v in variants:
        if v["id"] == control["id"]:
            continue
        
        v_rate = float(v.get("conversion_rate", 0))
        lift = ((v_rate - control_rate) / control_rate * 100) if control_rate > 0 else 0
        
        comparisons.append({
            "variant": v["name"],
            "sample_size": v["sample_size"],
            "conversions": v["conversions"],
            "conversion_rate": v_rate,
            "revenue": float(v["revenue_generated"]),
            "lift_vs_control": lift
        })
    
    return {
        "success": True,
        "control": {
            "name": control["name"],
            "sample_size": control["sample_size"],
            "conversions": control["conversions"],
            "conversion_rate": control_rate,
            "revenue": float(control["revenue_generated"])
        },
        "treatments": comparisons,
        "winner": max(comparisons, key=lambda x: x["conversion_rate"])["variant"] if comparisons else None
    }


def conclude_experiment(
    experiment_id: str,
    conclusion: str,
    results_summary: Dict[str, Any],
    status: str = "completed",
    concluded_by: str = "SYSTEM",
    auto_rollback: bool = True
) -> Dict[str, Any]:
    """
    Conclude an experiment with final results.
    
    Automatically triggers rollback when status is 'failed' and auto_rollback
    is True (default behavior).
    
    Args:
        experiment_id: Experiment to conclude
        conclusion: Written conclusion
        results_summary: Summary of results
        status: Final status (completed, failed, cancelled)
        concluded_by: Who concluded it
        auto_rollback: If True, automatically rollback on failure (default: True)
    
    Returns:
        Dict with status and rollback info if applicable
    """
    query = f"""
    UPDATE experiments
    SET status = '{_escape_string(status)}',
        end_date = NOW(),
        conclusion = '{_escape_string(conclusion)}',
        results_summary = '{json.dumps(results_summary)}'::jsonb,
        updated_at = NOW()
    WHERE id = '{experiment_id}'
    """
    
    _execute_sql(query)
    log_experiment_event(experiment_id, "concluded", f"Status: {status}. {conclusion}", concluded_by)
    
    # Trigger learning extraction
    extract_learnings(experiment_id)
    
    result = {"success": True, "message": f"Experiment concluded as {status}"}
    
    # Auto-trigger rollback on failure
    if status == "failed" and auto_rollback:
        logger.info(f"Experiment {experiment_id} failed - triggering automatic rollback")
        rollback_result = execute_rollback(
            experiment_id=experiment_id,
            reason=f"Auto-rollback triggered by experiment failure: {conclusion}",
            triggered_by=concluded_by
        )
        result["rollback_triggered"] = True
        result["rollback_result"] = rollback_result
        log_experiment_event(
            experiment_id,
            "auto_rollback",
            f"Automatic rollback executed on failure. Rollback success: {rollback_result.get('success', False)}",
            concluded_by
        )
    
    return result


# =============================================================================
# PHASE 4.4: ROLLBACK SYSTEM
# =============================================================================

def create_rollback_snapshot(
    experiment_id: str,
    rollback_type: str,
    created_by: str = "SYSTEM"
) -> Dict[str, Any]:
    """
    Create a snapshot of pre-experiment state for potential rollback.
    
    Args:
        experiment_id: Experiment to snapshot
        rollback_type: Type (pre_start, checkpoint, manual)
        created_by: Who created the snapshot
    
    Returns:
        Dict with rollback_id
    """
    rollback_id = str(uuid.uuid4())
    
    # Capture current experiment state
    experiment = get_experiment(experiment_id)
    if not experiment:
        return {"success": False, "error": "Experiment not found"}
    
    # Remove non-serializable fields
    state_snapshot = {k: str(v) if isinstance(v, datetime) else v 
                     for k, v in experiment.items()}
    
    query = f"""
    INSERT INTO experiment_rollbacks (
        id, experiment_id, rollback_type, pre_experiment_state,
        rollback_executed, triggered_by
    ) VALUES (
        '{rollback_id}',
        '{experiment_id}',
        '{_escape_string(rollback_type)}',
        '{json.dumps(state_snapshot)}'::jsonb,
        FALSE,
        '{_escape_string(created_by)}'
    )
    """
    
    _execute_sql(query)
    
    return {
        "success": True,
        "rollback_id": rollback_id,
        "message": f"Rollback snapshot created ({rollback_type})"
    }


def execute_rollback(
    experiment_id: str,
    reason: str,
    triggered_by: str = "SYSTEM"
) -> Dict[str, Any]:
    """
    Execute a rollback to pre-experiment state.
    
    Args:
        experiment_id: Experiment to roll back
        reason: Why rolling back
        triggered_by: Who triggered the rollback
    
    Returns:
        Dict with rollback status
    """
    # Get the most recent rollback snapshot
    query = f"""
    SELECT id, pre_experiment_state
    FROM experiment_rollbacks
    WHERE experiment_id = '{experiment_id}'
      AND rollback_executed = FALSE
    ORDER BY created_at DESC
    LIMIT 1
    """
    
    result = _execute_sql(query)
    if not result.get("rows"):
        return {"success": False, "error": "No rollback snapshot available"}
    
    snapshot = result["rows"][0]
    rollback_id = snapshot["id"]
    pre_state = snapshot["pre_experiment_state"]
    
    # Capture current state before rollback
    current_experiment = get_experiment(experiment_id)
    
    # Mark experiment as rolled back
    update_query = f"""
    UPDATE experiments
    SET status = 'rolled_back',
        conclusion = 'Rolled back: {_escape_string(reason)}',
        end_date = NOW(),
        updated_at = NOW()
    WHERE id = '{experiment_id}'
    """
    _execute_sql(update_query)
    
    # Update rollback record
    rollback_query = f"""
    UPDATE experiment_rollbacks
    SET rollback_executed = TRUE,
        rollback_executed_at = NOW(),
        trigger_reason = '{_escape_string(reason)}',
        post_experiment_state = '{json.dumps({k: str(v) if isinstance(v, datetime) else v for k, v in (current_experiment or {}).items()})}'::jsonb,
        rollback_result = '{{"success": true, "rolled_back_at": "{datetime.now().isoformat()}"}}'::jsonb
    WHERE id = '{rollback_id}'
    """
    _execute_sql(rollback_query)
    
    log_experiment_event(experiment_id, "rolled_back", f"Reason: {reason}", triggered_by)
    
    return {
        "success": True,
        "message": f"Experiment rolled back: {reason}",
        "rollback_id": rollback_id
    }


def check_auto_rollback_triggers(experiment_id: str) -> Dict[str, Any]:
    """
    Check if automatic rollback should be triggered.
    
    Checks for:
    - Budget exhaustion
    - Failure criteria met
    - Scheduled end passed
    
    Args:
        experiment_id: Experiment to check
    
    Returns:
        Dict with trigger status
    """
    experiment = get_experiment(experiment_id)
    if not experiment:
        return {"success": False, "error": "Experiment not found"}
    
    triggers = []
    
    # Check budget
    budget_spent = float(experiment.get("budget_spent", 0))
    budget_limit = experiment.get("budget_limit")
    if budget_limit and budget_spent >= float(budget_limit):
        triggers.append("budget_exhausted")
    
    # Check scheduled end
    scheduled_end = experiment.get("scheduled_end")
    if scheduled_end:
        if isinstance(scheduled_end, str):
            scheduled_end = datetime.fromisoformat(scheduled_end.replace('Z', '+00:00'))
        if datetime.now() > scheduled_end:
            triggers.append("scheduled_end_passed")
    
    # Check failure criteria
    evaluation = evaluate_success_criteria(experiment_id)
    if evaluation.get("failure_criteria_triggered"):
        triggers.append("failure_criteria_met")
    
    if triggers:
        return {
            "success": True,
            "should_rollback": True,
            "triggers": triggers,
            "recommendation": f"Auto-rollback recommended due to: {', '.join(triggers)}"
        }
    
    return {
        "success": True,
        "should_rollback": False,
        "triggers": []
    }


def fail_experiment(
    experiment_id: str,
    failure_reason: str,
    results_summary: Optional[Dict[str, Any]] = None,
    failed_by: str = "SYSTEM",
    auto_rollback: bool = True
) -> Dict[str, Any]:
    """
    Mark an experiment as failed and automatically trigger rollback.
    
    This is a convenience function that wraps conclude_experiment with
    failure-specific defaults and ensures rollback is triggered.
    
    Args:
        experiment_id: Experiment to fail
        failure_reason: Why the experiment failed
        results_summary: Optional summary of results at failure
        failed_by: Who marked it as failed
        auto_rollback: If True, automatically rollback (default: True)
    
    Returns:
        Dict with failure status and rollback result
    """
    logger.info(f"Failing experiment {experiment_id}: {failure_reason}")
    
    return conclude_experiment(
        experiment_id=experiment_id,
        conclusion=failure_reason,
        results_summary=results_summary or {"failure_reason": failure_reason},
        status="failed",
        concluded_by=failed_by,
        auto_rollback=auto_rollback
    )


def process_auto_rollback_for_running_experiments(
    triggered_by: str = "SCHEDULER"
) -> Dict[str, Any]:
    """
    Check all running experiments for auto-rollback triggers and execute rollbacks.
    
    This function should be called periodically by the scheduler to ensure
    experiments that meet failure criteria are automatically rolled back.
    
    Checks each running experiment for:
    - Budget exhaustion
    - Failure criteria met
    - Scheduled end passed
    
    Args:
        triggered_by: Who/what is triggering this check (default: SCHEDULER)
    
    Returns:
        Dict with summary of experiments checked and any rollbacks executed
    """
    logger.info("Starting auto-rollback check for running experiments")
    
    # Get all running experiments
    running_experiments = list_experiments(status="running")
    
    results = {
        "success": True,
        "experiments_checked": len(running_experiments),
        "rollbacks_triggered": 0,
        "rollback_details": []
    }
    
    for experiment in running_experiments:
        experiment_id = experiment.get("id")
        if not experiment_id:
            continue
        
        # Check if rollback should be triggered
        trigger_check = check_auto_rollback_triggers(experiment_id)
        
        if trigger_check.get("should_rollback"):
            triggers = trigger_check.get("triggers", [])
            trigger_reason = f"Auto-rollback: {', '.join(triggers)}"
            
            logger.info(
                f"Auto-rollback triggered for experiment {experiment_id}: {triggers}"
            )
            
            # Execute the rollback by failing the experiment
            rollback_result = fail_experiment(
                experiment_id=experiment_id,
                failure_reason=trigger_reason,
                results_summary={"auto_rollback_triggers": triggers},
                failed_by=triggered_by,
                auto_rollback=True
            )
            
            results["rollbacks_triggered"] += 1
            results["rollback_details"].append({
                "experiment_id": experiment_id,
                "experiment_name": experiment.get("name"),
                "triggers": triggers,
                "rollback_success": rollback_result.get("rollback_result", {}).get("success", False)
            })
    
    logger.info(
        f"Auto-rollback check complete: {results['experiments_checked']} checked, "
        f"{results['rollbacks_triggered']} rollbacks triggered"
    )
    
    return results


def get_rollback_history(
    experiment_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get rollback history, optionally filtered by experiment.
    
    Args:
        experiment_id: Optional filter by experiment
        limit: Maximum results to return
    
    Returns:
        List of rollback records with details
    """
    where_clause = f"WHERE experiment_id = '{experiment_id}'" if experiment_id else ""
    
    query = f"""
    SELECT 
        r.id,
        r.experiment_id,
        e.name as experiment_name,
        r.rollback_type,
        r.rollback_executed,
        r.rollback_executed_at,
        r.triggered_by,
        r.trigger_reason,
        r.rollback_result,
        r.created_at
    FROM experiment_rollbacks r
    LEFT JOIN experiments e ON r.experiment_id = e.id
    {where_clause}
    ORDER BY r.created_at DESC
    LIMIT {limit}
    """
    
    result = _execute_sql(query)
    return result.get("rows", [])


# =============================================================================
# PHASE 4.5: SELF-IMPROVEMENT (LEARNINGS)
# =============================================================================

def record_learning(
    summary: str,
    category: str,
    details: Optional[Dict[str, Any]] = None,
    worker_id: str = "SYSTEM",
    goal_id: Optional[str] = None,
    task_id: Optional[str] = None,
    experiment_id: Optional[str] = None,
    evidence_task_ids: Optional[List[str]] = None,
    confidence: float = 0.7,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Record a learning/insight for future reference.
    
    Args:
        summary: Short summary of the learning
        category: Category (success_pattern, failure_pattern, optimization, insight)
        details: Detailed information
        worker_id: Which worker discovered this
        goal_id: Related goal
        task_id: Related task
        experiment_id: Related experiment
        evidence_task_ids: Tasks that provide evidence
        confidence: Confidence score (0-1)
        tags: Tags for categorization
    
    Returns:
        Dict with learning_id
    """
    learning_id = str(uuid.uuid4())
    
    # Include experiment reference in details
    full_details = details or {}
    if experiment_id:
        full_details["experiment_id"] = experiment_id
    if tags:
        full_details["tags"] = tags
    
    query = f"""
    INSERT INTO learnings (
        id, worker_id, goal_id, task_id, category,
        summary, details, evidence_task_ids, confidence,
        applied_count, is_validated
    ) VALUES (
        '{learning_id}',
        '{_escape_string(worker_id)}',
        {f"'{goal_id}'" if goal_id else "NULL"},
        {f"'{task_id}'" if task_id else "NULL"},
        '{_escape_string(category)}',
        '{_escape_string(summary)}',
        '{json.dumps(full_details)}'::jsonb,
        '{json.dumps(evidence_task_ids or [])}'::jsonb,
        {confidence},
        0,
        FALSE
    )
    """
    
    _execute_sql(query)
    
    return {
        "success": True,
        "learning_id": learning_id,
        "message": f"Learning recorded: {summary[:50]}..."
    }


def extract_learnings(experiment_id: str) -> Dict[str, Any]:
    """
    Automatically extract learnings from a completed experiment.
    
    Analyzes experiment results and generates insights.
    
    Args:
        experiment_id: Experiment to analyze
    
    Returns:
        Dict with extracted learnings
    """
    experiment = get_experiment(experiment_id)
    if not experiment:
        return {"success": False, "error": "Experiment not found"}
    
    learnings_created = []
    
    # Learning from success/failure
    status = experiment.get("status")
    conclusion = experiment.get("conclusion", "")
    
    if status == "completed":
        # Extract success patterns
        evaluation = evaluate_success_criteria(experiment_id)
        if evaluation.get("success_criteria_met"):
            learning = record_learning(
                summary=f"Successful experiment: {experiment['name']} - {conclusion[:100]}",
                category="success_pattern",
                details={
                    "experiment_name": experiment["name"],
                    "hypothesis": experiment.get("hypothesis"),
                    "success_criteria": experiment.get("success_criteria"),
                    "results": evaluation.get("current_metrics"),
                    "budget_used": float(experiment.get("budget_spent", 0)),
                    "iterations": experiment.get("current_iteration")
                },
                experiment_id=experiment_id,
                confidence=0.8
            )
            learnings_created.append(learning)
    
    elif status in ["failed", "rolled_back"]:
        # Extract failure patterns
        learning = record_learning(
            summary=f"Failed experiment: {experiment['name']} - {conclusion[:100]}",
            category="failure_pattern",
            details={
                "experiment_name": experiment["name"],
                "hypothesis": experiment.get("hypothesis"),
                "failure_reason": conclusion,
                "budget_used": float(experiment.get("budget_spent", 0)),
                "iterations": experiment.get("current_iteration")
            },
            experiment_id=experiment_id,
            confidence=0.7
        )
        learnings_created.append(learning)
    
    # Extract optimization insights from A/B tests
    comparison = compare_variants(experiment_id)
    if comparison.get("winner"):
        learning = record_learning(
            summary=f"A/B test winner: {comparison['winner']} outperformed control",
            category="optimization",
            details={
                "experiment_name": experiment["name"],
                "control": comparison.get("control"),
                "winner": comparison.get("winner"),
                "treatments": comparison.get("treatments")
            },
            experiment_id=experiment_id,
            confidence=0.75
        )
        learnings_created.append(learning)
    
    return {
        "success": True,
        "experiment_id": experiment_id,
        "learnings_extracted": len(learnings_created),
        "learnings": learnings_created
    }


def get_learnings(
    category: Optional[str] = None,
    min_confidence: float = 0.0,
    worker_id: Optional[str] = None,
    is_validated: Optional[bool] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get learnings with filtering.
    
    Args:
        category: Filter by category
        min_confidence: Minimum confidence score
        worker_id: Filter by worker
        is_validated: Filter by validation status
        limit: Maximum results
    
    Returns:
        List of learning dictionaries
    """
    conditions = [f"confidence >= {min_confidence}"]
    
    if category:
        conditions.append(f"category = '{_escape_string(category)}'")
    if worker_id:
        conditions.append(f"worker_id = '{_escape_string(worker_id)}'")
    if is_validated is not None:
        conditions.append(f"is_validated = {is_validated}")
    
    where_clause = f"WHERE {' AND '.join(conditions)}"
    
    query = f"""
    SELECT id, worker_id, category, summary, details,
           confidence, applied_count, effectiveness_score,
           is_validated, created_at
    FROM learnings
    {where_clause}
    ORDER BY confidence DESC, created_at DESC
    LIMIT {limit}
    """
    
    result = _execute_sql(query)
    return result.get("rows", [])


def get_relevant_learnings(
    context: str,
    category: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Get learnings relevant to a given context.
    
    Uses text search to find relevant past learnings.
    
    Args:
        context: Description of current situation
        category: Optional category filter
        limit: Maximum results
    
    Returns:
        List of relevant learnings
    """
    # Simple text search - could be enhanced with vector search
    search_terms = context.lower().split()[:5]  # Top 5 words
    
    conditions = []
    for term in search_terms:
        conditions.append(f"(LOWER(summary) LIKE '%{_escape_string(term)}%' OR details::text LIKE '%{_escape_string(term)}%')")
    
    search_clause = f"({' OR '.join(conditions)})" if conditions else "TRUE"
    category_clause = f"AND category = '{_escape_string(category)}'" if category else ""
    
    query = f"""
    SELECT id, category, summary, details, confidence, applied_count
    FROM learnings
    WHERE {search_clause} {category_clause}
    ORDER BY confidence DESC, applied_count DESC
    LIMIT {limit}
    """
    
    result = _execute_sql(query)
    return result.get("rows", [])


def validate_learning(
    learning_id: str,
    validated_by: str,
    effectiveness_score: float = 1.0
) -> Dict[str, Any]:
    """
    Validate a learning after it's been applied successfully.
    
    Args:
        learning_id: Learning to validate
        validated_by: Who validated it
        effectiveness_score: How effective (0-1)
    
    Returns:
        Dict with status
    """
    query = f"""
    UPDATE learnings
    SET is_validated = TRUE,
        validated_by = '{_escape_string(validated_by)}',
        effectiveness_score = {effectiveness_score},
        applied_count = applied_count + 1,
        updated_at = NOW()
    WHERE id = '{learning_id}'
    """
    
    result = _execute_sql(query)
    return {"success": True, "message": "Learning validated"}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def log_experiment_event(
    experiment_id: str,
    event_type: str,
    message: str,
    worker_id: str = "SYSTEM"
) -> None:
    """Log an experiment event to execution_logs."""
    query = f"""
    INSERT INTO execution_logs (worker_id, action, message, level, metadata)
    VALUES (
        '{_escape_string(worker_id)}',
        'experiment_{event_type}',
        '{_escape_string(message)}',
        'info',
        '{{"experiment_id": "{experiment_id}"}}'::jsonb
    )
    """
    _execute_sql(query)


def get_experiment_dashboard(experiment_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get comprehensive dashboard data for an experiment or summary of all experiments.
    
    Args:
        experiment_id: Experiment to get dashboard for. If None, returns summary of all experiments.
    
    Returns:
        Dict with experiment data or summary dashboard
    """
    # If no experiment_id provided, return summary dashboard
    if experiment_id is None:
        try:
            active_experiments = list_experiments(status="running")
            all_experiments = list_experiments()
            return {
                "success": True,
                "summary": True,
                "total_experiments": len(all_experiments) if all_experiments else 0,
                "active_experiments": len(active_experiments) if active_experiments else 0,
                "recent_experiments": all_experiments[:10] if all_experiments else [],
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get experiment summary: {str(e)}"}
    
    experiment = get_experiment(experiment_id)
    if not experiment:
        return {"success": False, "error": "Experiment not found"}
    
    return {
        "success": True,
        "experiment": experiment,
        "results_summary": get_result_summary(experiment_id),
        "variants": compare_variants(experiment_id) if experiment.get("status") != "draft" else None,
        "checkpoints": get_checkpoints(experiment_id),
        "success_evaluation": evaluate_success_criteria(experiment_id),
        "auto_rollback_check": check_auto_rollback_triggers(experiment_id)
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Phase 4.1: Experiment Design
    "create_experiment_template",
    "list_experiment_templates",
    "create_experiment",
    "get_experiment",
    "list_experiments",
    
    # Phase 4.2: Experiment Execution
    "start_experiment",
    "pause_experiment",
    "resume_experiment",
    "increment_iteration",
    "record_experiment_cost",
    "create_variant",
    "update_variant_metrics",
    "create_checkpoint",
    "get_checkpoints",
    "get_latest_checkpoint",
    
    # Phase 4.3: Experiment Analysis
    "record_result",
    "get_result_summary",
    "evaluate_success_criteria",
    "compare_variants",
    "conclude_experiment",
    
    # Phase 4.4: Rollback System
    "create_rollback_snapshot",
    "execute_rollback",
    "check_auto_rollback_triggers",
    "fail_experiment",
    "process_auto_rollback_for_running_experiments",
    "get_rollback_history",
    
    # Phase 4.5: Self-Improvement
    "record_learning",
    "extract_learnings",
    "get_learnings",
    "get_relevant_learnings",
    "validate_learning",
    
    # Utilities
    "log_experiment_event",
    "get_experiment_dashboard",
]
