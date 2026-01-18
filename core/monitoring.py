"""
Phase 5.2: Monitoring System - Proactive Systems

This module provides system health checks, performance monitoring,
anomaly detection, alerting, and dashboard data generation.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4
import statistics

from .database import execute_query, log_execution

# =============================================================================
# METRICS RECORDING
# =============================================================================


def record_metric(
    metric_name: str,
    value: float,
    metric_type: str = "gauge",
    unit: Optional[str] = None,
    component: Optional[str] = None,
    worker_id: Optional[str] = None,
    tags: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Record a system metric.
    
    Args:
        metric_name: Name of the metric (e.g., "api_latency_ms", "tasks_completed")
        value: Numeric value
        metric_type: Type of metric (counter, gauge, histogram, summary)
        unit: Unit of measurement (ms, bytes, count, etc.)
        component: System component (database, api, worker, etc.)
        worker_id: Associated worker if any
        tags: Additional metadata tags
        
    Returns:
        Dict with metric_id
    """
    metric_id = str(uuid4())
    tags = tags or {}
    
    result = execute_query(
        """
        INSERT INTO system_metrics (id, metric_name, value, metric_type, unit, component, worker_id, tags)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id, recorded_at
        """,
        [metric_id, metric_name, value, metric_type, unit, component, worker_id, json.dumps(tags)]
    )
    
    return {
        "success": True,
        "metric_id": metric_id,
        "metric_name": metric_name,
        "value": value
    }


