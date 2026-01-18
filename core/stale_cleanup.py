"""
Stale Task Cleanup Module
=========================

Finds tasks stuck in_progress for too long and resets them.
With multiple Claude chats working as workers, tasks get abandoned
when chats end. This module provides auto-cleanup.
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, List

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
NEON_ENDPOINT = os.getenv(
    "NEON_ENDPOINT",
    "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
)

# Default: 30 minutes threshold for stale tasks
STALE_THRESHOLD_MINUTES = int(os.getenv("STALE_THRESHOLD_MINUTES", "30"))


def execute_sql(sql: str) -> Dict[str, Any]:
    """Execute SQL via Neon HTTP API."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is required")
    
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": DATABASE_URL
    }
    
    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
    
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def reset_stale_tasks(threshold_minutes: int = None) -> Tuple[int, List[Dict]]:
    """
    Find and reset tasks that have been stuck in 'in_progress' too long.
    
    Args:
        threshold_minutes: Minutes after which a task is considered stale.
                          Defaults to STALE_THRESHOLD_MINUTES (30 min).
    
    Returns:
        Tuple of (count_reset, list_of_reset_tasks)
        
    Behavior:
        1. Finds tasks with status='in_progress' and started_at > X minutes ago
        2. Resets them to status='pending'
        3. Clears assigned_worker so any worker can claim
        4. Adds metadata with stale_reset timestamp for tracing
    """
    if threshold_minutes is None:
        threshold_minutes = STALE_THRESHOLD_MINUTES
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Step 1: Find stale tasks (for logging/reporting)
    find_sql = f"""
    SELECT id, title, assigned_worker, started_at
    FROM governance_tasks
    WHERE status = 'in_progress'
      AND started_at < NOW() - INTERVAL '{threshold_minutes} minutes'
    """
    
    try:
        find_result = execute_sql(find_sql)
        stale_tasks = find_result.get("rows", [])
    except Exception as e:
        print(f"[STALE_CLEANUP] Error finding stale tasks: {e}")
        return 0, []
    
    if not stale_tasks:
        return 0, []
    
    # Step 2: Reset stale tasks
    # Using jsonb_set to preserve existing metadata and add stale_reset info
    reset_sql = f"""
    UPDATE governance_tasks
    SET 
        status = 'pending',
        assigned_worker = NULL,
        started_at = NULL,
        metadata = COALESCE(metadata, '{{}}'::jsonb) || jsonb_build_object(
            'stale_reset_at', '{now}',
            'stale_reset_reason', 'Task stuck in_progress > {threshold_minutes} minutes'
        )
    WHERE status = 'in_progress'
      AND started_at < NOW() - INTERVAL '{threshold_minutes} minutes'
    RETURNING id, title
    """
    
    try:
        reset_result = execute_sql(reset_sql)
        reset_count = reset_result.get("rowCount", 0)
        reset_tasks = reset_result.get("rows", [])
        
        if reset_count > 0:
            print(f"[STALE_CLEANUP] Reset {reset_count} stale task(s):")
            for task in reset_tasks:
                print(f"  - {task.get('id')}:  {task.get('title')}")
        
        return reset_count, reset_tasks
        
    except Exception as e:
        print(f"[STALE_CLEANUP] Error resetting stale tasks: {e}")
        return 0, []


def get_stale_task_count(threshold_minutes: int = None) -> int:
    """
    Get count of currently stale tasks (without resetting them).
    Useful for monitoring/dashboards.
    """
    if threshold_minutes is None:
        threshold_minutes = STALE_THRESHOLD_MINUTES
    
    count_sql = f"""
    SELECT COUNT(*) as stale_count
    FROM governance_tasks
    WHERE status = 'in_progress'
      AND started_at < NOW() - INTERVAL '{threshold_minutes} minutes'
    """
    
    try:
        result = execute_sql(count_sql)
        rows = result.get("rows", [])
        if rows:
            return int(rows[0].get("stale_count", 0))
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    # Test the stale task cleanup directly
    print("Stale Task Cleanup Test")
    print("=" * 40)
    
    # Check how many stale tasks exist
    stale_count = get_stale_task_count()
    print(f"Current stale tasks:  {stale_count}")
    
    # Reset them
    reset_count, reset_tasks = reset_stale_tasks()
    print(f"Reset {reset_count} stale task(s)")
