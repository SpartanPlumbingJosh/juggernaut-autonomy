"""
JUGGERNAUT Learning Capture System
===================================
MED-02: Extracts and saves learnings from completed task execution.

Every completed task should generate learnings that include:
- What worked (success patterns)
- What failed (error patterns)
- Duration and performance metrics
- Confidence in the learning

This enables the system to improve over time by learning from experience.
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum


# Database configuration
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
NEON_CONNECTION_STRING = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_OYkCRU4aze2l@ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
)


class LearningCategory(Enum):
    """Categories of learnings that can be captured."""
    SUCCESS_PATTERN = "success_pattern"      # What worked well
    FAILURE_PATTERN = "failure_pattern"      # What didn't work
    PERFORMANCE = "performance"              # Speed/efficiency insights
    BEST_PRACTICE = "best_practice"          # Recommended approaches
    WORKAROUND = "workaround"                # Solutions to problems
    DEPENDENCY = "dependency"                # Task dependency insights
    RESOURCE_USAGE = "resource_usage"        # Cost/resource insights


def _execute_sql(sql: str) -> Dict[str, Any]:
    """Execute SQL via Neon HTTP API."""
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": NEON_CONNECTION_STRING
    }
    
    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        raise Exception(f"SQL Error: {error_body}")
    except Exception as e:
        raise Exception(f"SQL Exception: {str(e)}")


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


def save_learning(
    category: str,
    summary: str,
    worker_id: str = None,
    goal_id: str = None,
    task_id: str = None,
    details: Dict = None,
    evidence_task_ids: List[str] = None,
    confidence: float = 0.7
) -> Optional[str]:
    """
    Save a learning to the learnings table.
    
    Args:
        category: Type of learning (use LearningCategory enum values)
        summary: Brief description of the learning (required)
        worker_id: Which worker generated this learning
        goal_id: Associated goal UUID
        task_id: Associated task UUID
        details: JSON with additional context (what_worked, what_failed, duration_ms, etc.)
        evidence_task_ids: List of task IDs that support this learning
        confidence: 0.0-1.0 confidence score (default 0.7)
    
    Returns:
        Learning UUID or None on failure
    """
    now = datetime.now(timezone.utc).isoformat()
    
    cols = ["category", "summary", "confidence", "created_at", "updated_at"]
    vals = [
        _escape_value(category),
        _escape_value(summary),
        str(confidence),
        _escape_value(now),
        _escape_value(now)
    ]
    
    if worker_id:
        cols.append("worker_id")
        vals.append(_escape_value(worker_id))
    if goal_id:
        cols.append("goal_id")
        vals.append(_escape_value(goal_id))
    if task_id:
        cols.append("task_id")
        vals.append(_escape_value(task_id))
    if details:
        cols.append("details")
        vals.append(_escape_value(details))
    if evidence_task_ids:
        cols.append("evidence_task_ids")
        vals.append(_escape_value(evidence_task_ids))
    
    sql = f"INSERT INTO learnings ({', '.join(cols)}) VALUES ({', '.join(vals)}) RETURNING id"
    
    try:
        result = _execute_sql(sql)
        rows = result.get("rows", [])
        if rows:
            return rows[0].get("id")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to save learning: {e}")
        return None


def extract_learnings_from_task(
    task_id: str,
    task_title: str,
    task_type: str,
    status: str,
    worker_id: str,
    started_at: str = None,
    completed_at: str = None,
    error_message: str = None,
    execution_result: Dict = None,
    goal_id: str = None
) -> List[str]:
    """
    Extract learnings from a completed or failed task.
    
    This function analyzes the task execution and generates appropriate learnings
    based on whether the task succeeded, failed, or had notable characteristics.
    
    Args:
        task_id: UUID of the task
        task_title: Title/name of the task
        task_type: Type of task (e.g., 'code', 'research', 'verification')
        status: Final status ('completed' or 'failed')
        worker_id: Who executed the task
        started_at: When task started (ISO timestamp)
        completed_at: When task finished (ISO timestamp)
        error_message: Error message if task failed
        execution_result: Dict with execution details
        goal_id: Associated goal UUID
    
    Returns:
        List of learning UUIDs that were created
    """
    learning_ids = []
    
    # Calculate duration if timestamps available
    duration_ms = None
    if started_at and completed_at:
        try:
            start = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            end = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
            duration_ms = int((end - start).total_seconds() * 1000)
        except (ValueError, TypeError):
            pass
    
    if status == "completed":
        # Success learning
        details = {
            "what_worked": f"Task '{task_title}' completed successfully",
            "task_type": task_type,
            "duration_ms": duration_ms
        }
        if execution_result:
            details["execution_result"] = execution_result
        
        learning_id = save_learning(
            category=LearningCategory.SUCCESS_PATTERN.value,
            summary=f"Successfully completed {task_type} task: {task_title[:100]}",
            worker_id=worker_id,
            task_id=task_id,
            goal_id=goal_id,
            details=details,
            evidence_task_ids=[task_id],
            confidence=0.8
        )
        if learning_id:
            learning_ids.append(learning_id)
        
        # Performance learning if duration is available
        if duration_ms is not None:
            perf_details = {
                "task_type": task_type,
                "duration_ms": duration_ms,
                "duration_readable": _format_duration(duration_ms)
            }
            
            # Determine if this was fast, normal, or slow based on task type
            perf_assessment = _assess_performance(task_type, duration_ms)
            if perf_assessment:
                perf_details["assessment"] = perf_assessment
                
                perf_learning_id = save_learning(
                    category=LearningCategory.PERFORMANCE.value,
                    summary=f"{task_type} task took {_format_duration(duration_ms)} ({perf_assessment})",
                    worker_id=worker_id,
                    task_id=task_id,
                    goal_id=goal_id,
                    details=perf_details,
                    evidence_task_ids=[task_id],
                    confidence=0.7
                )
                if perf_learning_id:
                    learning_ids.append(perf_learning_id)
    
    elif status == "failed":
        # Failure learning
        details = {
            "what_failed": f"Task '{task_title}' failed",
            "task_type": task_type,
            "error_message": error_message,
            "duration_ms": duration_ms
        }
        if execution_result:
            details["execution_result"] = execution_result
        
        learning_id = save_learning(
            category=LearningCategory.FAILURE_PATTERN.value,
            summary=f"Failed {task_type} task: {error_message[:100] if error_message else 'Unknown error'}",
            worker_id=worker_id,
            task_id=task_id,
            goal_id=goal_id,
            details=details,
            evidence_task_ids=[task_id],
            confidence=0.75
        )
        if learning_id:
            learning_ids.append(learning_id)
    
    return learning_ids


def _format_duration(ms: int) -> str:
    """Format duration in milliseconds to human-readable string."""
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    elif ms < 3600000:
        return f"{ms / 60000:.1f}m"
    else:
        return f"{ms / 3600000:.1f}h"


def _assess_performance(task_type: str, duration_ms: int) -> Optional[str]:
    """
    Assess performance based on task type and duration.
    Returns a performance assessment string or None if not assessable.
    """
    # Expected durations by task type (in milliseconds)
    # These are initial estimates and should be refined based on actual data
    EXPECTED_DURATIONS = {
        "code": 300000,          # 5 minutes
        "research": 600000,      # 10 minutes
        "verification": 120000,  # 2 minutes
        "bug": 180000,           # 3 minutes
        "documentation": 240000, # 4 minutes
        "default": 300000        # 5 minutes default
    }
    
    expected = EXPECTED_DURATIONS.get(task_type, EXPECTED_DURATIONS["default"])
    ratio = duration_ms / expected
    
    if ratio < 0.5:
        return "very_fast"
    elif ratio < 0.8:
        return "fast"
    elif ratio < 1.2:
        return "normal"
    elif ratio < 2.0:
        return "slow"
    else:
        return "very_slow"


def get_learnings(
    category: str = None,
    task_id: str = None,
    worker_id: str = None,
    limit: int = 50,
    min_confidence: float = None
) -> List[Dict]:
    """
    Retrieve learnings from the database.
    
    Args:
        category: Filter by category
        task_id: Filter by associated task
        worker_id: Filter by worker who generated
        limit: Max results to return
        min_confidence: Minimum confidence score
    
    Returns:
        List of learning records
    """
    conditions = []
    if category:
        conditions.append(f"category = {_escape_value(category)}")
    if task_id:
        conditions.append(f"task_id = {_escape_value(task_id)}")
    if worker_id:
        conditions.append(f"worker_id = {_escape_value(worker_id)}")
    if min_confidence is not None:
        conditions.append(f"confidence >= {min_confidence}")
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
        SELECT id, category, summary, worker_id, task_id, goal_id, 
               details, confidence, applied_count, effectiveness_score,
               is_validated, created_at
        FROM learnings 
        {where}
        ORDER BY created_at DESC 
        LIMIT {limit}
    """
    
    try:
        result = _execute_sql(sql)
        return result.get("rows", [])
    except Exception as e:
        print(f"[ERROR] Failed to get learnings: {e}")
        return []


