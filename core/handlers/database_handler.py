"""
Database Task Handler
=====================
Executes SQL queries from task payload and logs results.
"""

import json
import urllib.request
import urllib.error
import os
from typing import Dict, Any, Tuple
from datetime import datetime, timezone


DATABASE_URL = os.getenv("DATABASE_URL", "")
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
    
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def handle_database_task(task_id: str, payload: Dict[str, Any], log_action_fn) -> Tuple[bool, Dict[str, Any]]:
    """
    Execute SQL from payload.sql or payload.query.
    
    Args:
        task_id: Task identifier for logging
        payload: Task payload containing 'sql' or 'query' key
        log_action_fn: Function to log actions (signature: action, message, level, task_id, **kwargs)
    
    Returns:
        Tuple of (success: bool, result: dict)
    """
    sql = payload.get("sql") or payload.get("query")
    
    if not sql:
        log_action_fn(
            "task.database_handler",
            "No SQL provided in payload (expected 'sql' or 'query' key)",
            level="error",
            task_id=task_id
        )
        return False, {"error": "No SQL provided in payload"}
    
    # Safety: Check for dangerous operations
    sql_upper = sql.upper().strip()
    dangerous_keywords = ["DROP DATABASE", "TRUNCATE", "DELETE FROM" if "WHERE" not in sql_upper else ""]
    for keyword in dangerous_keywords:
        if keyword and keyword in sql_upper:
            log_action_fn(
                "task.database_handler",
                f"Dangerous SQL operation blocked: {keyword}",
                level="warn",
                task_id=task_id
            )
            return False, {"error": f"Dangerous operation blocked: {keyword}"}
    
    try:
        log_action_fn(
            "task.database_executing",
            f"Executing SQL: {sql[:100]}{'...' if len(sql) > 100 else ''}",
            level="info",
            task_id=task_id,
            input_data={"sql_preview": sql[:500]}
        )
        
        result = _execute_sql(sql)
        
        row_count = result.get("rowCount", 0)
        rows = result.get("rows", [])
        command = result.get("command", "UNKNOWN")
        
        log_action_fn(
            "task.database_executed",
            f"SQL executed: {command}, {row_count} rows affected/returned",
            level="info",
            task_id=task_id,
            output_data={
                "command": command,
                "rowCount": row_count,
                "rows_preview": rows[:5] if rows else []  # First 5 rows only
            }
        )
        
        return True, {
            "executed": True,
            "command": command,
            "rowCount": row_count,
            "rows": rows,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        log_action_fn(
            "task.database_error",
            f"SQL HTTP error: {e.code}",
            level="error",
            task_id=task_id,
            error_data={"http_code": e.code, "body": error_body[:500]}
        )
        return False, {"error": f"HTTP {e.code}", "details": error_body[:500]}
        
    except Exception as e:
        log_action_fn(
            "task.database_error",
            f"SQL exception: {str(e)}",
            level="error",
            task_id=task_id,
            error_data={"exception": str(e)}
        )
        return False, {"error": str(e)}
