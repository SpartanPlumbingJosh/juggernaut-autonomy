"""Task type handlers package.

This package provides modular handlers for different task types.
Each handler encapsulates the logic for executing a specific type of task.

Usage:
    from core.handlers import get_handler, AVAILABLE_HANDLERS
    
    handler = get_handler("database", execute_sql, log_action)
    if handler:
        result = handler.execute(task)

Available Handlers:
    - database: Execute SQL queries with read-only enforcement
    - research: Search web and summarize findings
    - scan: Run opportunity scanning operations
    - test: Execute verification/test queries
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Type

from .base import BaseHandler, HandlerResult
from .ai_handler import AIHandler
from .analysis_handler import AnalysisHandler
from .database_handler import DatabaseHandler
from .idea_scoring_handler import IdeaScoringHandler
from .research_handler import ResearchHandler
from .scan_handler import ScanHandler
from .test_handler import TestHandler

# Configure module logger
logger = logging.getLogger(__name__)

# Registry of available handlers
_HANDLER_REGISTRY: Dict[str, Type[BaseHandler]] = {
    "ai": AIHandler,
    "analysis": AnalysisHandler,
    "audit": AnalysisHandler,
    "reporting": AnalysisHandler,
    "database": DatabaseHandler,
    "idea_scoring": IdeaScoringHandler,
    "research": ResearchHandler,
    "scan": ScanHandler,
    "test": TestHandler,
    "workflow": AIHandler,
    "content_creation": AIHandler,
    "development": AIHandler,
    "integration": AIHandler,
    "planning": AIHandler,
    "design": AIHandler,
}

# Public list of available handler types
AVAILABLE_HANDLERS: List[str] = list(_HANDLER_REGISTRY.keys())


def get_handler(
    task_type: str,
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Optional[str]]
) -> Optional[BaseHandler]:
    """Get an initialized handler for the specified task type.
    
    Args:
        task_type: The type of task to get a handler for.
        execute_sql: Function to execute SQL queries.
        log_action: Function to log actions.
    
    Returns:
        Initialized handler instance, or None if no handler exists for the type.
    
    Example:
        handler = get_handler("database", execute_sql, log_action)
        if handler:
            result = handler.execute(task_dict)
    """
    handler_class = _HANDLER_REGISTRY.get(task_type)
    
    if handler_class is None:
        logger.debug("No handler registered for task type: %s", task_type)
        return None
    
    try:
        return handler_class(execute_sql, log_action)
    except Exception as init_error:
        logger.error(
            "Failed to initialize handler for %s: %s",
            task_type,
            init_error
        )
        return None


def has_handler(task_type: str) -> bool:
    """Check if a handler exists for the specified task type.
    
    Args:
        task_type: The task type to check.
    
    Returns:
        True if a handler is registered for this type.
    """
    return task_type in _HANDLER_REGISTRY


def register_handler(task_type: str, handler_class: Type[BaseHandler]) -> None:
    """Register a custom handler for a task type.
    
    Args:
        task_type: The task type identifier.
        handler_class: The handler class (must inherit from BaseHandler).
    
    Raises:
        TypeError: If handler_class doesn't inherit from BaseHandler.
        ValueError: If task_type is empty.
    """
    if not task_type:
        raise ValueError("task_type cannot be empty")
    
    if not issubclass(handler_class, BaseHandler):
        raise TypeError(
            f"Handler class must inherit from BaseHandler, got {type(handler_class)}"
        )
    
    _HANDLER_REGISTRY[task_type] = handler_class
    
    # Update public list
    global AVAILABLE_HANDLERS
    AVAILABLE_HANDLERS = list(_HANDLER_REGISTRY.keys())
    
    logger.info("Registered handler for task type: %s", task_type)


def dispatch_task(
    task: Dict[str, Any],
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Optional[str]]
) -> Optional[HandlerResult]:
    """Dispatch a task to its appropriate handler.
    
    This is a convenience function that combines get_handler and execute.
    
    Args:
        task: Task dictionary containing at least 'task_type' field.
        execute_sql: Function to execute SQL queries.
        log_action: Function to log actions.
    
    Returns:
        HandlerResult from the handler, or None if no handler exists.
    
    Example:
        result = dispatch_task(task_dict, execute_sql, log_action)
        if result and result.success:
            print("Task completed successfully")
    """
    task_type = task.get("task_type")
    
    if not task_type:
        logger.warning("Task missing 'task_type' field")
        return None
    
    handler = get_handler(task_type, execute_sql, log_action)
    
    if handler is None:
        return None
    
    try:
        return handler.execute(task)
    except Exception as dispatch_error:
        logger.error(
            "Handler dispatch failed for %s: %s",
            task_type,
            dispatch_error
        )
        return HandlerResult(
            success=False,
            data={"task_type": task_type},
            error=f"Handler dispatch failed: {str(dispatch_error)}"
        )


# Export public interface
__all__ = [
    # Classes
    "BaseHandler",
    "HandlerResult",
    "AIHandler",
    "AnalysisHandler",
    "DatabaseHandler",
    "ResearchHandler",
    "ScanHandler",
    "TestHandler",
    # Functions
    "get_handler",
    "has_handler",
    "register_handler",
    "dispatch_task",
    # Constants
    "AVAILABLE_HANDLERS",
]
