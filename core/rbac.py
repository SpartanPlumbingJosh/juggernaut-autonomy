"""
RBAC-01: Runtime Permission Enforcement

This module provides role-based access control (RBAC) enforcement at runtime.
It checks worker capabilities before tool execution, logs unauthorized attempts
to access_audit_log, and provides decorators for sensitive operations.

Usage:
    from core.rbac import check_permission, require_permission, PermissionDenied

    # Function decorator
    @require_permission("task.execute")
    def execute_task(worker_id: str, task_data: Dict) -> Dict:
        ...

    # Direct permission check
    result = check_permission(worker_id, "database.write", "users_table")
    if not result.allowed:
        raise PermissionDenied(result.reason)
"""

import functools
import json
import logging
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from uuid import uuid4

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# SCOPE DEFINITIONS (RBAC + Scoped Credentials)
# =============================================================================

# Canonical scopes for tool/task actions.
# Note: these are permissions strings that should appear in roles.permissions and/or worker_registry.permissions.
SCOPES = {
    # Database
    "database.read",
    "database.write",
    "database.admin",
    # GitHub
    "github.read",
    "github.write",
    "github.admin",
    # Railway
    "railway.read",
    "railway.deploy",
    # Generic external API calls
    "api.execute",
}


# Default permissions by role (fallback when DB roles table is missing/out-of-date).
DEFAULT_ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "EXECUTOR": ["database.write", "github.write", "api.execute"],
    "ANALYST": ["database.read", "api.execute"],
    "ORCHESTRATOR": ["*"],
    "STRATEGIST": ["database.read", "github.read"],
    "WATCHDOG": ["database.read", "railway.read"],
}


def _normalize_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    if isinstance(value, (tuple, set)):
        return [str(v) for v in value if v is not None]
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        # Try JSON parsing first
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(v) for v in parsed if v is not None]
        except Exception:
            pass
        # Comma-separated fallback
        if "," in s:
            return [p.strip() for p in s.split(",") if p.strip()]
        return [s]
    return [str(value)]


def get_default_permissions_for_role(role_name: Optional[str]) -> List[str]:
    if not role_name:
        return []
    return DEFAULT_ROLE_PERMISSIONS.get(str(role_name).upper(), [])


def get_scoped_credential(
    worker_id: str,
    credential_key: str,
    required_scope: Optional[str] = None,
) -> Optional[str]:
    """Retrieve a credential scoped to a worker and/or role.

    Lookup order:
    1) If a `worker_credentials` table exists, read latest active credential for (worker_id, credential_key).
       Optional required_scope can further constrain lookup.
    2) Environment variable fallback (most specific to least):
       - {CREDENTIAL_KEY}__{WORKER_ID}
       - {CREDENTIAL_KEY}__{ROLE_NAME}
       - {CREDENTIAL_KEY}

    This function does NOT log secrets. Permission checks should be enforced by callers via check_permission().
    """
    key = str(credential_key or "").strip()
    if not key:
        return None

    worker = get_worker_info(worker_id)
    role_name = (worker or {}).get("role_name")

    # DB-backed credentials (optional)
    try:
        scope_filter = ""
        if required_scope:
            scope_filter = f" AND (scope = {_escape_value(required_scope)} OR scope IS NULL)"
        sql = f"""
        SELECT credential_value
        FROM worker_credentials
        WHERE worker_id = {_escape_value(worker_id)}
          AND credential_key = {_escape_value(key)}
          AND status = 'active'
          {scope_filter}
        ORDER BY created_at DESC
        LIMIT 1
        """
        result = _execute_query(sql)
        rows = result.get("rows", [])
        if rows and rows[0].get("credential_value"):
            return str(rows[0].get("credential_value"))
    except Exception:
        # Table may not exist or query may fail; fall back to env
        pass

    # Env-backed credentials
    def _env_key(suffix: str) -> str:
        # Env vars can't reliably contain '-' so normalize.
        return f"{key}__{suffix}".upper().replace("-", "_")

    v = os.environ.get(_env_key(worker_id))
    if v:
        return v

    if role_name:
        v = os.environ.get(_env_key(str(role_name)))
        if v:
            return v

    return os.environ.get(key)

# Database configuration
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
NEON_CONNECTION_STRING = (
    "postgresql://neondb_owner:npg_OYkCRU4aze2l@"
    "ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
)

# Type variable for decorator
F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# EXCEPTIONS
# =============================================================================


