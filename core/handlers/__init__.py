"""
Task Type Handlers Registry
===========================

Dispatches task execution to the appropriate handler based on task_type.

Supported task types:
- database: Executes SQL from payload
- research: Searches web, summarizes findings
- scan: Runs opportunity scanner
- test: Runs verification queries
"""

from typing import Dict, Any, Callable, Optional

from core.handlers.database_handler import handle_database_task
from core.handlers.research_handler import handle_research_task
from core.handlers.scan_handler import handle_scan_task
from core.handlers.test_handler import handle_test_task


# Registry maps task_type -> handler function
TASK_HANDLERS: Dict[str, Callable] = {
    "database": handle_database_task,
    "research": handle_research_task,
    "scan": handle_scan_task,
    "test": handle_test_task,
}


def get_handler(task_type: str) -> Optional[Callable]:
    """Get the handler function for a task type.
    
    Args:
        task_type: The type of task (e.g., 'database', 'research')
        
    Returns:
        Handler function or None if no handler exists
    """
    return TASK_HANDLERS.get(task_type.lower())


def dispatch_task(
    task: Dict[str, Any],
    execute_sql: Callable,
    log_action: Callable
) -> Dict[str, Any]:
    """Dispatch a task to its appropriate handler.
    
    Args:
        task: The task dictionary with id, task_type, payload, etc.
        execute_sql: Function to execute SQL queries
        log_action: Function to log actions
        
    Returns:
        Result dictionary with 'success' bool and results/error
    """
    task_type = task.get("task_type", "unknown").lower()
    task_id = task.get("id", "unknown")
    
    handler = get_handler(task_type)
    
    if not handler:
        log_action(
            "task.handler.not_found",
            f"No handler found for task_type: {task_type}",
            "error",
            task_id=task_id
        )
        return {
            "success": False,
            "error": f"No handler found for task_type: {task_type}",
            "available_handlers": list(TASK_HANDLERS.keys())
        }
    
    log_action(
        "task.handler.start",
        f"Dispatching to {task_type} handler",
        "info",
        task_id=task_id
    )
    
    try:
        result = handler(task, execute_sql, log_action)
        
        log_action(
            "task.handler.complete",
            f"{task_type} handler completed: {str(result)[:200]}",
            "info" if result.get("success") else "error",
            task_id=task_id,
            output_data=result
        )
        
        return result
        
    except Exception as e:
        error_msg = f"{task_type} handler raised exception: {str(e)}"
        log_action(
            "task.handler.exception",
            error_msg,
            "error",
            task_id=task_id
        )
        return {"success": False, "error": error_msg}


def list_handlers() -> Dict[str, str]:
    """List all available task handlers.
    
    Returns:
        Dict mapping task_type to handler function name
    """
    return {
        task_type: handler.__name__
        for task_type, handler in TASK_HANDLERS.items()
    }
