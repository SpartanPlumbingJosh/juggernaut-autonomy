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
    TASK_FAILURE = "task_failure"
    DLQ_ITEM_ADDED = "dlq_item_added"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    BUDGET_THRESHOLD = "budget_threshold"
    DATABASE_ERROR = "database_error"
    EXPERIMENT_FAILURE = "experiment_failure"
    SECURITY_VIOLATION = "security_violation"


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


def check_unresponsive_workers(threshold_minutes: int = 5) -> List[Dict[str, Any]]:
    """Check for workers that haven't sent heartbeats recently.
    
    Args:
        threshold_minutes: Minutes since last heartbeat to consider worker unresponsive.
        
    Returns:
        List of unresponsive worker records.
    """
    try:
        result = execute_query(
            f"""SELECT worker_id, status, last_heartbeat,
                   EXTRACT(EPOCH FROM (NOW() - last_heartbeat))/60 as minutes_since
            FROM worker_registry
            WHERE status = 'active'
              AND last_heartbeat < NOW() - INTERVAL '{threshold_minutes} minutes'""", []
        )
        unresponsive_workers = result.get("rows", [])
        for worker in unresponsive_workers:
            create_alert(
                alert_type=AlertType.WORKER_UNRESPONSIVE,
                severity=AlertSeverity.WARNING if worker.get('minutes_since', 0) < 15 else AlertSeverity.ERROR,
                title=f"Worker unresponsive: {worker.get('worker_id', 'Unknown')}",
                message=f"Worker {worker.get('worker_id')} hasn't sent heartbeat for {int(float(worker.get('minutes_since', 0)))} minutes",
                component="worker_registry",
                metadata={"worker_id": worker.get("worker_id"), "minutes_since": worker.get("minutes_since")}
            )
        return unresponsive_workers
    except Exception as e:
        logger.error(f"Failed to check unresponsive workers: {e}")
        return []


def check_dlq_items() -> Dict[str, Any]:
    """Check for new items in the dead letter queue.
    
    Returns:
        Dict with counts and status.
    """
    try:
        # Check if we have the new DLQ module
        try:
            from .dlq import get_dlq_stats
            stats = get_dlq_stats()
            pending_count = stats.get("pending_count", 0)
        except ImportError:
            # Fall back to direct query
            result = execute_query(
                """SELECT COUNT(*) as pending_count FROM dead_letter_queue
                WHERE status = 'pending'""", []
            )
            pending_count = int(result.get("rows", [{}])[0].get("pending_count", 0))
        
        # Create alert if there are pending items
        if pending_count > 0:
            create_alert(
                alert_type=AlertType.DLQ_ITEM_ADDED,
                severity=AlertSeverity.WARNING if pending_count < 5 else AlertSeverity.ERROR,
                title=f"DLQ has {pending_count} pending items",
                message=f"{pending_count} tasks in dead letter queue need attention",
                component="dead_letter_queue",
                metadata={"pending_count": pending_count}
            )
        
        return {"pending_count": pending_count, "has_pending": pending_count > 0}
    except Exception as e:
        logger.error(f"Failed to check DLQ items: {e}")
        return {"pending_count": 0, "has_pending": False, "error": str(e)}


def check_circuit_breakers() -> Dict[str, Any]:
    """Check for open circuit breakers.
    
    Returns:
        Dict with open circuit breakers and status.
    """
    try:
        # Check if we have the circuit breaker module
        try:
            from .circuit_breaker import _circuit_breakers
            open_circuits = []
            for name, cb in _circuit_breakers.items():
                if cb.is_open:
                    open_circuits.append({
                        "name": name,
                        "failure_count": cb.failure_count,
                        "last_failure_time": cb.last_failure_time.isoformat() if cb.last_failure_time else None
                    })
                    create_alert(
                        alert_type=AlertType.CIRCUIT_BREAKER_OPEN,
                        severity=AlertSeverity.ERROR,
                        title=f"Circuit breaker open: {name}",
                        message=f"Circuit breaker for {name} is OPEN after {cb.failure_count} failures",
                        component=name,
                        metadata={
                            "circuit": name,
                            "failure_count": cb.failure_count,
                            "last_failure": cb.last_failure_time.isoformat() if cb.last_failure_time else None
                        }
                    )
            return {"open_circuits": open_circuits, "count": len(open_circuits)}
        except (ImportError, AttributeError):
            # Circuit breaker module not available
            return {"open_circuits": [], "count": 0, "available": False}
    except Exception as e:
        logger.error(f"Failed to check circuit breakers: {e}")
        return {"open_circuits": [], "count": 0, "error": str(e)}


def check_api_costs(daily_threshold: float = 50.0) -> Dict[str, Any]:
    """Check API costs against budget thresholds.
    
    Args:
        daily_threshold: Daily cost threshold in USD.
        
    Returns:
        Dict with cost metrics and status.
    """
    try:
        result = execute_query(
            """SELECT COALESCE(SUM(cost_usd), 0) as daily_cost
            FROM api_cost_tracking
            WHERE created_at > NOW() - INTERVAL '24 hours'""", []
        )
        daily_cost = float(result.get("rows", [{}])[0].get("daily_cost", 0))
        
        # Get weekly cost too
        result = execute_query(
            """SELECT COALESCE(SUM(cost_usd), 0) as weekly_cost
            FROM api_cost_tracking
            WHERE created_at > NOW() - INTERVAL '7 days'""", []
        )
        weekly_cost = float(result.get("rows", [{}])[0].get("weekly_cost", 0))
        
        # Create alert if over threshold
        if daily_cost > daily_threshold:
            create_alert(
                alert_type=AlertType.BUDGET_THRESHOLD,
                severity=AlertSeverity.WARNING if daily_cost < daily_threshold * 1.5 else AlertSeverity.ERROR,
                title=f"API cost threshold exceeded: ${daily_cost:.2f}",
                message=f"Daily API cost ${daily_cost:.2f} exceeds threshold of ${daily_threshold:.2f}",
                component="api_costs",
                metadata={"daily_cost": daily_cost, "threshold": daily_threshold, "weekly_cost": weekly_cost}
            )
        
        return {
            "daily_cost": daily_cost,
            "weekly_cost": weekly_cost,
            "over_threshold": daily_cost > daily_threshold,
            "threshold": daily_threshold
        }
    except Exception as e:
        logger.error(f"Failed to check API costs: {e}")
        return {"daily_cost": 0, "weekly_cost": 0, "over_threshold": False, "error": str(e)}


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
        "unresponsive_workers": check_unresponsive_workers(),
        "dlq_items": check_dlq_items(),
        "circuit_breakers": check_circuit_breakers(),
        "api_costs": check_api_costs()
    }
    
    # Calculate total issues
    total_issues = (
        len(results["stale_tasks"]) + 
        (1 if results["error_spike"].get("is_spike") else 0) +
        len(results["unresponsive_workers"]) +
        (results["dlq_items"].get("pending_count", 0)) +
        results["circuit_breakers"].get("count", 0) +
        (1 if results["api_costs"].get("over_threshold") else 0)
    )
    
    results["total_issues"] = total_issues
    results["status"] = "healthy" if total_issues == 0 else "issues_detected"
    logger.info(f"Alert check complete: {total_issues} issues found")
    return results
