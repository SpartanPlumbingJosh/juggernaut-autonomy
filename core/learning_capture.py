"""
Learning Capture Module for JUGGERNAUT Autonomy Engine.

This module implements learning extraction from task executions to enable
continuous improvement of the autonomous system.

Features:
- Extracts learnings from completed tasks (both success and failure)
- Categorizes learnings by type (success_pattern, failure_pattern, etc.)
- Stores learnings in the learnings table for future reference
- Calculates confidence scores based on task outcomes
- Tracks source references for L2-02 References and Sourcing (FIX-11)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

# Constants for learning categories
LEARNING_CATEGORY_SUCCESS = "success_pattern"
LEARNING_CATEGORY_FAILURE = "failure_pattern"
LEARNING_CATEGORY_PERFORMANCE = "performance_insight"
LEARNING_CATEGORY_OPTIMIZATION = "optimization_opportunity"

# Confidence score thresholds
CONFIDENCE_HIGH = 0.9
CONFIDENCE_MEDIUM = 0.7
CONFIDENCE_LOW = 0.5
CONFIDENCE_VERY_LOW = 0.3

# Duration thresholds (in milliseconds) for performance insights
DURATION_FAST_THRESHOLD_MS = 1000
DURATION_SLOW_THRESHOLD_MS = 10000

# Source type constants for standardized source references
SOURCE_TYPE_TASK = "task_execution"
SOURCE_TYPE_SCAN = "opportunity_scan"
SOURCE_TYPE_MANUAL = "manual_entry"
SOURCE_TYPE_EXTERNAL = "external_data"
SOURCE_TYPE_WORKER = "worker_observation"

# Configure module logger
logger = logging.getLogger(__name__)


def build_source_reference(
    source_type: str,
    source_id: Optional[str] = None,
    worker_id: Optional[str] = None,
    additional_context: Optional[str] = None,
) -> str:
    """
    Build a standardized source reference string.

    Args:
        source_type: Type of source (task_execution, opportunity_scan, etc.)
        source_id: Optional ID of the source entity (task_id, scan_id, etc.)
        worker_id: Optional ID of the worker that captured this
        additional_context: Optional additional context about the source

    Returns:
        Formatted source reference string
    """
    parts = [source_type]

    if source_id:
        parts.append(f"id={source_id}")

    if worker_id:
        parts.append(f"worker={worker_id}")

    if additional_context:
        # Truncate context if too long
        context = additional_context[:100] if len(additional_context) > 100 else additional_context
        parts.append(f"context={context}")

    return " | ".join(parts)


def extract_learning_from_task(
    task_id: str,
    task_type: str,
    task_title: str,
    task_description: str,
    success: bool,
    result: Dict[str, Any],
    duration_ms: int,
    worker_id: str,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract learning insights from a completed task execution.

    Args:
        task_id: Unique identifier of the completed task
        task_type: Type of the task (e.g., 'database', 'workflow', 'tool_execution')
        task_title: Human-readable title of the task
        task_description: Full description of the task
        success: Whether the task completed successfully
        result: Result dictionary from task execution
        duration_ms: Execution duration in milliseconds
        worker_id: ID of the worker that executed the task
        source: Optional explicit source reference (if not provided, auto-generated)

    Returns:
        Dictionary containing extracted learning with keys:
        - category: Learning category string
        - summary: Brief summary of the learning
        - details: Detailed learning information as dict
        - confidence: Confidence score (0.0 to 1.0)
        - source: Source reference string
    """
    category = _determine_learning_category(success, result, duration_ms)
    summary = _generate_learning_summary(
        task_type=task_type,
        task_title=task_title,
        success=success,
        result=result,
        duration_ms=duration_ms,
    )
    details = _build_learning_details(
        task_type=task_type,
        task_title=task_title,
        task_description=task_description,
        success=success,
        result=result,
        duration_ms=duration_ms,
        worker_id=worker_id,
    )
    confidence = _calculate_confidence(success, result, duration_ms)

    # Build source reference if not explicitly provided
    if not source:
        source = build_source_reference(
            source_type=SOURCE_TYPE_TASK,
            source_id=task_id,
            worker_id=worker_id,
            additional_context=task_type,
        )

    return {
        "category": category,
        "summary": summary,
        "details": details,
        "confidence": confidence,
        "source": source,
    }


def _determine_learning_category(
    success: bool,
    result: Dict[str, Any],
    duration_ms: int,
) -> str:
    """
    Determine the appropriate learning category based on task outcome.

    Args:
        success: Whether the task completed successfully
        result: Result dictionary from task execution
        duration_ms: Execution duration in milliseconds

    Returns:
        Learning category string
    """
    if not success:
        return LEARNING_CATEGORY_FAILURE

    # Check for performance insights
    if duration_ms < DURATION_FAST_THRESHOLD_MS:
        return LEARNING_CATEGORY_PERFORMANCE
    elif duration_ms > DURATION_SLOW_THRESHOLD_MS:
        return LEARNING_CATEGORY_OPTIMIZATION

    return LEARNING_CATEGORY_SUCCESS


