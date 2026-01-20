"""Base handler interface for task type handlers.

This module defines the base interface that all task type handlers must implement.
Handlers are responsible for executing specific task types and returning structured results.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
MAX_LOG_MESSAGE_LENGTH = 500
MAX_RESULT_PREVIEW_LENGTH = 1000


@dataclass
class HandlerResult:
    """Standardized result from task handler execution.
    
    Attributes:
        success: Whether the handler completed successfully.
        data: Result data from the handler execution.
        error: Error message if execution failed.
        logs: List of log entries generated during execution.
    """
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    logs: Optional[list] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for storage/serialization.
        
        Returns:
            Dictionary representation of the handler result.
        """
        result = {
            "success": self.success,
            "data": self.data,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }
        if self.error:
            result["error"] = self.error[:MAX_RESULT_PREVIEW_LENGTH]
        if self.logs:
            result["logs"] = self.logs
        return result


class BaseHandler(ABC):
    """Abstract base class for task type handlers.
    
    All task type handlers must inherit from this class and implement
    the execute() method. Handlers receive database and logging functions
    as dependencies to maintain separation of concerns.
    
    Attributes:
        task_type: The task type string this handler processes.
        execute_sql: Function to execute SQL queries.
        log_action: Function to log actions.
    """

    task_type: str = "unknown"

    def __init__(
        self,
        execute_sql: Callable[[str], Dict[str, Any]],
        log_action: Callable[..., Optional[str]]
    ) -> None:
        """Initialize handler with required dependencies.
        
        Args:
            execute_sql: Function to execute SQL queries against the database.
            log_action: Function to log actions and events.
        """
        self.execute_sql = execute_sql
        self.log_action = log_action
        self._execution_logs: list = []

    def _log(
        self,
        action: str,
        message: str,
        level: str = "info",
        task_id: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Internal logging helper that tracks logs for result.
        
        Args:
            action: Action identifier for the log entry.
            message: Human-readable log message.
            level: Log level (info, warn, error).
            task_id: Optional task ID to associate with the log.
            **kwargs: Additional key-value pairs to include in log.
        """
        truncated_message = message[:MAX_LOG_MESSAGE_LENGTH]
        self._execution_logs.append({
            "action": action,
            "message": truncated_message,
            "level": level,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Also log to the main logging system
        try:
            self.log_action(action, truncated_message, level=level, task_id=task_id, **kwargs)
        except Exception as log_err:
            logger.warning("Failed to log action %s: %s", action, log_err)

    @abstractmethod
    def execute(self, task: Dict[str, Any]) -> HandlerResult:
        """Execute the handler logic for a task.
        
        Args:
            task: Task dictionary containing id, payload, title, description, etc.
        
        Returns:
            HandlerResult containing success status, data, and any errors.
        """
        pass

    def validate_payload(
        self,
        payload: Dict[str, Any],
        required_fields: list
    ) -> tuple[bool, Optional[str]]:
        """Validate that payload contains required fields.
        
        Args:
            payload: The task payload to validate.
            required_fields: List of field names that must be present.
        
        Returns:
            Tuple of (is_valid, error_message). Error message is None if valid.
        """
        if not isinstance(payload, dict):
            return False, "Payload must be a dictionary"
        
        missing = [f for f in required_fields if f not in payload]
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"
        
        return True, None
