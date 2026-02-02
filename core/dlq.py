"""
Dead Letter Queue (DLQ) utilities for handling permanently failed tasks.

This module provides functions to move failed tasks to a dead letter queue
after they have exceeded their retry limits, allowing for manual review
and potential recovery.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Union

from .database import query_db

logger = logging.getLogger(__name__)

class DLQError(Exception):
    """Exception raised for errors in the DLQ module."""
    pass

async def move_to_dlq(
    task_id: Union[str, uuid.UUID],
    failure_reason: str,
    task_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Move a permanently failed task to the dead letter queue.
    
    Args:
        task_id: UUID of the failed task
        failure_reason: Reason for the failure
        task_data: Optional task data if already available
        
    Returns:
        UUID of the DLQ entry
        
    Raises:
        DLQError: If the task cannot be moved to DLQ
    """
    try:
        # Convert task_id to string if it's a UUID
        task_id_str = str(task_id)
        
        # Use the database function to move the task to DLQ
        result = query_db(
            """
            SELECT move_to_dlq($1, $2) as dlq_id
            """,
            [task_id_str, failure_reason]
        )
        
        if not result or "rows" not in result or not result["rows"]:
            raise DLQError(f"Failed to move task {task_id} to DLQ: No result returned")
        
        dlq_id = result["rows"][0].get("dlq_id")
        if not dlq_id:
            raise DLQError(f"Failed to move task {task_id} to DLQ: No DLQ ID returned")
        
        logger.warning(f"Task {task_id} moved to DLQ: {failure_reason}")
        return dlq_id
        
    except Exception as e:
        logger.error(f"Error moving task {task_id} to DLQ: {e}")
        raise DLQError(f"Failed to move task to DLQ: {e}")

async def retry_dlq_item(
    dlq_id: Union[str, uuid.UUID],
    retry_by: str = "system"
) -> Dict[str, Any]:
    """
    Retry a task from the dead letter queue.
    
    Args:
        dlq_id: UUID of the DLQ entry
        retry_by: Identifier of who initiated the retry
        
    Returns:
        Dict with retry information
        
    Raises:
        DLQError: If the retry fails
    """
    try:
        # Convert dlq_id to string if it's a UUID
        dlq_id_str = str(dlq_id)
        
        # Get the DLQ entry
        dlq_result = query_db(
            """
            SELECT * FROM dead_letter_queue WHERE id = $1
            """,
            [dlq_id_str]
        )
        
        if not dlq_result or "rows" not in dlq_result or not dlq_result["rows"]:
            raise DLQError(f"DLQ entry {dlq_id} not found")
        
        dlq_entry = dlq_result["rows"][0]
        original_task_id = dlq_entry.get("original_task_id")
        task_snapshot = dlq_entry.get("task_snapshot")
        
        if not original_task_id or not task_snapshot:
            raise DLQError(f"Invalid DLQ entry {dlq_id}: missing task data")
        
        # Update the DLQ entry
        update_result = query_db(
            """
            UPDATE dead_letter_queue
            SET status = 'retrying',
                retry_count = retry_count + 1,
                last_failure_at = NOW()
            WHERE id = $1
            RETURNING retry_count
            """,
            [dlq_id_str]
        )
        
        if not update_result or "rows" not in update_result or not update_result["rows"]:
            raise DLQError(f"Failed to update DLQ entry {dlq_id}")
        
        retry_count = update_result["rows"][0].get("retry_count", 1)
        
        # Reset the original task
        task_result = query_db(
            """
            UPDATE governance_tasks
            SET status = 'pending',
                moved_to_dlq = FALSE,
                dlq_id = NULL,
                completion_evidence = completion_evidence || jsonb_build_object(
                    'retried_from_dlq', true,
                    'retry_count', $2,
                    'retried_by', $3,
                    'retried_at', NOW()::text
                )
            WHERE id = $1
            RETURNING id, title
            """,
            [original_task_id, retry_count, retry_by]
        )
        
        if not task_result or "rows" not in task_result or not task_result["rows"]:
            raise DLQError(f"Failed to reset task {original_task_id}")
        
        task_info = task_result["rows"][0]
        
        logger.info(f"Task {original_task_id} ({task_info.get('title')}) retried from DLQ by {retry_by}")
        
        return {
            "dlq_id": dlq_id_str,
            "task_id": original_task_id,
            "task_title": task_info.get("title"),
            "retry_count": retry_count,
            "retried_by": retry_by
        }
        
    except Exception as e:
        logger.error(f"Error retrying DLQ item {dlq_id}: {e}")
        raise DLQError(f"Failed to retry DLQ item: {e}")

