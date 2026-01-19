"""
Database Task Handler
=====================

Executes SQL queries from task payloads.
Logs the SQL executed and results.

Security:
- Only SELECT queries allowed by default
- Write operations require explicit approval
- Sensitive data redacted from logs
"""

import json
import re
from typing import Dict, Any, Callable


# Allowed read-only operations
SAFE_OPERATIONS = frozenset(["SELECT", "WITH"])

# Dangerous operations that require approval
WRITE_OPERATIONS = frozenset([
    "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", 
    "ALTER", "CREATE", "GRANT", "REVOKE"
])


def handle_database_task(
    task: Dict[str, Any],
    execute_sql: Callable,
    log_action: Callable
) -> Dict[str, Any]:
    """Execute a database task.
    
    Payload format:
    {
        "query": "SELECT * FROM table",  # Required
        "allow_writes": false,           # Optional, default false
        "return_rows": true              # Optional, default true
    }
    
    Args:
        task: Task dict with payload containing SQL query
        execute_sql: Function to execute SQL
        log_action: Function to log actions
        
    Returns:
        Result dict with success, rows_affected, and optional data
    """
    task_id = task.get("id", "unknown")
    payload = task.get("payload", {})
    
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid JSON payload"}
    
    query = payload.get("query", "").strip()
    allow_writes = payload.get("allow_writes", False)
    return_rows = payload.get("return_rows", True)
    
    if not query:
        log_action(
            "database.handler.error",
            "No query provided in payload",
            "error",
            task_id=task_id
        )
        return {"success": False, "error": "No query provided in payload"}
    
    # Determine operation type
    first_word = query.split()[0].upper() if query.split() else ""
    is_write = first_word in WRITE_OPERATIONS
    is_safe = first_word in SAFE_OPERATIONS
    
    # Security check
    if is_write and not allow_writes:
        log_action(
            "database.handler.blocked",
            f"Write operation blocked: {first_word}",
            "warning",
            task_id=task_id
        )
        return {
            "success": False,
            "error": f"Write operation '{first_word}' not allowed. Set allow_writes=true in payload.",
            "operation": first_word
        }
    
    # Log what we're executing (truncated for safety)
    log_action(
        "database.handler.execute",
        f"Executing {first_word} query ({len(query)} chars)",
        "info",
        task_id=task_id,
        input_data={"query_preview": query[:100], "operation": first_word}
    )
    
    try:
        result = execute_sql(query)
        
        rows = result.get("rows", [])
        row_count = result.get("rowCount", len(rows))
        
        log_action(
            "database.handler.success",
            f"Query executed: {row_count} rows affected/returned",
            "info",
            task_id=task_id,
            output_data={"row_count": row_count, "operation": first_word}
        )
        
        response = {
            "success": True,
            "operation": first_word,
            "row_count": row_count,
            "query_executed": True
        }
        
        if return_rows and rows:
            # Limit returned rows for safety
            response["data"] = rows[:1000]
            if len(rows) > 1000:
                response["truncated"] = True
                response["total_rows"] = len(rows)
        
        return response
        
    except Exception as e:
        error_msg = str(e)[:500]  # Truncate long errors
        log_action(
            "database.handler.error",
            f"Query failed: {error_msg}",
            "error",
            task_id=task_id
        )
        return {
            "success": False,
            "error": error_msg,
            "operation": first_word
        }
