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

from .database import execute_query, log_execution, _db


def _escape_sql_value(val: Any) -> str:
    """Escape a value for SQL insertion."""
    if val is None:
        return "NULL"
    elif isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    elif isinstance(val, (int, float)):
        return str(val)
    elif isinstance(val, (dict, list)):
        return _db._format_value(val)
    else:
        return _db._format_value(str(val))

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
    
    result = execute_query(f"""
        INSERT INTO system_metrics (id, metric_name, value, metric_type, unit, component, worker_id, tags)
        VALUES ({_escape_sql_value(metric_id)}, {_escape_sql_value(metric_name)}, {_escape_sql_value(value)}, {_escape_sql_value(metric_type)}, {_escape_sql_value(unit)}, {_escape_sql_value(component)}, {_escape_sql_value(worker_id)}, {_escape_sql_value(json.dumps(tags))})
        RETURNING id, recorded_at
    """)
    
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
    conditions = [f"metric_name = {_escape_sql_value(metric_name)}", f"recorded_at > NOW() - INTERVAL '{hours} hours'"]
    
    if component:
        conditions.append(f"component = {_escape_sql_value(component)}")
    
    result = execute_query(f"""
        SELECT id, metric_name, value, metric_type, unit, component, 
               worker_id, tags, recorded_at
        FROM system_metrics
        WHERE {' AND '.join(conditions)}
        ORDER BY recorded_at DESC
        LIMIT {limit}
    """)
    
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
    conditions = [f"metric_name = {_escape_sql_value(metric_name)}", f"recorded_at > NOW() - INTERVAL '{hours} hours'"]
    
    if component:
        conditions.append(f"component = {_escape_sql_value(component)}")
    
    result = execute_query(f"""
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
    """)
    
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
    execute_query(f"""
        INSERT INTO health_checks (component, check_type, status, response_time_ms, error_message, last_check_at, consecutive_failures)
        VALUES ({_escape_sql_value(component)}, {_escape_sql_value(check_type)}, {_escape_sql_value(status)}, {_escape_sql_value(response_time)}, {_escape_sql_value(error_message)}, NOW(), CASE WHEN {_escape_sql_value(status)} = 'healthy' THEN 0 ELSE 1 END)
        ON CONFLICT (component, check_type) DO UPDATE SET
            status = EXCLUDED.status,
            response_time_ms = EXCLUDED.response_time_ms,
            error_message = EXCLUDED.error_message,
            last_check_at = NOW(),
            consecutive_failures = CASE 
                WHEN EXCLUDED.status = 'healthy' THEN 0 
                ELSE health_checks.consecutive_failures + 1 
            END
    """)
    
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
    
    result = execute_query(f"""
        INSERT INTO anomaly_events (
            id, anomaly_type, severity, component, metric_name,
            expected_value, actual_value, deviation_percent, description, metadata
        ) VALUES ({_escape_sql_value(anomaly_id)}, {_escape_sql_value(anomaly_type)}, {_escape_sql_value(severity)}, {_escape_sql_value(component)}, {_escape_sql_value(metric_name)},
                  {_escape_sql_value(expected_value)}, {_escape_sql_value(actual_value)}, {_escape_sql_value(deviation_percent)}, {_escape_sql_value(description)}, {_escape_sql_value(json.dumps(metadata or {}))})
        RETURNING id, detected_at
    """)
    
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
    result = execute_query(f"""
        UPDATE anomaly_events
        SET status = {_escape_sql_value(resolution_status)}, resolved_at = NOW(), resolved_by = {_escape_sql_value(resolved_by)}, resolution_notes = {_escape_sql_value(notes)}
        WHERE id = {_escape_sql_value(anomaly_id)}
        RETURNING id, status
    """)
    
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


# =============================================================================
# HEALTH DASHBOARD (INT-03)
# =============================================================================


def get_tasks_per_hour(hours: int = 24) -> List[Dict[str, Any]]:
    """
    Calculate tasks completed per hour for the given time window.
    
    Args:
        hours: Number of hours to analyze (default: 24)
    
    Returns:
        List of hourly task counts with timestamps
    """
    result = execute_query(
        f"""
        SELECT 
            date_trunc('hour', completed_at) as hour,
            COUNT(*) as tasks_completed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as tasks_failed
        FROM governance_tasks
        WHERE completed_at > NOW() - INTERVAL '{hours} hours'
          AND completed_at IS NOT NULL
        GROUP BY date_trunc('hour', completed_at)
        ORDER BY hour DESC
        """
    )
    return result.get("rows", [])


