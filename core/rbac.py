"""
JUGGERNAUT Role-Based Access Control (RBAC)

Provides permission checking with full audit trail.
All access decisions are logged to access_audit_log table.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import _db, log_execution

logger = logging.getLogger(__name__)

# Permission constants
PERMISSION_WILDCARD = "*"


@dataclass
class AccessCheckResult:
    """Result of an access permission check."""
    
    allowed: bool
    worker_id: str
    role_name: Optional[str]
    action: str
    resource: Optional[str]
    permission_checked: str
    reason: str


def get_worker_role(worker_id: str) -> Optional[str]:
    """
    Get the role assigned to a worker.
    
    Args:
        worker_id: The worker's unique identifier
    
    Returns:
        Role name string or None if worker not found
    """
    escaped_worker_id = worker_id.replace("'", "''")
    sql = f"SELECT role_name FROM worker_registry WHERE worker_id = '{escaped_worker_id}'"
    
    try:
        result = _db.query(sql)
        rows = result.get("rows", [])
        if rows and rows[0].get("role_name"):
            return rows[0]["role_name"]
        return None
    except Exception as e:
        logger.error("Failed to get worker role for %s: %s", worker_id, e)
        return None


def get_role_permissions(role_name: str) -> Dict[str, Any]:
    """
    Get the permission configuration for a role.
    
    Args:
        role_name: Name of the role (admin, operator, viewer)
    
    Returns:
        Dict with permissions, forbidden_actions, allowed_task_types, max_risk_level
    """
    escaped_role = role_name.replace("'", "''")
    sql = f"""
        SELECT permissions, forbidden_actions, allowed_task_types, max_risk_level
        FROM roles
        WHERE role_name = '{escaped_role}'
    """
    
    try:
        result = _db.query(sql)
        rows = result.get("rows", [])
        if rows:
            return {
                "permissions": rows[0].get("permissions", []),
                "forbidden_actions": rows[0].get("forbidden_actions", []),
                "allowed_task_types": rows[0].get("allowed_task_types", []),
                "max_risk_level": rows[0].get("max_risk_level", "low")
            }
        return {
            "permissions": [],
            "forbidden_actions": [],
            "allowed_task_types": [],
            "max_risk_level": "low"
        }
    except Exception as e:
        logger.error("Failed to get role permissions for %s: %s", role_name, e)
        return {
            "permissions": [],
            "forbidden_actions": [],
            "allowed_task_types": [],
            "max_risk_level": "low"
        }


def log_access_check(
    worker_id: str,
    action: str,
    resource: Optional[str],
    role_name: Optional[str],
    permission_checked: str,
    decision: str,
    reason: str,
    context: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Log an access check to the audit trail.
    
    Args:
        worker_id: Worker attempting the action
        action: Action being attempted (e.g., 'task.execute')
        resource: Resource being accessed (e.g., task ID)
        role_name: Worker's role at time of check
        permission_checked: Permission string that was checked
        decision: 'allowed' or 'denied'
        reason: Human-readable explanation
        context: Additional context as JSON
    
    Returns:
        Audit log entry UUID or None on failure
    """
    data = {
        "worker_id": worker_id,
        "action": action,
        "resource": resource or "",
        "role_name": role_name or "unknown",
        "permission_checked": permission_checked,
        "decision": decision,
        "reason": reason,
        "context": context or {},
        "checked_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        return _db.insert("access_audit_log", data)
    except Exception as e:
        logger.error("Failed to log access check: %s", e)
        return None


def _permission_matches(required: str, available: List[str]) -> bool:
    """
    Check if a required permission matches any available permission.
    
    Supports wildcard matching:
    - '*' matches everything
    - 'task.*' matches 'task.execute', 'task.create', etc.
    
    Args:
        required: Permission string needed
        available: List of permission strings the role has
    
    Returns:
        True if permission is granted
    """
    if PERMISSION_WILDCARD in available:
        return True
    
    if required in available:
        return True
    
    # Check prefix wildcards (e.g., 'task.*' matches 'task.execute')
    for perm in available:
        if perm.endswith(".*"):
            prefix = perm[:-2]
            if required.startswith(prefix + "."):
                return True
    
    return False


def _action_is_forbidden(action: str, forbidden_list: List[str]) -> bool:
    """
    Check if an action is in the forbidden list.
    
    Supports wildcard matching for forbidden actions.
    
    Args:
        action: Action string to check
        forbidden_list: List of forbidden action patterns
    
    Returns:
        True if action is forbidden
    """
    if action in forbidden_list:
        return True
    
    # Check prefix wildcards
    for forbidden in forbidden_list:
        if forbidden.endswith(".*"):
            prefix = forbidden[:-2]
            if action.startswith(prefix + "."):
                return True
    
    return False


def check_permission(
    worker_id: str,
    action: str,
    resource: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> AccessCheckResult:
    """
    Check if a worker has permission to perform an action.
    
    This is the main entry point for permission checks. It:
    1. Looks up the worker's role
    2. Gets the role's permissions
    3. Checks if the action is allowed
    4. Logs the decision to the audit trail
    5. Returns the result
    
    Args:
        worker_id: Worker attempting the action
        action: Action being attempted (e.g., 'task.execute', 'system.shutdown')
        resource: Optional resource identifier (e.g., task UUID)
        context: Optional additional context for logging
    
    Returns:
        AccessCheckResult with allowed status and details
    """
    # Get worker's role
    role_name = get_worker_role(worker_id)
    
    if not role_name:
        result = AccessCheckResult(
            allowed=False,
            worker_id=worker_id,
            role_name=None,
            action=action,
            resource=resource,
            permission_checked=action,
            reason="Worker not found or has no assigned role"
        )
        log_access_check(
            worker_id=worker_id,
            action=action,
            resource=resource,
            role_name=None,
            permission_checked=action,
            decision="denied",
            reason=result.reason,
            context=context
        )
        log_execution(
            worker_id=worker_id,
            action="rbac.denied",
            message=f"Access denied: {result.reason}",
            level="warn",
            output_data={"action": action, "resource": resource}
        )
        return result
    
    # Get role permissions
    role_config = get_role_permissions(role_name)
    permissions = role_config.get("permissions", [])
    forbidden = role_config.get("forbidden_actions", [])
    
    # Check if action is explicitly forbidden
    if _action_is_forbidden(action, forbidden):
        result = AccessCheckResult(
            allowed=False,
            worker_id=worker_id,
            role_name=role_name,
            action=action,
            resource=resource,
            permission_checked=action,
            reason=f"Action '{action}' is forbidden for role '{role_name}'"
        )
        log_access_check(
            worker_id=worker_id,
            action=action,
            resource=resource,
            role_name=role_name,
            permission_checked=action,
            decision="denied",
            reason=result.reason,
            context=context
        )
        log_execution(
            worker_id=worker_id,
            action="rbac.denied",
            message=f"Access denied: {result.reason}",
            level="warn",
            output_data={"action": action, "resource": resource, "role": role_name}
        )
        return result
    
    # Check if action is permitted
    if _permission_matches(action, permissions):
        result = AccessCheckResult(
            allowed=True,
            worker_id=worker_id,
            role_name=role_name,
            action=action,
            resource=resource,
            permission_checked=action,
            reason=f"Permission granted via role '{role_name}'"
        )
        log_access_check(
            worker_id=worker_id,
            action=action,
            resource=resource,
            role_name=role_name,
            permission_checked=action,
            decision="allowed",
            reason=result.reason,
            context=context
        )
        return result
    
    # Default deny
    result = AccessCheckResult(
        allowed=False,
        worker_id=worker_id,
        role_name=role_name,
        action=action,
        resource=resource,
        permission_checked=action,
        reason=f"Role '{role_name}' does not have permission for action '{action}'"
    )
    log_access_check(
        worker_id=worker_id,
        action=action,
        resource=resource,
        role_name=role_name,
        permission_checked=action,
        decision="denied",
        reason=result.reason,
        context=context
    )
    log_execution(
        worker_id=worker_id,
        action="rbac.denied",
        message=f"Access denied: {result.reason}",
        level="warn",
        output_data={"action": action, "resource": resource, "role": role_name}
    )
    return result


def check_task_type_allowed(
    worker_id: str,
    task_type: str
) -> AccessCheckResult:
    """
    Check if a worker's role allows executing a specific task type.
    
    Args:
        worker_id: Worker attempting to execute the task
        task_type: Type of task (e.g., 'code', 'database', 'scan')
    
    Returns:
        AccessCheckResult with allowed status
    """
    role_name = get_worker_role(worker_id)
    
    if not role_name:
        result = AccessCheckResult(
            allowed=False,
            worker_id=worker_id,
            role_name=None,
            action="task.execute",
            resource=task_type,
            permission_checked=f"task_type:{task_type}",
            reason="Worker not found or has no assigned role"
        )
        log_access_check(
            worker_id=worker_id,
            action="task.execute",
            resource=task_type,
            role_name=None,
            permission_checked=f"task_type:{task_type}",
            decision="denied",
            reason=result.reason
        )
        return result
    
    role_config = get_role_permissions(role_name)
    allowed_types = role_config.get("allowed_task_types", [])
    
    # Wildcard allows all task types
    if PERMISSION_WILDCARD in allowed_types or task_type in allowed_types:
        result = AccessCheckResult(
            allowed=True,
            worker_id=worker_id,
            role_name=role_name,
            action="task.execute",
            resource=task_type,
            permission_checked=f"task_type:{task_type}",
            reason=f"Task type '{task_type}' allowed for role '{role_name}'"
        )
        log_access_check(
            worker_id=worker_id,
            action="task.execute",
            resource=task_type,
            role_name=role_name,
            permission_checked=f"task_type:{task_type}",
            decision="allowed",
            reason=result.reason
        )
        return result
    
    result = AccessCheckResult(
        allowed=False,
        worker_id=worker_id,
        role_name=role_name,
        action="task.execute",
        resource=task_type,
        permission_checked=f"task_type:{task_type}",
        reason=f"Task type '{task_type}' not allowed for role '{role_name}'"
    )
    log_access_check(
        worker_id=worker_id,
        action="task.execute",
        resource=task_type,
        role_name=role_name,
        permission_checked=f"task_type:{task_type}",
        decision="denied",
        reason=result.reason
    )
    log_execution(
        worker_id=worker_id,
        action="rbac.task_type_denied",
        message=f"Task type denied: {result.reason}",
        level="warn",
        output_data={"task_type": task_type, "role": role_name}
    )
    return result


def require_permission(
    worker_id: str,
    action: str,
    resource: Optional[str] = None
) -> None:
    """
    Require a permission, raising PermissionError if denied.
    
    Use this as a guard at the start of protected functions.
    
    Args:
        worker_id: Worker attempting the action
        action: Action being attempted
        resource: Optional resource identifier
    
    Raises:
        PermissionError: If permission is denied
    """
    result = check_permission(worker_id, action, resource)
    if not result.allowed:
        raise PermissionError(
            f"Permission denied for worker '{worker_id}': {result.reason}"
        )


def get_access_audit_log(
    worker_id: Optional[str] = None,
    decision: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Retrieve access audit log entries.
    
    Args:
        worker_id: Filter by worker (optional)
        decision: Filter by decision 'allowed' or 'denied' (optional)
        limit: Maximum entries to return (default: 100)
    
    Returns:
        List of audit log entries
    """
    conditions = []
    if worker_id:
        escaped = worker_id.replace("'", "''")
        conditions.append(f"worker_id = '{escaped}'")
    if decision:
        escaped = decision.replace("'", "''")
        conditions.append(f"decision = '{escaped}'")
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
        SELECT * FROM access_audit_log
        {where_clause}
        ORDER BY checked_at DESC
        LIMIT {limit}
    """
    
    try:
        result = _db.query(sql)
        return result.get("rows", [])
    except Exception as e:
        logger.error("Failed to get access audit log: %s", e)
        return []