async def resolve_dlq_item(
    dlq_id: Union[str, uuid.UUID],
    resolution_notes: str,
    resolved_by: str = "system"
) -> Dict[str, Any]:
    """
    Mark a DLQ item as resolved without retrying.
    
    Args:
        dlq_id: UUID of the DLQ entry
        resolution_notes: Notes explaining the resolution
        resolved_by: Identifier of who resolved the item
        
    Returns:
        Dict with resolution information
        
    Raises:
        DLQError: If the resolution fails
    """
    try:
        # Convert dlq_id to string if it's a UUID
        dlq_id_str = str(dlq_id)
        
        # Update the DLQ entry
        result = query_db(
            """
            UPDATE dead_letter_queue
            SET status = 'resolved',
                resolution_notes = $2,
                resolved_by = $3,
                resolved_at = NOW()
            WHERE id = $1
            RETURNING original_task_id
            """,
            [dlq_id_str, resolution_notes, resolved_by]
        )
        
        if not result or "rows" not in result or not result["rows"]:
            raise DLQError(f"DLQ entry {dlq_id} not found")
        
        original_task_id = result["rows"][0].get("original_task_id")
        
        # Update the original task with resolution info
        if original_task_id:
            task_result = query_db(
                """
                UPDATE governance_tasks
                SET completion_evidence = completion_evidence || jsonb_build_object(
                    'dlq_resolved', true,
                    'resolution_notes', $2,
                    'resolved_by', $3,
                    'resolved_at', NOW()::text
                )
                WHERE id = $1
                RETURNING title
                """,
                [original_task_id, resolution_notes, resolved_by]
            )
            
            task_title = task_result["rows"][0].get("title") if task_result and "rows" in task_result and task_result["rows"] else "Unknown"
        else:
            task_title = "Unknown"
        
        logger.info(f"DLQ item {dlq_id} resolved by {resolved_by}: {resolution_notes}")
        
        return {
            "dlq_id": dlq_id_str,
            "task_id": original_task_id,
            "task_title": task_title,
            "resolution_notes": resolution_notes,
            "resolved_by": resolved_by
        }
        
    except Exception as e:
        logger.error(f"Error resolving DLQ item {dlq_id}: {e}")
        raise DLQError(f"Failed to resolve DLQ item: {e}")

async def get_dlq_items(
    status: Optional[str] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Get items from the dead letter queue.
    
    Args:
        status: Optional filter by status (pending, retrying, resolved, abandoned)
        limit: Maximum number of items to return
        
    Returns:
        List of DLQ items
        
    Raises:
        DLQError: If the query fails
    """
    try:
        if status:
            result = query_db(
                """
                SELECT dlq.*, gt.title as task_title
                FROM dead_letter_queue dlq
                LEFT JOIN governance_tasks gt ON dlq.original_task_id = gt.id
                WHERE dlq.status = $1
                ORDER BY dlq.last_failure_at DESC
                LIMIT $2
                """,
                [status, limit]
            )
        else:
            result = query_db(
                """
                SELECT dlq.*, gt.title as task_title
                FROM dead_letter_queue dlq
                LEFT JOIN governance_tasks gt ON dlq.original_task_id = gt.id
                ORDER BY dlq.last_failure_at DESC
                LIMIT $1
                """,
                [limit]
            )
        
        if not result or "rows" not in result:
            return []
        
        return result["rows"]
        
    except Exception as e:
        logger.error(f"Error getting DLQ items: {e}")
        raise DLQError(f"Failed to get DLQ items: {e}")

async def get_dlq_stats() -> Dict[str, Any]:
    """
    Get statistics about the dead letter queue.
    
    Returns:
        Dict with DLQ statistics
        
    Raises:
        DLQError: If the query fails
    """
    try:
        result = query_db(
            """
            SELECT
                COUNT(*) as total_count,
                COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                COUNT(*) FILTER (WHERE status = 'retrying') as retrying_count,
                COUNT(*) FILTER (WHERE status = 'resolved') as resolved_count,
                COUNT(*) FILTER (WHERE status = 'abandoned') as abandoned_count,
                MAX(last_failure_at) as last_failure,
                AVG(failure_count) as avg_failures
            FROM dead_letter_queue
            """
        )
        
        if not result or "rows" not in result or not result["rows"]:
            return {
                "total_count": 0,
                "pending_count": 0,
                "retrying_count": 0,
                "resolved_count": 0,
                "abandoned_count": 0,
                "last_failure": None,
                "avg_failures": 0
            }
        
        return result["rows"][0]
        
    except Exception as e:
        logger.error(f"Error getting DLQ stats: {e}")
        raise DLQError(f"Failed to get DLQ stats: {e}")

def should_move_to_dlq(failure_count: int, max_retries: int = 3) -> bool:
    """
    Determine if a task should be moved to the dead letter queue.
    
    Args:
        failure_count: Number of times the task has failed
        max_retries: Maximum number of retries before moving to DLQ
        
    Returns:
        True if the task should be moved to DLQ, False otherwise
    """
    return failure_count >= max_retries
