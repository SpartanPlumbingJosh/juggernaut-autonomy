"""
JUGGERNAUT LEARNING CAPTURE MODULE
==================================
Extracts and stores learnings from completed task executions.

MED-02: Every completed task should extract learnings including:
- What worked
- What failed  
- Duration
- Key insights

Learnings are stored in the learnings table for future reference.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import os

# Database configuration (from environment)
DATABASE_URL = os.getenv("DATABASE_URL")
NEON_ENDPOINT = os.getenv(
    "NEON_ENDPOINT",
    "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
)


def _execute_sql(sql: str) -> Dict[str, Any]:
    """Execute SQL via Neon HTTP API."""
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": DATABASE_URL
    }
    
    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"[ERROR] SQL Error: {error_body}")
        raise
    except Exception as e:
        print(f"[ERROR] SQL Exception: {str(e)}")
        raise


def _escape_value(value: Any) -> str:
    """Escape a value for SQL insertion."""
    if value is None:
        return "NULL"
    elif isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, (dict, list)):
        json_str = json.dumps(value)
        escaped = json_str.replace("\\", "\\\\").replace("'", "''").replace("\x00", "")
        return f"'{escaped}'"
    else:
        s = str(value)
        escaped = s.replace("\\", "\\\\").replace("'", "''").replace("\x00", "")
        return f"'{escaped}'"


def extract_learning_from_task(
    task_id: str,
    task_title: str,
    task_type: str,
    status: str,
    worker_id: str,
    duration_ms: Optional[int] = None,
    error_message: Optional[str] = None,
    result_data: Optional[Dict] = None,
    goal_id: Optional[str] = None
) -> Optional[str]:
    """
    Extract and store a learning from a completed (or failed) task.
    
    Args:
        task_id: UUID of the completed task
        task_title: Title of the task
        task_type: Type of task (code, verification, etc.)
        status: Final status (completed, failed)
        worker_id: ID of the worker that executed the task
        duration_ms: How long the task took in milliseconds
        error_message: Error message if task failed
        result_data: Any result data from task execution
        goal_id: Optional goal ID this task belongs to
    
    Returns:
        UUID of the created learning, or None if failed
    """
    now = datetime.now(timezone.utc).isoformat()
    
    # Determine category based on outcome
    if status == "completed":
        category = "success"
        confidence = 0.8
    elif status == "failed":
        category = "failure"
        confidence = 0.9  # Failures are often clearer learnings
    else:
        category = "observation"
        confidence = 0.5
    
    # Build summary
    if status == "completed":
        summary = f"Task '{task_title}' completed successfully"
        if duration_ms:
            summary += f" in {duration_ms/1000:.1f}s"
    elif status == "failed":
        summary = f"Task '{task_title}' failed"
        if error_message:
            # Truncate long error messages
            error_preview = error_message[:200] + "..." if len(error_message) > 200 else error_message
            summary += f": {error_preview}"
    else:
        summary = f"Task '{task_title}' ended with status: {status}"
    
    # Build details JSON
    details = {
        "task_type": task_type,
        "status": status,
        "duration_ms": duration_ms,
        "timestamp": now
    }
    
    if error_message:
        details["error"] = error_message
    if result_data:
        # Limit result data size
        details["result_preview"] = str(result_data)[:500]
    
    # Determine what worked/failed
    if status == "completed":
        details["what_worked"] = f"Execution of {task_type} task succeeded"
    elif status == "failed":
        details["what_failed"] = error_message or "Unknown error"
    
    # Store the learning
    return store_learning(
        worker_id=worker_id,
        task_id=task_id,
        goal_id=goal_id,
        category=category,
        summary=summary,
        details=details,
        confidence=confidence
    )


def store_learning(
    worker_id: str,
    category: str,
    summary: str,
    details: Optional[Dict] = None,
    task_id: Optional[str] = None,
    goal_id: Optional[str] = None,
    evidence_task_ids: Optional[List[str]] = None,
    confidence: float = 0.7
) -> Optional[str]:
    """
    Store a learning in the database.
    
    Args:
        worker_id: ID of the worker recording this learning
        category: Category (success, failure, observation, pattern, improvement)
        summary: Brief summary of the learning
        details: Additional details as JSON
        task_id: Related task ID if applicable
        goal_id: Related goal ID if applicable
        evidence_task_ids: List of task IDs that support this learning
        confidence: Confidence score 0.0-1.0
    
    Returns:
        UUID of created learning, or None if failed
    """
    now = datetime.now(timezone.utc).isoformat()
    
    # Build columns and values
    cols = ["worker_id", "category", "summary", "confidence", "applied_count", 
            "is_validated", "created_at", "updated_at"]
    vals = [
        _escape_value(worker_id),
        _escape_value(category),
        _escape_value(summary),
        str(confidence),
        "0",
        "FALSE",
        _escape_value(now),
        _escape_value(now)
    ]
    
    if task_id:
        cols.append("task_id")
        vals.append(_escape_value(task_id))
    
    if goal_id:
        cols.append("goal_id")
        vals.append(_escape_value(goal_id))
    
    if details:
        cols.append("details")
        vals.append(_escape_value(details))
    
    if evidence_task_ids:
        cols.append("evidence_task_ids")
        vals.append(_escape_value(evidence_task_ids))
    
    sql = f"""
        INSERT INTO learnings ({', '.join(cols)})
        VALUES ({', '.join(vals)})
        RETURNING id
    """
    
    try:
        result = _execute_sql(sql)
        rows = result.get("rows", [])
        if rows:
            learning_id = rows[0].get("id")
            print(f"[LEARNING] Stored learning {learning_id}: {summary[:50]}...")
            return learning_id
        return None
    except Exception as e:
        print(f"[ERROR] Failed to store learning: {e}")
        return None


def get_learnings(
    category: Optional[str] = None,
    task_type: Optional[str] = None,
    worker_id: Optional[str] = None,
    limit: int = 20,
    min_confidence: float = 0.0
) -> List[Dict]:
    """
    Retrieve learnings from the database.
    
    Args:
        category: Filter by category (success, failure, etc.)
        task_type: Filter by task type in details
        worker_id: Filter by worker
        limit: Maximum number of results
        min_confidence: Minimum confidence score
    
    Returns:
        List of learning records
    """
    conditions = [f"confidence >= {min_confidence}"]
    
    if category:
        conditions.append(f"category = {_escape_value(category)}")
    if worker_id:
        conditions.append(f"worker_id = {_escape_value(worker_id)}")
    if task_type:
        conditions.append(f"details->>'task_type' = {_escape_value(task_type)}")
    
    where_clause = " AND ".join(conditions)
    
    sql = f"""
        SELECT id, worker_id, task_id, goal_id, category, summary, 
               details, confidence, applied_count, created_at
        FROM learnings
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT {limit}
    """
    
    try:
        result = _execute_sql(sql)
        return result.get("rows", [])
    except Exception as e:
        print(f"[ERROR] Failed to get learnings: {e}")
        return []


def get_relevant_learnings_for_task(
    task_type: str,
    limit: int = 5
) -> List[Dict]:
    """
    Get learnings relevant to a specific task type.
    Useful for informing future task execution with past experience.
    
    Args:
        task_type: The type of task to find learnings for
        limit: Maximum number of learnings to return
    
    Returns:
        List of relevant learning records
    """
    sql = f"""
        SELECT id, category, summary, details, confidence
        FROM learnings
        WHERE details->>'task_type' = {_escape_value(task_type)}
          AND confidence >= 0.6
        ORDER BY 
            CASE category 
                WHEN 'failure' THEN 1  -- Failures first (avoid repeating)
                WHEN 'success' THEN 2  -- Then successes
                ELSE 3 
            END,
            confidence DESC,
            created_at DESC
        LIMIT {limit}
    """
    
    try:
        result = _execute_sql(sql)
        return result.get("rows", [])
    except Exception as e:
        print(f"[ERROR] Failed to get relevant learnings: {e}")
        return []


def increment_learning_applied(learning_id: str) -> bool:
    """
    Increment the applied_count for a learning when it's used.
    
    Args:
        learning_id: UUID of the learning
    
    Returns:
        True if updated, False otherwise
    """
    sql = f"""
        UPDATE learnings
        SET applied_count = applied_count + 1,
            updated_at = NOW()
        WHERE id = {_escape_value(learning_id)}
    """
    
    try:
        result = _execute_sql(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        print(f"[ERROR] Failed to increment learning applied count: {e}")
        return False


def get_learning_stats() -> Dict[str, Any]:
    """
    Get statistics about stored learnings.
    
    Returns:
        Dictionary with learning statistics
    """
    sql = """
        SELECT 
            COUNT(*) as total_learnings,
            COUNT(CASE WHEN category = 'success' THEN 1 END) as successes,
            COUNT(CASE WHEN category = 'failure' THEN 1 END) as failures,
            COUNT(CASE WHEN category = 'observation' THEN 1 END) as observations,
            AVG(confidence) as avg_confidence,
            SUM(applied_count) as total_applications
        FROM learnings
    """
    
    try:
        result = _execute_sql(sql)
        rows = result.get("rows", [])
        if rows:
            return rows[0]
        return {}
    except Exception as e:
        print(f"[ERROR] Failed to get learning stats: {e}")
        return {}
