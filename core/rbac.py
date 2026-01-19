"""
JUGGERNAUT RBAC (Role-Based Access Control) Module

Provides runtime permission enforcement with comprehensive audit logging.
All permission checks are logged to access_audit_log table for security compliance.

Functions:
- check_permission: Check if a worker has a specific permission
- check_action_allowed: Check if an action is allowed for a worker
- log_access_audit: Log permission checks to audit table
- require_permission: Decorator for permission-protected functions

FIX-05: Enables access_audit_log for RBAC
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

# Configure logging
logger = logging.getLogger(__name__)

# Database configuration
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
NEON_CONNECTION_STRING = "postgresql://neondb_owner:npg_OYkCRU4aze2l@ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"


def _execute_sql(query: str) -> Dict[str, Any]:
    """
    Execute SQL query against Neon database.
    
    Args:
        query: SQL query to execute
        
    Returns:
        Dict with query results
    """
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": NEON_CONNECTION_STRING
    }
    try:
        response = httpx.post(
            NEON_ENDPOINT,
            json={"query": query},
            headers=headers,
            timeout=30.0
        )
        return response.json()
    except Exception as e:
        logger.error("SQL execution failed: %s", e)
        return {"error": str(e), "rows": [], "rowCount": 0}


def _escape_string(value: str) -> str:
    """Escape single quotes for SQL."""
    if value is None:
        return "NULL"
    return value.replace("'", "''")


def log_access_audit(
    worker_id: str,
    action: str,
    resource: str,
    permission_checked: str,
    decision: str,
    role_name: Optional[str] = None,
    reason: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Log a permission check to access_audit_log table.
    
    This function is called whenever a permission is checked, regardless
    of whether access is granted or denied. This provides comprehensive
    audit trail for security compliance.
    
    Args:
        worker_id: ID of the worker/user attempting the action
        action: The action being attempted (e.g., 'task.execute', 'database.write')
        resource: The resource being accessed (e.g., 'governance_tasks', 'tool:slack')
        permission_checked: The specific permission that was checked
        decision: 'granted' or 'denied'
        role_name: The role of the worker (if known)
        reason: Explanation for the decision
        context: Additional context as JSON
        
    Returns:
        UUID of the audit log entry, or None if logging failed
    """
    audit_id = str(uuid.uuid4())
    
    context_json = json.dumps(context or {}).replace("'", "''")
    
    query = f"""
    INSERT INTO access_audit_log (
        id, worker_id, action, resource, role_name, 
        permission_checked, decision, reason, context, checked_at
    ) VALUES (
        '{audit_id}',
        '{_escape_string(worker_id)}',
        '{_escape_string(action)}',
        '{_escape_string(resource)}',
        {f"'{_escape_string(role_name)}'" if role_name else "NULL"},
        '{_escape_string(permission_checked)}',
        '{_escape_string(decision)}',
        {f"'{_escape_string(reason)}'" if reason else "NULL"},
        '{context_json}'::jsonb,
        NOW()
    )
    RETURNING id
    """
    
    try:
        result = _execute_sql(query)
        if result.get("rows"):
            logger.debug(
                "Access audit logged: worker=%s action=%s decision=%s",
                worker_id, action, decision
            )
            return audit_id
        return None
    except Exception as e:
        logger.error("Failed to log access audit: %s", e)
        return None