def get_learning_stats() -> Dict[str, Any]:
    """
    Get statistics about learnings.
    
    Returns:
        Dict with learning counts by category, confidence distribution, etc.
    """
    sql = """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN category = 'success_pattern' THEN 1 END) as success_patterns,
            COUNT(CASE WHEN category = 'failure_pattern' THEN 1 END) as failure_patterns,
            COUNT(CASE WHEN category = 'performance' THEN 1 END) as performance_insights,
            COUNT(CASE WHEN is_validated = true THEN 1 END) as validated,
            AVG(confidence) as avg_confidence
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


def apply_learning(learning_id: str) -> bool:
    """
    Mark a learning as applied (increment applied_count).
    
    Args:
        learning_id: UUID of the learning
    
    Returns:
        True if successful, False otherwise
    """
    now = datetime.now(timezone.utc).isoformat()
    sql = f"""
        UPDATE learnings 
        SET applied_count = COALESCE(applied_count, 0) + 1,
            updated_at = {_escape_value(now)}
        WHERE id = {_escape_value(learning_id)}
    """
    
    try:
        result = _execute_sql(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        print(f"[ERROR] Failed to apply learning: {e}")
        return False


def validate_learning(learning_id: str, validator: str, is_valid: bool = True) -> bool:
    """
    Validate or invalidate a learning.
    
    Args:
        learning_id: UUID of the learning
        validator: Who validated (e.g., 'JOSH', 'ORCHESTRATOR')
        is_valid: Whether the learning is valid
    
    Returns:
        True if successful, False otherwise
    """
    now = datetime.now(timezone.utc).isoformat()
    sql = f"""
        UPDATE learnings 
        SET is_validated = {_escape_value(is_valid)},
            validated_by = {_escape_value(validator)},
            updated_at = {_escape_value(now)}
        WHERE id = {_escape_value(learning_id)}
    """
    
    try:
        result = _execute_sql(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        print(f"[ERROR] Failed to validate learning: {e}")
        return False
