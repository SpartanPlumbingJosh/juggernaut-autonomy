"""
JUGGERNAUT Agent Framework
Phase 2: Workers, Goals, Tasks, Approvals, Permissions
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
import uuid

import logging

from core.database import query_db as _query, escape_sql_value as _format_value

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================
# PHASE 2.1: WORKER REGISTRY
# ============================================================

def register_worker(
    worker_id: str,
    name: str,
    description: str,
    level: str = "L3",
    worker_type: str = "agent",
    capabilities: List[str] = None,
    permissions: Dict = None,
    forbidden_actions: List[str] = None,
    approval_required_for: List[str] = None,
    max_concurrent_tasks: int = 5,
    allowed_task_types: List[str] = None,
    max_tokens_per_task: int = 10000,
    max_cost_per_task_cents: int = 100,
    max_cost_per_day_cents: int = 1000,
    parent_worker_id: str = None,
    config: Dict = None
) -> Optional[str]:
    """
    Register a new worker or update existing one.
    
    Returns:
        Worker UUID or None on failure
    """
    sql = f"""
    INSERT INTO worker_registry (
        worker_id, name, description, level, worker_type, status,
        version, capabilities, permissions, forbidden_actions,
        approval_required_for, max_concurrent_tasks, allowed_task_types,
        max_tokens_per_task, max_cost_per_task_cents, max_cost_per_day_cents,
        current_day_cost_cents, consecutive_failures, health_score,
        parent_worker_id, config, created_at, updated_at, tasks_completed, tasks_failed
    ) VALUES (
        {_format_value(worker_id)},
        {_format_value(name)},
        {_format_value(description)},
        {_format_value(level)},
        {_format_value(worker_type)},
        'active',
        '1.0.0',
        {_format_value(capabilities or [])},
        {_format_value(permissions or {})},
        {_format_value(forbidden_actions or [])},
        {_format_value(approval_required_for or [])},
        {max_concurrent_tasks},
        {_format_value(allowed_task_types or [])},
        {max_tokens_per_task},
        {max_cost_per_task_cents},
        {max_cost_per_day_cents},
        0, 0, 1.0,
        {_format_value(parent_worker_id)},
        {_format_value(config or {})},
        NOW(), NOW(), 0, 0
    )
    ON CONFLICT (worker_id) DO UPDATE SET
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        level = EXCLUDED.level,
        capabilities = EXCLUDED.capabilities,
        updated_at = NOW()
    RETURNING id
    """
    
    try:
        result = _query(sql)
        if result.get("rows"):
            return result["rows"][0].get("id")
    except Exception as e:
        logger.error("Failed to register worker: %s", e)
    return None


def update_worker_status(worker_id: str, status: str) -> bool:
    """Update worker status (active, idle, busy, paused, error, offline)."""
    try:
        normalized = (status or "").strip().lower()
    except Exception:
        normalized = ""
    if normalized == "idle" or not normalized:
        status = "active"
    sql = f"""
    UPDATE worker_registry
    SET status = {_format_value(status)}, updated_at = NOW()
    WHERE worker_id = {_format_value(worker_id)}
    """
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        logger.error("Failed to update worker status: %s", e)
        return False


def worker_heartbeat(worker_id: str) -> bool:
    """Record worker heartbeat."""
    sql = f"""
    UPDATE worker_registry
    SET last_heartbeat = NOW(), updated_at = NOW()
    WHERE worker_id = {_format_value(worker_id)}
    """
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        logger.error("Failed to send heartbeat: %s", e)
        return False


def get_worker(worker_id: str) -> Optional[Dict]:
    """Get worker details."""
    sql = f"SELECT * FROM worker_registry WHERE worker_id = {_format_value(worker_id)}"
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        return rows[0] if rows else None
    except Exception as e:
        logger.error("Failed to get worker: %s", e)
        return None


def list_workers(status: str = None, worker_type: str = None) -> List[Dict]:
    """List workers with optional filters."""
    conditions = []
    if status:
        conditions.append(f"status = {_format_value(status)}")
    if worker_type:
        conditions.append(f"worker_type = {_format_value(worker_type)}")
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM worker_registry {where} ORDER BY created_at"
    
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        logger.error("Failed to list workers: %s", e)
        return []


def find_workers_by_capability(capability: str) -> List[Dict]:
    """Find active workers with a specific capability."""
    sql = f"""
    SELECT worker_id, name, capabilities, health_score, status
    FROM worker_registry
    WHERE capabilities @> {_format_value([capability])}
      AND status = 'active'
    ORDER BY health_score DESC
    """
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        logger.error("Failed to find workers: %s", e)
        return []


def record_worker_task_outcome(worker_id: str, success: bool, cost_cents: int = 0) -> bool:
    """Record task outcome for worker stats."""
    if success:
        sql = f"""
        UPDATE worker_registry SET
            tasks_completed = tasks_completed + 1,
            consecutive_failures = 0,
            current_day_cost_cents = current_day_cost_cents + {cost_cents},
            health_score = LEAST(1.0, health_score + 0.02),
            updated_at = NOW()
        WHERE worker_id = {_format_value(worker_id)}
        """
    else:
        sql = f"""
        UPDATE worker_registry SET
            tasks_failed = tasks_failed + 1,
            consecutive_failures = consecutive_failures + 1,
            current_day_cost_cents = current_day_cost_cents + {cost_cents},
            health_score = GREATEST(0.0, health_score - 0.1),
            updated_at = NOW()
        WHERE worker_id = {_format_value(worker_id)}
        """
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        logger.error("Failed to record outcome: %s", e)
        return False


# ============================================================
# PHASE 2.2: GOAL SYSTEM
# ============================================================

def create_goal(
    title: str,
    description: str,
    created_by: str = "ORCHESTRATOR",
    parent_goal_id: str = None,
    success_criteria: Dict = None,
    assigned_worker_id: str = None,
    deadline: str = None,
    max_cost_cents: int = 0,
    required_approvals: List[str] = None
) -> Optional[str]:
    """
    Create a new goal.
    
    Returns:
        Goal UUID or None on failure
    """
    sql = f"""
    INSERT INTO goals (
        parent_goal_id, title, description, success_criteria,
        created_by, assigned_worker_id, status, progress,
        deadline, max_cost_cents, required_approvals,
        created_at, updated_at
    ) VALUES (
        {_format_value(parent_goal_id)},
        {_format_value(title)},
        {_format_value(description)},
        {_format_value(success_criteria or {})},
        {_format_value(created_by)},
        {_format_value(assigned_worker_id)},
        'pending',
        0,
        {_format_value(deadline)},
        {max_cost_cents},
        {_format_value(required_approvals or [])},
        NOW(), NOW()
    ) RETURNING id
    """
    
    try:
        result = _query(sql)
        if result.get("rows"):
            return result["rows"][0].get("id")
    except Exception as e:
        logger.error("Failed to create goal: %s", e)
    return None


def get_goal(goal_id: str) -> Optional[Dict]:
    """Get goal by ID."""
    sql = f"SELECT * FROM goals WHERE id = {_format_value(goal_id)}"
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        return rows[0] if rows else None
    except Exception as e:
        logger.error("Failed to get goal: %s", e)
        return None


def list_goals(status: str = None, assigned_to: str = None, limit: int = 50) -> List[Dict]:
    """List goals with optional filters."""
    conditions = []
    if status:
        conditions.append(f"status = {_format_value(status)}")
    if assigned_to:
        conditions.append(f"assigned_worker_id = {_format_value(assigned_to)}")
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM goals {where} ORDER BY created_at DESC LIMIT {limit}"
    
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        logger.error("Failed to list goals: %s", e)
        return []


def get_sub_goals(parent_goal_id: str) -> List[Dict]:
    """Get all sub-goals of a parent goal."""
    sql = f"""
    SELECT * FROM goals 
    WHERE parent_goal_id = {_format_value(parent_goal_id)}
    ORDER BY created_at
    """
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        logger.error("Failed to get sub-goals: %s", e)
        return []


def update_goal_status(goal_id: str, status: str, progress: float = None, outcome: str = None) -> bool:
    """Update goal status and progress."""
    updates = [f"status = {_format_value(status)}", "updated_at = NOW()"]
    
    if progress is not None:
        updates.append(f"progress = {progress}")
    if outcome:
        updates.append(f"outcome = {_format_value(outcome)}")
    if status == 'in_progress':
        updates.append("started_at = COALESCE(started_at, NOW())")
    if status in ('completed', 'failed', 'cancelled'):
        updates.append("completed_at = NOW()")
    
    sql = f"UPDATE goals SET {', '.join(updates)} WHERE id = {_format_value(goal_id)}"
    
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        logger.error("Failed to update goal: %s", e)
        return False


def assign_goal(goal_id: str, worker_id: str) -> bool:
    """Assign a goal to a worker."""
    sql = f"""
    UPDATE goals SET
        assigned_worker_id = (SELECT id FROM worker_registry WHERE worker_id = {_format_value(worker_id)}),
        status = 'assigned',
        updated_at = NOW()
    WHERE id = {_format_value(goal_id)}
    """
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        logger.error("Failed to assign goal: %s", e)
        return False


def decompose_goal(parent_goal_id: str, sub_goals: List[Dict], created_by: str = "ORCHESTRATOR") -> List[str]:
    """
    Decompose a goal into sub-goals.
    
    Args:
        parent_goal_id: UUID of the parent goal
        sub_goals: List of dicts with {title, description, success_criteria}
    
    Returns:
        List of created sub-goal UUIDs
    """
    created_ids = []
    for sg in sub_goals:
        sub_id = create_goal(
            title=sg.get("title"),
            description=sg.get("description"),
            created_by=created_by,
            parent_goal_id=parent_goal_id,
            success_criteria=sg.get("success_criteria"),
            max_cost_cents=sg.get("max_cost_cents", 0)
        )
        if sub_id:
            created_ids.append(sub_id)
    return created_ids


# ============================================================
# PHASE 2.3: TASK SYSTEM
# ============================================================

def create_task(
    title: str,
    task_type: str,
    created_by: str,
    description: str = None,
    goal_id: str = None,
    parent_task_id: str = None,
    assigned_worker: str = None,
    payload: Dict = None,
    priority: str = "medium",
    deadline: str = None,
    depends_on: List[str] = None,
    estimated_cost_cents: int = 0,
    requires_approval: bool = False,
    approval_reason: str = None,
    tags: List[str] = None,
    metadata: Dict = None,
    max_attempts: int = 3
) -> Optional[str]:
    """
    Create a new task.
    
    Returns:
        Task UUID or None on failure
    """
    sql = f"""
    INSERT INTO governance_tasks (
        goal_id, parent_task_id, assigned_worker, created_by,
        task_type, title, description, payload, priority, status,
        deadline, depends_on, estimated_cost_cents, requires_approval,
        approval_reason, tags, metadata, attempt_count, max_attempts,
        created_at
    ) VALUES (
        {_format_value(goal_id)},
        {_format_value(parent_task_id)},
        {_format_value(assigned_worker)},
        {_format_value(created_by)},
        {_format_value(task_type)},
        {_format_value(title)},
        {_format_value(description)},
        {_format_value(payload or {})},
        {_format_value(priority)},
        'pending',
        {_format_value(deadline)},
        {_format_value(depends_on or [])},
        {estimated_cost_cents},
        {_format_value(requires_approval)},
        {_format_value(approval_reason)},
        {_format_value(tags or [])},
        {_format_value(metadata or {})},
        0,
        {max_attempts},
        NOW()
    ) RETURNING id
    """
    
    try:
        result = _query(sql)
        if result.get("rows"):
            return result["rows"][0].get("id")
    except Exception as e:
        logger.error("Failed to create task: %s", e)
    return None


def get_task(task_id: str) -> Optional[Dict]:
    """Get task by ID."""
    sql = f"SELECT * FROM governance_tasks WHERE id = {_format_value(task_id)}"
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        return rows[0] if rows else None
    except Exception as e:
        logger.error("Failed to get task: %s", e)
        return None


def list_tasks(
    status: str = None,
    assigned_worker: str = None,
    task_type: str = None,
    priority: str = None,
    goal_id: str = None,
    limit: int = 50
) -> List[Dict]:
    """List tasks with optional filters."""
    conditions = []
    if status:
        conditions.append(f"status = {_format_value(status)}")
    if assigned_worker:
        conditions.append(f"assigned_worker = {_format_value(assigned_worker)}")
    if task_type:
        conditions.append(f"task_type = {_format_value(task_type)}")
    if priority:
        conditions.append(f"priority = {_format_value(priority)}")
    if goal_id:
        conditions.append(f"goal_id = {_format_value(goal_id)}")
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
    SELECT * FROM governance_tasks {where}
    ORDER BY 
        CASE priority 
            WHEN 'critical' THEN 1 
            WHEN 'high' THEN 2 
            WHEN 'medium' THEN 3 
            WHEN 'low' THEN 4 
        END,
        created_at
    LIMIT {limit}
    """
    
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        logger.error("Failed to list tasks: %s", e)
        return []


