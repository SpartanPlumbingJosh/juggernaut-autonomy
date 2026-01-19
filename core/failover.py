"""
Failover and Resilience Module for JUGGERNAUT

Implements L5-07: Resilience/Failover - Operations continue if one agent fails

Features:
- Monitor worker heartbeats via health_checks table
- Detect worker failures (no heartbeat beyond threshold)
- Automatically reassign tasks from failed workers
- Alert on worker failures
- System continues operating with degraded capacity

EVIDENCE REQUIRED: Worker marked failed, its tasks reassigned
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Configuration constants
DEFAULT_FAILURE_THRESHOLD_MINUTES = 5
FAILURE_THRESHOLD_MINUTES = int(
    os.environ.get("FAILURE_THRESHOLD_MINUTES", DEFAULT_FAILURE_THRESHOLD_MINUTES)
)
MAX_CONSECUTIVE_FAILURES = 3

# Database configuration
NEON_HTTP_ENDPOINT = os.environ.get(
    "NEON_HTTP_ENDPOINT",
    "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_OYkCRU4aze2l@ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
)

logger = logging.getLogger(__name__)


def _execute_query(query: str) -> dict:
    """
    Execute a SQL query via Neon HTTP API.
    
    Args:
        query: SQL query string to execute
        
    Returns:
        Dict with rows, rowCount, and fields from query result
        
    Raises:
        URLError: If database connection fails
        HTTPError: If query fails
    """
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": DATABASE_URL
    }
    data = json.dumps({"query": query}).encode("utf-8")
    
    request = Request(NEON_HTTP_ENDPOINT, data=data, headers=headers, method="POST")
    
    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result
    except HTTPError as e:
        logger.error("Database query failed: %s - %s", e.code, e.reason)
        raise
    except URLError as e:
        logger.error("Database connection failed: %s", e.reason)
        raise


def detect_failed_workers(
    threshold_minutes: Optional[int] = None
) -> list[dict]:
    """
    Detect workers that have failed based on heartbeat timeout.
    
    A worker is considered failed if:
    - No heartbeat recorded in health_checks for > threshold_minutes
    - Has consecutive_failures >= MAX_CONSECUTIVE_FAILURES
    
    Args:
        threshold_minutes: Minutes without heartbeat to consider failed.
                          Defaults to FAILURE_THRESHOLD_MINUTES.
    
    Returns:
        List of dicts with failed worker info:
        [{component, check_type, last_check_at, consecutive_failures, status}]
    """
    if threshold_minutes is None:
        threshold_minutes = FAILURE_THRESHOLD_MINUTES
    
    query = f"""
        SELECT 
            component,
            check_type,
            status,
            last_check_at,
            consecutive_failures,
            error_message,
            metadata
        FROM health_checks
        WHERE (
            last_check_at < NOW() - INTERVAL '{threshold_minutes} minutes'
            OR consecutive_failures >= {MAX_CONSECUTIVE_FAILURES}
        )
        AND status != 'failed'
        ORDER BY last_check_at ASC;
    """
    
    result = _execute_query(query)
    
    failed_workers = []
    for row in result.get("rows", []):
        failed_workers.append({
            "component": row.get("component"),
            "check_type": row.get("check_type"),
            "status": row.get("status"),
            "last_check_at": row.get("last_check_at"),
            "consecutive_failures": row.get("consecutive_failures"),
            "error_message": row.get("error_message"),
            "metadata": row.get("metadata")
        })
    
    return failed_workers


def mark_worker_failed(component: str) -> bool:
    """
    Mark a worker as failed in health_checks table.
    
    Args:
        component: The worker/component name to mark as failed
        
    Returns:
        True if worker was marked failed, False if no matching worker found
    """
    query = f"""
        UPDATE health_checks
        SET 
            status = 'failed',
            error_message = COALESCE(error_message, '') || 
                ' [AUTO-FAILOVER: Marked failed due to heartbeat timeout at ' || 
                NOW()::text || ']',
            metadata = COALESCE(metadata, '{{}}'::jsonb) || 
                jsonb_build_object(
                    'failed_at', NOW()::text,
                    'failure_reason', 'heartbeat_timeout'
                )
        WHERE component = '{component}'
        RETURNING id, component, status;
    """
    
    result = _execute_query(query)
    
    if result.get("rowCount", 0) > 0:
        logger.info("Marked worker '%s' as failed", component)
        return True
    
    logger.warning("No worker found with component '%s' to mark as failed", component)
    return False


def reassign_tasks_from_worker(
    failed_worker: str,
    target_worker: Optional[str] = None
) -> tuple[int, list[dict]]:
    """
    Reassign all in-progress tasks from a failed worker.
    
    Tasks are reset to 'pending' status so they can be claimed by any available worker.
    The original assignment is recorded in metadata for audit.
    
    Args:
        failed_worker: The worker name whose tasks should be reassigned
        target_worker: Optional specific worker to assign to. If None, tasks
                      are reset to pending for any worker to claim.
    
    Returns:
        Tuple of (count of reassigned tasks, list of task details)
    """
    # Build the target assignment
    if target_worker:
        new_assignment = f"'{target_worker}'"
        new_status = "'in_progress'"
    else:
        new_assignment = "NULL"
        new_status = "'pending'"
    
    query = f"""
        UPDATE governance_tasks
        SET 
            status = {new_status},
            assigned_worker = {new_assignment},
            started_at = NULL,
            metadata = COALESCE(metadata, '{{}}'::jsonb) || 
                jsonb_build_object(
                    'reassigned_from', '{failed_worker}',
                    'reassigned_at', NOW()::text,
                    'reassigned_reason', 'worker_failure'
                )
        WHERE assigned_worker LIKE '{failed_worker}%'
          AND status = 'in_progress'
        RETURNING id, title, priority, task_type, 
                  metadata->>'reassigned_from' as previous_worker;
    """
    
    result = _execute_query(query)
    
    reassigned_tasks = []
    for row in result.get("rows", []):
        reassigned_tasks.append({
            "id": row.get("id"),
            "title": row.get("title"),
            "priority": row.get("priority"),
            "task_type": row.get("task_type"),
            "previous_worker": row.get("previous_worker")
        })
    
    count = result.get("rowCount", 0)
    
    if count > 0:
        logger.info(
            "Reassigned %d tasks from failed worker '%s'", 
            count, 
            failed_worker
        )
    
    return count, reassigned_tasks


def process_failover() -> dict:
    """
    Main failover processing function. Run this periodically from the engine loop.
    
    This function:
    1. Detects workers that have failed
    2. Marks them as failed in health_checks
    3. Reassigns their tasks
    4. Returns a summary for alerting
    
    Returns:
        Dict with failover processing results:
        {
            'failed_workers': list of detected failed workers,
            'workers_marked_failed': count of workers marked as failed,
            'tasks_reassigned': total count of tasks reassigned,
            'reassignment_details': list of task reassignment details
        }
    """
    result = {
        "failed_workers": [],
        "workers_marked_failed": 0,
        "tasks_reassigned": 0,
        "reassignment_details": []
    }
    
    # Step 1: Detect failed workers
    failed_workers = detect_failed_workers()
    result["failed_workers"] = failed_workers
    
    if not failed_workers:
        logger.debug("No failed workers detected")
        return result
    
    logger.warning(
        "Detected %d failed worker(s): %s",
        len(failed_workers),
        [w.get("component") for w in failed_workers]
    )
    
    # Step 2: Process each failed worker
    for worker in failed_workers:
        component = worker.get("component")
        if not component:
            continue
        
        # Mark as failed
        if mark_worker_failed(component):
            result["workers_marked_failed"] += 1
        
        # Reassign tasks
        count, tasks = reassign_tasks_from_worker(component)
        result["tasks_reassigned"] += count
        result["reassignment_details"].extend(tasks)
    
    return result


def record_worker_heartbeat(
    component: str,
    check_type: str = "heartbeat",
    response_time_ms: int = 0,
    metadata: Optional[dict] = None
) -> bool:
    """
    Record a worker heartbeat to indicate the worker is alive.
    
    Workers should call this periodically to avoid being marked as failed.
    
    Args:
        component: The worker/component name
        check_type: Type of health check (default: 'heartbeat')
        response_time_ms: Response time in milliseconds
        metadata: Optional additional metadata
        
    Returns:
        True if heartbeat was recorded successfully
    """
    metadata_json = json.dumps(metadata) if metadata else "{}"
    
    query = f"""
        INSERT INTO health_checks (
            id, component, check_type, status, 
            response_time_ms, last_check_at, consecutive_failures, metadata
        )
        VALUES (
            gen_random_uuid(), '{component}', '{check_type}', 'healthy',
            {response_time_ms}, NOW(), 0, '{metadata_json}'::jsonb
        )
        ON CONFLICT (component, check_type) 
        DO UPDATE SET
            status = 'healthy',
            response_time_ms = EXCLUDED.response_time_ms,
            last_check_at = NOW(),
            consecutive_failures = 0,
            metadata = EXCLUDED.metadata
        RETURNING id;
    """
    
    try:
        result = _execute_query(query)
        return result.get("rowCount", 0) > 0
    except (URLError, HTTPError) as e:
        logger.error("Failed to record heartbeat for '%s': %s", component, e)
        return False


def get_worker_health_status() -> list[dict]:
    """
    Get current health status of all workers.
    
    Returns:
        List of worker health status dicts
    """
    query = """
        SELECT 
            component,
            check_type,
            status,
            response_time_ms,
            last_check_at,
            consecutive_failures,
            error_message,
            CASE 
                WHEN status = 'failed' THEN 'FAILED'
                WHEN last_check_at < NOW() - INTERVAL '5 minutes' THEN 'STALE'
                WHEN consecutive_failures > 0 THEN 'DEGRADED'
                ELSE 'HEALTHY'
            END as health_status
        FROM health_checks
        ORDER BY 
            CASE status WHEN 'failed' THEN 0 ELSE 1 END,
            last_check_at DESC;
    """
    
    result = _execute_query(query)
    
    workers = []
    for row in result.get("rows", []):
        workers.append({
            "component": row.get("component"),
            "check_type": row.get("check_type"),
            "status": row.get("status"),
            "health_status": row.get("health_status"),
            "response_time_ms": row.get("response_time_ms"),
            "last_check_at": row.get("last_check_at"),
            "consecutive_failures": row.get("consecutive_failures"),
            "error_message": row.get("error_message")
        })
    
    return workers


def reset_failed_worker(component: str) -> bool:
    """
    Reset a failed worker back to healthy status.
    
    Use this when a worker has been fixed and is ready to resume work.
    
    Args:
        component: The worker/component name to reset
        
    Returns:
        True if worker was reset successfully
    """
    query = f"""
        UPDATE health_checks
        SET 
            status = 'healthy',
            consecutive_failures = 0,
            error_message = NULL,
            last_check_at = NOW(),
            metadata = COALESCE(metadata, '{{}}'::jsonb) || 
                jsonb_build_object(
                    'reset_at', NOW()::text,
                    'reset_reason', 'manual_recovery'
                )
        WHERE component = '{component}'
          AND status = 'failed'
        RETURNING id, component;
    """
    
    result = _execute_query(query)
    
    if result.get("rowCount", 0) > 0:
        logger.info("Reset failed worker '%s' to healthy", component)
        return True
    
    return False


# Convenience exports
__all__ = [
    "detect_failed_workers",
    "mark_worker_failed", 
    "reassign_tasks_from_worker",
    "process_failover",
    "record_worker_heartbeat",
    "get_worker_health_status",
    "reset_failed_worker",
    "FAILURE_THRESHOLD_MINUTES",
    "MAX_CONSECUTIVE_FAILURES"
]
