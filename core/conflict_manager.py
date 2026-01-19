"""
JUGGERNAUT Conflict Manager
Level 5: Cross-Team Conflict Management

Detects and resolves resource conflicts between workers.
Implements lock-based resource management with priority-based resolution.
"""

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Configure module logger
logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================

# Lock timeout in seconds (5 minutes default)
LOCK_TIMEOUT_SECONDS: int = 300

# Max lock hold time before auto-release (1 hour)
MAX_LOCK_DURATION_SECONDS: int = 3600

# Escalation delay - how long to wait before escalating unresolved conflicts
ESCALATION_DELAY_SECONDS: int = 60

# Database configuration
NEON_ENDPOINT: str = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
NEON_CONNECTION_STRING: str = (
    "postgresql://neondb_owner:npg_OYkCRU4aze2l@"
    "ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
)


class ConflictResolution(Enum):
    """Possible outcomes of conflict resolution."""
    GRANTED = "granted"
    DENIED = "denied"
    QUEUED = "queued"
    ESCALATED = "escalated"


class LockStatus(Enum):
    """Status of a resource lock."""
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"
    STOLEN = "stolen"


@dataclass
class ResourceLock:
    """Represents a lock on a resource."""
    id: str
    resource_type: str
    resource_id: str
    worker_id: str
    priority: int
    acquired_at: str
    expires_at: str
    status: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ConflictRecord:
    """Records a conflict between workers."""
    id: str
    resource_type: str
    resource_id: str
    requesting_worker: str
    holding_worker: str
    requesting_priority: int
    holding_priority: int
    resolution: str
    resolved_at: Optional[str] = None
    escalated: bool = False


# ============================================================
# DATABASE UTILITIES
# ============================================================

def _query(sql: str) -> Dict[str, Any]:
    """
    Execute SQL query via Neon HTTP API.
    
    Args:
        sql: SQL query string to execute
        
    Returns:
        Dict containing query results with 'rows' and 'rowCount' keys
        
    Raises:
        urllib.error.HTTPError: If HTTP request fails
        json.JSONDecodeError: If response is not valid JSON
    """
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": NEON_CONNECTION_STRING
    }
    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        logger.error("SQL HTTP Error: %s - %s", e.code, error_body)
        raise
    except urllib.error.URLError as e:
        logger.error("SQL URL Error: %s", str(e))
        raise