def get_pending_tasks(worker_id: str = None, limit: int = 20) -> List[Dict]:
    """Get pending tasks, optionally for a specific worker."""
    worker_filter = f"AND assigned_worker = {_format_value(worker_id)}" if worker_id else ""
    
    sql = f"""
    SELECT * FROM governance_tasks
    WHERE status = 'pending'
      AND (requires_approval = FALSE OR id IN (
          SELECT task_id FROM approvals WHERE decision = 'approved'
      ))
      {worker_filter}
    ORDER BY 
        CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END,
        created_at
    LIMIT {limit}
    """
    
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        logger.error("Failed to get pending tasks: %s", e)
        return []


def assign_task(task_id: str, worker_id: str) -> bool:
    """Assign a task to a worker."""
    sql = f"""
    UPDATE governance_tasks SET
        assigned_worker = {_format_value(worker_id)},
        assigned_at = NOW(),
        status = 'assigned'
    WHERE id = {_format_value(task_id)}
    """
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        logger.error("Failed to assign task: %s", e)
        return False


def start_task(task_id: str) -> bool:
    """Mark task as started."""
    sql = f"""
    UPDATE governance_tasks SET
        status = 'in_progress',
        started_at = NOW(),
        attempt_count = attempt_count + 1
    WHERE id = {_format_value(task_id)}
    """
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        logger.error("Failed to start task: %s", e)
        return False