class PermissionDenied(Exception):
    """Raised when a permission check fails."""

    def __init__(self, reason: str, worker_id: str = None, action: str = None):
        """
        Initialize PermissionDenied exception.

        Args:
            reason: Human-readable reason for denial
            worker_id: ID of the worker that was denied
            action: The action that was attempted
        """
        self.reason = reason
        self.worker_id = worker_id
        self.action = action
        super().__init__(f"Permission denied: {reason}")


class RBACError(Exception):
    """Raised when RBAC system encounters an error."""

    pass


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class PermissionResult:
    """Result of a permission check."""

    allowed: bool
    reason: str
    action: str
    worker_id: Optional[str] = None
    scope: Optional[str] = None
    requires_approval: bool = False
    daily_calls_remaining: Optional[int] = None
    resource: Optional[str] = None
    role_name: Optional[str] = None
    checked_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "worker_id": self.worker_id,
            "action": self.action,
            "resource": self.resource,
            "role_name": self.role_name,
            "checked_at": self.checked_at,
        }


# =============================================================================
# DATABASE HELPERS
# =============================================================================


def _execute_query(sql: str) -> Dict[str, Any]:
    """
    Execute SQL query against the database.

    Args:
        sql: SQL query to execute

    Returns:
        Dict with query results

    Raises:
        RBACError: If query fails
    """
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": NEON_CONNECTION_STRING,
    }
    data = json.dumps({"query": sql}).encode("utf-8")

    try:
        req = urllib.request.Request(
            NEON_ENDPOINT, data=data, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        logger.error("Database query failed: %s", str(e))
        raise RBACError(f"Database query failed: {e}") from e
    except json.JSONDecodeError as e:
        logger.error("Failed to parse database response: %s", str(e))
        raise RBACError(f"Failed to parse response: {e}") from e


def _escape_value(value: Any) -> str:
    """
    Escape a value for safe SQL insertion.

    Args:
        value: Value to escape

    Returns:
        SQL-safe string representation
    """
    if value is None:
        return "NULL"
    elif isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, (dict, list)):
        json_str = json.dumps(value).replace("'", "''")
        return f"'{json_str}'"
    else:
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"


# =============================================================================
# CORE RBAC FUNCTIONS
# =============================================================================


def get_worker_info(worker_id: str) -> Optional[Dict[str, Any]]:
    """
    Get worker information including role and permissions.

    Args:
        worker_id: The worker ID to look up

    Returns:
        Dict with worker info or None if not found
    """
    sql = f"""
    SELECT 
        worker_id, role_name, capabilities, permissions,
        forbidden_actions, approval_required_for, allowed_task_types,
        status
    FROM worker_registry
    WHERE worker_id = {_escape_value(worker_id)}
    """
    try:
        result = _execute_query(sql)
        rows = result.get("rows", [])
        return rows[0] if rows else None
    except RBACError:
        return None


def _expand_implied_permissions(perms: List[str]) -> List[str]:
    """Expand implied permissions (admin implies write/read)."""
    s = set(perms)

    if "database.admin" in s:
        s.add("database.write")
        s.add("database.read")
    if "database.write" in s:
        s.add("database.read")

    if "github.admin" in s:
        s.add("github.write")
        s.add("github.read")
    if "github.write" in s:
        s.add("github.read")

    if "railway.deploy" in s:
        s.add("railway.read")

    return list(s)


def get_role_permissions(role_name: str) -> Optional[Dict[str, Any]]:
    """
    Get role permissions from the roles table.

    Args:
        role_name: Name of the role

    Returns:
        Dict with role permissions or None if not found
    """
    sql = f"""
    SELECT 
        role_name, permissions, forbidden_actions,
        allowed_task_types, max_risk_level
    FROM roles
    WHERE role_name = {_escape_value(role_name)}
    """
    try:
        result = _execute_query(sql)
        rows = result.get("rows", [])
        return rows[0] if rows else None
    except RBACError:
        return None