def _format_value(value: Any) -> str:
    """
    Format a Python value for SQL insertion with proper escaping.
    
    Args:
        value: Any Python value to format
        
    Returns:
        SQL-safe string representation of the value
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


# ============================================================
# LOCK TABLE INITIALIZATION
# ============================================================

def ensure_tables_exist() -> bool:
    """
    Ensure the resource_locks and conflict_log tables exist.
    
    Returns:
        True if tables exist or were created successfully, False otherwise
    """
    create_locks_sql = """
    CREATE TABLE IF NOT EXISTS resource_locks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        resource_type VARCHAR(100) NOT NULL,
        resource_id VARCHAR(255) NOT NULL,
        worker_id VARCHAR(100) NOT NULL,
        priority INTEGER DEFAULT 3,
        acquired_at TIMESTAMPTZ DEFAULT NOW(),
        expires_at TIMESTAMPTZ NOT NULL,
        status VARCHAR(50) DEFAULT 'active',
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(resource_type, resource_id, status) 
            WHERE status = 'active'
    );
    """
    
    create_conflicts_sql = """
    CREATE TABLE IF NOT EXISTS conflict_log (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        resource_type VARCHAR(100) NOT NULL,
        resource_id VARCHAR(255) NOT NULL,
        requesting_worker VARCHAR(100) NOT NULL,
        holding_worker VARCHAR(100) NOT NULL,
        requesting_priority INTEGER NOT NULL,
        holding_priority INTEGER NOT NULL,
        resolution VARCHAR(50) NOT NULL,
        resolved_at TIMESTAMPTZ,
        escalated BOOLEAN DEFAULT FALSE,
        escalation_id UUID,
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """
    
    create_index_sql = """
    CREATE INDEX IF NOT EXISTS idx_resource_locks_active 
        ON resource_locks(resource_type, resource_id) 
        WHERE status = 'active';
    """
    
    try:
        _query(create_locks_sql)
        _query(create_conflicts_sql)
        _query(create_index_sql)
        logger.info("Conflict management tables verified/created")
        return True
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logger.error("Failed to create conflict tables: %s", str(e))
        return False


# ============================================================
# LOCK MANAGEMENT
# ============================================================

def acquire_lock(
    resource_type: str,
    resource_id: str,
    worker_id: str,
    priority: int = 3,
    timeout_seconds: int = LOCK_TIMEOUT_SECONDS,
    metadata: Optional[Dict[str, Any]] = None
) -> Tuple[ConflictResolution, Optional[ResourceLock], Optional[ConflictRecord]]:
    """
    Attempt to acquire a lock on a resource.
    
    Implements priority-based conflict resolution:
    - Higher priority (lower number) wins
    - Equal priority: first come first served
    - Conflicts are logged for audit
    
    Args:
        resource_type: Type of resource (e.g., 'task', 'customer', 'api_endpoint')
        resource_id: Unique identifier of the resource
        worker_id: ID of the worker requesting the lock
        priority: Priority level (1=critical, 5=low). Default 3 (medium)
        timeout_seconds: How long the lock should be held
        metadata: Optional additional data about the lock request
        
    Returns:
        Tuple of (resolution, lock_if_granted, conflict_record_if_any)
    """
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)).isoformat()
    
    # First, clean up expired locks
    _cleanup_expired_locks()
    
    # Check for existing active lock
    existing_lock = get_active_lock(resource_type, resource_id)
    
    if existing_lock is None:
        # No existing lock - grant immediately
        lock = _create_lock(resource_type, resource_id, worker_id, priority, expires_at, metadata)
        if lock:
            logger.info(
                "Lock granted: %s/%s to %s (priority %d)",
                resource_type, resource_id, worker_id, priority
            )
            return ConflictResolution.GRANTED, lock, None
        else:
            logger.error("Failed to create lock for %s/%s", resource_type, resource_id)
            return ConflictResolution.DENIED, None, None
    
    # Lock exists - check if same worker
    if existing_lock.worker_id == worker_id:
        # Same worker - extend the lock
        extended_lock = _extend_lock(existing_lock.id, expires_at)
        if extended_lock:
            logger.info("Lock extended: %s/%s for %s", resource_type, resource_id, worker_id)
            return ConflictResolution.GRANTED, extended_lock, None
        return ConflictResolution.DENIED, None, None
    
    # Different worker holds the lock - CONFLICT
    conflict = _resolve_conflict(
        resource_type=resource_type,
        resource_id=resource_id,
        requesting_worker=worker_id,
        requesting_priority=priority,
        existing_lock=existing_lock,
        new_expires_at=expires_at,
        metadata=metadata
    )
    
    return conflict


def release_lock(
    resource_type: str,
    resource_id: str,
    worker_id: str
) -> bool:
    """
    Release a lock held by a worker.
    
    Args:
        resource_type: Type of resource
        resource_id: Unique identifier of the resource
        worker_id: ID of the worker releasing the lock
        
    Returns:
        True if lock was released, False if not found or not owned
    """
    sql = f"""
    UPDATE resource_locks 
    SET status = 'released', 
        metadata = metadata || {_format_value({"released_at": datetime.now(timezone.utc).isoformat()})}
    WHERE resource_type = {_format_value(resource_type)}
      AND resource_id = {_format_value(resource_id)}
      AND worker_id = {_format_value(worker_id)}
      AND status = 'active'
    RETURNING id
    """
    
    try:
        result = _query(sql)
        if result.get("rowCount", 0) > 0:
            logger.info("Lock released: %s/%s by %s", resource_type, resource_id, worker_id)
            return True
        logger.warning(
            "Lock not found or not owned: %s/%s by %s", 
            resource_type, resource_id, worker_id
        )
        return False
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logger.error("Failed to release lock: %s", str(e))
        return False


def get_active_lock(resource_type: str, resource_id: str) -> Optional[ResourceLock]:
    """
    Get the active lock on a resource if one exists.
    
    Args:
        resource_type: Type of resource
        resource_id: Unique identifier of the resource
        
    Returns:
        ResourceLock if found, None otherwise
    """
    sql = f"""
    SELECT id, resource_type, resource_id, worker_id, priority, 
           acquired_at, expires_at, status, metadata
    FROM resource_locks
    WHERE resource_type = {_format_value(resource_type)}
      AND resource_id = {_format_value(resource_id)}
      AND status = 'active'
      AND expires_at > NOW()
    LIMIT 1
    """
    
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        if rows:
            row = rows[0]
            return ResourceLock(
                id=row["id"],
                resource_type=row["resource_type"],
                resource_id=row["resource_id"],
                worker_id=row["worker_id"],
                priority=row.get("priority", 3),
                acquired_at=row["acquired_at"],
                expires_at=row["expires_at"],
                status=row["status"],
                metadata=row.get("metadata")
            )
        return None
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logger.error("Failed to get active lock: %s", str(e))
        return None


def get_worker_locks(worker_id: str) -> List[ResourceLock]:
    """
    Get all active locks held by a worker.
    
    Args:
        worker_id: ID of the worker
        
    Returns:
        List of ResourceLock objects
    """
    sql = f"""
    SELECT id, resource_type, resource_id, worker_id, priority,
           acquired_at, expires_at, status, metadata
    FROM resource_locks
    WHERE worker_id = {_format_value(worker_id)}
      AND status = 'active'
      AND expires_at > NOW()
    ORDER BY acquired_at
    """
    
    try:
        result = _query(sql)
        locks = []
        for row in result.get("rows", []):
            locks.append(ResourceLock(
                id=row["id"],
                resource_type=row["resource_type"],
                resource_id=row["resource_id"],
                worker_id=row["worker_id"],
                priority=row.get("priority", 3),
                acquired_at=row["acquired_at"],
                expires_at=row["expires_at"],
                status=row["status"],
                metadata=row.get("metadata")
            ))
        return locks
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logger.error("Failed to get worker locks: %s", str(e))
        return []


# ============================================================
# CONFLICT RESOLUTION
# ============================================================

def _resolve_conflict(
    resource_type: str,
    resource_id: str,
    requesting_worker: str,
    requesting_priority: int,
    existing_lock: ResourceLock,
    new_expires_at: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Tuple[ConflictResolution, Optional[ResourceLock], Optional[ConflictRecord]]:
    """
    Resolve a conflict between two workers wanting the same resource.
    
    Resolution rules:
    1. Higher priority (lower number) wins
    2. Equal priority: existing lock holder wins (first come first served)
    3. If resolution impossible, escalate to human
    
    Args:
        resource_type: Type of resource
        resource_id: Unique identifier
        requesting_worker: Worker requesting the lock
        requesting_priority: Priority of request (1-5)
        existing_lock: The current lock holder's lock
        new_expires_at: When the new lock would expire
        metadata: Optional context data
        
    Returns:
        Tuple of (resolution, lock_if_granted, conflict_record)
    """
    conflict_record = None
    resolution = ConflictResolution.DENIED
    granted_lock = None
    
    # Priority comparison: lower number = higher priority
    if requesting_priority < existing_lock.priority:
        # Requester has higher priority - steal the lock
        resolution = ConflictResolution.GRANTED
        
        # Mark old lock as stolen
        _mark_lock_stolen(existing_lock.id, requesting_worker)
        
        # Create new lock
        granted_lock = _create_lock(
            resource_type, resource_id, requesting_worker,
            requesting_priority, new_expires_at, metadata
        )
        
        logger.warning(
            "Lock stolen: %s/%s from %s (priority %d) by %s (priority %d)",
            resource_type, resource_id, existing_lock.worker_id,
            existing_lock.priority, requesting_worker, requesting_priority
        )
    else:
        # Equal or lower priority - deny
        resolution = ConflictResolution.DENIED
        logger.info(
            "Lock denied: %s/%s to %s (priority %d), held by %s (priority %d)",
            resource_type, resource_id, requesting_worker, requesting_priority,
            existing_lock.worker_id, existing_lock.priority
        )
    
    # Log the conflict
    conflict_record = _log_conflict(
        resource_type=resource_type,
        resource_id=resource_id,
        requesting_worker=requesting_worker,
        holding_worker=existing_lock.worker_id,
        requesting_priority=requesting_priority,
        holding_priority=existing_lock.priority,
        resolution=resolution.value,
        metadata=metadata
    )
    
    return resolution, granted_lock, conflict_record


def _log_conflict(
    resource_type: str,
    resource_id: str,
    requesting_worker: str,
    holding_worker: str,
    requesting_priority: int,
    holding_priority: int,
    resolution: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[ConflictRecord]:
    """
    Log a conflict to the conflict_log table.
    
    Args:
        resource_type: Type of resource
        resource_id: Unique identifier
        requesting_worker: Worker who requested
        holding_worker: Worker who held the lock
        requesting_priority: Requester's priority
        holding_priority: Holder's priority
        resolution: How it was resolved
        metadata: Optional context
        
    Returns:
        ConflictRecord if logged successfully, None otherwise
    """
    sql = f"""
    INSERT INTO conflict_log (
        resource_type, resource_id, requesting_worker, holding_worker,
        requesting_priority, holding_priority, resolution, resolved_at, metadata
    ) VALUES (
        {_format_value(resource_type)},
        {_format_value(resource_id)},
        {_format_value(requesting_worker)},
        {_format_value(holding_worker)},
        {requesting_priority},
        {holding_priority},
        {_format_value(resolution)},
        NOW(),
        {_format_value(metadata or {})}
    )
    RETURNING id
    """
    
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        if rows:
            return ConflictRecord(
                id=rows[0]["id"],
                resource_type=resource_type,
                resource_id=resource_id,
                requesting_worker=requesting_worker,
                holding_worker=holding_worker,
                requesting_priority=requesting_priority,
                holding_priority=holding_priority,
                resolution=resolution
            )
        return None
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logger.error("Failed to log conflict: %s", str(e))
        return None


def escalate_conflict(conflict_id: str, reason: str) -> Optional[str]:
    """
    Escalate a conflict to human review.
    
    Args:
        conflict_id: UUID of the conflict to escalate
        reason: Why escalation is needed
        
    Returns:
        Escalation ID if created, None otherwise
    """
    # Create escalation record
    escalation_sql = f"""
    INSERT INTO escalations (
        level, issue_type, description, status, created_at
    ) VALUES (
        'high',
        'resource_conflict',
        {_format_value(f'Resource conflict requires human review: {reason}')},
        'open',
        NOW()
    )
    RETURNING id
    """
    
    try:
        result = _query(escalation_sql)
        rows = result.get("rows", [])
        if rows:
            escalation_id = rows[0]["id"]
            
            # Update conflict record
            update_sql = f"""
            UPDATE conflict_log 
            SET escalated = TRUE, escalation_id = {_format_value(escalation_id)}
            WHERE id = {_format_value(conflict_id)}
            """
            _query(update_sql)
            
            logger.warning("Conflict escalated: %s - %s", conflict_id, reason)
            return escalation_id
        return None
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logger.error("Failed to escalate conflict: %s", str(e))
        return None


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _create_lock(
    resource_type: str,
    resource_id: str,
    worker_id: str,
    priority: int,
    expires_at: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[ResourceLock]:
    """Create a new lock record."""
    sql = f"""
    INSERT INTO resource_locks (
        resource_type, resource_id, worker_id, priority, expires_at, status, metadata
    ) VALUES (
        {_format_value(resource_type)},
        {_format_value(resource_id)},
        {_format_value(worker_id)},
        {priority},
        {_format_value(expires_at)},
        'active',
        {_format_value(metadata or {})}
    )
    RETURNING id, resource_type, resource_id, worker_id, priority, acquired_at, expires_at, status, metadata
    """
    
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        if rows:
            row = rows[0]
            return ResourceLock(
                id=row["id"],
                resource_type=row["resource_type"],
                resource_id=row["resource_id"],
                worker_id=row["worker_id"],
                priority=row.get("priority", 3),
                acquired_at=row["acquired_at"],
                expires_at=row["expires_at"],
                status=row["status"],
                metadata=row.get("metadata")
            )
        return None
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logger.error("Failed to create lock: %s", str(e))
        return None


def _extend_lock(lock_id: str, new_expires_at: str) -> Optional[ResourceLock]:
    """Extend an existing lock's expiration."""
    sql = f"""
    UPDATE resource_locks 
    SET expires_at = {_format_value(new_expires_at)}
    WHERE id = {_format_value(lock_id)}
      AND status = 'active'
    RETURNING id, resource_type, resource_id, worker_id, priority, acquired_at, expires_at, status, metadata
    """
    
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        if rows:
            row = rows[0]
            return ResourceLock(
                id=row["id"],
                resource_type=row["resource_type"],
                resource_id=row["resource_id"],
                worker_id=row["worker_id"],
                priority=row.get("priority", 3),
                acquired_at=row["acquired_at"],
                expires_at=row["expires_at"],
                status=row["status"],
                metadata=row.get("metadata")
            )
        return None
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logger.error("Failed to extend lock: %s", str(e))
        return None


def _mark_lock_stolen(lock_id: str, stolen_by: str) -> bool:
    """Mark a lock as stolen by another worker."""
    sql = f"""
    UPDATE resource_locks 
    SET status = 'stolen',
        metadata = metadata || {_format_value({"stolen_by": stolen_by, "stolen_at": datetime.now(timezone.utc).isoformat()})}
    WHERE id = {_format_value(lock_id)}
    """
    
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logger.error("Failed to mark lock stolen: %s", str(e))
        return False


def _cleanup_expired_locks() -> int:
    """Clean up expired locks."""
    sql = """
    UPDATE resource_locks 
    SET status = 'expired'
    WHERE status = 'active'
      AND expires_at < NOW()
    """
    
    try:
        result = _query(sql)
        count = result.get("rowCount", 0)
        if count > 0:
            logger.info("Cleaned up %d expired locks", count)
        return count
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logger.error("Failed to cleanup expired locks: %s", str(e))
        return 0


# ============================================================
# CONFLICT STATISTICS
# ============================================================

def get_conflict_stats(days: int = 7) -> Dict[str, Any]:
    """
    Get conflict statistics for the specified period.
    
    Args:
        days: Number of days to analyze
        
    Returns:
        Dict with conflict statistics
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    sql = f"""
    SELECT 
        COUNT(*) as total_conflicts,
        SUM(CASE WHEN resolution = 'granted' THEN 1 ELSE 0 END) as granted_count,
        SUM(CASE WHEN resolution = 'denied' THEN 1 ELSE 0 END) as denied_count,
        SUM(CASE WHEN escalated = TRUE THEN 1 ELSE 0 END) as escalated_count,
        COUNT(DISTINCT resource_type || ':' || resource_id) as unique_resources,
        COUNT(DISTINCT requesting_worker) as unique_requesters
    FROM conflict_log
    WHERE created_at >= {_format_value(cutoff)}
    """
    
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        if rows:
            row = rows[0]
            return {
                "period_days": days,
                "total_conflicts": int(row.get("total_conflicts") or 0),
                "granted_count": int(row.get("granted_count") or 0),
                "denied_count": int(row.get("denied_count") or 0),
                "escalated_count": int(row.get("escalated_count") or 0),
                "unique_resources": int(row.get("unique_resources") or 0),
                "unique_requesters": int(row.get("unique_requesters") or 0)
            }
        return {"period_days": days, "total_conflicts": 0}
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logger.error("Failed to get conflict stats: %s", str(e))
        return {"period_days": days, "error": str(e)}
