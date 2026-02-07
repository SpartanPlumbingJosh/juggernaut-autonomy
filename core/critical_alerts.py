"""
JUGGERNAUT Critical Alerting System

Integrates Slack notifications with critical system events:
1. Worker failures (from watchdog/orchestration)
2. Experiment budget exceeded
3. Task queue backup (>10 pending high priority)
4. Database connection failures

Uses existing SLACK_WEBHOOK_URL environment variable.
"""

import json
import logging
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# M-06: Centralized DB access via core.database
from core.database import query_db as _query

HIGH_PRIORITY_QUEUE_THRESHOLD: int = 10
DATABASE_TIMEOUT_SECONDS: int = 30
BUDGET_WARNING_THRESHOLD: float = 0.8  # 80% of budget

# Module-level cache for slack import
_slack_module_cache: Optional[Any] = None
_slack_module_checked: bool = False


# =============================================================================
# DATABASE UTILITIES
# =============================================================================

# =============================================================================
# ERROR SANITIZATION
# =============================================================================

def _sanitize_error_message(error_message: str) -> str:
    """
    Sanitize error messages to remove sensitive information.
    
    Args:
        error_message: Raw error message
        
    Returns:
        Sanitized error message safe for logging/alerting
    """
    if not error_message:
        return ""
    
    sanitized = error_message
    
    # Redact patterns that look like connection strings
    # Pattern for postgresql:// URLs
    sanitized = re.sub(
        r'postgresql://[^@\s]+@[^\s]+',
        'postgresql://[REDACTED]',
        sanitized
    )
    
    # Pattern for password-like strings
    sanitized = re.sub(
        r'(password|pwd|passwd|secret|token|key|apikey|api_key)[\s]*[=:]\s*[^\s,;]+',
        r'\1=[REDACTED]',
        sanitized,
        flags=re.IGNORECASE
    )
    
    # Redact anything that looks like a credential in a URL
    sanitized = re.sub(
        r'://[^:]+:[^@]+@',
        '://[REDACTED]@',
        sanitized
    )
    
    return sanitized[:500]  # Truncate long errors


# =============================================================================
# SLACK INTEGRATION
# =============================================================================

def _import_slack_notifications() -> Optional[Any]:
    """
    Import slack_notifications module with graceful degradation.
    Caches the import result for efficiency.
    
    Returns:
        Module reference or None if unavailable
    """
    global _slack_module_cache, _slack_module_checked
    
    if _slack_module_checked:
        return _slack_module_cache
    
    try:
        from core import slack_notifications
        _slack_module_cache = slack_notifications
    except ImportError as e:
        logger.warning("slack_notifications module unavailable: %s", e)
        _slack_module_cache = None
    
    _slack_module_checked = True
    return _slack_module_cache


def _send_critical_alert(
    title: str,
    message: str,
    alert_type: str,
    details: Optional[Dict[str, str]] = None
) -> bool:
    """
    Send a critical alert via Slack.
    
    Args:
        title: Alert title
        message: Alert message
        alert_type: Type of alert (error, warning, info)
        details: Additional key-value details
        
    Returns:
        True if sent successfully, False otherwise
    """
    slack = _import_slack_notifications()
    
    if slack is None:
        logger.error("Cannot send alert - slack_notifications unavailable")
        return False
    
    try:
        return slack.send_system_alert(
            alert_type=alert_type,
            component="Critical Alerting",
            message=f"{title}: {message}",
            details=details
        )
    except Exception as e:
        logger.error("Failed to send Slack alert: %s", _sanitize_error_message(str(e)))
        return False


# =============================================================================
# ALERT: WORKER FAILURES
# =============================================================================

def alert_worker_failure(
    worker_id: str,
    worker_name: Optional[str] = None,
    failure_reason: Optional[str] = None,
    consecutive_failures: int = 0
) -> bool:
    """
    Send alert for worker/agent failure.
    
    Called when detect_agent_failures() identifies a failed worker.
    
    Args:
        worker_id: Unique worker identifier
        worker_name: Human-readable worker name
        failure_reason: Reason for failure (if known)
        consecutive_failures: Number of consecutive failures
        
    Returns:
        True if alert sent successfully
    """
    logger.warning(
        "Worker failure detected: %s (name=%s, failures=%d)",
        worker_id,
        worker_name,
        consecutive_failures
    )
    
    details = {
        "Worker ID": worker_id,
        "Worker Name": worker_name or "Unknown",
        "Consecutive Failures": str(consecutive_failures),
        "Detected At": datetime.now(timezone.utc).isoformat()
    }
    
    if failure_reason:
        details["Failure Reason"] = _sanitize_error_message(failure_reason)
    
    return _send_critical_alert(
        title="Worker Failure Detected",
        message=f"Worker '{worker_name or worker_id}' has failed with {consecutive_failures} consecutive failures",
        alert_type="error",
        details=details
    )