def record_counter(
    metric_name: str,
    increment: int = 1,
    component: Optional[str] = None,
    tags: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Increment a counter metric.
    
    Args:
        metric_name: Counter name
        increment: Amount to increment
        component: System component
        tags: Additional tags
        
    Returns:
        Dict with new counter value
    """
    return record_metric(
        metric_name=metric_name,
        value=increment,
        metric_type="counter",
        unit="count",
        component=component,
        tags=tags
    )


def record_latency(
    metric_name: str,
    latency_ms: float,
    component: Optional[str] = None,
    tags: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Record a latency measurement.
    
    Args:
        metric_name: Metric name
        latency_ms: Latency in milliseconds
        component: System component
        tags: Additional tags
        
    Returns:
        Dict with recorded metric
    """
    return record_metric(
        metric_name=metric_name,
        value=latency_ms,
        metric_type="histogram",
        unit="ms",
        component=component,
        tags=tags
    )


def get_metrics(
    metric_name: str,
    component: Optional[str] = None,
    hours: int = 24,
    limit: int = 1000
) -> List[Dict]:
    """
    Get historical metrics.
    
    Args:
        metric_name: Metric to retrieve
        component: Filter by component
        hours: How many hours back
        limit: Maximum records
        
    Returns:
        List of metric records
    """
    conditions = ["metric_name = $1", f"recorded_at > NOW() - INTERVAL '{hours} hours'"]
    params = [metric_name]
    
    if component:
        conditions.append("component = $2")
        params.append(component)
    
    result = execute_query(
        f"""
        SELECT id, metric_name, value, metric_type, unit, component, 
               worker_id, tags, recorded_at
        FROM system_metrics
        WHERE {' AND '.join(conditions)}
        ORDER BY recorded_at DESC
        LIMIT {limit}
        """,
        params
    )
    
    return result.get("rows", [])


def get_metric_stats(
    metric_name: str,
    component: Optional[str] = None,
    hours: int = 24
) -> Dict[str, Any]:
    """
    Get statistical summary of a metric.
    
    Args:
        metric_name: Metric to analyze
        component: Filter by component
        hours: Time window
        
    Returns:
        Dict with min, max, avg, p50, p95, p99, count
    """
    conditions = ["metric_name = $1", f"recorded_at > NOW() - INTERVAL '{hours} hours'"]
    params = [metric_name]
    
    if component:
        conditions.append("component = $2")
        params.append(component)
    
    result = execute_query(
        f"""
        SELECT 
            COUNT(*) as count,
            MIN(value) as min_val,
            MAX(value) as max_val,
            AVG(value) as avg_val,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY value) as p50,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) as p99
        FROM system_metrics
        WHERE {' AND '.join(conditions)}
        """,
        params
    )
    
    if result.get("rows"):
        row = result["rows"][0]
        return {
            "metric_name": metric_name,
            "hours": hours,
            "count": int(row.get("count", 0)),
            "min": float(row.get("min_val") or 0),
            "max": float(row.get("max_val") or 0),
            "avg": float(row.get("avg_val") or 0),
            "p50": float(row.get("p50") or 0),
            "p95": float(row.get("p95") or 0),
            "p99": float(row.get("p99") or 0)
        }
    
    return {"metric_name": metric_name, "count": 0}


# =============================================================================
# HEALTH CHECKS
# =============================================================================


def run_health_check(
    component: str,
    check_type: str,
    check_function: callable = None
) -> Dict[str, Any]:
    """
    Run a health check for a component.
    
    Args:
        component: Component to check (database, api, worker, etc.)
        check_type: Type of check (connectivity, latency, capacity, etc.)
        check_function: Optional custom check function
        
    Returns:
        Dict with health status
    """
    import time
    start = time.time()
    status = "unknown"
    error_message = None
    
    try:
        if check_function:
            result = check_function()
            status = "healthy" if result.get("success") else "unhealthy"
            error_message = result.get("error")
        else:
            # Default checks by component
            if component == "database":
                result = execute_query("SELECT 1 as health")
                status = "healthy" if result.get("rows") else "unhealthy"
            elif component == "workers":
                result = execute_query(
                    """
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                           SUM(CASE WHEN last_heartbeat > NOW() - INTERVAL '5 minutes' THEN 1 ELSE 0 END) as recent_heartbeat
                    FROM worker_registry
                    """
                )
                if result.get("rows"):
                    row = result["rows"][0]
                    active = int(row.get("active", 0))
                    recent = int(row.get("recent_heartbeat", 0))
                    if recent > 0:
                        status = "healthy"
                    elif active > 0:
                        status = "degraded"
                    else:
                        status = "unhealthy"
            else:
                status = "healthy"  # Default to healthy for unknown components
                
    except Exception as e:
        status = "unhealthy"
        error_message = str(e)
    
    response_time = int((time.time() - start) * 1000)
    
    # Upsert health check record
    execute_query(
        """
        INSERT INTO health_checks (component, check_type, status, response_time_ms, error_message, last_check_at, consecutive_failures)
        VALUES ($1, $2, $3, $4, $5, NOW(), CASE WHEN $3 = 'healthy' THEN 0 ELSE 1 END)
        ON CONFLICT (component, check_type) DO UPDATE SET
            status = EXCLUDED.status,
            response_time_ms = EXCLUDED.response_time_ms,
            error_message = EXCLUDED.error_message,
            last_check_at = NOW(),
            consecutive_failures = CASE 
                WHEN EXCLUDED.status = 'healthy' THEN 0 
                ELSE health_checks.consecutive_failures + 1 
            END
        """,
        [component, check_type, status, response_time, error_message]
    )
    
    return {
        "component": component,
        "check_type": check_type,
        "status": status,
        "response_time_ms": response_time,
        "error": error_message
    }


def check_all_components() -> Dict[str, Any]:
    """
    Run health checks on all known components.
    
    Returns:
        Dict with overall status and component statuses
    """
    components = [
        ("database", "connectivity"),
        ("workers", "status"),
        ("tasks", "queue_health"),
        ("api", "latency"),
    ]
    
    results = {}
    overall_status = "healthy"
    
    for component, check_type in components:
        result = run_health_check(component, check_type)
        results[component] = result
        
        if result["status"] == "unhealthy":
            overall_status = "unhealthy"
        elif result["status"] == "degraded" and overall_status == "healthy":
            overall_status = "degraded"
    
    return {
        "overall_status": overall_status,
        "components": results,
        "checked_at": datetime.utcnow().isoformat()
    }


def get_health_status() -> Dict[str, Any]:
    """
    Get current health status of all components.
    
    Returns:
        Dict with current health states
    """
    result = execute_query(
        """
        SELECT component, check_type, status, response_time_ms, 
               last_check_at, consecutive_failures, error_message
        FROM health_checks
        ORDER BY component, check_type
        """
    )
    
    components = {}
    for row in result.get("rows", []):
        comp = row["component"]
        if comp not in components:
            components[comp] = {}
        components[comp][row["check_type"]] = {
            "status": row["status"],
            "response_time_ms": row.get("response_time_ms"),
            "last_check": row.get("last_check_at"),
            "failures": row.get("consecutive_failures", 0),
            "error": row.get("error_message")
        }
    
    # Determine overall status
    statuses = [check["status"] for comp in components.values() for check in comp.values()]
    if "unhealthy" in statuses:
        overall = "unhealthy"
    elif "degraded" in statuses:
        overall = "degraded"
    elif statuses:
        overall = "healthy"
    else:
        overall = "unknown"
    
    return {
        "overall_status": overall,
        "components": components
    }


# =============================================================================
# ANOMALY DETECTION
# =============================================================================


def detect_anomaly(
    metric_name: str,
    current_value: float,
    component: str,
    baseline_hours: int = 168,  # 1 week
    threshold_std_devs: float = 3.0
) -> Dict[str, Any]:
    """
    Detect if a metric value is anomalous based on historical data.
    
    Args:
        metric_name: Metric to check
        current_value: Current value to evaluate
        component: System component
        baseline_hours: Hours of history to use as baseline
        threshold_std_devs: Number of standard deviations for anomaly
        
    Returns:
        Dict with is_anomaly flag and details
    """
    # Get baseline statistics
    stats = get_metric_stats(metric_name, component, baseline_hours)
    
    if stats["count"] < 10:
        return {
            "is_anomaly": False,
            "reason": "insufficient_data",
            "count": stats["count"]
        }
    
    # Calculate deviation
    avg = stats["avg"]
    if avg == 0:
        return {"is_anomaly": False, "reason": "zero_baseline"}
    
    # Use p95 - p50 as a proxy for standard deviation
    spread = stats["p95"] - stats["p50"]
    if spread == 0:
        spread = abs(avg * 0.1)  # Use 10% of average as fallback
    
    deviation = abs(current_value - avg) / spread if spread > 0 else 0
    deviation_pct = ((current_value - avg) / avg) * 100
    
    is_anomaly = deviation > threshold_std_devs
    
    if is_anomaly:
        # Record anomaly event
        severity = "low"
        if deviation > threshold_std_devs * 2:
            severity = "high"
        elif deviation > threshold_std_devs * 1.5:
            severity = "medium"
        
        record_anomaly(
            anomaly_type="metric_deviation",
            severity=severity,
            component=component,
            metric_name=metric_name,
            expected_value=avg,
            actual_value=current_value,
            deviation_percent=deviation_pct,
            description=f"{metric_name} deviated {deviation_pct:.1f}% from baseline"
        )
    
    return {
        "is_anomaly": is_anomaly,
        "metric_name": metric_name,
        "current_value": current_value,
        "baseline_avg": avg,
        "deviation_std": deviation,
        "deviation_pct": deviation_pct,
        "threshold": threshold_std_devs
    }


def record_anomaly(
    anomaly_type: str,
    severity: str,
    component: str,
    description: str,
    metric_name: Optional[str] = None,
    expected_value: Optional[float] = None,
    actual_value: Optional[float] = None,
    deviation_percent: Optional[float] = None,
    metadata: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Record an anomaly event.
    
    Args:
        anomaly_type: Type (metric_deviation, missing_data, error_spike, etc.)
        severity: low, medium, high, critical
        component: Affected component
        description: Human-readable description
        metric_name: Related metric if any
        expected_value: What was expected
        actual_value: What was observed
        deviation_percent: Percentage deviation
        metadata: Additional context
        
    Returns:
        Dict with anomaly_id
    """
    anomaly_id = str(uuid4())
    
    result = execute_query(
        """
        INSERT INTO anomaly_events (
            id, anomaly_type, severity, component, metric_name,
            expected_value, actual_value, deviation_percent, description, metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id, detected_at
        """,
        [anomaly_id, anomaly_type, severity, component, metric_name,
         expected_value, actual_value, deviation_percent, description,
         json.dumps(metadata or {})]
    )
    
    # Also create system alert for high/critical
    if severity in ("high", "critical"):
        from .error_recovery import create_alert
        create_alert(
            alert_type="anomaly_detected",
            severity=severity,
            message=description,
            component=component,
            metadata={"anomaly_id": anomaly_id}
        )
    
    log_execution(
        worker_id="MONITOR",
        action="anomaly.detected",
        message=f"[{severity.upper()}] {description}",
        level="warning" if severity in ("low", "medium") else "error",
        details={"anomaly_id": anomaly_id, "component": component}
    )
    
    return {
        "success": True,
        "anomaly_id": anomaly_id,
        "severity": severity
    }


def get_open_anomalies(
    severity: Optional[str] = None,
    component: Optional[str] = None,
    limit: int = 50
) -> List[Dict]:
    """
    Get unresolved anomaly events.
    
    Args:
        severity: Filter by severity
        component: Filter by component
        limit: Maximum results
        
    Returns:
        List of open anomalies
    """
    conditions = ["status = 'open'"]
    params = []
    param_idx = 1
    
    if severity:
        conditions.append(f"severity = ${param_idx}")
        params.append(severity)
        param_idx += 1
    if component:
        conditions.append(f"component = ${param_idx}")
        params.append(component)
    
    result = execute_query(
        f"""
        SELECT id, anomaly_type, severity, component, metric_name,
               expected_value, actual_value, deviation_percent,
               description, status, detected_at
        FROM anomaly_events
        WHERE {' AND '.join(conditions)}
        ORDER BY 
            CASE severity 
                WHEN 'critical' THEN 1 
                WHEN 'high' THEN 2 
                WHEN 'medium' THEN 3 
                ELSE 4 
            END,
            detected_at DESC
        LIMIT {limit}
        """,
        params
    )
    
    return result.get("rows", [])


def resolve_anomaly(
    anomaly_id: str,
    resolution_status: str,
    resolved_by: str,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolve an anomaly event.
    
    Args:
        anomaly_id: Anomaly to resolve
        resolution_status: resolved, false_positive, acknowledged
        resolved_by: Who resolved it
        notes: Resolution notes
        
    Returns:
        Dict with resolution status
    """
    result = execute_query(
        """
        UPDATE anomaly_events
        SET status = $2, resolved_at = NOW(), resolved_by = $3, resolution_notes = $4
        WHERE id = $1
        RETURNING id, status
        """,
        [anomaly_id, resolution_status, resolved_by, notes]
    )
    
    return {
        "success": bool(result.get("rows")),
        "anomaly_id": anomaly_id,
        "status": resolution_status
    }


# =============================================================================
# PERFORMANCE MONITORING
# =============================================================================


def get_performance_summary(hours: int = 24) -> Dict[str, Any]:
    """
    Get overall system performance summary.
    
    Args:
        hours: Time window for analysis
        
    Returns:
        Dict with performance metrics
    """
    # Task performance
    tasks_result = execute_query(
        f"""
        SELECT 
            COUNT(*) as total_tasks,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_sec
        FROM governance_tasks
        WHERE created_at > NOW() - INTERVAL '{hours} hours'
        """
    )
    
    # Worker performance
    workers_result = execute_query(
        """
        SELECT 
            COUNT(*) as total_workers,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
            AVG(health_score) as avg_health,
            SUM(tasks_completed) as tasks_completed,
            SUM(tasks_failed) as tasks_failed
        FROM worker_registry
        """
    )
    
    # API costs
    costs_result = execute_query(
        f"""
        SELECT 
            SUM(amount) as total_cost,
            COUNT(*) as api_calls
        FROM cost_events
        WHERE recorded_at > NOW() - INTERVAL '{hours} hours'
        """
    )
    
    # Opportunities
    opps_result = execute_query(
        f"""
        SELECT 
            COUNT(*) as total_opportunities,
            SUM(CASE WHEN status = 'new' THEN 1 ELSE 0 END) as new_opps,
            SUM(estimated_value) as total_pipeline_value
        FROM opportunities
        WHERE created_at > NOW() - INTERVAL '{hours} hours'
        """
    )
    
    return {
        "period_hours": hours,
        "tasks": tasks_result.get("rows", [{}])[0] if tasks_result.get("rows") else {},
        "workers": workers_result.get("rows", [{}])[0] if workers_result.get("rows") else {},
        "costs": costs_result.get("rows", [{}])[0] if costs_result.get("rows") else {},
        "opportunities": opps_result.get("rows", [{}])[0] if opps_result.get("rows") else {},
        "generated_at": datetime.utcnow().isoformat()
    }


def check_task_queue_health() -> Dict[str, Any]:
    """
    Check health of the task queue.
    
    Returns:
        Dict with queue health metrics
    """
    result = execute_query(
        """
        SELECT 
            COUNT(*) FILTER (WHERE status = 'pending') as pending,
            COUNT(*) FILTER (WHERE status = 'running') as running,
            COUNT(*) FILTER (WHERE status = 'failed' AND created_at > NOW() - INTERVAL '1 hour') as recent_failures,
            MAX(created_at) FILTER (WHERE status = 'pending') as oldest_pending,
            AVG(EXTRACT(EPOCH FROM (NOW() - created_at))) FILTER (WHERE status = 'pending') as avg_wait_sec
        FROM governance_tasks
        WHERE status IN ('pending', 'running') OR (status = 'failed' AND created_at > NOW() - INTERVAL '1 hour')
        """
    )
    
    if result.get("rows"):
        row = result["rows"][0]
        pending = int(row.get("pending", 0))
        running = int(row.get("running", 0))
        failures = int(row.get("recent_failures", 0))
        avg_wait = float(row.get("avg_wait_sec") or 0)
        
        # Determine health status
        if pending > 100 or failures > 10:
            status = "unhealthy"
        elif pending > 50 or failures > 5 or avg_wait > 300:
            status = "degraded"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "pending_tasks": pending,
            "running_tasks": running,
            "recent_failures": failures,
            "avg_wait_seconds": round(avg_wait, 1)
        }
    
    return {"status": "healthy", "pending_tasks": 0}


# =============================================================================
# DASHBOARD DATA
# =============================================================================


def get_dashboard_data() -> Dict[str, Any]:
    """
    Generate comprehensive dashboard data for UI.
    
    Returns:
        Dict with all dashboard metrics
    """
    return {
        "health": get_health_status(),
        "performance": get_performance_summary(24),
        "task_queue": check_task_queue_health(),
        "open_anomalies": len(get_open_anomalies(limit=100)),
        "recent_alerts": _get_recent_alerts(limit=10),
        "generated_at": datetime.utcnow().isoformat()
    }


def _get_recent_alerts(limit: int = 10) -> List[Dict]:
    """Get recent system alerts for dashboard."""
    result = execute_query(
        f"""
        SELECT id, alert_type, severity, message, component, status, created_at
        FROM system_alerts
        WHERE created_at > NOW() - INTERVAL '24 hours'
        ORDER BY created_at DESC
        LIMIT {limit}
        """
    )
    return result.get("rows", [])


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Metrics
    "record_metric",
    "record_counter",
    "record_latency",
    "get_metrics",
    "get_metric_stats",
    
    # Health Checks
    "run_health_check",
    "check_all_components",
    "get_health_status",
    
    # Anomaly Detection
    "detect_anomaly",
    "record_anomaly",
    "get_open_anomalies",
    "resolve_anomaly",
    
    # Performance
    "get_performance_summary",
    "check_task_queue_health",
    
    # Dashboard
    "get_dashboard_data",
]