def complete_task(task_id: str, result_data: Dict = None, actual_cost_cents: int = 0) -> bool:
    """Mark task as completed."""
    sql = f"""
    UPDATE governance_tasks SET
        status = 'completed',
        completed_at = NOW(),
        result = {_format_value(result_data or {})},
        actual_cost_cents = {actual_cost_cents}
    WHERE id = {_format_value(task_id)}
    """
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        logger.error("Failed to complete task: %s", e)
        return False


def fail_task(task_id: str, error_message: str, retry: bool = True) -> bool:
    """Mark task as failed, optionally scheduling retry."""
    task = get_task(task_id)
    if not task:
        return False
    
    attempt_count = int(task.get("attempt_count") or 0)
    max_attempts = int(task.get("max_attempts") or 3)
    
    if retry and attempt_count < max_attempts:
        # Schedule retry with exponential backoff
        backoff_minutes = 2 ** attempt_count  # 1, 2, 4, 8, 16...
        sql = f"""
        UPDATE governance_tasks SET
            status = 'pending',
            error_message = {_format_value(error_message)},
            next_retry_at = NOW() + INTERVAL '{backoff_minutes} minutes'
        WHERE id = {_format_value(task_id)}
        """
    else:
        sql = f"""
        UPDATE governance_tasks SET
            status = 'failed',
            error_message = {_format_value(error_message)},
            completed_at = NOW()
        WHERE id = {_format_value(task_id)}
        """
    
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        logger.error("Failed to fail task: %s", e)
        return False


