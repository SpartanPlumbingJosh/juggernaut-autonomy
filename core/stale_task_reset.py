"""
Stale Task Reset - Automatically reset stuck in_progress tasks

Finds tasks that have been in_progress for too long with no updates
and resets them to pending so they can be retried.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


def reset_stale_tasks(
    execute_sql: Callable,
    log_action: Callable,
    stale_threshold_minutes: int = 30
) -> Dict[str, Any]:
    """Reset tasks that have been stuck in_progress for too long.
    
    Args:
        execute_sql: SQL execution function
        log_action: Logging function
        stale_threshold_minutes: Minutes before task is considered stale
    
    Returns:
        Dict with reset count and task IDs
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_threshold_minutes)
        
        # Find stale tasks
        find_sql = f"""
            SELECT id, title, assigned_worker, updated_at
            FROM governance_tasks
            WHERE status = 'in_progress'
              AND updated_at < '{cutoff.isoformat()}'
              AND assigned_worker IS NOT NULL
        """
        
        result = execute_sql(find_sql)
        stale_tasks = result.get("rows", [])
        
        if not stale_tasks:
            return {
                "success": True,
                "reset_count": 0,
                "task_ids": []
            }
        
        # Reset each stale task
        reset_ids = []
        for task in stale_tasks:
            task_id = task.get("id")
            title = task.get("title", "")
            worker = task.get("assigned_worker", "")
            updated_at = task.get("updated_at", "")
            
            try:
                reset_sql = f"""
                    UPDATE governance_tasks
                    SET status = 'pending',
                        assigned_worker = NULL,
                        started_at = NULL,
                        error_message = CONCAT(
                            COALESCE(error_message, ''),
                            '[STALE RESET] Task was stuck in_progress for {stale_threshold_minutes}+ minutes. '
                        ),
                        updated_at = NOW()
                    WHERE id = '{task_id}'
                      AND status = 'in_progress'
                """
                execute_sql(reset_sql)
                
                log_action(
                    "stale_task.reset",
                    f"Reset stale task: {title}",
                    level="warning",
                    task_id=task_id,
                    output_data={
                        "worker": worker,
                        "last_updated": updated_at,
                        "stale_minutes": stale_threshold_minutes
                    }
                )
                
                reset_ids.append(task_id)
                
            except Exception as e:
                logger.error(f"Failed to reset task {task_id}: {e}")
        
        log_action(
            "stale_task.reset_complete",
            f"Reset {len(reset_ids)} stale tasks",
            level="info",
            output_data={
                "reset_count": len(reset_ids),
                "threshold_minutes": stale_threshold_minutes
            }
        )
        
        return {
            "success": True,
            "reset_count": len(reset_ids),
            "task_ids": reset_ids
        }
        
    except Exception as e:
        logger.exception(f"Stale task reset failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "reset_count": 0
        }
