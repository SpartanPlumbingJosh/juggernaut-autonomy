"""
JUGGERNAUT Error Recovery System
Phase 2.5: Dead letter queue, alerting, graceful degradation
"""

import json
import urllib.request
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta

# Database configuration
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
NEON_CONNECTION_STRING = "postgresql://neondb_owner:npg_OYkCRU4aze2l@ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"


def _query(sql: str) -> Dict[str, Any]:
    """Execute SQL query."""
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": NEON_CONNECTION_STRING
    }
    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
    
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def _format_value(v: Any) -> str:
    """Format value for SQL."""
    if v is None:
        return "NULL"
    elif isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    elif isinstance(v, (int, float)):
        return str(v)
    elif isinstance(v, (dict, list)):
        json_str = json.dumps(v).replace("'", "''")
        return f"'{json_str}'"
    else:
        escaped = str(v).replace("'", "''")
        return f"'{escaped}'"


# ============================================================
# DEAD LETTER QUEUE
# ============================================================

def move_to_dead_letter(
    task_id: str,
    reason: str,
    final_error: str = None,
    metadata: Dict = None
) -> Optional[str]:
    """
    Move a permanently failed task to the dead letter queue.
    
    Tasks are moved here when:
    - Max retries exceeded
    - Unrecoverable error
    - Manual intervention required
    """
    sql = f"""
    INSERT INTO dead_letter_queue (
        original_task_id, reason, final_error, metadata,
        task_snapshot, created_at
    )
    SELECT 
        {_format_value(task_id)},
        {_format_value(reason)},
        {_format_value(final_error)},
        {_format_value(metadata or {})},
        row_to_json(t),
        NOW()
    FROM governance_tasks t
    WHERE id = {_format_value(task_id)}
    RETURNING id
    """
    try:
        result = _query(sql)
        if result.get("rows"):
            # Mark original task as dead-lettered
            _query(f"""
                UPDATE governance_tasks 
                SET status = 'dead_lettered', updated_at = NOW()
                WHERE id = {_format_value(task_id)}
            """)
            return result["rows"][0].get("id")
    except Exception as e:
        print(f"Failed to move to dead letter queue: {e}")
    return None