def get_tasks_ready_for_retry() -> List[Dict]:
    """Get tasks that are ready for retry."""
    sql = """
    SELECT * FROM governance_tasks
    WHERE status = 'pending'
      AND next_retry_at IS NOT NULL
      AND next_retry_at <= NOW()
    ORDER BY next_retry_at
    """
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        logger.error("Failed to get retry tasks: %s", e)
        return []


# ============================================================
# PHASE 2.6: HUMAN-IN-THE-LOOP (APPROVALS)
# ============================================================

def request_approval(
    worker_id: str,
    action_type: str,
    action_description: str,
    task_id: str = None,
    goal_id: str = None,
    action_data: Dict = None,
    risk_level: str = "medium",
    risk_factors: List[str] = None,
    estimated_impact: str = None,
    expires_hours: int = 24
) -> Optional[str]:
    """
    Request human approval for an action.
    
    Returns:
        Approval UUID or None on failure
    """
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()
    
    sql = f"""
    INSERT INTO approvals (
        task_id, goal_id, worker_id, action_type, action_description,
        action_data, risk_level, risk_factors, estimated_impact,
        decision, created_at, expires_at, escalation_level
    ) VALUES (
        {_format_value(task_id)},
        {_format_value(goal_id)},
        {_format_value(worker_id)},
        {_format_value(action_type)},
        {_format_value(action_description)},
        {_format_value(action_data or {})},
        {_format_value(risk_level)},
        {_format_value(risk_factors or [])},
        {_format_value(estimated_impact)},
        'pending',
        NOW(),
        {_format_value(expires_at)},
        0
    ) RETURNING id
    """
    
    try:
        result = _query(sql)
        if result.get("rows"):
            return result["rows"][0].get("id")
    except Exception as e:
        logger.error("Failed to request approval: %s", e)
    return None