def check_tool_permission(
    worker_id: str,
    tool_name: str,
    estimated_cost: Optional[float] = None
) -> PermissionResult:
    """
    Check if a worker has permission to use a specific tool.
    
    This function uses the new tool-level permissions schema to check if
    a worker is allowed to use a specific tool, considering:
    - Tool risk level
    - Worker permissions
    - Rate limits
    - Budget constraints
    
    Args:
        worker_id: ID of the worker requesting permission
        tool_name: Name of the tool to use
        estimated_cost: Optional estimated cost of the tool execution
        
    Returns:
        PermissionResult with allowed status, reason, and additional metadata
    """
    checked_at = datetime.now(timezone.utc).isoformat()
    
    # First try using the new schema
    try:
        sql = f"""
        SELECT * FROM check_tool_permission({_escape_value(worker_id)}, {_escape_value(tool_name)})
        """
        result = _execute_query(sql)
        rows = result.get("rows", [])
        
        if rows:
            permission_data = rows[0]
            allowed = permission_data.get("allowed", False)
            reason = permission_data.get("reason", "")
            requires_approval = permission_data.get("requires_approval", False)
            permission_level = permission_data.get("permission_level")
            daily_calls_remaining = permission_data.get("daily_calls_remaining", 0)
            
            # Log the access attempt
            log_access_attempt(
                worker_id=worker_id,
                action=f"tool.{tool_name}",
                resource=None,
                role_name=None,  # We don't have this from the function
                permission_checked=f"tool.{tool_name}",
                decision="allowed" if allowed else "denied",
                reason=reason,
                context={"estimated_cost": estimated_cost, "requires_approval": requires_approval}
            )
            
            return PermissionResult(
                allowed=allowed,
                reason=reason,
                worker_id=worker_id,
                action=f"tool.{tool_name}",
                resource=None,
                role_name=None,
                checked_at=checked_at,
                requires_approval=requires_approval,
                daily_calls_remaining=daily_calls_remaining
            )
    except Exception as e:
        logger.warning(f"Tool permission check using new schema failed: {e}")
        # Fall back to traditional permission check
    
    # Fall back to traditional permission check
    return check_permission(worker_id, f"tool.{tool_name}")


def log_tool_execution(
    worker_id: str,
    tool_name: str,
    parameters: Dict[str, Any],
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    cost_usd: Optional[float] = None,
    duration_ms: Optional[int] = None,
    task_id: Optional[str] = None
) -> Optional[str]:
    """
    Log a tool execution to the tool_execution_logs table.
    
    Args:
        worker_id: ID of the worker executing the tool
        tool_name: Name of the tool being executed
        parameters: Parameters passed to the tool
        result: Optional result of the tool execution
        error_message: Optional error message if the tool failed
        cost_usd: Optional cost of the tool execution in USD
        duration_ms: Optional duration of the tool execution in milliseconds
        task_id: Optional ID of the task that triggered this tool execution
        
    Returns:
        ID of the created log entry or None if logging failed
    """
    log_id = str(uuid4())
    status = "success" if error_message is None else "failed"
    
    try:
        sql = f"""
        INSERT INTO tool_execution_logs (
            id, worker_id, tool_name, status, parameters,
            result, error_message, cost_usd, duration_ms,
            started_at, completed_at, task_id
        ) VALUES (
            {_escape_value(log_id)},
            {_escape_value(worker_id)},
            {_escape_value(tool_name)},
            {_escape_value(status)},
            {_escape_value(parameters)},
            {_escape_value(result)},
            {_escape_value(error_message)},
            {_escape_value(cost_usd)},
            {_escape_value(duration_ms)},
            NOW(),
            {"NOW()" if status == "success" else "NULL"},
            {_escape_value(task_id)}
        )
        """
        _execute_query(sql)
        
        # If we have a cost, update the worker's budget usage
        if cost_usd is not None and cost_usd > 0:
            try:
                update_sql = f"""
                UPDATE worker_budgets
                SET 
                    current_daily_usage = current_daily_usage + {cost_usd},
                    current_weekly_usage = current_weekly_usage + {cost_usd},
                    current_monthly_usage = current_monthly_usage + {cost_usd},
                    updated_at = NOW()
                WHERE worker_id = {_escape_value(worker_id)}
                """
                _execute_query(update_sql)
            except Exception as budget_err:
                logger.warning(f"Failed to update budget usage: {budget_err}")
        
        return log_id
    except Exception as e:
        logger.error(f"Failed to log tool execution: {e}")
        return None


