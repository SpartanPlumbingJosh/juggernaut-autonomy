"""
Learning Application Module for JUGGERNAUT Autonomy Engine.

This module implements the application loop for captured learnings, enabling
the system to improve by applying validated learnings to workflows and configs.

Features:
- Reads validated/high-confidence learnings from the database
- Applies learnings to relevant workflows and configurations
- Increments applied_count and tracks effectiveness
- Supports scheduled execution from the main orchestration loop
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

# Constants for learning application
CONFIDENCE_THRESHOLD_FOR_APPLICATION = 0.7
MAX_LEARNINGS_PER_CYCLE = 10
DEFAULT_APPLICATION_INTERVAL_SECONDS = 300  # 5 minutes

# Learning categories that can be applied
APPLICABLE_CATEGORIES = [
    "success_pattern",
    "failure_pattern",
    "performance",
    "optimization_opportunity",
    "process",
]

# Configure module logger
logger = logging.getLogger(__name__)


def get_applicable_learnings(
    execute_sql_func: Callable[[str], Dict[str, Any]],
    limit: int = MAX_LEARNINGS_PER_CYCLE,
) -> List[Dict[str, Any]]:
    """
    Retrieve learnings that are ready to be applied.

    Fetches learnings that either:
    - Have is_validated=true, OR
    - Have confidence >= threshold

    Args:
        execute_sql_func: Function to execute SQL queries
        limit: Maximum number of learnings to retrieve

    Returns:
        List of learning dictionaries ready for application
    """
    sql = f"""
        SELECT 
            id,
            worker_id,
            goal_id,
            task_id,
            category,
            summary,
            details,
            confidence,
            applied_count,
            effectiveness_score,
            is_validated,
            created_at,
            updated_at
        FROM learnings
        WHERE (is_validated = true OR confidence >= {CONFIDENCE_THRESHOLD_FOR_APPLICATION})
          AND category IN ({', '.join([f"'{cat}'" for cat in APPLICABLE_CATEGORIES])})
        ORDER BY 
            is_validated DESC,
            confidence DESC,
            applied_count ASC,
            created_at DESC
        LIMIT {limit}
    """

    try:
        result = execute_sql_func(sql)
        rows = result.get("rows", [])
        logger.info(
            "Retrieved applicable learnings",
            extra={"count": len(rows)},
        )
        return rows
    except Exception as db_error:
        logger.error(
            "Failed to retrieve applicable learnings",
            extra={"error": str(db_error)},
        )
        return []


def apply_learning(
    learning: Dict[str, Any],
    execute_sql_func: Callable[[str], Dict[str, Any]],
    escape_value_func: Callable[[Any], str],
    log_action_func: Callable[..., Any],
) -> Tuple[bool, Optional[str]]:
    """
    Apply a single learning to the system.

    This function determines the appropriate application strategy based on
    the learning category and applies it to the relevant system component.

    Args:
        learning: Learning dictionary from the database
        execute_sql_func: Function to execute SQL queries
        escape_value_func: Function to escape values for SQL
        log_action_func: Function to log actions

    Returns:
        Tuple of (success: bool, application_result: Optional[str])
    """
    learning_id = learning.get("id")
    category = learning.get("category", "")
    summary = learning.get("summary", "")
    details = learning.get("details", {})

    # Parse details if it's a string
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            details = {}

    log_action_func(
        "learning.applying",
        f"Applying learning: {category} - {summary[:100]}",
        output_data={"learning_id": learning_id},
    )

    application_result = None
    success = False

    try:
        if category == "success_pattern":
            success, application_result = _apply_success_pattern(
                learning, execute_sql_func, escape_value_func
            )
        elif category == "failure_pattern":
            success, application_result = _apply_failure_pattern(
                learning, execute_sql_func, escape_value_func
            )
        elif category == "performance":
            success, application_result = _apply_performance_insight(
                learning, execute_sql_func, escape_value_func
            )
        elif category == "optimization_opportunity":
            success, application_result = _apply_optimization(
                learning, execute_sql_func, escape_value_func
            )
        elif category == "process":
            success, application_result = _apply_process_learning(
                learning, execute_sql_func, escape_value_func
            )
        else:
            application_result = f"Unknown category: {category}"
            logger.warning(
                "Unknown learning category",
                extra={"learning_id": learning_id, "category": category},
            )

        if success:
            log_action_func(
                "learning.applied",
                f"Successfully applied learning: {summary[:100]}",
                output_data={"result": application_result},
            )
        else:
            log_action_func(
                "learning.apply_failed",
                f"Failed to apply learning: {application_result}",
                level="warn",
            )

    except ValueError as val_error:
        application_result = f"Value error: {str(val_error)}"
        logger.error(
            "Learning application failed with value error",
            extra={"learning_id": learning_id, "error": str(val_error)},
        )
    except TypeError as type_error:
        application_result = f"Type error: {str(type_error)}"
        logger.error(
            "Learning application failed with type error",
            extra={"learning_id": learning_id, "error": str(type_error)},
        )

    return success, application_result


def _apply_success_pattern(
    learning: Dict[str, Any],
    execute_sql_func: Callable[[str], Dict[str, Any]],
    escape_value_func: Callable[[Any], str],
) -> Tuple[bool, str]:
    """
    Apply a success pattern learning.

    Success patterns are stored in system_config for future reference
    and used to guide similar task executions.

    Args:
        learning: Learning dictionary
        execute_sql_func: Function to execute SQL queries
        escape_value_func: Function to escape values for SQL

    Returns:
        Tuple of (success: bool, result: str)
    """
    learning_id = learning.get("id")
    summary = learning.get("summary", "")
    details = learning.get("details", {})

    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            details = {}

    task_type = details.get("task_type", "unknown")

    # Store success pattern in system_config for future reference
    config_key = f"success_pattern_{task_type}"
    config_value = {
        "learning_id": learning_id,
        "summary": summary,
        "what_worked": details.get("what_worked", ""),
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }

    sql = f"""
        INSERT INTO system_config (key, value, description, updated_at)
        VALUES (
            {escape_value_func(config_key)},
            {escape_value_func(json.dumps(config_value))}::jsonb,
            {escape_value_func(f'Success pattern from learning {learning_id}')},
            NOW()
        )
        ON CONFLICT (key) DO UPDATE SET
            value = {escape_value_func(json.dumps(config_value))}::jsonb,
            updated_at = NOW()
        RETURNING key
    """

    try:
        result = execute_sql_func(sql)
        if result.get("rows"):
            return True, f"Stored success pattern for {task_type}"
        return False, "No rows returned from insert"
    except Exception as db_error:
        return False, f"Database error: {str(db_error)}"


def _apply_failure_pattern(
    learning: Dict[str, Any],
    execute_sql_func: Callable[[str], Dict[str, Any]],
    escape_value_func: Callable[[Any], str],
) -> Tuple[bool, str]:
    """
    Apply a failure pattern learning.

    Failure patterns are stored to help avoid similar failures in the future.

    Args:
        learning: Learning dictionary
        execute_sql_func: Function to execute SQL queries
        escape_value_func: Function to escape values for SQL

    Returns:
        Tuple of (success: bool, result: str)
    """
    learning_id = learning.get("id")
    summary = learning.get("summary", "")
    details = learning.get("details", {})

    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            details = {}

    task_type = details.get("task_type", "unknown")
    error_info = details.get("error", details.get("what_failed", ""))

    config_key = f"failure_pattern_{task_type}"
    config_value = {
        "learning_id": learning_id,
        "summary": summary,
        "what_failed": error_info,
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }

    sql = f"""
        INSERT INTO system_config (key, value, description, updated_at)
        VALUES (
            {escape_value_func(config_key)},
            {escape_value_func(json.dumps(config_value))}::jsonb,
            {escape_value_func(f'Failure pattern from learning {learning_id}')},
            NOW()
        )
        ON CONFLICT (key) DO UPDATE SET
            value = {escape_value_func(json.dumps(config_value))}::jsonb,
            updated_at = NOW()
        RETURNING key
    """

    try:
        result = execute_sql_func(sql)
        if result.get("rows"):
            return True, f"Stored failure pattern for {task_type}"
        return False, "No rows returned from insert"
    except Exception as db_error:
        return False, f"Database error: {str(db_error)}"


def _apply_performance_insight(
    learning: Dict[str, Any],
    execute_sql_func: Callable[[str], Dict[str, Any]],
    escape_value_func: Callable[[Any], str],
) -> Tuple[bool, str]:
    """
    Apply a performance insight learning.

    Performance insights are used to adjust system parameters and thresholds.

    Args:
        learning: Learning dictionary
        execute_sql_func: Function to execute SQL queries
        escape_value_func: Function to escape values for SQL

    Returns:
        Tuple of (success: bool, result: str)
    """
    learning_id = learning.get("id")
    summary = learning.get("summary", "")
    details = learning.get("details", {})

    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            details = {}

    task_type = details.get("task_type", "unknown")
    duration_ms = details.get("duration_ms", 0)

    config_key = f"performance_baseline_{task_type}"
    config_value = {
        "learning_id": learning_id,
        "baseline_duration_ms": duration_ms,
        "summary": summary,
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }

    sql = f"""
        INSERT INTO system_config (key, value, description, updated_at)
        VALUES (
            {escape_value_func(config_key)},
            {escape_value_func(json.dumps(config_value))}::jsonb,
            {escape_value_func(f'Performance baseline from learning {learning_id}')},
            NOW()
        )
        ON CONFLICT (key) DO UPDATE SET
            value = {escape_value_func(json.dumps(config_value))}::jsonb,
            updated_at = NOW()
        RETURNING key
    """

    try:
        result = execute_sql_func(sql)
        if result.get("rows"):
            return True, f"Stored performance baseline for {task_type}"
        return False, "No rows returned from insert"
    except Exception as db_error:
        return False, f"Database error: {str(db_error)}"


def _apply_optimization(
    learning: Dict[str, Any],
    execute_sql_func: Callable[[str], Dict[str, Any]],
    escape_value_func: Callable[[Any], str],
) -> Tuple[bool, str]:
    """
    Apply an optimization opportunity learning.

    Optimization opportunities create tasks for future improvement.

    Args:
        learning: Learning dictionary
        execute_sql_func: Function to execute SQL queries
        escape_value_func: Function to escape values for SQL

    Returns:
        Tuple of (success: bool, result: str)
    """
    learning_id = learning.get("id")
    summary = learning.get("summary", "")

    # Store optimization opportunity for review
    config_key = f"optimization_queue_{learning_id}"
    config_value = {
        "learning_id": learning_id,
        "summary": summary,
        "status": "pending_review",
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }

    sql = f"""
        INSERT INTO system_config (key, value, description, updated_at)
        VALUES (
            {escape_value_func(config_key)},
            {escape_value_func(json.dumps(config_value))}::jsonb,
            {escape_value_func(f'Optimization opportunity from learning {learning_id}')},
            NOW()
        )
        ON CONFLICT (key) DO UPDATE SET
            value = {escape_value_func(json.dumps(config_value))}::jsonb,
            updated_at = NOW()
        RETURNING key
    """

    try:
        result = execute_sql_func(sql)
        if result.get("rows"):
            return True, "Queued optimization for review"
        return False, "No rows returned from insert"
    except Exception as db_error:
        return False, f"Database error: {str(db_error)}"


def _apply_process_learning(
    learning: Dict[str, Any],
    execute_sql_func: Callable[[str], Dict[str, Any]],
    escape_value_func: Callable[[Any], str],
) -> Tuple[bool, str]:
    """
    Apply a process learning.

    Process learnings are stored as best practices for future reference.

    Args:
        learning: Learning dictionary
        execute_sql_func: Function to execute SQL queries
        escape_value_func: Function to escape values for SQL

    Returns:
        Tuple of (success: bool, result: str)
    """
    learning_id = learning.get("id")
    summary = learning.get("summary", "")

    config_key = f"process_learning_{learning_id}"
    config_value = {
        "learning_id": learning_id,
        "summary": summary,
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }

    sql = f"""
        INSERT INTO system_config (key, value, description, updated_at)
        VALUES (
            {escape_value_func(config_key)},
            {escape_value_func(json.dumps(config_value))}::jsonb,
            {escape_value_func(f'Process learning {learning_id}')},
            NOW()
        )
        ON CONFLICT (key) DO UPDATE SET
            value = {escape_value_func(json.dumps(config_value))}::jsonb,
            updated_at = NOW()
        RETURNING key
    """

    try:
        result = execute_sql_func(sql)
        if result.get("rows"):
            return True, "Stored process learning"
        return False, "No rows returned from insert"
    except Exception as db_error:
        return False, f"Database error: {str(db_error)}"


def increment_applied_count(
    learning_id: str,
    execute_sql_func: Callable[[str], Dict[str, Any]],
    escape_value_func: Callable[[Any], str],
    effectiveness_score: Optional[float] = None,
) -> bool:
    """
    Increment the applied_count for a learning and optionally update effectiveness.

    Args:
        learning_id: ID of the learning to update
        execute_sql_func: Function to execute SQL queries
        escape_value_func: Function to escape values for SQL
        effectiveness_score: Optional effectiveness score (0.0 to 1.0)

    Returns:
        True if update succeeded, False otherwise
    """
    if effectiveness_score is not None:
        sql = f"""
            UPDATE learnings
            SET applied_count = applied_count + 1,
                effectiveness_score = {effectiveness_score},
                updated_at = NOW()
            WHERE id = {escape_value_func(learning_id)}
            RETURNING id, applied_count
        """
    else:
        sql = f"""
            UPDATE learnings
            SET applied_count = applied_count + 1,
                updated_at = NOW()
            WHERE id = {escape_value_func(learning_id)}
            RETURNING id, applied_count
        """

    try:
        result = execute_sql_func(sql)
        rows = result.get("rows", [])
        if rows:
            new_count = rows[0].get("applied_count", 0)
            logger.info(
                "Incremented learning applied_count",
                extra={"learning_id": learning_id, "new_count": new_count},
            )
            return True
        return False
    except Exception as db_error:
        logger.error(
            "Failed to increment applied_count",
            extra={"learning_id": learning_id, "error": str(db_error)},
        )
        return False


def execute_learning_application_cycle(
    execute_sql_func: Callable[[str], Dict[str, Any]],
    escape_value_func: Callable[[Any], str],
    log_action_func: Callable[..., Any],
    max_learnings: int = MAX_LEARNINGS_PER_CYCLE,
) -> Dict[str, Any]:
    """
    Execute a single learning application cycle.

    This is the main entry point for the learning application loop.
    It should be called periodically from the orchestration loop.

    Args:
        execute_sql_func: Function to execute SQL queries
        escape_value_func: Function to escape values for SQL
        log_action_func: Function to log actions
        max_learnings: Maximum learnings to process per cycle

    Returns:
        Dictionary with cycle results:
        - learnings_processed: int
        - learnings_applied: int
        - learnings_failed: int
        - details: list of application results
    """
    # Check if learning cycles are enabled (default OFF to reduce noise)
    enabled = os.environ.get("ENABLE_LEARNING_CYCLES", "false").lower()
    if enabled not in ("true", "1", "yes"):
        logger.debug("Learning application cycles disabled via ENABLE_LEARNING_CYCLES")
        return {
            "learnings_processed": 0,
            "learnings_applied": 0,
            "learnings_failed": 0,
            "details": [],
            "status": "disabled",
        }

    log_action_func(
        "learning.cycle_start",
        f"Starting learning application cycle (max={max_learnings})",
    )

    learnings = get_applicable_learnings(execute_sql_func, limit=max_learnings)

    results = {
        "learnings_processed": 0,
        "learnings_applied": 0,
        "learnings_failed": 0,
        "details": [],
        "status": "completed",
    }

    for learning in learnings:
        learning_id = learning.get("id")
        results["learnings_processed"] += 1

        success, application_result = apply_learning(
            learning=learning,
            execute_sql_func=execute_sql_func,
            escape_value_func=escape_value_func,
            log_action_func=log_action_func,
        )

        if success:
            results["learnings_applied"] += 1
            # Increment applied_count with initial effectiveness of 0.5
            increment_applied_count(
                learning_id=learning_id,
                execute_sql_func=execute_sql_func,
                escape_value_func=escape_value_func,
                effectiveness_score=0.5,  # Initial score, can be updated later
            )
        else:
            results["learnings_failed"] += 1

        results["details"].append({
            "learning_id": learning_id,
            "success": success,
            "result": application_result,
        })

    log_action_func(
        "learning.cycle_complete",
        f"Learning cycle complete: {results['learnings_applied']}/{results['learnings_processed']} applied",
        output_data=results,
    )

    return results
