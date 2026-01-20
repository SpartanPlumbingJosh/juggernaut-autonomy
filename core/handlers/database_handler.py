"""Database handler for executing SQL queries.

This module handles tasks of type 'database' that execute SQL queries
against the database. Read-only queries execute directly; write operations
require approval and return a waiting_approval status.
"""

import logging
from typing import Any, Dict

from .base import BaseHandler, HandlerResult

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
READ_ONLY_STATEMENTS = frozenset({"SELECT", "WITH", "SHOW", "EXPLAIN", "DESCRIBE"})
SQL_PREVIEW_LENGTH = 100
MAX_ROWS_PREVIEW = 5


class DatabaseHandler(BaseHandler):
    """Handler for database task type.
    
    Executes SQL queries from task payloads. Enforces read-only restrictions
    for unapproved queries and logs execution details securely without
    exposing sensitive data.
    """

    task_type = "database"

    def execute(self, task: Dict[str, Any]) -> HandlerResult:
        """Execute a database query task.
        
        Args:
            task: Task dictionary with payload containing 'sql' or 'query' field.
        
        Returns:
            HandlerResult with query results or error information.
        """
        self._execution_logs = []
        task_id = task.get("id")
        payload = task.get("payload", {})

        # Extract SQL query from payload (support both 'sql' and 'query' keys)
        sql_query = payload.get("sql") or payload.get("query")
        
        if not sql_query:
            error_msg = "Database task missing 'sql' or 'query' in payload"
            self._log(
                "handler.database.missing_sql",
                error_msg,
                level="error",
                task_id=task_id
            )
            return HandlerResult(
                success=False,
                data={"expected_fields": ["sql", "query"]},
                error=error_msg,
                logs=self._execution_logs
            )

        # Validate query is not empty after stripping whitespace
        sql_query = sql_query.strip()
        if not sql_query:
            error_msg = "SQL query is empty"
            self._log(
                "handler.database.empty_sql",
                error_msg,
                level="error",
                task_id=task_id
            )
            return HandlerResult(
                success=False,
                data={},
                error=error_msg,
                logs=self._execution_logs
            )

        # Security check: identify statement type
        sql_upper = sql_query.upper()
        tokens = sql_upper.split()
        first_token = tokens[0] if tokens else ""

        # Check if this is a write operation
        if first_token not in READ_ONLY_STATEMENTS:
            self._log(
                "handler.database.write_blocked",
                f"Write operation '{first_token}' requires approval",
                level="warn",
                task_id=task_id,
                output_data={"statement_type": first_token}
            )
            return HandlerResult(
                success=False,
                data={
                    "waiting_approval": True,
                    "statement_type": first_token,
                    "sql_preview": (
                        sql_query[:SQL_PREVIEW_LENGTH] + "..."
                        if len(sql_query) > SQL_PREVIEW_LENGTH
                        else sql_query
                    ),
                    "reason": f"Write operation '{first_token}' requires human approval"
                },
                error=None,
                logs=self._execution_logs
            )

        # Execute the read-only query
        try:
            self._log(
                "handler.database.executing",
                f"Executing {first_token} query ({len(sql_query)} chars)",
                task_id=task_id
            )
            
            query_result = self.execute_sql(sql_query)
            row_count = query_result.get("rowCount", 0)
            rows = query_result.get("rows", [])
            
            result_data = {
                "executed": True,
                "statement_type": first_token,
                "rowCount": row_count,
                "rows_preview": rows[:MAX_ROWS_PREVIEW],
                "sql_length": len(sql_query)
            }
            
            self._log(
                "handler.database.success",
                f"Query executed successfully: {row_count} rows returned",
                task_id=task_id,
                output_data={
                    "rowCount": row_count,
                    "sql_length": len(sql_query)
                }
            )
            
            return HandlerResult(
                success=True,
                data=result_data,
                logs=self._execution_logs
            )

        except Exception as sql_error:
            error_msg = str(sql_error)
            self._log(
                "handler.database.failed",
                f"SQL execution failed: {error_msg[:200]}",
                level="error",
                task_id=task_id,
                error_data={"sql_length": len(sql_query)}
            )
            return HandlerResult(
                success=False,
                data={"sql_length": len(sql_query)},
                error=error_msg,
                logs=self._execution_logs
            )