def get_worker_role(worker_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the role information for a worker.
    
    Args:
        worker_id: ID of the worker
        
    Returns:
        Role information dict or None if not found
    """
    query = f"""
    SELECT 
        wr.worker_id,
        wr.capabilities,
        r.role_name,
        r.permissions,
        r.forbidden_actions,
        r.allowed_task_types,
        r.max_risk_level
    FROM worker_registry wr
    LEFT JOIN roles r ON r.role_name = ANY(
        SELECT jsonb_array_elements_text(wr.capabilities)
        WHERE jsonb_typeof(wr.capabilities) = 'array'
    )
    WHERE wr.worker_id = '{_escape_string(worker_id)}'
    LIMIT 1
    """
    
    result = _execute_sql(query)
    rows = result.get("rows", [])
    
    if rows:
        return rows[0]
    
    # Fallback: check if worker has forbidden_actions directly
    fallback_query = f"""
    SELECT 
        worker_id,
        forbidden_actions,
        allowed_task_types,
        capabilities
    FROM worker_registry
    WHERE worker_id = '{_escape_string(worker_id)}'
    """
    
    fallback_result = _execute_sql(fallback_query)
    fallback_rows = fallback_result.get("rows", [])
    
    if fallback_rows:
        return fallback_rows[0]
    
    return None


def get_role_by_name(role_name: str) -> Optional[Dict[str, Any]]:
    """
    Get role information by role name.
    
    Args:
        role_name: Name of the role (e.g., 'admin', 'operator', 'viewer')
        
    Returns:
        Role information dict or None if not found
    """
    query = f"""
    SELECT 
        role_name,
        permissions,
        forbidden_actions,
        allowed_task_types,
        max_risk_level
    FROM roles
    WHERE role_name = '{_escape_string(role_name)}'
    """
    
    result = _execute_sql(query)
    rows = result.get("rows", [])
    return rows[0] if rows else None


def check_permission(
    worker_id: str,
    permission: str,
    resource: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """
    Check if a worker has a specific permission.
    
    This function:
    1. Gets the worker's role
    2. Checks if the permission is granted
    3. Logs the check to access_audit_log
    4. Returns the decision
    
    Args:
        worker_id: ID of the worker
        permission: Permission to check (e.g., 'task.execute', 'database.write')
        resource: Optional resource being accessed
        context: Optional additional context
        
    Returns:
        Tuple of (is_allowed: bool, reason: str)
    """
    worker_info = get_worker_role(worker_id)
    
    if not worker_info:
        # Unknown worker - deny by default and log
        log_access_audit(
            worker_id=worker_id,
            action=permission,
            resource=resource or "unknown",
            permission_checked=permission,
            decision="denied",
            reason="Worker not found in registry",
            context=context
        )
        return False, "Worker not found in registry"
    
    role_name = worker_info.get("role_name")
    permissions = worker_info.get("permissions", [])
    forbidden_actions = worker_info.get("forbidden_actions", [])
    
    # Ensure permissions and forbidden_actions are lists
    if isinstance(permissions, str):
        try:
            permissions = json.loads(permissions)
        except (json.JSONDecodeError, TypeError):
            permissions = []
    
    if isinstance(forbidden_actions, str):
        try:
            forbidden_actions = json.loads(forbidden_actions)
        except (json.JSONDecodeError, TypeError):
            forbidden_actions = []
    
    # Check if explicitly forbidden
    for forbidden in (forbidden_actions or []):
        if forbidden == permission or permission.startswith(forbidden.rstrip("*")):
            log_access_audit(
                worker_id=worker_id,
                action=permission,
                resource=resource or "unknown",
                permission_checked=permission,
                decision="denied",
                role_name=role_name,
                reason=f"Action matches forbidden pattern: {forbidden}",
                context=context
            )
            return False, f"Action '{permission}' is forbidden by pattern '{forbidden}'"
    
    # Check if permission is granted
    is_granted = False
    grant_reason = "No matching permission"
    
    for perm in (permissions or []):
        if perm == "*":
            is_granted = True
            grant_reason = "Wildcard permission (*)"
            break
        elif perm == permission:
            is_granted = True
            grant_reason = f"Exact permission match: {perm}"
            break
        elif permission.startswith(perm.rstrip("*") if perm.endswith("*") else perm + "."):
            is_granted = True
            grant_reason = f"Pattern permission match: {perm}"
            break
    
    # Log the decision
    log_access_audit(
        worker_id=worker_id,
        action=permission,
        resource=resource or "unknown",
        permission_checked=permission,
        decision="granted" if is_granted else "denied",
        role_name=role_name,
        reason=grant_reason,
        context=context
    )
    
    if is_granted:
        return True, grant_reason
    return False, grant_reason


def check_action_allowed(
    worker_id: str,
    action: str,
    resource: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """
    Check if an action is allowed for a worker (checks forbidden_actions).
    
    This is a simplified check that only looks at forbidden_actions,
    suitable for use in the autonomy loop where we want to quickly
    filter out forbidden actions.
    
    Args:
        worker_id: ID of the worker
        action: Action to check
        resource: Optional resource being accessed
        context: Optional additional context
        
    Returns:
        Tuple of (is_allowed: bool, reason: str)
    """
    worker_info = get_worker_role(worker_id)
    
    if not worker_info:
        log_access_audit(
            worker_id=worker_id,
            action=action,
            resource=resource or "unknown",
            permission_checked=action,
            decision="denied",
            reason="Worker not found",
            context=context
        )
        return False, "Worker not found in registry"
    
    role_name = worker_info.get("role_name")
    forbidden_actions = worker_info.get("forbidden_actions", [])
    
    # Ensure forbidden_actions is a list
    if isinstance(forbidden_actions, str):
        try:
            forbidden_actions = json.loads(forbidden_actions)
        except (json.JSONDecodeError, TypeError):
            forbidden_actions = []
    
    # Check against forbidden actions
    for pattern in (forbidden_actions or []):
        if pattern == action or action.startswith(pattern.rstrip("*")):
            log_access_audit(
                worker_id=worker_id,
                action=action,
                resource=resource or "unknown",
                permission_checked=action,
                decision="denied",
                role_name=role_name,
                reason=f"Action forbidden by pattern: {pattern}",
                context=context
            )
            return False, f"Action '{action}' is forbidden by pattern '{pattern}'"
    
    # Action is allowed
    log_access_audit(
        worker_id=worker_id,
        action=action,
        resource=resource or "unknown",
        permission_checked=action,
        decision="granted",
        role_name=role_name,
        reason="No forbidden pattern matched",
        context=context
    )
    
    return True, "Action allowed"


def check_task_type_allowed(
    worker_id: str,
    task_type: str,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """
    Check if a worker is allowed to execute a specific task type.
    
    Args:
        worker_id: ID of the worker
        task_type: Type of task (e.g., 'code', 'database', 'scan')
        context: Optional additional context
        
    Returns:
        Tuple of (is_allowed: bool, reason: str)
    """
    worker_info = get_worker_role(worker_id)
    
    if not worker_info:
        log_access_audit(
            worker_id=worker_id,
            action=f"task.{task_type}",
            resource="governance_tasks",
            permission_checked=f"task_type:{task_type}",
            decision="denied",
            reason="Worker not found",
            context=context
        )
        return False, "Worker not found in registry"
    
    role_name = worker_info.get("role_name")
    allowed_task_types = worker_info.get("allowed_task_types", [])
    
    # Ensure allowed_task_types is a list
    if isinstance(allowed_task_types, str):
        try:
            allowed_task_types = json.loads(allowed_task_types)
        except (json.JSONDecodeError, TypeError):
            allowed_task_types = []
    
    # Check if task type is allowed
    is_allowed = False
    reason = "Task type not in allowed list"
    
    if not allowed_task_types:
        # Empty list means no restrictions (depends on role interpretation)
        # For viewer role, empty means no task types allowed
        if role_name == "viewer":
            reason = "Viewer role cannot execute tasks"
        else:
            is_allowed = True
            reason = "No task type restrictions"
    elif "*" in allowed_task_types:
        is_allowed = True
        reason = "All task types allowed (*)"
    elif task_type in allowed_task_types:
        is_allowed = True
        reason = f"Task type '{task_type}' in allowed list"
    
    log_access_audit(
        worker_id=worker_id,
        action=f"task.{task_type}",
        resource="governance_tasks",
        permission_checked=f"task_type:{task_type}",
        decision="granted" if is_allowed else "denied",
        role_name=role_name,
        reason=reason,
        context=context
    )
    
    return is_allowed, reason


def require_permission(permission: str, resource: Optional[str] = None):
    """
    Decorator to require a specific permission for a function.
    
    Usage:
        @require_permission("database.write", "governance_tasks")
        def update_task(worker_id, task_id, data):
            ...
    
    The decorated function MUST have worker_id as its first argument.
    
    Args:
        permission: Required permission
        resource: Optional resource identifier
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(worker_id: str, *args, **kwargs) -> Any:
            is_allowed, reason = check_permission(
                worker_id=worker_id,
                permission=permission,
                resource=resource or func.__name__,
                context={"function": func.__name__, "args_count": len(args)}
            )
            
            if not is_allowed:
                logger.warning(
                    "Permission denied: worker=%s permission=%s reason=%s",
                    worker_id, permission, reason
                )
                raise PermissionError(f"Permission denied: {reason}")
            
            return func(worker_id, *args, **kwargs)
        
        return wrapper
    return decorator


def log_role_change(
    worker_id: str,
    old_role: Optional[str],
    new_role: str,
    changed_by: str,
    reason: Optional[str] = None
) -> Optional[str]:
    """
    Log a role change event to access_audit_log.
    
    Args:
        worker_id: Worker whose role changed
        old_role: Previous role (None if new worker)
        new_role: New role being assigned
        changed_by: Who made the change
        reason: Reason for the change
        
    Returns:
        Audit log ID or None if logging failed
    """
    context = {
        "old_role": old_role,
        "new_role": new_role,
        "changed_by": changed_by,
        "change_type": "role_assignment"
    }
    
    return log_access_audit(
        worker_id=worker_id,
        action="role.change",
        resource="worker_registry",
        permission_checked="role.modify",
        decision="executed",
        role_name=new_role,
        reason=reason or f"Role changed from {old_role} to {new_role}",
        context=context
    )


def get_audit_log(
    worker_id: Optional[str] = None,
    action: Optional[str] = None,
    decision: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Query the access audit log with optional filters.
    
    Args:
        worker_id: Filter by worker ID
        action: Filter by action
        decision: Filter by decision (granted/denied)
        since: Filter by time (records after this time)
        limit: Maximum records to return
        
    Returns:
        List of audit log entries
    """
    conditions = []
    
    if worker_id:
        conditions.append(f"worker_id = '{_escape_string(worker_id)}'")
    if action:
        conditions.append(f"action = '{_escape_string(action)}'")
    if decision:
        conditions.append(f"decision = '{_escape_string(decision)}'")
    if since:
        conditions.append(f"checked_at >= '{since.isoformat()}'")
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    query = f"""
    SELECT 
        id, worker_id, action, resource, role_name,
        permission_checked, decision, reason, context, checked_at
    FROM access_audit_log
    {where_clause}
    ORDER BY checked_at DESC
    LIMIT {limit}
    """
    
    result = _execute_sql(query)
    return result.get("rows", [])


# Export all public functions
__all__ = [
    "check_permission",
    "check_action_allowed",
    "check_task_type_allowed",
    "log_access_audit",
    "require_permission",
    "get_worker_role",
    "get_role_by_name",
    "log_role_change",
    "get_audit_log",
]
