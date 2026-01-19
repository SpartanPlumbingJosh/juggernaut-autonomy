"""
JUGGERNAUT Worker Auto-Scaling Module

Implements dynamic worker scaling based on task queue depth.
Monitors queue metrics and provides scaling recommendations.

Functions:
- get_queue_metrics: Get current queue depth and worker count
- get_scaling_recommendation: Determine if scaling is needed
- record_scaling_event: Log scaling decisions
- get_scaling_history: Retrieve recent scaling events
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

# Configure logging
logger = logging.getLogger(__name__)

# Database configuration
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
NEON_CONNECTION_STRING = (
    "postgresql://neondb_owner:npg_OYkCRU4aze2l@"
    "ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/"
    "neondb?sslmode=require"
)

# Scaling configuration constants
MIN_WORKERS = 1
MAX_WORKERS = 10
SCALE_UP_THRESHOLD = 5  # Pending tasks per worker to trigger scale-up
SCALE_DOWN_THRESHOLD = 1  # Pending tasks per worker to trigger scale-down
COOLDOWN_MINUTES = 5  # Minutes between scaling events
STALE_WORKER_MINUTES = 30  # Minutes before a worker is considered stale


class ScalingAction(Enum):
    """Possible scaling actions."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_CHANGE = "no_change"


@dataclass
class QueueMetrics:
    """Container for queue metrics."""
    pending_tasks: int
    in_progress_tasks: int
    active_workers: int
    stale_workers: int
    tasks_per_worker: float
    timestamp: datetime


@dataclass
class ScalingRecommendation:
    """Container for scaling recommendation."""
    action: ScalingAction
    current_workers: int
    recommended_workers: int
    reason: str
    metrics: QueueMetrics


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


def get_queue_metrics() -> QueueMetrics:
    """
    Get current queue depth and worker metrics.
    
    Returns:
        QueueMetrics object with current queue state
    """
    # Get task counts by status
    task_query = """
    SELECT 
        status,
        COUNT(*) as count
    FROM governance_tasks
    WHERE status IN ('pending', 'in_progress')
    GROUP BY status
    """
    task_result = _execute_sql(task_query)
    
    pending_count = 0
    in_progress_count = 0
    for row in task_result.get("rows", []):
        if row["status"] == "pending":
            pending_count = int(row["count"])
        elif row["status"] == "in_progress":
            in_progress_count = int(row["count"])
    
    # Get active worker count (workers with in-progress tasks in last N minutes)
    stale_cutoff = datetime.utcnow() - timedelta(minutes=STALE_WORKER_MINUTES)
    worker_query = f"""
    SELECT 
        assigned_worker,
        MAX(started_at) as last_activity
    FROM governance_tasks
    WHERE status = 'in_progress'
      AND assigned_worker IS NOT NULL
      AND assigned_worker != 'claude-chat'
    GROUP BY assigned_worker
    """
    worker_result = _execute_sql(worker_query)
    
    active_workers = 0
    stale_workers = 0
    for row in worker_result.get("rows", []):
        # Check if worker is stale
        if row.get("last_activity"):
            try:
                last_activity = datetime.fromisoformat(
                    row["last_activity"].replace("Z", "+00:00").replace("+00", "+00:00")
                )
                if last_activity.replace(tzinfo=None) < stale_cutoff:
                    stale_workers += 1
                else:
                    active_workers += 1
            except (ValueError, TypeError):
                active_workers += 1
        else:
            active_workers += 1
    
    # Calculate tasks per worker (avoid division by zero)
    effective_workers = max(active_workers, 1)
    tasks_per_worker = pending_count / effective_workers
    
    return QueueMetrics(
        pending_tasks=pending_count,
        in_progress_tasks=in_progress_count,
        active_workers=active_workers,
        stale_workers=stale_workers,
        tasks_per_worker=round(tasks_per_worker, 2),
        timestamp=datetime.utcnow()
    )