def get_dead_letter_items(
    status: str = None,
    limit: int = 50,
    include_resolved: bool = False
) -> List[Dict]:
    """Get items from dead letter queue."""
    conditions = []
    if status:
        conditions.append(f"status = {_format_value(status)}")
    if not include_resolved:
        conditions.append("status != 'resolved'")
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
    SELECT * FROM dead_letter_queue 
    {where}
    ORDER BY created_at DESC 
    LIMIT {limit}
    """
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        print(f"Failed to get dead letter items: {e}")
        return []


def resolve_dead_letter(
    dlq_id: str,
    resolution: str,
    resolved_by: str = "JOSH",
    notes: str = None
) -> bool:
    """Mark a dead letter item as resolved."""
    sql = f"""
    UPDATE dead_letter_queue SET
        status = 'resolved',
        resolution = {_format_value(resolution)},
        resolved_by = {_format_value(resolved_by)},
        resolution_notes = {_format_value(notes)},
        resolved_at = NOW()
    WHERE id = {_format_value(dlq_id)}
    """
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        print(f"Failed to resolve dead letter: {e}")
        return False


def retry_dead_letter(dlq_id: str, modified_params: Dict = None) -> Optional[str]:
    """
    Retry a dead-lettered task with optional modified parameters.
    Creates a new task based on the snapshot.
    """
    # Get the original task snapshot
    sql = f"""
    SELECT task_snapshot FROM dead_letter_queue
    WHERE id = {_format_value(dlq_id)}
    """
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        if not rows:
            return None
        
        snapshot = rows[0].get("task_snapshot")
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)
        
        # Merge modified params
        params = snapshot.get("params") or {}
        if modified_params:
            params.update(modified_params)
        
        # Create new task
        new_sql = f"""
        INSERT INTO governance_tasks (
            task_type, title, description, priority, params,
            created_by, goal_id, status, requires_approval,
            created_at, updated_at
        ) VALUES (
            {_format_value(snapshot.get('task_type'))},
            {_format_value(snapshot.get('title', 'Retry of dead-lettered task'))},
            {_format_value(snapshot.get('description'))},
            {_format_value(snapshot.get('priority', 'medium'))},
            {_format_value(params)},
            'RETRY_SYSTEM',
            {_format_value(snapshot.get('goal_id'))},
            'pending',
            {_format_value(snapshot.get('requires_approval', False))},
            NOW(), NOW()
        ) RETURNING id
        """
        
        new_result = _query(new_sql)
        if new_result.get("rows"):
            new_task_id = new_result["rows"][0].get("id")
            
            # Update DLQ record
            _query(f"""
                UPDATE dead_letter_queue SET
                    status = 'retried',
                    retry_task_id = {_format_value(new_task_id)},
                    resolved_at = NOW()
                WHERE id = {_format_value(dlq_id)}
            """)
            
            return new_task_id
    
    except Exception as e:
        print(f"Failed to retry dead letter: {e}")
    return None


# ============================================================
# ALERTING SYSTEM
# ============================================================

def create_alert(
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    source: str = None,
    related_id: str = None,
    metadata: Dict = None
) -> Optional[str]:
    """
    Create a system alert.
    
    Severity levels: info, warning, error, critical
    Alert types: task_failure, worker_unhealthy, cost_limit, system_error, security
    """
    sql = f"""
    INSERT INTO system_alerts (
        alert_type, severity, title, message, source,
        related_id, metadata, status, created_at
    ) VALUES (
        {_format_value(alert_type)},
        {_format_value(severity)},
        {_format_value(title)},
        {_format_value(message)},
        {_format_value(source)},
        {_format_value(related_id)},
        {_format_value(metadata or {})},
        'open',
        NOW()
    ) RETURNING id
    """
    try:
        result = _query(sql)
        if result.get("rows"):
            return result["rows"][0].get("id")
    except Exception as e:
        print(f"Failed to create alert: {e}")
    return None


def get_open_alerts(severity: str = None, limit: int = 50) -> List[Dict]:
    """Get open alerts, optionally filtered by severity."""
    conditions = ["status = 'open'"]
    if severity:
        conditions.append(f"severity = {_format_value(severity)}")
    
    where = f"WHERE {' AND '.join(conditions)}"
    sql = f"""
    SELECT * FROM system_alerts 
    {where}
    ORDER BY 
        CASE severity 
            WHEN 'critical' THEN 1 
            WHEN 'error' THEN 2 
            WHEN 'warning' THEN 3 
            ELSE 4 
        END,
        created_at DESC
    LIMIT {limit}
    """
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        print(f"Failed to get alerts: {e}")
        return []


def acknowledge_alert(alert_id: str, acknowledged_by: str = "SYSTEM") -> bool:
    """Acknowledge an alert (mark as seen but not resolved)."""
    sql = f"""
    UPDATE system_alerts SET
        status = 'acknowledged',
        acknowledged_by = {_format_value(acknowledged_by)},
        acknowledged_at = NOW()
    WHERE id = {_format_value(alert_id)}
    """
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        print(f"Failed to acknowledge alert: {e}")
        return False


def resolve_alert(alert_id: str, resolved_by: str = "SYSTEM", notes: str = None) -> bool:
    """Resolve and close an alert."""
    sql = f"""
    UPDATE system_alerts SET
        status = 'resolved',
        resolved_by = {_format_value(resolved_by)},
        resolution_notes = {_format_value(notes)},
        resolved_at = NOW()
    WHERE id = {_format_value(alert_id)}
    """
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        print(f"Failed to resolve alert: {e}")
        return False


def check_repeated_failures(worker_id: str, threshold: int = 3) -> bool:
    """
    Check if a worker has too many consecutive failures.
    Creates an alert if threshold exceeded.
    """
    sql = f"""
    SELECT consecutive_failures, health_score, name
    FROM worker_registry
    WHERE worker_id = {_format_value(worker_id)}
    """
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        if not rows:
            return False
        
        worker = rows[0]
        failures = worker.get("consecutive_failures", 0)
        
        if failures >= threshold:
            create_alert(
                alert_type="worker_unhealthy",
                severity="warning" if failures < threshold * 2 else "error",
                title=f"Worker {worker.get('name', worker_id)} has repeated failures",
                message=f"Worker has {failures} consecutive failures. Health score: {worker.get('health_score', 0)}",
                source="error_recovery",
                related_id=worker_id,
                metadata={"consecutive_failures": failures, "health_score": worker.get("health_score")}
            )
            return True
        
        return False
    
    except Exception as e:
        print(f"Failed to check failures: {e}")
        return False


# ============================================================
# GRACEFUL DEGRADATION
# ============================================================

def get_fallback_worker(
    task_type: str,
    excluded_workers: List[str] = None
) -> Optional[str]:
    """
    Find a fallback worker for a task type.
    Used when primary worker fails or is unhealthy.
    """
    excluded = excluded_workers or []
    excluded_sql = ""
    if excluded:
        excluded_list = ", ".join([_format_value(w) for w in excluded])
        excluded_sql = f"AND worker_id NOT IN ({excluded_list})"
    
    sql = f"""
    SELECT worker_id, name, health_score
    FROM worker_registry
    WHERE status IN ('active', 'idle')
      AND health_score >= 0.5
      AND (allowed_task_types = '[]'::JSONB OR allowed_task_types @> {_format_value([task_type])})
      {excluded_sql}
    ORDER BY health_score DESC, consecutive_failures ASC
    LIMIT 1
    """
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        if rows:
            return rows[0].get("worker_id")
    except Exception as e:
        print(f"Failed to find fallback worker: {e}")
    return None


def enable_degraded_mode(worker_id: str, reason: str) -> bool:
    """
    Put a worker in degraded mode - limited functionality.
    Worker can still operate but with restrictions.
    """
    sql = f"""
    UPDATE worker_registry SET
        status = 'degraded',
        config = config || {_format_value({"degraded_mode": True, "degraded_reason": reason, "degraded_at": datetime.now(timezone.utc).isoformat()})},
        updated_at = NOW()
    WHERE worker_id = {_format_value(worker_id)}
    """
    try:
        result = _query(sql)
        if result.get("rowCount", 0) > 0:
            create_alert(
                alert_type="worker_degraded",
                severity="warning",
                title=f"Worker {worker_id} entered degraded mode",
                message=reason,
                source="error_recovery",
                related_id=worker_id
            )
            return True
    except Exception as e:
        print(f"Failed to enable degraded mode: {e}")
    return False


def disable_degraded_mode(worker_id: str) -> bool:
    """Restore worker from degraded mode to active."""
    sql = f"""
    UPDATE worker_registry SET
        status = 'active',
        config = config - 'degraded_mode' - 'degraded_reason' - 'degraded_at',
        updated_at = NOW()
    WHERE worker_id = {_format_value(worker_id)}
      AND status = 'degraded'
    """
    try:
        result = _query(sql)
        return result.get("rowCount", 0) > 0
    except Exception as e:
        print(f"Failed to disable degraded mode: {e}")
    return False


def circuit_breaker_open(service: str, failure_count: int, window_minutes: int = 5) -> bool:
    """
    Check if circuit breaker should be opened for a service.
    Returns True if too many failures in the time window.
    """
    sql = f"""
    SELECT COUNT(*) as failure_count
    FROM tool_executions
    WHERE tool_name = {_format_value(service)}
      AND status IN ('failed', 'error')
      AND started_at > NOW() - INTERVAL '{window_minutes} minutes'
    """
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        if rows and rows[0].get("failure_count", 0) >= failure_count:
            return True
    except Exception as e:
        print(f"Failed to check circuit breaker: {e}")
    return False


def get_system_health() -> Dict[str, Any]:
    """
    Get overall system health status.
    Used for monitoring and degradation decisions.
    """
    try:
        # Worker health
        workers_sql = """
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'active') as active,
            COUNT(*) FILTER (WHERE status = 'degraded') as degraded,
            COUNT(*) FILTER (WHERE status IN ('error', 'offline')) as unhealthy,
            AVG(health_score) as avg_health_score
        FROM worker_registry
        """
        workers = _query(workers_sql).get("rows", [{}])[0]
        
        # Task health
        tasks_sql = """
        SELECT 
            COUNT(*) FILTER (WHERE status = 'pending') as pending,
            COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
            COUNT(*) FILTER (WHERE status = 'failed' AND created_at > NOW() - INTERVAL '1 hour') as recent_failures
        FROM governance_tasks
        """
        tasks = _query(tasks_sql).get("rows", [{}])[0]
        
        # Alert health
        alerts_sql = """
        SELECT 
            COUNT(*) FILTER (WHERE severity = 'critical' AND status = 'open') as critical,
            COUNT(*) FILTER (WHERE severity = 'error' AND status = 'open') as errors
        FROM system_alerts
        """
        alerts = _query(alerts_sql).get("rows", [{}])[0]
        
        # Dead letter queue
        dlq_sql = "SELECT COUNT(*) as count FROM dead_letter_queue WHERE status = 'pending'"
        dlq = _query(dlq_sql).get("rows", [{}])[0]
        
        # Determine overall status
        critical_alerts = alerts.get("critical", 0) or 0
        unhealthy_workers = workers.get("unhealthy", 0) or 0
        
        if critical_alerts > 0 or unhealthy_workers > workers.get("total", 1) / 2:
            status = "critical"
        elif alerts.get("errors", 0) or 0 > 0 or workers.get("degraded", 0) or 0 > 0:
            status = "degraded"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "workers": workers,
            "tasks": tasks,
            "alerts": alerts,
            "dead_letter_queue": dlq.get("count", 0),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        return {"status": "unknown", "error": str(e)}