def get_pending_approvals(limit: int = 50) -> List[Dict]:
    """Get all pending approvals."""
    sql = f"""
    SELECT * FROM approvals
    WHERE decision = 'pending'
      AND (expires_at IS NULL OR expires_at > NOW())
    ORDER BY 
        CASE risk_level WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END,
        created_at
    LIMIT {limit}
    """
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        logger.error("Failed to get pending approvals: %s", e)
        return []


def approve(approval_id: str, decided_by: str = "JOSH", notes: str = None) -> bool:
    """Approve a request."""
    sql = f"""
    UPDATE approvals SET
        decision = 'approved',
        decided_by = {_format_value(decided_by)},
        decided_at = NOW(),
        decision_notes = {_format_value(notes)}
    WHERE id = {_format_value(approval_id)}
    """
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        logger.error("Failed to approve: %s", e)
        return False


def reject(approval_id: str, decided_by: str = "JOSH", notes: str = None) -> bool:
    """Reject a request."""
    sql = f"""
    UPDATE approvals SET
        decision = 'rejected',
        decided_by = {_format_value(decided_by)},
        decided_at = NOW(),
        decision_notes = {_format_value(notes)}
    WHERE id = {_format_value(approval_id)}
    """
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        logger.error("Failed to reject: %s", e)
        return False


def check_approval_status(approval_id: str) -> Optional[str]:
    """Check if an approval has been decided."""
    sql = f"SELECT decision FROM approvals WHERE id = {_format_value(approval_id)}"
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        return rows[0].get("decision") if rows else None
    except Exception as e:
        logger.error("Failed to check approval: %s", e)
        return None


def is_task_approved(task_id: str) -> bool:
    """Check if a task has been approved."""
    sql = f"""
    SELECT decision FROM approvals
    WHERE task_id = {_format_value(task_id)}
    ORDER BY created_at DESC
    LIMIT 1
    """
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        return rows[0].get("decision") == "approved" if rows else True  # No approval needed = approved
    except Exception as e:
        logger.error("Failed to check task approval: %s", e)
        return False


# ============================================================
# PHASE 2.7: PERMISSION SYSTEM
# ============================================================

def check_permission(worker_id: str, action: str) -> Dict[str, Any]:
    """
    Check if a worker has permission for an action.
    
    Returns:
        {allowed: bool, reason: str, requires_approval: bool}
    """
    worker = get_worker(worker_id)
    if not worker:
        return {"allowed": False, "reason": "Worker not found", "requires_approval": False}
    
    # Check forbidden actions
    forbidden = worker.get("forbidden_actions") or []
    if isinstance(forbidden, str):
        forbidden = json.loads(forbidden)
    
    for forbidden_action in forbidden:
        if action.startswith(forbidden_action) or forbidden_action == "*":
            return {"allowed": False, "reason": f"Action '{action}' is forbidden", "requires_approval": False}
    
    # Check if approval required
    approval_required = worker.get("approval_required_for") or []
    if isinstance(approval_required, str):
        approval_required = json.loads(approval_required)
    
    for approval_action in approval_required:
        if action.startswith(approval_action):
            return {"allowed": True, "reason": "Requires approval", "requires_approval": True}
    
    # Check cost limits
    current_cost = int(worker.get("current_day_cost_cents") or 0)
    max_cost = int(worker.get("max_cost_per_day_cents") or 0)
    
    if max_cost > 0 and current_cost >= max_cost:
        return {"allowed": False, "reason": "Daily cost limit exceeded", "requires_approval": False}
    
    return {"allowed": True, "reason": "Permitted", "requires_approval": False}