def _generate_learning_summary(
    task_type: str,
    task_title: str,
    success: bool,
    result: Dict[str, Any],
    duration_ms: int,
) -> str:
    """
    Generate a concise summary of the learning.

    Args:
        task_type: Type of the task
        task_title: Human-readable title of the task
        success: Whether the task completed successfully
        result: Result dictionary from task execution
        duration_ms: Execution duration in milliseconds

    Returns:
        Summary string describing the learning
    """
    duration_secs = duration_ms / 1000.0

    if success:
        if duration_ms < DURATION_FAST_THRESHOLD_MS:
            return (
                f"Task type '{task_type}' completed quickly ({duration_secs:.2f}s): "
                f"{task_title}"
            )
        elif duration_ms > DURATION_SLOW_THRESHOLD_MS:
            return (
                f"Task type '{task_type}' was slow ({duration_secs:.2f}s), "
                f"potential optimization opportunity: {task_title}"
            )
        else:
            return (
                f"Task type '{task_type}' succeeded ({duration_secs:.2f}s): "
                f"{task_title}"
            )
    else:
        error_msg = result.get("error", "Unknown error")
        # Truncate error message if too long
        if len(error_msg) > 100:
            error_msg = error_msg[:97] + "..."
        return (
            f"Task type '{task_type}' failed ({duration_secs:.2f}s): "
            f"{error_msg}"
        )


def _sanitize_task_description(description: str) -> str:
    """
    Sanitize task description to remove potential sensitive data.

    Redacts patterns that look like credentials, API keys, SQL queries,
    connection strings, etc.

    Args:
        description: Raw task description

    Returns:
        Sanitized description safe for storage
    """
    import re

    if not description:
        return ""

    sanitized = description

    # Redact patterns that look like credentials/secrets
    sensitive_patterns = [
        # API keys and tokens (various formats)
        (r'(?i)(api[_-]?key|token|secret|password|auth)\s*[=:]\s*[\'"]?[\w\-_.]+[\'"]?', r'\1=<REDACTED>'),
        # Connection strings
        (r'(?i)(postgresql|mysql|mongodb|redis)://[^\s]+', r'\1://<REDACTED>'),
        # Bearer tokens
        (r'(?i)bearer\s+[\w\-_.]+', 'Bearer <REDACTED>'),
        # Generic key=value patterns with sensitive keys
        (r'(?i)(password|secret|token|key|credential)[\'"]?\s*[=:]\s*[\'"]?[^\s,\'"}\]]+', r'\1=<REDACTED>'),
    ]

    for pattern, replacement in sensitive_patterns:
        sanitized = re.sub(pattern, replacement, sanitized)

    return sanitized


def _build_learning_details(
    task_type: str,
    task_title: str,
    task_description: str,
    success: bool,
    result: Dict[str, Any],
    duration_ms: int,
    worker_id: str,
) -> Dict[str, Any]:
    """
    Build detailed learning information dictionary.

    Args:
        task_type: Type of the task
        task_title: Human-readable title of the task
        task_description: Full description of the task
        success: Whether the task completed successfully
        result: Result dictionary from task execution
        duration_ms: Execution duration in milliseconds
        worker_id: ID of the worker that executed the task

    Returns:
        Dictionary with detailed learning information
    """
    details = {
        "task_type": task_type,
        "task_title": task_title,
        "success": success,
        "duration_ms": duration_ms,
        "worker_id": worker_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }

    # Add description excerpt (first 500 chars, sanitized)
    if task_description:
        sanitized_desc = _sanitize_task_description(task_description)
        details["description_excerpt"] = sanitized_desc[:500]

    # Add what worked or what failed
    if success:
        details["what_worked"] = _extract_what_worked(result)
    else:
        details["what_failed"] = _extract_what_failed(result)
        details["error"] = result.get("error")

    # Add result summary (sanitized)
    details["result_summary"] = _sanitize_result_for_storage(result)

    return details


def _extract_what_worked(result: Dict[str, Any]) -> str:
    """
    Extract a summary of what worked from a successful result.

    Args:
        result: Result dictionary from successful task execution

    Returns:
        String describing what worked
    """
    if result.get("dry_run"):
        return "Dry run completed successfully"

    if result.get("executed"):
        row_count = result.get("rowCount", result.get("rows_preview", []))
        if isinstance(row_count, list):
            row_count = len(row_count)
        if row_count:
            return f"Executed successfully with {row_count} rows affected/returned"
        return "Executed successfully"

    if result.get("steps"):
        successful_steps = sum(
            1 for step in result["steps"] if step.get("success", False)
        )
        total_steps = len(result["steps"])
        return f"Workflow completed: {successful_steps}/{total_steps} steps succeeded"

    if result.get("healthy"):
        return f"Health check passed for {result.get('component', 'system')}"

    return "Task completed successfully"


