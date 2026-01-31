"""
Phase 5.3: Scheduled Tasks - Proactive Systems

This module provides cron-like scheduling, recurring task definitions,
task dependency chains, conflict resolution, and schedule reporting.
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Callable
from uuid import uuid4

from .database import execute_query, log_execution

# =============================================================================
# CRON EXPRESSION PARSER
# =============================================================================


def parse_cron_expression(expression: str) -> Dict[str, Any]:
    """
    Parse a cron expression into its components.
    
    Format: minute hour day_of_month month day_of_week
    Example: "0 */6 * * *" = every 6 hours at minute 0
    
    Args:
        expression: Cron expression string
        
    Returns:
        Dict with parsed fields
    """
    parts = expression.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: expected 5 fields, got {len(parts)}")
    
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day_of_month": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
        "raw": expression
    }


def cron_field_matches(field: str, value: int, field_min: int, field_max: int) -> bool:
    """
    Check if a value matches a cron field expression.
    
    Supports: *, */N, N, N-M, N,M,O
    
    Args:
        field: Cron field expression
        value: Value to check
        field_min: Minimum valid value for this field
        field_max: Maximum valid value for this field
        
    Returns:
        True if value matches the field expression
    """
    if field == "*":
        return True
    
    # Handle */N (every N)
    if field.startswith("*/"):
        step = int(field[2:])
        return value % step == 0
    
    # Handle ranges like 1-5
    if "-" in field and "," not in field:
        start, end = map(int, field.split("-"))
        return start <= value <= end
    
    # Handle lists like 1,3,5
    if "," in field:
        values = []
        for part in field.split(","):
            if "-" in part:
                start, end = map(int, part.split("-"))
                values.extend(range(start, end + 1))
            else:
                values.append(int(part))
        return value in values
    
    # Simple number
    return value == int(field)


def calculate_next_cron_run(
    expression: str,
    from_time: Optional[datetime] = None
) -> datetime:
    """
    Calculate the next run time for a cron expression.
    
    Args:
        expression: Cron expression
        from_time: Start time (default: now)
        
    Returns:
        Next scheduled datetime
    """
    if from_time is None:
        from_time = datetime.utcnow()
    
    cron = parse_cron_expression(expression)
    
    # Start from the next minute
    candidate = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
    
    # Search for up to a year
    max_iterations = 525600  # minutes in a year
    
    for _ in range(max_iterations):
        if (cron_field_matches(cron["minute"], candidate.minute, 0, 59) and
            cron_field_matches(cron["hour"], candidate.hour, 0, 23) and
            cron_field_matches(cron["day_of_month"], candidate.day, 1, 31) and
            cron_field_matches(cron["month"], candidate.month, 1, 12) and
            cron_field_matches(cron["day_of_week"], candidate.weekday(), 0, 6)):
            return candidate
        
        candidate += timedelta(minutes=1)
    
    raise ValueError(f"Could not find next run time for: {expression}")


# =============================================================================
# SCHEDULED TASK MANAGEMENT
# =============================================================================


def create_scheduled_task(
    name: str,
    description: str,
    task_type: str,
    cron_expression: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    config: Optional[Dict] = None,
    priority: int = 5,
    dependencies: Optional[List[str]] = None,
    max_consecutive_failures: int = 3,
    created_by: str = "SYSTEM"
) -> Dict[str, Any]:
    """
    Create a new scheduled task.
    
    Args:
        name: Task name (unique)
        description: What this task does
        task_type: Type of task (opportunity_scan, health_check, report, cleanup, etc.)
        cron_expression: Cron schedule (e.g., "0 */6 * * *")
        interval_seconds: Alternative: run every N seconds
        config: Task configuration
        priority: 1-10, higher = more important
        dependencies: List of task IDs that must complete first
        max_consecutive_failures: Disable after this many failures
        created_by: Who created this task
        
    Returns:
        Dict with task_id
    """
    task_id = str(uuid4())
    config = config or {}
    dependencies = dependencies or []
    
    # Determine schedule type and next run
    if cron_expression:
        schedule_type = "cron"
        next_run = calculate_next_cron_run(cron_expression)
    elif interval_seconds:
        schedule_type = "interval"
        next_run = datetime.utcnow() + timedelta(seconds=interval_seconds)
    else:
        schedule_type = "once"
        next_run = datetime.utcnow()
    
    result = execute_query(
        """
        INSERT INTO scheduled_tasks (
            id, name, description, task_type, cron_expression, interval_seconds,
            schedule_type, next_run_at, priority, dependencies, config,
            max_consecutive_failures, created_by
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        RETURNING id, name, next_run_at
        """,
        [task_id, name, description, task_type, cron_expression, interval_seconds,
         schedule_type, next_run.isoformat(), priority, json.dumps(dependencies),
         json.dumps(config), max_consecutive_failures, created_by]
    )
    
    log_execution(
        worker_id=created_by,
        action="scheduler.create",
        message=f"Created scheduled task: {name}",
        details={"task_id": task_id, "schedule_type": schedule_type, "next_run": next_run.isoformat()}
    )
    
    return {
        "success": True,
        "task_id": task_id,
        "name": name,
        "schedule_type": schedule_type,
        "next_run_at": next_run.isoformat()
    }


def update_scheduled_task(
    task_id: str,
    updates: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update a scheduled task.
    
    Args:
        task_id: Task to update
        updates: Fields to update (cron_expression, interval_seconds, config, enabled, priority)
        
    Returns:
        Dict with update status
    """
    allowed_fields = ["cron_expression", "interval_seconds", "config", "enabled", 
                     "priority", "description", "max_consecutive_failures"]
    
    set_clauses = []
    params = [task_id]
    param_idx = 2
    
    for field, value in updates.items():
        if field in allowed_fields:
            if field == "config":
                value = json.dumps(value)
            set_clauses.append(f"{field} = ${param_idx}")
            params.append(value)
            param_idx += 1
    
    if not set_clauses:
        return {"success": False, "error": "No valid fields to update"}
    
    # Recalculate next_run if schedule changed
    if "cron_expression" in updates:
        next_run = calculate_next_cron_run(updates["cron_expression"])
        set_clauses.append(f"next_run_at = ${param_idx}")
        params.append(next_run.isoformat())
        param_idx += 1
        set_clauses.append("schedule_type = 'cron'")
    elif "interval_seconds" in updates:
        next_run = datetime.utcnow() + timedelta(seconds=updates["interval_seconds"])
        set_clauses.append(f"next_run_at = ${param_idx}")
        params.append(next_run.isoformat())
        param_idx += 1
        set_clauses.append("schedule_type = 'interval'")
    
    set_clauses.append("updated_at = NOW()")
    
    result = execute_query(
        f"""
        UPDATE scheduled_tasks
        SET {', '.join(set_clauses)}
        WHERE id = $1
        RETURNING id, name, next_run_at, enabled
        """,
        params
    )
    
    return {
        "success": bool(result.get("rows")),
        "task": result.get("rows", [{}])[0] if result.get("rows") else None
    }


def delete_scheduled_task(task_id: str) -> Dict[str, Any]:
    """
    Delete a scheduled task.
    
    Args:
        task_id: Task to delete
        
    Returns:
        Dict with deletion status
    """
    result = execute_query(
        "DELETE FROM scheduled_tasks WHERE id = $1 RETURNING id, name",
        [task_id]
    )
    
    return {
        "success": bool(result.get("rows")),
        "deleted": result.get("rows", [{}])[0] if result.get("rows") else None
    }


def enable_task(task_id: str) -> Dict[str, Any]:
    """Enable a scheduled task."""
    return update_scheduled_task(task_id, {"enabled": True})


def disable_task(task_id: str) -> Dict[str, Any]:
    """Disable a scheduled task."""
    return update_scheduled_task(task_id, {"enabled": False})


# =============================================================================
# TASK EXECUTION
# =============================================================================


def get_due_tasks(limit: int = 100) -> List[Dict]:
    """
    Get tasks that are due to run.
    
    Args:
        limit: Maximum tasks to return
        
    Returns:
        List of due tasks ordered by priority
    """
    result = execute_query(
        f"""
        SELECT id, name, description, task_type, cron_expression, interval_seconds,
               schedule_type, next_run_at, config, priority, dependencies,
               consecutive_failures, max_consecutive_failures
        FROM scheduled_tasks
        WHERE enabled = true
        AND next_run_at <= NOW()
        AND (last_run_status IS NULL OR last_run_status != 'running')
        ORDER BY priority DESC, next_run_at ASC
        LIMIT {limit}
        """
    )
    
    return result.get("rows", [])


def start_task_run(
    task_id: str,
    triggered_by: str = "scheduler"
) -> Dict[str, Any]:
    """
    Start execution of a scheduled task.
    
    Args:
        task_id: Task to start
        triggered_by: What triggered this run
        
    Returns:
        Dict with run_id and task details
    """
    run_id = str(uuid4())
    
    # Create run record
    execute_query(
        """
        INSERT INTO scheduled_task_runs (id, task_id, triggered_by)
        VALUES ($1, $2, $3)
        """,
        [run_id, task_id, triggered_by]
    )
    
    # Update task status
    execute_query(
        """
        UPDATE scheduled_tasks
        SET last_run_status = 'running', updated_at = NOW()
        WHERE id = $1
        """,
        [task_id]
    )
    
    # Get task details
    result = execute_query(
        "SELECT * FROM scheduled_tasks WHERE id = $1",
        [task_id]
    )
    
    task = result.get("rows", [{}])[0] if result.get("rows") else {}
    
    log_execution(
        worker_id="SCHEDULER",
        action="task.start",
        message=f"Started scheduled task: {task.get('name', task_id)}",
        details={"run_id": run_id, "task_id": task_id}
    )
    
    return {
        "success": True,
        "run_id": run_id,
        "task_id": task_id,
        "task": task
    }


def _parse_timestamp_to_naive(timestamp: Any) -> datetime:
    """
    Parse a timestamp (string or datetime) to a naive datetime for comparison.
    
    Handles various formats including timezone-aware strings from the database.
    
    Args:
        timestamp: String or datetime object
        
    Returns:
        Naive datetime object
    """
    if timestamp is None:
        return None
    
    if isinstance(timestamp, str):
        # Remove timezone info for naive comparison with datetime.utcnow()
        ts_clean = timestamp.replace("Z", "").replace("+00:00", "")
        # Handle other positive timezone offsets like +05:00
        if "+" in ts_clean:
            ts_clean = ts_clean.split("+")[0]
        # Handle negative timezone offsets like -05:00 (but not date separators)
        if "T" in ts_clean and "-" in ts_clean.split("T")[-1]:
            time_part = ts_clean.split("T")[-1]
            if "-" in time_part:
                ts_clean = ts_clean.rsplit("-", 1)[0]
        return datetime.fromisoformat(ts_clean)
    else:
        # Handle datetime objects - strip timezone if present
        if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
            return timestamp.replace(tzinfo=None)
        return timestamp


def complete_task_run(
    run_id: str,
    result: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Mark a task run as completed successfully.
    
    Args:
        run_id: Run to complete
        result: Results from the run
        
    Returns:
        Dict with completion status
    """
    # Get run info to calculate duration
    run_info = execute_query(
        "SELECT task_id, started_at FROM scheduled_task_runs WHERE id = $1",
        [run_id]
    )
    
    if not run_info.get("rows"):
        return {"success": False, "error": "Run not found"}
    
    run = run_info["rows"][0]
    task_id = run["task_id"]
    started_at = run["started_at"]
    
    # Calculate duration using helper function for proper timestamp handling
    if started_at:
        started_dt = _parse_timestamp_to_naive(started_at)
        duration_ms = int((datetime.utcnow() - started_dt).total_seconds() * 1000)
    else:
        duration_ms = 0
    
    # Update run record
    execute_query(
        """
        UPDATE scheduled_task_runs
        SET status = 'success', completed_at = NOW(), result = $2, duration_ms = $3
        WHERE id = $1
        """,
        [run_id, json.dumps(result or {}), duration_ms]
    )
    
    # Update task and calculate next run
    task_info = execute_query(
        "SELECT cron_expression, interval_seconds, schedule_type FROM scheduled_tasks WHERE id = $1",
        [task_id]
    )
    
    if task_info.get("rows"):
        task = task_info["rows"][0]
        
        if task["schedule_type"] == "cron" and task["cron_expression"]:
            next_run = calculate_next_cron_run(task["cron_expression"])
        elif task["schedule_type"] == "interval" and task["interval_seconds"]:
            next_run = datetime.utcnow() + timedelta(seconds=task["interval_seconds"])
        else:
            next_run = None  # One-time task
        
        execute_query(
            """
            UPDATE scheduled_tasks
            SET last_run_at = NOW(),
                last_run_status = 'success',
                last_run_result = $2,
                last_run_duration_ms = $3,
                consecutive_failures = 0,
                next_run_at = $4,
                updated_at = NOW()
            WHERE id = $1
            """,
            [task_id, json.dumps(result or {}), duration_ms, 
             next_run.isoformat() if next_run else None]
        )
    
    log_execution(
        worker_id="SCHEDULER",
        action="task.complete",
        message=f"Completed scheduled task run: {run_id}",
        details={"run_id": run_id, "task_id": task_id, "duration_ms": duration_ms}
    )
    
    return {
        "success": True,
        "run_id": run_id,
        "duration_ms": duration_ms
    }


def fail_task_run(
    run_id: str,
    error_message: str
) -> Dict[str, Any]:
    """
    Mark a task run as failed.
    
    Args:
        run_id: Run that failed
        error_message: What went wrong
        
    Returns:
        Dict with failure status
    """
    # Get run info
    run_info = execute_query(
        "SELECT task_id, started_at FROM scheduled_task_runs WHERE id = $1",
        [run_id]
    )
    
    if not run_info.get("rows"):
        return {"success": False, "error": "Run not found"}
    
    run = run_info["rows"][0]
    task_id = run["task_id"]
    
    # Update run record
    execute_query(
        """
        UPDATE scheduled_task_runs
        SET status = 'failed', completed_at = NOW(), error_message = $2
        WHERE id = $1
        """,
        [run_id, error_message]
    )
    
    # Update task - increment failures and maybe disable
    task_info = execute_query(
        """
        UPDATE scheduled_tasks
        SET last_run_at = NOW(),
            last_run_status = 'failed',
            consecutive_failures = consecutive_failures + 1,
            updated_at = NOW()
        WHERE id = $1
        RETURNING consecutive_failures, max_consecutive_failures, name, cron_expression, interval_seconds, schedule_type
        """,
        [task_id]
    )
    
    disabled = False
    if task_info.get("rows"):
        task = task_info["rows"][0]
        
        # Check if should disable
        if task["consecutive_failures"] >= task["max_consecutive_failures"]:
            execute_query(
                "UPDATE scheduled_tasks SET enabled = false WHERE id = $1",
                [task_id]
            )
            disabled = True
            
            # Create alert - FIXED: Added title parameter, changed component to source
            from .error_recovery import create_alert
            create_alert(
                alert_type="scheduled_task_disabled",
                severity="high",
                title=f"Scheduled task '{task['name']}' disabled",
                message=f"Scheduled task '{task['name']}' disabled after {task['consecutive_failures']} failures",
                source="scheduler",
                metadata={"task_id": task_id, "last_error": error_message}
            )
        else:
            # Calculate next run for retry
            if task["schedule_type"] == "cron" and task["cron_expression"]:
                next_run = calculate_next_cron_run(task["cron_expression"])
            elif task["schedule_type"] == "interval" and task["interval_seconds"]:
                next_run = datetime.utcnow() + timedelta(seconds=task["interval_seconds"])
            else:
                next_run = None
            
            if next_run:
                execute_query(
                    "UPDATE scheduled_tasks SET next_run_at = $2 WHERE id = $1",
                    [task_id, next_run.isoformat()]
                )
    
    log_execution(
        worker_id="SCHEDULER",
        action="task.failed",
        message=f"Scheduled task run failed: {error_message}",
        level="error",
        details={"run_id": run_id, "task_id": task_id, "disabled": disabled}
    )
    
    return {
        "success": True,
        "run_id": run_id,
        "task_disabled": disabled
    }


# =============================================================================
# DEPENDENCY MANAGEMENT
# =============================================================================


def check_dependencies_satisfied(task_id: str) -> Tuple[bool, List[str]]:
    """
    Check if all dependencies for a task are satisfied.
    
    Args:
        task_id: Task to check
        
    Returns:
        Tuple of (all_satisfied, list of unsatisfied dependency IDs)
    """
    result = execute_query(
        "SELECT dependencies FROM scheduled_tasks WHERE id = $1",
        [task_id]
    )
    
    if not result.get("rows"):
        return True, []
    
    dependencies = result["rows"][0].get("dependencies", [])
    if not dependencies:
        return True, []
    
    # Check each dependency's last run status
    unsatisfied = []
    for dep_id in dependencies:
        dep_result = execute_query(
            """
            SELECT id, name, last_run_status, last_run_at
            FROM scheduled_tasks
            WHERE id = $1
            AND last_run_status = 'success'
            AND last_run_at > NOW() - INTERVAL '1 day'
            """,
            [dep_id]
        )
        
        if not dep_result.get("rows"):
            unsatisfied.append(dep_id)
    
    return len(unsatisfied) == 0, unsatisfied


def add_dependency(task_id: str, depends_on_id: str) -> Dict[str, Any]:
    """
    Add a dependency to a task.
    
    Args:
        task_id: Task that will have the dependency
        depends_on_id: Task that must complete first
        
    Returns:
        Dict with update status
    """
    # Check for circular dependencies
    if _would_create_cycle(task_id, depends_on_id):
        return {"success": False, "error": "Would create circular dependency"}
    
    result = execute_query(
        """
        UPDATE scheduled_tasks
        SET dependencies = dependencies || $2::jsonb,
            updated_at = NOW()
        WHERE id = $1
        AND NOT (dependencies @> $2::jsonb)
        RETURNING id, dependencies
        """,
        [task_id, json.dumps([depends_on_id])]
    )
    
    return {
        "success": bool(result.get("rows")),
        "task_id": task_id,
        "depends_on": depends_on_id
    }


def remove_dependency(task_id: str, depends_on_id: str) -> Dict[str, Any]:
    """
    Remove a dependency from a task.
    
    Args:
        task_id: Task to modify
        depends_on_id: Dependency to remove
        
    Returns:
        Dict with update status
    """
    result = execute_query(
        """
        UPDATE scheduled_tasks
        SET dependencies = (
            SELECT COALESCE(jsonb_agg(elem), '[]'::jsonb)
            FROM jsonb_array_elements(dependencies) elem
            WHERE elem::text != $2
        ),
        updated_at = NOW()
        WHERE id = $1
        RETURNING id, dependencies
        """,
        [task_id, json.dumps(depends_on_id)]
    )
    
    return {
        "success": bool(result.get("rows")),
        "task_id": task_id
    }


def _would_create_cycle(task_id: str, new_dependency_id: str) -> bool:
    """Check if adding a dependency would create a cycle."""
    # Get the potential dependency's dependencies recursively
    visited = set()
    to_check = [new_dependency_id]
    
    while to_check:
        current = to_check.pop()
        if current == task_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        
        result = execute_query(
            "SELECT dependencies FROM scheduled_tasks WHERE id = $1",
            [current]
        )
        if result.get("rows"):
            deps = result["rows"][0].get("dependencies", [])
            to_check.extend(deps)
    
    return False


# =============================================================================
# CONFLICT RESOLUTION
# =============================================================================


def get_schedule_conflicts(time_window_minutes: int = 5) -> List[Dict]:
    """
    Find tasks scheduled to run at conflicting times.
    
    Args:
        time_window_minutes: Window to consider as conflicting
        
    Returns:
        List of conflict groups
    """
    result = execute_query(
        f"""
        WITH task_windows AS (
            SELECT 
                id, name, task_type, next_run_at, priority,
                next_run_at - INTERVAL '{time_window_minutes} minutes' as window_start,
                next_run_at + INTERVAL '{time_window_minutes} minutes' as window_end
            FROM scheduled_tasks
            WHERE enabled = true AND next_run_at IS NOT NULL
        )
        SELECT 
            t1.id as task1_id, t1.name as task1_name, t1.priority as task1_priority,
            t2.id as task2_id, t2.name as task2_name, t2.priority as task2_priority,
            t1.next_run_at as task1_time, t2.next_run_at as task2_time
        FROM task_windows t1
        JOIN task_windows t2 ON t1.id < t2.id
        WHERE t1.next_run_at BETWEEN t2.window_start AND t2.window_end
           OR t2.next_run_at BETWEEN t1.window_start AND t1.window_end
        ORDER BY t1.next_run_at
        """
    )
    
    return result.get("rows", [])


def resolve_conflict(
    task_id: str,
    resolution: str,
    delay_minutes: int = 10
) -> Dict[str, Any]:
    """
    Resolve a scheduling conflict.
    
    Args:
        task_id: Task to adjust
        resolution: How to resolve (delay, skip_this_run, change_priority)
        delay_minutes: Minutes to delay if using delay resolution
        
    Returns:
        Dict with resolution status
    """
    if resolution == "delay":
        result = execute_query(
            """
            UPDATE scheduled_tasks
            SET next_run_at = next_run_at + INTERVAL '%s minutes',
                updated_at = NOW()
            WHERE id = $1
            RETURNING id, name, next_run_at
            """ % delay_minutes,
            [task_id]
        )
        return {
            "success": bool(result.get("rows")),
            "resolution": "delayed",
            "delay_minutes": delay_minutes
        }
    
    elif resolution == "skip_this_run":
        # Calculate next run after the current one
        task = execute_query(
            "SELECT cron_expression, interval_seconds, schedule_type, next_run_at FROM scheduled_tasks WHERE id = $1",
            [task_id]
        )
        if task.get("rows"):
            t = task["rows"][0]
            current_next = _parse_timestamp_to_naive(t["next_run_at"])
            
            if t["schedule_type"] == "cron":
                new_next = calculate_next_cron_run(t["cron_expression"], current_next)
            elif t["schedule_type"] == "interval":
                new_next = current_next + timedelta(seconds=t["interval_seconds"])
            else:
                return {"success": False, "error": "Cannot skip one-time task"}
            
            execute_query(
                "UPDATE scheduled_tasks SET next_run_at = $2 WHERE id = $1",
                [task_id, new_next.isoformat()]
            )
            
            return {
                "success": True,
                "resolution": "skipped",
                "new_next_run": new_next.isoformat()
            }
    
    elif resolution == "change_priority":
        # Lower priority to let other task run first
        result = execute_query(
            """
            UPDATE scheduled_tasks
            SET priority = GREATEST(1, priority - 1),
                updated_at = NOW()
            WHERE id = $1
            RETURNING id, priority
            """,
            [task_id]
        )
        return {
            "success": bool(result.get("rows")),
            "resolution": "priority_lowered"
        }
    
    return {"success": False, "error": f"Unknown resolution: {resolution}"}


# =============================================================================
# SCHEDULE REPORTING
# =============================================================================


def get_schedule_report(days_ahead: int = 7) -> Dict[str, Any]:
    """
    Generate a report of upcoming scheduled tasks.
    
    Args:
        days_ahead: How many days to look ahead
        
    Returns:
        Dict with schedule summary and details
    """
    # Get upcoming tasks
    upcoming = execute_query(
        f"""
        SELECT id, name, task_type, next_run_at, cron_expression, 
               interval_seconds, priority, last_run_status, consecutive_failures
        FROM scheduled_tasks
        WHERE enabled = true
        AND next_run_at <= NOW() + INTERVAL '{days_ahead} days'
        ORDER BY next_run_at ASC
        """
    )
    
    # Get recent run statistics
    stats = execute_query(
        """
        SELECT 
            COUNT(*) as total_runs,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            AVG(duration_ms) as avg_duration_ms
        FROM scheduled_task_runs
        WHERE started_at > NOW() - INTERVAL '7 days'
        """
    )
    
    # Get disabled tasks
    disabled = execute_query(
        """
        SELECT id, name, task_type, consecutive_failures, last_run_status
        FROM scheduled_tasks
        WHERE enabled = false
        """
    )
    
    # Get conflicts
    conflicts = get_schedule_conflicts()
    
    return {
        "upcoming_tasks": upcoming.get("rows", []),
        "upcoming_count": len(upcoming.get("rows", [])),
        "recent_stats": stats.get("rows", [{}])[0] if stats.get("rows") else {},
        "disabled_tasks": disabled.get("rows", []),
        "disabled_count": len(disabled.get("rows", [])),
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
        "generated_at": datetime.utcnow().isoformat(),
        "days_ahead": days_ahead
    }


def get_task_run_history(
    task_id: str,
    limit: int = 50
) -> List[Dict]:
    """
    Get run history for a specific task.
    
    Args:
        task_id: Task to get history for
        limit: Maximum records
        
    Returns:
        List of run records
    """
    result = execute_query(
        f"""
        SELECT id, started_at, completed_at, status, result, 
               error_message, duration_ms, triggered_by
        FROM scheduled_task_runs
        WHERE task_id = $1
        ORDER BY started_at DESC
        LIMIT {limit}
        """,
        [task_id]
    )
    
    return result.get("rows", [])


def get_all_scheduled_tasks(
    enabled_only: bool = False,
    task_type: Optional[str] = None
) -> List[Dict]:
    """
    Get all scheduled tasks.
    
    Args:
        enabled_only: Only return enabled tasks
        task_type: Filter by task type
        
    Returns:
        List of scheduled tasks
    """
    conditions = []
    params = []
    param_idx = 1
    
    if enabled_only:
        conditions.append("enabled = true")
    if task_type:
        conditions.append(f"task_type = ${param_idx}")
        params.append(task_type)
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    result = execute_query(
        f"""
        SELECT id, name, description, task_type, cron_expression, interval_seconds,
               schedule_type, next_run_at, last_run_at, last_run_status,
               consecutive_failures, enabled, priority, config
        FROM scheduled_tasks
        {where_clause}
        ORDER BY priority DESC, next_run_at ASC
        """,
        params
    )
    
    return result.get("rows", [])


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Cron
    "parse_cron_expression",
    "calculate_next_cron_run",
    
    # Task Management
    "create_scheduled_task",
    "update_scheduled_task",
    "delete_scheduled_task",
    "enable_task",
    "disable_task",
    "get_all_scheduled_tasks",
    
    # Execution
    "get_due_tasks",
    "start_task_run",
    "complete_task_run",
    "fail_task_run",
    
    # Dependencies
    "check_dependencies_satisfied",
    "add_dependency",
    "remove_dependency",
    
    # Conflicts
    "get_schedule_conflicts",
    "resolve_conflict",
    
    # Reporting
    "get_schedule_report",
    "get_task_run_history",
]