def get_last_scaling_event() -> Optional[Dict[str, Any]]:
    """
    Get the most recent scaling event.
    
    Returns:
        Dict with last scaling event or None if no events
    """
    query = """
    SELECT 
        id, action, previous_workers, new_workers, reason, created_at
    FROM scaling_events
    ORDER BY created_at DESC
    LIMIT 1
    """
    try:
        result = _execute_sql(query)
        rows = result.get("rows", [])
        return rows[0] if rows else None
    except Exception as e:
        logger.warning(f"Could not fetch last scaling event: {e}")
        return None


def is_in_cooldown() -> bool:
    """
    Check if we're in a cooldown period from recent scaling.
    
    Returns:
        True if in cooldown, False otherwise
    """
    last_event = get_last_scaling_event()
    if not last_event:
        return False
    
    try:
        last_time = datetime.fromisoformat(
            last_event["created_at"].replace("Z", "+00:00").replace("+00", "+00:00")
        )
        cooldown_end = last_time + timedelta(minutes=COOLDOWN_MINUTES)
        return datetime.utcnow().replace(tzinfo=last_time.tzinfo) < cooldown_end
    except (ValueError, TypeError, KeyError):
        return False


def get_scaling_recommendation(
    metrics: Optional[QueueMetrics] = None
) -> ScalingRecommendation:
    """
    Determine if scaling is needed based on queue metrics.
    
    Args:
        metrics: Optional pre-fetched metrics (will fetch if not provided)
    
    Returns:
        ScalingRecommendation with action and reasoning
    """
    if metrics is None:
        metrics = get_queue_metrics()
    
    current_workers = metrics.active_workers
    recommended_workers = current_workers
    
    # Check cooldown
    if is_in_cooldown():
        return ScalingRecommendation(
            action=ScalingAction.NO_CHANGE,
            current_workers=current_workers,
            recommended_workers=current_workers,
            reason="In cooldown period from recent scaling event",
            metrics=metrics
        )
    
    # No pending tasks - consider scale down
    if metrics.pending_tasks == 0:
        if current_workers > MIN_WORKERS:
            return ScalingRecommendation(
                action=ScalingAction.SCALE_DOWN,
                current_workers=current_workers,
                recommended_workers=max(MIN_WORKERS, current_workers - 1),
                reason=f"No pending tasks, reducing workers from {current_workers}",
                metrics=metrics
            )
        return ScalingRecommendation(
            action=ScalingAction.NO_CHANGE,
            current_workers=current_workers,
            recommended_workers=current_workers,
            reason="No pending tasks, already at minimum workers",
            metrics=metrics
        )
    
    # High queue depth - scale up
    if metrics.tasks_per_worker >= SCALE_UP_THRESHOLD:
        if current_workers < MAX_WORKERS:
            # Calculate how many workers we need
            target_workers = min(
                MAX_WORKERS,
                current_workers + max(1, int(metrics.tasks_per_worker / SCALE_UP_THRESHOLD))
            )
            return ScalingRecommendation(
                action=ScalingAction.SCALE_UP,
                current_workers=current_workers,
                recommended_workers=target_workers,
                reason=f"High queue depth ({metrics.tasks_per_worker:.1f} tasks/worker), scaling up",
                metrics=metrics
            )
        return ScalingRecommendation(
            action=ScalingAction.NO_CHANGE,
            current_workers=current_workers,
            recommended_workers=current_workers,
            reason="High queue depth but already at maximum workers",
            metrics=metrics
        )
    
    # Low queue depth - consider scale down
    if metrics.tasks_per_worker <= SCALE_DOWN_THRESHOLD:
        if current_workers > MIN_WORKERS:
            return ScalingRecommendation(
                action=ScalingAction.SCALE_DOWN,
                current_workers=current_workers,
                recommended_workers=max(MIN_WORKERS, current_workers - 1),
                reason=f"Low queue depth ({metrics.tasks_per_worker:.1f} tasks/worker), scaling down",
                metrics=metrics
            )
    
    # Default - no change needed
    return ScalingRecommendation(
        action=ScalingAction.NO_CHANGE,
        current_workers=current_workers,
        recommended_workers=current_workers,
        reason=f"Queue depth normal ({metrics.tasks_per_worker:.1f} tasks/worker)",
        metrics=metrics
    )


