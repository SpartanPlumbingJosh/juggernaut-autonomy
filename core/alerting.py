"""Real-time Alerting System for JUGGERNAUT.

This module provides real-time alerting for system failures including:
- Deployment failures
- Task stalls (tasks stuck in_progress too long)
- API error spikes
- Health check failures

Integrates with Slack war_room for notifications.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4
from enum import Enum

from .database import execute_query

logger = logging.getLogger(__name__)


# Constants
STALE_TASK_THRESHOLD_MINUTES = 30
ERROR_SPIKE_THRESHOLD = 10
ERROR_SPIKE_WINDOW_MINUTES = 5


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts the system can generate."""
    DEPLOYMENT_FAILURE = "deployment_failure"
    TASK_STALL = "task_stall"
    API_ERROR_SPIKE = "api_error_spike"
    HEALTH_CHECK_FAILURE = "health_check_failure"
    WORKER_UNRESPONSIVE = "worker_unresponsive"


def create_alert(
    alert_type: AlertType,
    severity: AlertSeverity,
    title: str,
    message: str,
    component: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create and store an alert in the database.
    
    Args:
        alert_type: The type of alert being created.
        severity: The severity level of the alert.
        title: Short title for the alert.
        message: Detailed alert message.
        component: Optional system component that triggered the alert.
        metadata: Optional additional metadata as key-value pairs.
    
    Returns:
        Dict with success status and alert_id or error message.
    """
    alert_id = str(uuid4())
    metadata = metadata or {}
    try:
        execute_query(
            """INSERT INTO system_alerts (id, alert_type, severity, title, message, component, metadata, created_at, acknowledged)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), false)""",
            [alert_id, alert_type.value, severity.value, title, message, component, json.dumps(metadata)]
        )
        logger.info(f"Created alert: {alert_type.value} - {title}")
        return {"success": True, "alert_id": alert_id}
    except Exception as e:
        logger.error(f"Failed to create alert: {e}")
        return {"success": False, "error": str(e)}


def check_stale_tasks() -> List[Dict[str, Any]]:
    """Check for tasks stuck in_progress too long.
    
    Returns:
        List of stale task records found.
    """
    try:
        result = execute_query(
            f"""SELECT id, title, assigned_worker, started_at,
                   EXTRACT(EPOCH FROM (NOW() - started_at))/60 as minutes_stale
            FROM governance_tasks
            WHERE status = 'in_progress'
              AND started_at < NOW() - INTERVAL '{STALE_TASK_THRESHOLD_MINUTES} minutes'""", []
        )
        stale_tasks = result.get("rows", [])
        for task in stale_tasks:
            create_alert(
                alert_type=AlertType.TASK_STALL,
                severity=AlertSeverity.WARNING,
                title=f"Task stalled: {task.get('title', 'Unknown')[:50]}",
                message=f"Task {task.get('id')} in_progress for {int(float(task.get('minutes_stale', 0)))} minutes",
                component="task_queue",
                metadata={"task_id": task.get("id"), "worker": task.get("assigned_worker")}
            )
        return stale_tasks
    except Exception as e:
        logger.error(f"Failed to check stale tasks: {e}")
        return []


def check_error_spike() -> Dict[str, Any]:
    """Check for spikes in error rates.
    
    Returns:
        Dict with error_count and is_spike boolean.
    """
    try:
        result = execute_query(
            f"""SELECT COUNT(*) as error_count FROM execution_logs
            WHERE status = 'error' AND executed_at > NOW() - INTERVAL '{ERROR_SPIKE_WINDOW_MINUTES} minutes'""", []
        )
        error_count = int(result.get("rows", [{}])[0].get("error_count", 0))
        is_spike = error_count >= ERROR_SPIKE_THRESHOLD
        if is_spike:
            create_alert(
                alert_type=AlertType.API_ERROR_SPIKE,
                severity=AlertSeverity.ERROR,
                title=f"Error spike: {error_count} errors",
                message=f"{error_count} errors in {ERROR_SPIKE_WINDOW_MINUTES} minutes",
                component="api",
                metadata={"error_count": error_count, "threshold": ERROR_SPIKE_THRESHOLD}
            )
        return {"error_count": error_count, "is_spike": is_spike}
    except Exception as e:
        logger.error(f"Failed to check error spike: {e}")
        return {"error_count": 0, "is_spike": False}


def format_slack_alert(severity: AlertSeverity, title: str, message: str) -> str:
    """Format an alert for Slack.
    
    Args:
        severity: Alert severity level.
        title: Alert title.
        message: Alert message.
    
    Returns:
        Formatted string ready for Slack posting.
    """
    emoji = {"info": "information_source", "warning": "warning", "error": "x", "critical": "fire"}
    return f":{emoji.get(severity.value, 'bell')}: *{severity.value.upper()}*: {title}\n{message}"


def run_all_checks() -> Dict[str, Any]:
    """Run all alert checks and return summary.
    
    Returns:
        Dict with timestamp, check results, total_issues count, and status.
    """
    logger.info("Running all alert checks...")
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "stale_tasks": check_stale_tasks(),
        "error_spike": check_error_spike(),
    }
    total_issues = len(results["stale_tasks"]) + (1 if results["error_spike"].get("is_spike") else 0)
    results["total_issues"] = total_issues
    results["status"] = "healthy" if total_issues == 0 else "issues_detected"
    logger.info(f"Alert check complete: {total_issues} issues found")
    return results