def _extract_what_failed(result: Dict[str, Any]) -> str:
    """
    Extract a summary of what failed from an unsuccessful result.

    Args:
        result: Result dictionary from failed task execution

    Returns:
        String describing what failed
    """
    if result.get("blocked"):
        return f"Blocked: {result.get('reason', 'Permission denied')}"

    if result.get("denied"):
        return "Approval denied"

    if result.get("waiting_approval"):
        return "Waiting for approval (not a permanent failure)"

    if result.get("workflow_failed"):
        failed_steps = [
            step for step in result.get("steps", [])
            if not step.get("success", True)
        ]
        if failed_steps:
            return f"Workflow failed at step {failed_steps[0].get('step', '?')}"
        return "Workflow failed"

    error = result.get("error", "Unknown error")
    return f"Failed with error: {error}"


def _sanitize_result_for_storage(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize result dictionary for safe storage in learnings table.

    Removes sensitive data and limits size of stored values.

    Args:
        result: Raw result dictionary

    Returns:
        Sanitized result dictionary safe for storage
    """
    # Keys to exclude from storage
    sensitive_keys = {
        "password", "secret", "token", "api_key", "apikey", "key",
        "authorization", "auth", "credential", "rows_preview", "rows",
    }

    sanitized = {}
    for key, value in result.items():
        # Skip sensitive keys
        if key.lower() in sensitive_keys:
            continue

        # Handle nested dicts
        if isinstance(value, dict):
            sanitized[key] = _sanitize_result_for_storage(value)
        # Recursively sanitize and truncate lists
        elif isinstance(value, list):
            sanitized_list = []
            for item in value[:5]:  # Limit to 5 items
                if isinstance(item, dict):
                    sanitized_list.append(_sanitize_result_for_storage(item))
                elif isinstance(item, list):
                    # For nested lists, just take first 5 items (no deep recursion)
                    sanitized_list.append(item[:5] if len(item) > 5 else item)
                elif isinstance(item, str) and len(item) > 200:
                    sanitized_list.append(item[:197] + "...")
                else:
                    sanitized_list.append(item)
            sanitized[key] = sanitized_list
        # Truncate long strings
        elif isinstance(value, str) and len(value) > 200:
            sanitized[key] = value[:197] + "..."
        else:
            sanitized[key] = value

    return sanitized


def _calculate_confidence(
    success: bool,
    result: Dict[str, Any],
    duration_ms: int,
) -> float:
    """
    Calculate confidence score for the learning.

    Higher confidence for clear success/failure patterns.
    Lower confidence for edge cases or uncertain outcomes.

    Args:
        success: Whether the task completed successfully
        result: Result dictionary from task execution
        duration_ms: Execution duration in milliseconds

    Returns:
        Confidence score between 0.0 and 1.0
    """
    # Dry runs have lower confidence (not real execution)
    if result.get("dry_run"):
        return CONFIDENCE_LOW

    # Waiting for approval is not a real outcome
    if result.get("waiting_approval"):
        return CONFIDENCE_VERY_LOW

    # Clear success with good execution time
    if success and DURATION_FAST_THRESHOLD_MS <= duration_ms <= DURATION_SLOW_THRESHOLD_MS:
        return CONFIDENCE_HIGH

    # Clear failure with error message
    if not success and result.get("error"):
        return CONFIDENCE_HIGH

    # Success but unusual timing
    if success:
        return CONFIDENCE_MEDIUM

    # Failure without clear error
    return CONFIDENCE_MEDIUM


def save_learning_to_db(
    execute_sql_func: Callable[[str], Dict[str, Any]],
    escape_value_func: Callable[[Any], str],
    task_id: str,
    worker_id: str,
    learning: Dict[str, Any],
    goal_id: Optional[str] = None,
    source: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Save extracted learning to the learnings database table.

    Args:
        execute_sql_func: Function to execute SQL queries
        escape_value_func: Function to escape values for SQL
        task_id: ID of the task this learning is from
        worker_id: ID of the worker that captured this learning
        learning: Learning dictionary from extract_learning_from_task
        goal_id: Optional goal ID if task was part of a goal
        source: Source description for L2-02 compliance (e.g., "task_execution:code")

    Returns:
        Tuple of (success: bool, learning_id: Optional[str])
    """
    now = datetime.now(timezone.utc).isoformat()

    # Build column and value lists
    columns = [
        "worker_id",
        "task_id",
        "category",
        "summary",
        "details",
        "confidence",
        "applied_count",
        "is_validated",
        "created_at",
        "updated_at",
        "source",
    ]

    # Build source string if not provided
    if source is None:
        source = f"task_execution:{learning.get('details', {}).get('task_type', 'unknown')}"

    values = [
        escape_value_func(worker_id),
        escape_value_func(task_id),
        escape_value_func(learning["category"]),
        escape_value_func(learning["summary"]),
        escape_value_func(learning["details"]),
        str(learning["confidence"]),
        "0",  # applied_count starts at 0
        "FALSE",  # is_validated starts as false
        escape_value_func(now),
        escape_value_func(now),
        escape_value_func(source),
    ]

    # Add optional goal_id
    if goal_id:
        columns.append("goal_id")
        values.append(escape_value_func(goal_id))

    # Add evidence_task_ids as JSONB array containing just this task
    columns.append("evidence_task_ids")
    values.append(f"{escape_value_func([task_id])}::jsonb")


    sql = f"""
        INSERT INTO learnings ({', '.join(columns)})
        VALUES ({', '.join(values)})
        RETURNING id
    """

    try:
        result = execute_sql_func(sql)
        rows = result.get("rows", [])
        if rows:
            learning_id = rows[0].get("id")
            logger.info(
                "Learning saved successfully",
                extra={"learning_id": learning_id, "task_id": task_id}
            )
            return True, learning_id
        return False, None
    except Exception as db_error:
        logger.error(
            "Failed to save learning to database",
            extra={"error": str(db_error), "task_id": task_id}
        )
        return False, None


def capture_task_learning(
    execute_sql_func: Callable[[str], Dict[str, Any]],
    escape_value_func: Callable[[Any], str],
    log_action_func: Callable[..., Any],
    task_id: str,
    task_type: str,
    task_title: str,
    task_description: str,
    success: bool,
    result: Dict[str, Any],
    duration_ms: int,
    worker_id: str,
    goal_id: Optional[str] = None,
    source: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Main entry point to capture learning from a completed task.

    This function extracts learning from the task execution and saves it
    to the database. It's designed to be called from main.py after each
    task completion.

    Args:
        execute_sql_func: Function to execute SQL queries
        escape_value_func: Function to escape values for SQL
        log_action_func: Function to log actions
        task_id: ID of the completed task
        task_type: Type of the task
        task_title: Human-readable title of the task
        task_description: Full description of the task
        success: Whether the task completed successfully
        result: Result dictionary from task execution
        duration_ms: Execution duration in milliseconds
        worker_id: ID of the worker that executed the task
        goal_id: Optional goal ID if task was part of a goal
        source: Optional explicit source reference (auto-generated if not provided)

    Returns:
        Tuple of (success: bool, learning_id: Optional[str])
    """
    # Skip learning capture for certain result types
    if result.get("waiting_approval"):
        log_action_func(
            "learning.skipped",
            "Skipping learning capture for task waiting approval",
            task_id=task_id,
        )
        return False, None

    if result.get("dry_run"):
        log_action_func(
            "learning.skipped",
            "Skipping learning capture for dry run",
            task_id=task_id,
        )
        return False, None

    try:
        # Extract learning from the task with source tracking
        learning = extract_learning_from_task(
            task_id=task_id,
            task_type=task_type,
            task_title=task_title,
            task_description=task_description,
            success=success,
            result=result,
            duration_ms=duration_ms,
            worker_id=worker_id,
            source=source,
        )

        # Build source string for L2-02 compliance
        source_str = f"task_execution:{task_type}:{task_id}"

        # Save to database
        saved, learning_id = save_learning_to_db(
            execute_sql_func=execute_sql_func,
            escape_value_func=escape_value_func,
            task_id=task_id,
            worker_id=worker_id,
            learning=learning,
            goal_id=goal_id,
            source=source_str,
        )

        if saved:
            log_action_func(
                "learning.captured",
                f"Learning captured: {learning['category']} - {learning['summary'][:100]}",
                task_id=task_id,
                output_data={
                    "learning_id": learning_id,
                    "category": learning["category"],
                    "confidence": learning["confidence"],
                    "source": learning.get("source", ""),
                },
            )
        else:
            log_action_func(
                "learning.save_failed",
                "Failed to save learning to database",
                level="warn",
                task_id=task_id,
            )

        return saved, learning_id

    except ValueError as val_error:
        log_action_func(
            "learning.extraction_failed",
            f"Learning extraction failed: {str(val_error)}",
            level="error",
            task_id=task_id,
            error_data={"error": str(val_error)},
        )
        return False, None
    except TypeError as type_error:
        log_action_func(
            "learning.extraction_failed",
            f"Learning extraction failed due to type error: {str(type_error)}",
            level="error",
            task_id=task_id,
            error_data={"error": str(type_error)},
        )
        return False, None

