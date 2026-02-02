"""
Audit logging system with immutable hash chain.

This module provides functions for logging auditable events with an immutable
hash chain to ensure log integrity. Each audit log entry includes a hash of
the previous entry, creating a tamper-evident chain.

Usage:
    from core.audit import audit_log
    
    # Log an event
    await audit_log(
        event_type="tool.execution",
        actor_type="worker",
        actor_id="EXECUTOR",
        action="sql_query",
        resource_type="database",
        resource_id="governance_tasks",
        action_details={"query": "SELECT COUNT(*) FROM tasks", "rows_returned": 150},
        success=True,
        duration_ms=45,
        cost_usd=0.001
    )
"""

import json
import logging
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from .database import query_db

logger = logging.getLogger(__name__)

class AuditError(Exception):
    """Exception raised for errors in the audit module."""
    pass

async def audit_log(
    event_type: str,
    actor_type: str,
    actor_id: str,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action_details: Optional[Dict[str, Any]] = None,
    prev_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    cost_usd: Optional[float] = None,
    request_id: Optional[Union[str, UUID]] = None,
    session_id: Optional[Union[str, UUID]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> str:
    """
    Log an auditable event with immutable hash chain.
    
    Args:
        event_type: Type of event (e.g., "tool.execution", "task.create")
        actor_type: Type of actor (e.g., "worker", "user", "system")
        actor_id: ID of the actor
        action: Action performed (e.g., "execute", "create", "update")
        resource_type: Optional type of resource affected
        resource_id: Optional ID of resource affected
        action_details: Optional details about the action
        prev_state: Optional previous state of the resource
        new_state: Optional new state of the resource
        success: Whether the action was successful
        error_message: Optional error message if action failed
        duration_ms: Optional duration of the action in milliseconds
        cost_usd: Optional cost of the action in USD
        request_id: Optional request ID for correlation
        session_id: Optional session ID for correlation
        ip_address: Optional IP address of the actor
        user_agent: Optional user agent of the actor
        
    Returns:
        ID of the created audit log entry
        
    Raises:
        AuditError: If audit logging fails
    """
    log_id = str(uuid4())
    
    try:
        # Convert UUIDs to strings
        if isinstance(request_id, UUID):
            request_id = str(request_id)
        if isinstance(session_id, UUID):
            session_id = str(session_id)
        
        # Execute insert query
        result = await query_db(
            """
            INSERT INTO audit_log (
                id, event_type, actor_type, actor_id, action,
                resource_type, resource_id, action_details,
                prev_state, new_state, success, error_message,
                duration_ms, cost_usd, request_id, session_id,
                ip_address, user_agent
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18
            )
            RETURNING id, current_hash
            """,
            [
                log_id, event_type, actor_type, actor_id, action,
                resource_type, resource_id, 
                json.dumps(action_details) if action_details else None,
                json.dumps(prev_state) if prev_state else None,
                json.dumps(new_state) if new_state else None,
                success, error_message, duration_ms, cost_usd,
                request_id, session_id, ip_address, user_agent
            ]
        )
        
        if not result or "rows" not in result or not result["rows"]:
            raise AuditError("Failed to insert audit log entry")
        
        current_hash = result["rows"][0].get("current_hash")
        logger.debug(f"Audit log entry created: {log_id}, hash: {current_hash}")
        
        return log_id
    except Exception as e:
        logger.error(f"Failed to create audit log entry: {e}")
        raise AuditError(f"Failed to create audit log entry: {e}")

async def verify_audit_log_integrity() -> Dict[str, Any]:
    """
    Verify the integrity of the audit log chain.
    
    Returns:
        Dict with verification results
        
    Raises:
        AuditError: If verification fails
    """
    try:
        result = await query_db(
            """
            SELECT * FROM verify_audit_log_integrity()
            """,
            []
        )
        
        if not result or "rows" not in result:
            raise AuditError("Failed to verify audit log integrity")
        
        invalid_entries = [row for row in result["rows"] if not row.get("hash_valid", True)]
        
        return {
            "valid": len(invalid_entries) == 0,
            "invalid_entries": invalid_entries,
            "total_entries": len(result["rows"]),
            "verified_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to verify audit log integrity: {e}")
        raise AuditError(f"Failed to verify audit log integrity: {e}")

async def get_audit_log_entries(
    actor_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    event_type: Optional[str] = None,
    action: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Get audit log entries with optional filters.
    
    Args:
        actor_id: Optional filter by actor ID
        resource_id: Optional filter by resource ID
        event_type: Optional filter by event type
        action: Optional filter by action
        start_time: Optional filter by start time (ISO format)
        end_time: Optional filter by end time (ISO format)
        limit: Maximum number of entries to return
        offset: Offset for pagination
        
    Returns:
        List of audit log entries
        
    Raises:
        AuditError: If query fails
    """
    try:
        # Build query conditions
        conditions = []
        params = []
        param_index = 1
        
        if actor_id:
            conditions.append(f"actor_id = ${param_index}")
            params.append(actor_id)
            param_index += 1
        
        if resource_id:
            conditions.append(f"resource_id = ${param_index}")
            params.append(resource_id)
            param_index += 1
        
        if event_type:
            conditions.append(f"event_type = ${param_index}")
            params.append(event_type)
            param_index += 1
        
        if action:
            conditions.append(f"action = ${param_index}")
            params.append(action)
            param_index += 1
        
        if start_time:
            conditions.append(f"created_at >= ${param_index}::timestamptz")
            params.append(start_time)
            param_index += 1
        
        if end_time:
            conditions.append(f"created_at <= ${param_index}::timestamptz")
            params.append(end_time)
            param_index += 1
        
        # Build WHERE clause
        where_clause = " AND ".join(conditions)
        if where_clause:
            where_clause = f"WHERE {where_clause}"
        
        # Execute query
        result = await query_db(
            f"""
            SELECT * FROM audit_log
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_index} OFFSET ${param_index + 1}
            """,
            params + [limit, offset]
        )
        
        if not result or "rows" not in result:
            return []
        
        return result["rows"]
    except Exception as e:
        logger.error(f"Failed to get audit log entries: {e}")
        raise AuditError(f"Failed to get audit log entries: {e}")

def compute_hash(data: str) -> str:
    """
    Compute SHA-256 hash of data.
    
    Args:
        data: Data to hash
        
    Returns:
        Hex-encoded hash
    """
    return hashlib.sha256(data.encode()).hexdigest()