def can_worker_execute(worker_id: str, task_type: str, estimated_cost_cents: int = 0) -> Dict[str, Any]:
    """
    Check if a worker can execute a specific task type.
    
    Returns:
        {can_execute: bool, reason: str}
    """
    worker = get_worker(worker_id)
    if not worker:
        return {"can_execute": False, "reason": "Worker not found"}
    
    # Check status
    if worker.get("status") not in ("active", "degraded"):
        return {"can_execute": False, "reason": f"Worker status is {worker.get('status')}"}
    
    # Check allowed task types
    allowed_types = worker.get("allowed_task_types") or []
    if isinstance(allowed_types, str):
        allowed_types = json.loads(allowed_types)
    
    if allowed_types and task_type not in allowed_types:
        return {"can_execute": False, "reason": f"Task type '{task_type}' not in allowed types"}
    
    # Check cost limits
    if estimated_cost_cents > 0:
        max_per_task = int(worker.get("max_cost_per_task_cents") or 0)
        if max_per_task > 0 and estimated_cost_cents > max_per_task:
            return {"can_execute": False, "reason": f"Estimated cost ${estimated_cost_cents/100:.2f} exceeds per-task limit ${max_per_task/100:.2f}"}
        
        current_daily = int(worker.get("current_day_cost_cents") or 0)
        max_daily = int(worker.get("max_cost_per_day_cents") or 0)
        if max_daily > 0 and (current_daily + estimated_cost_cents) > max_daily:
            return {"can_execute": False, "reason": "Would exceed daily cost limit"}
    
    # Check health
    health = float(worker.get("health_score") or 1.0)
    if health < 0.3:
        return {"can_execute": False, "reason": f"Worker health too low: {health}"}
    
    return {"can_execute": True, "reason": "OK"}


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def get_worker_dashboard(worker_id: str) -> Dict[str, Any]:
    """Get comprehensive dashboard data for a worker."""
    worker = get_worker(worker_id)
    if not worker:
        return {"error": "Worker not found"}
    
    pending_tasks = list_tasks(status="pending", assigned_worker=worker_id, limit=10)
    active_tasks = list_tasks(status="in_progress", assigned_worker=worker_id, limit=10)
    
    return {
        "worker": worker,
        "pending_tasks": pending_tasks,
        "active_tasks": active_tasks,
        "stats": {
            "tasks_completed": worker.get("tasks_completed", 0),
            "tasks_failed": worker.get("tasks_failed", 0),
            "health_score": worker.get("health_score", 1.0),
            "daily_cost_cents": worker.get("current_day_cost_cents", 0)
        }
    }


def get_system_status() -> Dict[str, Any]:
    """Get overall system status."""
    try:
        workers_result = _query("SELECT status, COUNT(*) as count FROM worker_registry GROUP BY status")
        tasks_result = _query("SELECT status, COUNT(*) as count FROM governance_tasks GROUP BY status")
        goals_result = _query("SELECT status, COUNT(*) as count FROM goals GROUP BY status")
        approvals_result = _query("SELECT COUNT(*) as count FROM approvals WHERE decision = 'pending'")
        
        return {
            "workers": {r["status"]: int(r["count"]) for r in workers_result.get("rows", [])},
            "tasks": {r["status"]: int(r["count"]) for r in tasks_result.get("rows", [])},
            "goals": {r["status"]: int(r["count"]) for r in goals_result.get("rows", [])},
            "pending_approvals": int(approvals_result.get("rows", [{}])[0].get("count", 0))
        }
    except Exception as e:
        logger.error("Failed to get system status: %s", e)
        return {"error": str(e)}


if __name__ == "__main__":
    logger.info("Testing Agent Framework...")
    
    # Test system status
    status = get_system_status()
    logger.info("System Status: %s", json.dumps(status, indent=2))
    
    # List workers
    workers = list_workers()
    logger.info("Workers: %s", len(workers))
    for w in workers:
        logger.info("  - %s: %s", w['worker_id'], w['status'])
