"""Stale Task Cleanup Module

Automatically detects and resets tasks that have been stuck in 'in_progress'
status for too long, making them available for other workers to pick up.
"""

import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any

# Configuration
DEFAULT_STALE_THRESHOLD_MINUTES = 30
NEON_ENDPOINT = os.getenv("NEON_ENDPOINT", "")
NEON_CONNECTION_STRING = os.getenv(
    "DATABASE_URL",
    ""
)

# Logger setup
logger = logging.getLogger(__name__)


def _validate_threshold(threshold_minutes: int | None) -> int:
    """Validate and normalize threshold_minutes parameter.
    
    Args:
        threshold_minutes: Minutes threshold or None for default
        
    Returns:
        Validated positive integer threshold
        
    Raises:
        ValueError: If threshold is not a positive integer
    """
    if threshold_minutes is None:
        threshold_minutes = os.getenv(
            "STALE_THRESHOLD_MINUTES", str(DEFAULT_STALE_THRESHOLD_MINUTES)
        )
    try:
        threshold_minutes = int(threshold_minutes)
    except (TypeError, ValueError) as e:
        raise ValueError("threshold_minutes must be a positive integer") from e
    if threshold_minutes <= 0:
        raise ValueError("threshold_minutes must be a positive integer")
    return threshold_minutes


def execute_sql(sql: str) -> dict[str, Any]:
    """Execute SQL against Neon database via HTTP API.
    
    Args:
        sql: SQL query to execute
        
    Returns:
        Dictionary with query results including 'rows' and 'rowCount'
        
    Raises:
        ValueError: If NEON_ENDPOINT is not configured or has invalid scheme
        Exception: If database query fails
    """
    if not NEON_ENDPOINT:
        raise ValueError(
            "NEON_ENDPOINT environment variable is not set. "
            "Please configure it with your Neon database HTTP endpoint."
        )
    
    # Validate URL scheme is HTTPS
    parsed = urllib.parse.urlparse(NEON_ENDPOINT)
    if parsed.scheme != "https":
        raise ValueError(
            f"NEON_ENDPOINT must use HTTPS scheme, got: {parsed.scheme}. "
            "Refusing to connect over insecure protocol."
        )
    
    if not NEON_CONNECTION_STRING:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Please configure it with your Neon connection string."
        )
    
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": NEON_CONNECTION_STRING
    }
    
    data = json.dumps({"query": sql}).encode("utf-8")
    req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers)
    
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result


def reset_stale_tasks(threshold_minutes: int | None = None) -> tuple[int, list[dict[str, Any]]]:
    """Find and reset tasks stuck in 'in_progress' status.
    
    Uses a single atomic UPDATE with RETURNING to avoid race conditions.
    Captures previous assigned_worker and started_at values before clearing.
    
    Args:
        threshold_minutes: Minutes after which a task is considered stale.
                          Defaults to STALE_THRESHOLD_MINUTES env var or 30.
    
    Returns:
        Tuple of (count of reset tasks, list of reset task details)
        
    Raises:
        ValueError: If threshold_minutes is not a positive integer
    """
    threshold_minutes = _validate_threshold(threshold_minutes)
    
    # Single atomic UPDATE with RETURNING to avoid TOCTOU race
    # Capture previous values before clearing by embedding in metadata
    reset_sql = f"""
        UPDATE governance_tasks
        SET 
            status = 'pending',
            assigned_worker = NULL,
            started_at = NULL,
            metadata = COALESCE(metadata, '{{}}'::jsonb) || jsonb_build_object(
                'stale_reset_at', NOW()::text,
                'stale_reset_reason', 'Task exceeded {threshold_minutes} minute threshold',
                'previous_assigned_worker', assigned_worker,
                'previous_started_at', started_at::text
            )
        WHERE status = 'in_progress'
          AND started_at < NOW() - INTERVAL '{threshold_minutes} minutes'
        RETURNING id, title, task_type, 
                  (metadata->>'previous_assigned_worker') as previous_worker,
                  (metadata->>'previous_started_at') as previous_started;
    """
    
    try:
        result = execute_sql(reset_sql)
        reset_tasks = result.get("rows", [])
        reset_count = result.get("rowCount", len(reset_tasks))
        
        if reset_count > 0:
            logger.info(f"Reset {reset_count} stale tasks: {[t.get('id') for t in reset_tasks]}")
            for task in reset_tasks:
                logger.info(
                    f"  - {task.get('id')}: {task.get('title')} "
                    f"(was assigned to {task.get('previous_worker')})"
                )
        else:
            logger.debug("No stale tasks found to reset")
            
        return reset_count, reset_tasks
        
    except Exception as e:
        logger.error(f"Failed to reset stale tasks: {e}", exc_info=True)
        raise


def get_stale_task_count(threshold_minutes: int | None = None) -> int:
    """Get count of currently stale tasks without resetting them.
    
    Useful for monitoring/alerting on stale task buildup.
    
    Args:
        threshold_minutes: Minutes after which a task is considered stale.
                          Defaults to STALE_THRESHOLD_MINUTES env var or 30.
    
    Returns:
        Number of stale tasks, or -1 if query fails (error is logged)
        
    Raises:
        ValueError: If threshold_minutes is not a positive integer
    """
    threshold_minutes = _validate_threshold(threshold_minutes)
    
    count_sql = f"""
        SELECT COUNT(*) as stale_count
        FROM governance_tasks
        WHERE status = 'in_progress'
          AND started_at < NOW() - INTERVAL '{threshold_minutes} minutes';
    """
    
    try:
        result = execute_sql(count_sql)
        rows = result.get("rows", [])
        if rows:
            return int(rows[0].get("stale_count", 0))
        return 0
    except Exception as e:
        logger.error(
            f"Failed to get stale task count: {e}",
            exc_info=True
        )
        return -1  # Sentinel value indicating error


if __name__ == "__main__":
    # Enable logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    print("Checking for stale tasks...")
    count = get_stale_task_count()
    if count == -1:
        print("Error checking stale task count - see logs")
    else:
        print(f"Found {count} stale task(s)")
    
    if count > 0:
        print("Resetting stale tasks...")
        reset_count, reset_tasks = reset_stale_tasks()
        print(f"Reset {reset_count} task(s)")
