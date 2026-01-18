"""
Scheduled Task Handlers

This module contains handler functions for different scheduled task types.
Each handler is invoked when a scheduled task of that type is due.
"""

from typing import Any, Dict, Optional
from datetime import datetime, timezone

from .database import (
    cleanup_old_logs,
    get_log_summary,
    log_execution,
)


# =============================================================================
# LOG RETENTION HANDLER
# =============================================================================


def execute_log_retention(
    task_id: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute log retention cleanup.
    
    This handler:
    1. Captures summary stats before deletion (if configured)
    2. Deletes logs older than retention_days
    3. Logs the operation results
    
    Args:
        task_id: The scheduled task ID
        config: Task configuration containing:
            - retention_days: Number of days to keep logs (default: 90)
            - summarize_before_delete: Whether to capture stats first (default: True)
    
    Returns:
        Dict with execution results
    """
    start_time = datetime.now(timezone.utc)
    
    # Extract configuration
    retention_days = config.get("retention_days", 90)
    summarize_first = config.get("summarize_before_delete", True)
    
    result = {
        "success": False,
        "task_id": task_id,
        "retention_days": retention_days,
        "summary": None,
        "deleted_count": 0,
        "error": None,
    }
    
    try:
        # Step 1: Capture summary stats before deletion
        if summarize_first:
            summary = get_log_summary(days=retention_days)
            result["summary"] = summary
            
            # Log the pre-deletion summary
            log_execution(
                worker_id="scheduler",
                action="log_retention.summary",
                message=f"Log summary before cleanup ({retention_days} days)",
                details=summary,
            )
        
        # Step 2: Delete old logs
        deleted_count = cleanup_old_logs(days_to_keep=retention_days)
        result["deleted_count"] = deleted_count
        result["success"] = True
        
        # Step 3: Log the completion
        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        log_execution(
            worker_id="scheduler",
            action="log_retention.complete",
            message=f"Log retention cleanup completed: {deleted_count} logs deleted",
            details={
                "retention_days": retention_days,
                "deleted_count": deleted_count,
                "duration_ms": duration_ms,
            },
            duration_ms=duration_ms,
        )
        
    except Exception as e:
        result["error"] = str(e)
        log_execution(
            worker_id="scheduler",
            action="log_retention.error",
            message=f"Log retention cleanup failed: {str(e)}",
            level="error",
            details={"error": str(e), "task_id": task_id},
        )
    
    return result


# =============================================================================
# TASK HANDLER REGISTRY
# =============================================================================

# Maps task_type to handler function
TASK_HANDLERS = {
    "log_retention": execute_log_retention,
}


def get_task_handler(task_type: str):
    """
    Get the handler function for a task type.
    
    Args:
        task_type: The type of scheduled task
        
    Returns:
        Handler function or None if not found
    """
    return TASK_HANDLERS.get(task_type)


def execute_scheduled_task(
    task_id: str,
    task_type: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute a scheduled task by its type.
    
    Args:
        task_id: The scheduled task ID
        task_type: The type of task (e.g., 'log_retention', 'health_check')
        config: Task configuration
        
    Returns:
        Dict with execution results
    """
    handler = get_task_handler(task_type)
    
    if handler is None:
        return {
            "success": False,
            "error": f"No handler registered for task type: '{task_type}'",
            "task_id": task_id,
        }
    
    return handler(task_id, config)