def check_and_alert_worker_failures(
    heartbeat_threshold_seconds: int = 120
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Check for worker failures and send alerts for each.
    
    This function can be called periodically in the orchestration loop.
    
    Args:
        heartbeat_threshold_seconds: Seconds since last heartbeat to consider failed
        
    Returns:
        Tuple of (list of failed workers, number of alerts actually sent)
    """
    alerted_workers: List[Dict[str, Any]] = []
    alerts_sent: int = 0
    
    try:
        # Query for workers with consecutive failures or missed heartbeats
        # Use explicit int cast for defense-in-depth
        threshold = int(heartbeat_threshold_seconds)
        failures_sql = f"""
        SELECT worker_id, name, status, last_heartbeat, consecutive_failures
        FROM worker_registry
        WHERE status::text NOT IN ('offline', 'maintenance')
          AND (
            consecutive_failures >= 5 
            OR (last_heartbeat IS NOT NULL 
                AND last_heartbeat < NOW() - INTERVAL '{threshold} seconds')
          )
        """
        
        result = _query(failures_sql)
        
        for worker in result.get("rows", []):
            worker_id = worker.get("worker_id", "unknown")
            worker_name = worker.get("name")
            consecutive_failures = worker.get("consecutive_failures", 0)
            
            # Send alert and track actual success
            if alert_worker_failure(
                worker_id=worker_id,
                worker_name=worker_name,
                consecutive_failures=consecutive_failures
            ):
                alerted_workers.append(worker)
                alerts_sent += 1
        
    except Exception as e:
        safe_error = _sanitize_error_message(str(e))
        logger.error("Failed to check worker failures: %s", safe_error)
        if alert_database_failure("check_worker_failures", str(e)):
            alerts_sent += 1
    
    return alerted_workers, alerts_sent


# =============================================================================
# ALERT: EXPERIMENT BUDGET EXCEEDED
# =============================================================================

def alert_experiment_budget_exceeded(
    experiment_id: str,
    experiment_name: Optional[str] = None,
    budget_spent: float = 0.0,
    budget_limit: float = 0.0
) -> bool:
    """
    Send alert when experiment budget is exceeded.
    
    Called when record_experiment_cost() detects budget exhaustion.
    
    Args:
        experiment_id: Experiment unique identifier
        experiment_name: Human-readable experiment name
        budget_spent: Total amount spent
        budget_limit: Maximum budget allowed
        
    Returns:
        True if alert sent successfully
    """
    logger.warning(
        "Experiment budget exceeded: %s (spent=%.2f, limit=%.2f)",
        experiment_id,
        budget_spent,
        budget_limit
    )
    
    overage = budget_spent - budget_limit
    overage_pct = (overage / budget_limit * 100) if budget_limit > 0 else 0
    
    details = {
        "Experiment ID": experiment_id,
        "Experiment Name": experiment_name or "Unknown",
        "Budget Spent": f"${budget_spent:.2f}",
        "Budget Limit": f"${budget_limit:.2f}",
        "Overage": f"${overage:.2f} ({overage_pct:.1f}%)",
        "Detected At": datetime.now(timezone.utc).isoformat()
    }
    
    return _send_critical_alert(
        title="Experiment Budget Exceeded",
        message=f"Experiment '{experiment_name or experiment_id}' has exceeded its budget",
        alert_type="warning",
        details=details
    )


def alert_experiment_budget_warning(
    experiment_id: str,
    experiment_name: Optional[str] = None,
    budget_spent: float = 0.0,
    budget_limit: float = 0.0,
    threshold_pct: float = 80.0
) -> bool:
    """
    Send warning when experiment approaches budget limit.
    
    Args:
        experiment_id: Experiment unique identifier
        experiment_name: Human-readable experiment name
        budget_spent: Total amount spent
        budget_limit: Maximum budget allowed
        threshold_pct: Warning threshold percentage
        
    Returns:
        True if alert sent successfully
    """
    logger.info(
        "Experiment budget warning: %s at %.1f%% (spent=%.2f, limit=%.2f)",
        experiment_id,
        (budget_spent / budget_limit * 100) if budget_limit > 0 else 0,
        budget_spent,
        budget_limit
    )
    
    remaining = budget_limit - budget_spent
    used_pct = (budget_spent / budget_limit * 100) if budget_limit > 0 else 0
    
    details = {
        "Experiment ID": experiment_id,
        "Experiment Name": experiment_name or "Unknown",
        "Budget Spent": f"${budget_spent:.2f}",
        "Budget Limit": f"${budget_limit:.2f}",
        "Remaining": f"${remaining:.2f}",
        "Used": f"{used_pct:.1f}%"
    }
    
    return _send_critical_alert(
        title=f"Experiment Budget Warning ({threshold_pct:.0f}%)",
        message=f"Experiment '{experiment_name or experiment_id}' has used {used_pct:.1f}% of its budget",
        alert_type="warning",
        details=details
    )


# =============================================================================
# ALERT: TASK QUEUE BACKUP
# =============================================================================

def alert_task_queue_backup(
    pending_count: int,
    high_priority_count: int,
    critical_count: int = 0
) -> bool:
    """
    Send alert when task queue is backing up.
    
    Called when there are too many pending high-priority tasks.
    
    Args:
        pending_count: Total pending tasks
        high_priority_count: Number of high priority pending tasks
        critical_count: Number of critical pending tasks
        
    Returns:
        True if alert sent successfully
    """
    logger.warning(
        "Task queue backup detected: %d pending (%d high, %d critical)",
        pending_count,
        high_priority_count,
        critical_count
    )
    
    details = {
        "Total Pending": str(pending_count),
        "High Priority": str(high_priority_count),
        "Critical Priority": str(critical_count),
        "Threshold": str(HIGH_PRIORITY_QUEUE_THRESHOLD),
        "Detected At": datetime.now(timezone.utc).isoformat()
    }
    
    alert_type = "error" if critical_count > 0 else "warning"
    
    return _send_critical_alert(
        title="Task Queue Backup Detected",
        message=f"{high_priority_count} high-priority tasks pending (threshold: {HIGH_PRIORITY_QUEUE_THRESHOLD})",
        alert_type=alert_type,
        details=details
    )


def check_and_alert_task_queue_backup(
    threshold: int = HIGH_PRIORITY_QUEUE_THRESHOLD
) -> Tuple[Optional[Dict[str, int]], bool]:
    """
    Check task queue status and alert if backup detected.
    
    This function can be called periodically in the orchestration loop.
    
    Args:
        threshold: Number of high-priority tasks to trigger alert
        
    Returns:
        Tuple of (queue status dict if backup detected, alert_sent boolean)
    """
    try:
        queue_sql = """
        SELECT 
            COUNT(*) FILTER (WHERE status = 'pending') as total_pending,
            COUNT(*) FILTER (WHERE status = 'pending' AND priority = 'high') as high_pending,
            COUNT(*) FILTER (WHERE status = 'pending' AND priority = 'critical') as critical_pending
        FROM governance_tasks
        """
        
        result = _query(queue_sql)
        
        if not result.get("rows"):
            return None, False
        
        row = result["rows"][0]
        total_pending = int(row.get("total_pending", 0))
        high_pending = int(row.get("high_pending", 0))
        critical_pending = int(row.get("critical_pending", 0))
        
        # Alert if high priority tasks exceed threshold
        if high_pending >= threshold or critical_pending > 0:
            alert_sent = alert_task_queue_backup(
                pending_count=total_pending,
                high_priority_count=high_pending,
                critical_count=critical_pending
            )
            return {
                "total_pending": total_pending,
                "high_pending": high_pending,
                "critical_pending": critical_pending
            }, alert_sent
        
        return None, False
        
    except Exception as e:
        safe_error = _sanitize_error_message(str(e))
        logger.error("Failed to check task queue: %s", safe_error)
        alert_sent = alert_database_failure("check_task_queue", str(e))
        return None, alert_sent


# =============================================================================
# ALERT: DATABASE CONNECTION FAILURES
# =============================================================================

def alert_database_failure(
    operation: str,
    error_message: str,
    database: str = "neondb"
) -> bool:
    """
    Send alert for database connection failure.
    
    Called when database operations fail due to connectivity issues.
    
    Args:
        operation: Name of the operation that failed
        error_message: Error message from the exception
        database: Database name/identifier
        
    Returns:
        True if alert sent successfully
    """
    # Sanitize error BEFORE logging to prevent credential leaks
    safe_error = _sanitize_error_message(error_message)
    
    logger.error(
        "Database connection failure during %s: %s",
        operation,
        safe_error
    )
    
    details = {
        "Operation": operation,
        "Database": database,
        "Error": safe_error,
        "Detected At": datetime.now(timezone.utc).isoformat()
    }
    
    return _send_critical_alert(
        title="Database Connection Failure",
        message=f"Database operation '{operation}' failed: {safe_error[:100]}",
        alert_type="error",
        details=details
    )


def check_database_connectivity() -> Tuple[bool, bool]:
    """
    Check database connectivity and alert on failure.
    
    Returns:
        Tuple of (is_healthy, alert_sent)
    """
    try:
        result = _query("SELECT 1 as health_check")
        rows = result.get("rows", [])
        if not rows:
            return False, False
        # Handle both integer and string return values
        health_value = rows[0].get("health_check")
        is_healthy = str(health_value) == "1" or health_value == 1
        return is_healthy, False
    except Exception as e:
        alert_sent = alert_database_failure("health_check", str(e))
        return False, alert_sent


# =============================================================================
# ORCHESTRATION LOOP INTEGRATION
# =============================================================================

def run_critical_alerts_check() -> Dict[str, Any]:
    """
    Run all critical alert checks.
    
    This function should be called periodically in the main orchestration loop.
    It checks all alert conditions and sends notifications as needed.
    
    Returns:
        Summary of alerts triggered
    """
    summary: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database_healthy": False,
        "worker_failures": [],
        "queue_backup": None,
        "alerts_sent": 0
    }
    
    # Check database connectivity first
    db_healthy, db_alert_sent = check_database_connectivity()
    summary["database_healthy"] = db_healthy
    if db_alert_sent:
        summary["alerts_sent"] += 1
    
    if not db_healthy:
        return summary  # Skip other checks if database is down
    
    # Check worker failures
    failed_workers, worker_alerts_sent = check_and_alert_worker_failures()
    summary["worker_failures"] = [w.get("worker_id") for w in failed_workers]
    summary["alerts_sent"] += worker_alerts_sent
    
    # Check task queue backup
    queue_status, queue_alert_sent = check_and_alert_task_queue_backup()
    if queue_status:
        summary["queue_backup"] = queue_status
    if queue_alert_sent:
        summary["alerts_sent"] += 1
    
    logger.info(
        "Critical alerts check complete: %d alerts sent",
        summary["alerts_sent"]
    )
    
    return summary


# =============================================================================
# UTILITY FUNCTIONS FOR EXTERNAL INTEGRATION
# =============================================================================

def integrate_with_experiments(
    experiment_id: str,
    budget_spent: float,
    budget_limit: float,
    experiment_name: Optional[str] = None
) -> bool:
    """
    Integration point for experiments.py to call budget alerts.
    
    Call this after recording experiment cost to check thresholds.
    
    Args:
        experiment_id: Experiment identifier
        budget_spent: Current total spent
        budget_limit: Maximum budget
        experiment_name: Optional experiment name
        
    Returns:
        True if alert was sent successfully
    """
    if budget_limit <= 0:
        return False
    
    usage_pct = budget_spent / budget_limit
    
    if usage_pct >= 1.0:
        return alert_experiment_budget_exceeded(
            experiment_id=experiment_id,
            experiment_name=experiment_name,
            budget_spent=budget_spent,
            budget_limit=budget_limit
        )
    elif usage_pct >= BUDGET_WARNING_THRESHOLD:
        return alert_experiment_budget_warning(
            experiment_id=experiment_id,
            experiment_name=experiment_name,
            budget_spent=budget_spent,
            budget_limit=budget_limit,
            threshold_pct=BUDGET_WARNING_THRESHOLD * 100
        )
    
    return False


def integrate_with_orchestration(failed_agents: List[Dict[str, Any]]) -> int:
    """
    Integration point for orchestration.py to call worker failure alerts.
    
    Call this after detect_agent_failures() to alert on each failure.
    
    Args:
        failed_agents: List of failed agent records from detect_agent_failures()
        
    Returns:
        Number of alerts actually sent successfully
    """
    alerts_sent = 0
    
    for agent in failed_agents:
        if alert_worker_failure(
            worker_id=agent.get("worker_id", "unknown"),
            worker_name=agent.get("name"),
            consecutive_failures=agent.get("consecutive_failures", 0)
        ):
            alerts_sent += 1
    
    return alerts_sent