def get_error_rate(hours: int = 24) -> Dict[str, Any]:
    """
    Calculate error rate for tasks and tool executions.
    
    Args:
        hours: Time window for analysis
    
    Returns:
        Dict with error rates for different categories
    """
    # Task error rate
    task_result = execute_query(
        f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
        FROM governance_tasks
        WHERE created_at > NOW() - INTERVAL '{hours} hours'
        """
    )
    
    # Tool execution error rate
    tool_result = execute_query(
        f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
        FROM tool_executions
        WHERE created_at > NOW() - INTERVAL '{hours} hours'
        """
    )
    
    # Execution log error rate
    log_result = execute_query(
        f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN level = 'error' THEN 1 ELSE 0 END) as errors,
            SUM(CASE WHEN level = 'warning' THEN 1 ELSE 0 END) as warnings
        FROM execution_logs
        WHERE created_at > NOW() - INTERVAL '{hours} hours'
        """
    )
    
    task_data = task_result.get("rows", [{}])[0] if task_result.get("rows") else {}
    tool_data = tool_result.get("rows", [{}])[0] if tool_result.get("rows") else {}
    log_data = log_result.get("rows", [{}])[0] if log_result.get("rows") else {}
    
    task_total = int(task_data.get("total") or 0)
    task_failed = int(task_data.get("failed") or 0)
    tool_total = int(tool_data.get("total") or 0)
    tool_failed = int(tool_data.get("failed") or 0)
    
    return {
        "period_hours": hours,
        "tasks": {
            "total": task_total,
            "failed": task_failed,
            "completed": int(task_data.get("completed") or 0),
            "error_rate": round(task_failed / task_total * 100, 2) if task_total > 0 else 0
        },
        "tool_executions": {
            "total": tool_total,
            "failed": tool_failed,
            "completed": int(tool_data.get("completed") or 0),
            "error_rate": round(tool_failed / tool_total * 100, 2) if tool_total > 0 else 0
        },
        "logs": {
            "total": int(log_data.get("total") or 0),
            "errors": int(log_data.get("errors") or 0),
            "warnings": int(log_data.get("warnings") or 0)
        }
    }


def get_feature_usage() -> Dict[str, Any]:
    """
    Get counts of records in key feature tables to show feature usage.
    
    Returns:
        Dict with table counts for learnings, experiments, etc.
    """
    tables_to_check = [
        ("learnings", "Learnings recorded"),
        ("experiments", "Experiments created"),
        ("experiment_results", "Experiment results"),
        ("hypotheses", "Hypotheses tracked"),
        ("opportunities", "Opportunities found"),
        ("goals", "Goals defined"),
        ("governance_tasks", "Tasks processed"),
        ("tool_executions", "Tool executions"),
        ("cost_events", "Cost events tracked"),
        ("execution_logs", "Log entries"),
    ]
    
    feature_counts = {}
    
    for table_name, description in tables_to_check:
        result = execute_query(f"SELECT COUNT(*) as count FROM {table_name}")
        rows = result.get("rows", [])
        count = int(rows[0].get("count", 0)) if rows else 0
        feature_counts[table_name] = {
            "description": description,
            "count": count
        }
    
    # Also get counts from last 24 hours
    recent_counts = {}
    for table_name, description in tables_to_check:
        result = execute_query(
            f"SELECT COUNT(*) as count FROM {table_name} WHERE created_at > NOW() - INTERVAL '24 hours'"
        )
        rows = result.get("rows", [])
        count = int(rows[0].get("count", 0)) if rows else 0
        recent_counts[table_name] = count
    
    return {
        "total_counts": feature_counts,
        "last_24h_counts": recent_counts,
        "generated_at": datetime.utcnow().isoformat()
    }


def get_hourly_trends(hours: int = 24) -> Dict[str, Any]:
    """
    Get hourly breakdown of key metrics for trend visualization.
    
    Args:
        hours: Number of hours of history
    
    Returns:
        Dict with hourly data for tasks, errors, and costs
    """
    # Hourly task completion
    tasks_hourly = execute_query(
        f"""
        SELECT 
            date_trunc('hour', created_at) as hour,
            COUNT(*) as created,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
        FROM governance_tasks
        WHERE created_at > NOW() - INTERVAL '{hours} hours'
        GROUP BY date_trunc('hour', created_at)
        ORDER BY hour
        """
    )
    
    # Hourly errors from logs
    errors_hourly = execute_query(
        f"""
        SELECT 
            date_trunc('hour', created_at) as hour,
            COUNT(*) as total_logs,
            SUM(CASE WHEN level = 'error' THEN 1 ELSE 0 END) as errors
        FROM execution_logs
        WHERE created_at > NOW() - INTERVAL '{hours} hours'
        GROUP BY date_trunc('hour', created_at)
        ORDER BY hour
        """
    )
    
    # Hourly costs
    costs_hourly = execute_query(
        f"""
        SELECT 
            date_trunc('hour', recorded_at) as hour,
            SUM(amount) as total_cost,
            COUNT(*) as cost_events
        FROM cost_events
        WHERE recorded_at > NOW() - INTERVAL '{hours} hours'
        GROUP BY date_trunc('hour', recorded_at)
        ORDER BY hour
        """
    )
    
    return {
        "period_hours": hours,
        "tasks": tasks_hourly.get("rows", []),
        "errors": errors_hourly.get("rows", []),
        "costs": costs_hourly.get("rows", []),
        "generated_at": datetime.utcnow().isoformat()
    }


def check_degradation_alerts() -> List[Dict[str, Any]]:
    """
    Check for system degradation and generate alerts.
    
    Checks:
    - High error rate (>10%)
    - Low task throughput
    - Stale heartbeats
    - Consecutive health check failures
    
    Returns:
        List of alert dictionaries
    """
    alerts = []
    
    # Constants for thresholds
    ERROR_RATE_THRESHOLD = 10.0  # percent
    MIN_TASKS_PER_HOUR = 0  # Allow 0 for quiet periods
    HEARTBEAT_STALE_MINUTES = 30
    CONSECUTIVE_FAILURE_THRESHOLD = 3
    
    # Check error rate
    error_data = get_error_rate(hours=1)
    task_error_rate = error_data.get("tasks", {}).get("error_rate", 0)
    if task_error_rate > ERROR_RATE_THRESHOLD:
        alerts.append({
            "type": "error_rate",
            "severity": "high" if task_error_rate > 25 else "medium",
            "message": f"Task error rate is {task_error_rate}% (threshold: {ERROR_RATE_THRESHOLD}%)",
            "metric_value": task_error_rate,
            "threshold": ERROR_RATE_THRESHOLD
        })
    
    # Check for health check failures
    health_result = execute_query(
        f"""
        SELECT component, check_type, consecutive_failures, error_message
        FROM health_checks
        WHERE consecutive_failures >= {CONSECUTIVE_FAILURE_THRESHOLD}
        """
    )
    for row in health_result.get("rows", []):
        alerts.append({
            "type": "health_check_failure",
            "severity": "high",
            "message": f"{row['component']}/{row['check_type']} has {row['consecutive_failures']} consecutive failures",
            "component": row["component"],
            "error": row.get("error_message")
        })
    
    # Check for stale workers (no recent activity)
    stale_result = execute_query(
        f"""
        SELECT worker_id, last_heartbeat
        FROM worker_registry
        WHERE status = 'active'
          AND last_heartbeat < NOW() - INTERVAL '{HEARTBEAT_STALE_MINUTES} minutes'
        """
    )
    for row in stale_result.get("rows", []):
        alerts.append({
            "type": "stale_worker",
            "severity": "medium",
            "message": f"Worker {row['worker_id']} has not sent heartbeat in {HEARTBEAT_STALE_MINUTES}+ minutes",
            "worker_id": row["worker_id"],
            "last_heartbeat": str(row.get("last_heartbeat"))
        })
    
    # Check for stuck tasks (in_progress for too long)
    stuck_result = execute_query(
        """
        SELECT id, title, assigned_worker, started_at
        FROM governance_tasks
        WHERE status = 'in_progress'
          AND started_at < NOW() - INTERVAL '2 hours'
        """
    )
    for row in stuck_result.get("rows", []):
        alerts.append({
            "type": "stuck_task",
            "severity": "medium",
            "message": f"Task '{row['title']}' has been in_progress for >2 hours",
            "task_id": row["id"],
            "worker": row.get("assigned_worker")
        })
    
    return alerts


def get_health_dashboard() -> Dict[str, Any]:
    """
    Generate comprehensive health monitoring dashboard data.
    
    Provides:
    1. Real-time engine status
    2. Tasks/hour metrics
    3. Error rates
    4. Feature usage statistics
    5. Degradation alerts
    6. Historical trends (24 hours)
    
    Returns:
        Dict with all dashboard data for monitoring UI
    """
    # Get all dashboard components
    health_status = get_health_status()
    error_rates = get_error_rate(hours=24)
    feature_usage = get_feature_usage()
    hourly_trends = get_hourly_trends(hours=24)
    degradation_alerts = check_degradation_alerts()
    tasks_per_hour = get_tasks_per_hour(hours=24)
    
    # Calculate summary metrics
    total_tasks_24h = error_rates.get("tasks", {}).get("total", 0)
    hours_with_data = len([t for t in tasks_per_hour if t.get("tasks_completed", 0) > 0])
    avg_tasks_per_hour = round(total_tasks_24h / 24, 2) if total_tasks_24h > 0 else 0
    
    # Determine overall system status
    if degradation_alerts:
        high_severity = any(a.get("severity") == "high" for a in degradation_alerts)
        overall_status = "critical" if high_severity else "degraded"
    elif health_status.get("overall_status") == "unhealthy":
        overall_status = "unhealthy"
    elif health_status.get("overall_status") == "degraded":
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    return {
        "status": {
            "overall": overall_status,
            "health_check_status": health_status.get("overall_status", "unknown"),
            "active_alerts": len(degradation_alerts),
            "generated_at": datetime.utcnow().isoformat()
        },
        "throughput": {
            "tasks_last_24h": total_tasks_24h,
            "avg_tasks_per_hour": avg_tasks_per_hour,
            "hours_with_activity": hours_with_data,
            "tasks_per_hour_data": tasks_per_hour
        },
        "error_rates": error_rates,
        "feature_usage": feature_usage,
        "health_checks": health_status.get("components", {}),
        "alerts": degradation_alerts,
        "trends": hourly_trends,
        "summary": {
            "total_learnings": feature_usage.get("total_counts", {}).get("learnings", {}).get("count", 0),
            "total_experiments": feature_usage.get("total_counts", {}).get("experiments", {}).get("count", 0),
            "total_tasks": feature_usage.get("total_counts", {}).get("governance_tasks", {}).get("count", 0),
            "tasks_completed_24h": error_rates.get("tasks", {}).get("completed", 0),
            "task_error_rate": error_rates.get("tasks", {}).get("error_rate", 0),
            "tool_executions_24h": error_rates.get("tool_executions", {}).get("total", 0)
        }
    }


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
    
    # Health Dashboard (INT-03)
    "get_tasks_per_hour",
    "get_error_rate",
    "get_feature_usage",
    "get_hourly_trends",
    "check_degradation_alerts",
    "get_health_dashboard",
    
    # Performance
    "get_performance_summary",
    "check_task_queue_health",
    
    # Dashboard
    "get_dashboard_data",
]
import logging
from typing import Dict, Any
from core.database import query_db

def log_transaction_event(event_type: str, message: str, data: Dict[str, Any], level: str = 'info') -> None:
    """Log transaction-related events."""
    try:
        log_method = getattr(logging, level, logging.info)
        log_method(f"[Transaction] {event_type}: {message}")
        
        await query_db(f"""
            INSERT INTO transaction_events (
                id, event_type, message, data, 
                created_at, severity
            ) VALUES (
                gen_random_uuid(),
                '{event_type}',
                '{message.replace("'", "''")}',
                '{json.dumps(data)}',
                NOW(),
                '{level}'
            )
        """)
    except Exception:
        pass

def log_delivery_event(event_type: str, message: str, data: Dict[str, Any], level: str = 'info') -> None:
    """Log delivery-related events."""
    try:
        log_method = getattr(logging, level, logging.info)
        log_method(f"[Delivery] {event_type}: {message}")
        
        await query_db(f"""
            INSERT INTO delivery_events (
                id, event_type, message, data, 
                created_at, severity
            ) VALUES (
                gen_random_uuid(),
                '{event_type}',
                '{message.replace("'", "''")}',
                '{json.dumps(data)}',
                NOW(),
                '{level}'
            )
        """)
    except Exception:
        pass