def log_access_attempt(
    worker_id: str,
    action: str,
    resource: Optional[str],
    role_name: Optional[str],
    permission_checked: str,
    decision: str,
    reason: str,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Log an access attempt to the access_audit_log table.

    Args:
        worker_id: ID of the worker attempting access
        action: Action being attempted
        resource: Resource being accessed
        role_name: Worker's role
        permission_checked: The permission that was checked
        decision: 'allowed' or 'denied'
        reason: Reason for the decision
        context: Additional context information

    Returns:
        ID of the created log entry or None if logging failed
    """
    log_id = str(uuid4())
    sql = f"""
    INSERT INTO access_audit_log (
        id, worker_id, action, resource, role_name,
        permission_checked, decision, reason, context, checked_at
    ) VALUES (
        {_escape_value(log_id)},
        {_escape_value(worker_id)},
        {_escape_value(action)},
        {_escape_value(resource)},
        {_escape_value(role_name)},
        {_escape_value(permission_checked)},
        {_escape_value(decision)},
        {_escape_value(reason)},
        {_escape_value(context or {})},
        NOW()
    )
    """
    try:
        _execute_query(sql)
        logger.info(
            "Access %s for worker=%s action=%s resource=%s: %s",
            decision,
            worker_id,
            action,
            resource,
            reason,
        )
        return log_id
    except RBACError as e:
        logger.error("Failed to log access attempt: %s", str(e))
        return None


def check_permission(
    worker_id: str,
    action: str,
    resource: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> PermissionResult:
    """
    Check if a worker has permission to perform an action.

    This function:
    1. Looks up the worker in worker_registry
    2. Gets the worker's role permissions from roles table
    3. Checks if the action is allowed based on permissions and forbidden_actions
    4. Logs the access attempt to access_audit_log
    5. Returns a PermissionResult

    Args:
        worker_id: ID of the worker requesting permission
        action: Action being requested (e.g., "task.execute", "database.write")
        resource: Optional resource being accessed
        context: Optional additional context for logging

    Returns:
        PermissionResult with allowed status and reason
    """
    checked_at = datetime.now(timezone.utc).isoformat()

    # Get worker info
    worker = get_worker_info(worker_id)
    if not worker:
        reason = f"Worker '{worker_id}' not found in registry"
        log_access_attempt(
            worker_id=worker_id,
            action=action,
            resource=resource,
            role_name=None,
            permission_checked=action,
            decision="denied",
            reason=reason,
            context=context,
        )
        return PermissionResult(
            allowed=False,
            reason=reason,
            worker_id=worker_id,
            action=action,
            resource=resource,
            checked_at=checked_at,
        )

    # Check if worker is active
    if worker.get("status") not in ("active", "idle", "busy"):
        reason = f"Worker status is '{worker.get('status')}', not active"
        log_access_attempt(
            worker_id=worker_id,
            action=action,
            resource=resource,
            role_name=worker.get("role_name"),
            permission_checked=action,
            decision="denied",
            reason=reason,
            context=context,
        )
        return PermissionResult(
            allowed=False,
            reason=reason,
            worker_id=worker_id,
            action=action,
            resource=resource,
            role_name=worker.get("role_name"),
            checked_at=checked_at,
        )

    role_name = worker.get("role_name")

    # Get role permissions
    role = get_role_permissions(role_name) if role_name else None

    # Combine worker-level and role-level permissions (robust parsing)
    worker_permissions = _normalize_str_list(worker.get("permissions"))

    role_permissions: List[str] = []
    if role and role.get("permissions") is not None:
        role_permissions = _normalize_str_list(role.get("permissions"))
    else:
        # Fallback to hard-coded defaults by role name
        role_permissions = get_default_permissions_for_role(role_name)

    all_permissions = set(_expand_implied_permissions(list(set(worker_permissions) | set(role_permissions))))

    # Combine forbidden actions (robust parsing)
    worker_forbidden = _normalize_str_list(worker.get("forbidden_actions"))
    role_forbidden = _normalize_str_list(role.get("forbidden_actions")) if role else []
    all_forbidden = set(worker_forbidden) | set(role_forbidden)

    # Check if action is explicitly forbidden
    # Check exact match and wildcard patterns
    action_parts = action.split(".")
    for forbidden in all_forbidden:
        if forbidden == action:
            reason = f"Action '{action}' is explicitly forbidden"
            log_access_attempt(
                worker_id=worker_id,
                action=action,
                resource=resource,
                role_name=role_name,
                permission_checked=action,
                decision="denied",
                reason=reason,
                context=context,
            )
            return PermissionResult(
                allowed=False,
                reason=reason,
                worker_id=worker_id,
                action=action,
                resource=resource,
                role_name=role_name,
                checked_at=checked_at,
            )
        # Check wildcard patterns (e.g., "system.*" forbids "system.shutdown")
        if forbidden.endswith(".*"):
            prefix = forbidden[:-2]
            if action.startswith(prefix + "."):
                reason = f"Action '{action}' is forbidden by pattern '{forbidden}'"
                log_access_attempt(
                    worker_id=worker_id,
                    action=action,
                    resource=resource,
                    role_name=role_name,
                    permission_checked=action,
                    decision="denied",
                    reason=reason,
                    context=context,
                )
                return PermissionResult(
                    allowed=False,
                    reason=reason,
                    worker_id=worker_id,
                    action=action,
                    resource=resource,
                    role_name=role_name,
                    checked_at=checked_at,
                )

    # Check if action is allowed
    # Admin with "*" permission can do anything
    if "*" in all_permissions:
        reason = "Allowed by wildcard permission"
        log_access_attempt(
            worker_id=worker_id,
            action=action,
            resource=resource,
            role_name=role_name,
            permission_checked=action,
            decision="allowed",
            reason=reason,
            context=context,
        )
        return PermissionResult(
            allowed=True,
            reason=reason,
            worker_id=worker_id,
            action=action,
            resource=resource,
            role_name=role_name,
            checked_at=checked_at,
        )

    # Check exact permission match
    if action in all_permissions:
        reason = f"Allowed by permission '{action}'"
        log_access_attempt(
            worker_id=worker_id,
            action=action,
            resource=resource,
            role_name=role_name,
            permission_checked=action,
            decision="allowed",
            reason=reason,
            context=context,
        )
        return PermissionResult(
            allowed=True,
            reason=reason,
            worker_id=worker_id,
            action=action,
            resource=resource,
            role_name=role_name,
            checked_at=checked_at,
        )

    # Check wildcard permissions (e.g., "task.*" allows "task.execute")
    for perm in all_permissions:
        if perm.endswith(".*"):
            prefix = perm[:-2]
            if action.startswith(prefix + "."):
                reason = f"Allowed by wildcard permission '{perm}'"
                log_access_attempt(
                    worker_id=worker_id,
                    action=action,
                    resource=resource,
                    role_name=role_name,
                    permission_checked=action,
                    decision="allowed",
                    reason=reason,
                    context=context,
                )
                return PermissionResult(
                    allowed=True,
                    reason=reason,
                    worker_id=worker_id,
                    action=action,
                    resource=resource,
                    role_name=role_name,
                    checked_at=checked_at,
                )

    # Permission not found
    reason = f"Permission '{action}' not granted to worker or role"
    log_access_attempt(
        worker_id=worker_id,
        action=action,
        resource=resource,
        role_name=role_name,
        permission_checked=action,
        decision="denied",
        reason=reason,
        context=context,
    )
    return PermissionResult(
        allowed=False,
        reason=reason,
        worker_id=worker_id,
        action=action,
        resource=resource,
        role_name=role_name,
        checked_at=checked_at,
    )


def check_capability(worker_id: str, capability: str) -> PermissionResult:
    """
    Check if a worker has a specific capability.

    Args:
        worker_id: ID of the worker
        capability: Capability to check (e.g., "code_execution", "web_access")

    Returns:
        PermissionResult with allowed status
    """
    checked_at = datetime.now(timezone.utc).isoformat()

    worker = get_worker_info(worker_id)
    if not worker:
        return PermissionResult(
            allowed=False,
            reason=f"Worker '{worker_id}' not found",
            worker_id=worker_id,
            action=f"capability:{capability}",
            checked_at=checked_at,
        )

    capabilities = worker.get("capabilities") or []
    if capability in capabilities or "*" in capabilities:
        return PermissionResult(
            allowed=True,
            reason=f"Worker has capability '{capability}'",
            worker_id=worker_id,
            action=f"capability:{capability}",
            role_name=worker.get("role_name"),
            checked_at=checked_at,
        )

    return PermissionResult(
        allowed=False,
        reason=f"Worker lacks capability '{capability}'",
        worker_id=worker_id,
        action=f"capability:{capability}",
        role_name=worker.get("role_name"),
        checked_at=checked_at,
    )


# =============================================================================
# DECORATORS
# =============================================================================


def require_permission(
    permission: str,
    resource: Optional[str] = None,
    worker_id_param: str = "worker_id",
) -> Callable[[F], F]:
    """
    Decorator to require a permission before executing a function.

    The decorated function must have a parameter named `worker_id` (or as
    specified by worker_id_param) that contains the worker ID to check.

    Usage:
        @require_permission("task.execute")
        def execute_task(worker_id: str, task_data: Dict) -> Dict:
            ...

        @require_permission("database.write", resource="users")
        def update_user(worker_id: str, user_id: str, data: Dict) -> Dict:
            ...

    Args:
        permission: The permission required to execute the function
        resource: Optional resource name for logging
        worker_id_param: Name of the parameter containing worker ID

    Returns:
        Decorated function that checks permission before executing

    Raises:
        PermissionDenied: If permission check fails
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract worker_id from kwargs or args
            worker_id = kwargs.get(worker_id_param)

            # If not in kwargs, try to get from positional args
            if worker_id is None:
                import inspect

                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                if worker_id_param in params:
                    idx = params.index(worker_id_param)
                    if idx < len(args):
                        worker_id = args[idx]

            if worker_id is None:
                raise PermissionDenied(
                    reason=f"Could not determine worker_id from parameter '{worker_id_param}'",
                    action=permission,
                )

            # Check permission
            result = check_permission(
                worker_id=worker_id,
                action=permission,
                resource=resource,
                context={"function": func.__name__},
            )

            if not result.allowed:
                raise PermissionDenied(
                    reason=result.reason,
                    worker_id=worker_id,
                    action=permission,
                )

            # Permission granted, execute function
            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def require_capability(
    capability: str,
    worker_id_param: str = "worker_id",
) -> Callable[[F], F]:
    """
    Decorator to require a capability before executing a function.

    Args:
        capability: The capability required
        worker_id_param: Name of the parameter containing worker ID

    Returns:
        Decorated function

    Raises:
        PermissionDenied: If capability check fails
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            worker_id = kwargs.get(worker_id_param)

            if worker_id is None:
                import inspect

                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                if worker_id_param in params:
                    idx = params.index(worker_id_param)
                    if idx < len(args):
                        worker_id = args[idx]

            if worker_id is None:
                raise PermissionDenied(
                    reason="Could not determine worker_id",
                    action=f"capability:{capability}",
                )

            result = check_capability(worker_id, capability)
            if not result.allowed:
                raise PermissionDenied(
                    reason=result.reason,
                    worker_id=worker_id,
                    action=f"capability:{capability}",
                )

            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


# =============================================================================
# AUDIT FUNCTIONS
# =============================================================================


def get_access_audit_log(
    worker_id: Optional[str] = None,
    action: Optional[str] = None,
    decision: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Get access audit log entries with optional filters.

    Args:
        worker_id: Filter by worker ID
        action: Filter by action
        decision: Filter by decision ('allowed' or 'denied')
        limit: Maximum number of entries to return

    Returns:
        List of audit log entries
    """
    conditions = []
    if worker_id:
        conditions.append(f"worker_id = {_escape_value(worker_id)}")
    if action:
        conditions.append(f"action = {_escape_value(action)}")
    if decision:
        conditions.append(f"decision = {_escape_value(decision)}")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    sql = f"""
    SELECT *
    FROM access_audit_log
    {where_clause}
    ORDER BY checked_at DESC
    LIMIT {limit}
    """
    try:
        result = _execute_query(sql)
        return result.get("rows", [])
    except RBACError:
        return []


def get_denied_access_attempts(
    worker_id: Optional[str] = None,
    since_hours: int = 24,
) -> List[Dict[str, Any]]:
    """
    Get denied access attempts within a time window.

    Args:
        worker_id: Filter by worker ID
        since_hours: Look back this many hours

    Returns:
        List of denied access attempts
    """
    worker_filter = f"AND worker_id = {_escape_value(worker_id)}" if worker_id else ""

    sql = f"""
    SELECT *
    FROM access_audit_log
    WHERE decision = 'denied'
    AND checked_at > NOW() - INTERVAL '{since_hours} hours'
    {worker_filter}
    ORDER BY checked_at DESC
    """
    try:
        result = _execute_query(sql)
        return result.get("rows", [])
    except RBACError:
        return []


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Exceptions
    "PermissionDenied",
    "RBACError",
    # Data classes
    "PermissionResult",
    # Core functions
    "check_permission",
    "check_capability",
    "get_worker_info",
    "get_role_permissions",
    "log_access_attempt",
    # Decorators
    "require_permission",
    "require_capability",
    # Audit functions
    "get_access_audit_log",
    "get_denied_access_attempts",
]