def record_scaling_event(
    action: ScalingAction,
    previous_workers: int,
    new_workers: int,
    reason: str,
    triggered_by: str = "AUTOSCALER"
) -> Dict[str, Any]:
    """
    Record a scaling event to the database.
    
    Args:
        action: The scaling action taken
        previous_workers: Worker count before scaling
        new_workers: Worker count after scaling
        reason: Explanation for the scaling decision
        triggered_by: Who/what triggered the scaling
    
    Returns:
        Dict with event_id and status
    """
    event_id = str(uuid.uuid4())
    
    query = f"""
    INSERT INTO scaling_events (
        id, action, previous_workers, new_workers, reason, triggered_by
    ) VALUES (
        '{event_id}',
        '{action.value}',
        {previous_workers},
        {new_workers},
        '{reason.replace("'", "''")}',
        '{triggered_by}'
    )
    RETURNING id
    """
    
    try:
        result = _execute_sql(query)
        return {
            "success": True,
            "event_id": event_id,
            "action": action.value,
            "message": f"Scaling event recorded: {action.value}"
        }
    except Exception as e:
        logger.error(f"Failed to record scaling event: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_scaling_history(
    limit: int = 10,
    action_filter: Optional[ScalingAction] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve recent scaling events.
    
    Args:
        limit: Maximum number of events to return
        action_filter: Optional filter for specific action type
    
    Returns:
        List of scaling event dictionaries
    """
    conditions = []
    if action_filter:
        conditions.append(f"action = '{action_filter.value}'")
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    query = f"""
    SELECT 
        id, action, previous_workers, new_workers, 
        reason, triggered_by, created_at
    FROM scaling_events
    {where_clause}
    ORDER BY created_at DESC
    LIMIT {limit}
    """
    
    result = _execute_sql(query)
    return result.get("rows", [])


def reset_stale_workers() -> Dict[str, Any]:
    """
    Reset tasks from stale workers back to pending status.
    
    Returns:
        Dict with count of reset tasks
    """
    stale_cutoff = datetime.utcnow() - timedelta(minutes=STALE_WORKER_MINUTES)
    
    query = f"""
    UPDATE governance_tasks
    SET 
        status = 'pending',
        assigned_worker = 'claude-chat',
        started_at = NULL
    WHERE status = 'in_progress'
      AND started_at < '{stale_cutoff.isoformat()}'
    RETURNING id, title
    """
    
    result = _execute_sql(query)
    reset_count = result.get("rowCount", 0)
    
    logger.info(f"Reset {reset_count} tasks from stale workers")
    
    return {
        "success": True,
        "reset_count": reset_count,
        "reset_tasks": result.get("rows", [])
    }


def get_worker_status() -> List[Dict[str, Any]]:
    """
    Get status of all active workers.
    
    Returns:
        List of worker status dictionaries
    """
    query = """
    SELECT 
        assigned_worker,
        COUNT(*) as active_tasks,
        MIN(started_at) as oldest_task_started,
        MAX(started_at) as newest_task_started
    FROM governance_tasks
    WHERE status = 'in_progress'
      AND assigned_worker IS NOT NULL
      AND assigned_worker != 'claude-chat'
    GROUP BY assigned_worker
    ORDER BY active_tasks DESC
    """
    
    result = _execute_sql(query)
    return result.get("rows", [])


def create_scaling_events_table() -> Dict[str, Any]:
    """
    Create the scaling_events table if it doesn't exist.
    
    Returns:
        Dict with creation status
    """
    query = """
    CREATE TABLE IF NOT EXISTS scaling_events (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        action VARCHAR(50) NOT NULL,
        previous_workers INTEGER NOT NULL,
        new_workers INTEGER NOT NULL,
        reason TEXT,
        triggered_by VARCHAR(100) DEFAULT 'AUTOSCALER',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
    """
    
    try:
        _execute_sql(query, return_results=False)
        return {"success": True, "message": "scaling_events table created/verified"}
    except Exception as e:
        logger.error(f"Failed to create scaling_events table: {e}")
        return {"success": False, "error": str(e)}
