"""
Health Monitor - System health checks and alerting for L5 autonomy.

Monitors:
- Worker health (heartbeats, stuck tasks)
- Revenue generation progress
- Experiment execution
- Database connectivity
- API availability
- Task queue health
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional


def check_worker_health(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
    alert_threshold_minutes: int = 10
) -> Dict[str, Any]:
    """Check if workers are healthy and heartbeating."""
    try:
        threshold = datetime.now(timezone.utc) - timedelta(minutes=alert_threshold_minutes)
        threshold_str = threshold.isoformat()
        
        sql = f"""
        SELECT 
            worker_id,
            last_heartbeat,
            status,
            current_task_id,
            EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) / 60 as minutes_since_heartbeat
        FROM worker_registry
        WHERE last_heartbeat >= '{threshold_str}'
        ORDER BY last_heartbeat DESC;
        """
        
        result = execute_sql(sql)
        active_workers = result.get("rows", [])
        
        stale_sql = f"""
        SELECT 
            worker_id,
            last_heartbeat,
            status,
            EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) / 60 as minutes_since_heartbeat
        FROM worker_registry
        WHERE last_heartbeat < '{threshold_str}'
        AND status != 'stopped';
        """
        
        stale_result = execute_sql(stale_sql)
        stale_workers = stale_result.get("rows", [])
        
        health_status = {
            "healthy": len(active_workers) > 0,
            "active_workers": len(active_workers),
            "stale_workers": len(stale_workers),
            "workers": active_workers,
            "stale": stale_workers,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
        
        if len(stale_workers) > 0:
            log_action(
                "health.workers_stale",
                f"Warning: {len(stale_workers)} workers have stale heartbeats",
                level="warning",
                output_data={"stale_workers": [w.get("worker_id") for w in stale_workers]}
            )
        
        if len(active_workers) == 0:
            log_action(
                "health.no_active_workers",
                "CRITICAL: No active workers found",
                level="error",
                error_data={"alert": "no_workers"}
            )
        
        return {"success": True, "health": health_status}
        
    except Exception as e:
        log_action(
            "health.check_failed",
            f"Worker health check failed: {str(e)}",
            level="error",
            error_data={"error": str(e)}
        )
        return {"success": False, "error": str(e)}


def check_stuck_tasks(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
    stuck_threshold_minutes: int = 60
) -> Dict[str, Any]:
    """Check for tasks that have been running too long."""
    try:
        threshold = datetime.now(timezone.utc) - timedelta(minutes=stuck_threshold_minutes)
        threshold_str = threshold.isoformat()
        
        sql = f"""
        SELECT 
            id,
            title,
            task_type,
            status,
            started_at,
            EXTRACT(EPOCH FROM (NOW() - started_at)) / 60 as minutes_running
        FROM governance_tasks
        WHERE status = 'running'
        AND started_at < '{threshold_str}'
        ORDER BY started_at ASC
        LIMIT 20;
        """
        
        result = execute_sql(sql)
        stuck_tasks = result.get("rows", [])
        
        if len(stuck_tasks) > 0:
            log_action(
                "health.stuck_tasks_detected",
                f"Warning: {len(stuck_tasks)} tasks running longer than {stuck_threshold_minutes} minutes",
                level="warning",
                output_data={
                    "stuck_count": len(stuck_tasks),
                    "tasks": [{"id": t.get("id"), "title": t.get("title"), "minutes": t.get("minutes_running")} for t in stuck_tasks[:5]]
                }
            )
        
        return {
            "success": True,
            "stuck_tasks": len(stuck_tasks),
            "tasks": stuck_tasks,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        log_action(
            "health.stuck_check_failed",
            f"Stuck task check failed: {str(e)}",
            level="error",
            error_data={"error": str(e)}
        )
        return {"success": False, "error": str(e)}


def check_revenue_generation(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any]
) -> Dict[str, Any]:
    """Check if revenue generation pipeline is healthy."""
    try:
        ideas_sql = """
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'pending') as pending,
            COUNT(*) FILTER (WHERE status = 'approved') as approved,
            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as last_24h
        FROM revenue_ideas;
        """
        
        ideas_result = execute_sql(ideas_sql)
        ideas_stats = (ideas_result.get("rows", [{}])[0] or {})
        
        experiments_sql = """
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'running') as running,
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as last_24h
        FROM experiments;
        """
        
        experiments_result = execute_sql(experiments_sql)
        experiments_stats = (experiments_result.get("rows", [{}])[0] or {})
        
        revenue_sql = """
        SELECT 
            COUNT(*) as event_count,
            SUM(gross_amount) FILTER (WHERE event_type = 'revenue') as total_revenue_cents,
            COUNT(*) FILTER (WHERE recorded_at > NOW() - INTERVAL '24 hours') as last_24h
        FROM revenue_events
        WHERE event_type = 'revenue';
        """
        
        revenue_result = execute_sql(revenue_sql)
        revenue_stats = (revenue_result.get("rows", [{}])[0] or {})
        
        tasks_sql = """
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'pending') as pending,
            COUNT(*) FILTER (WHERE status = 'running') as running,
            COUNT(*) FILTER (WHERE status = 'failed') as failed
        FROM governance_tasks
        WHERE task_type IN ('idea_generation', 'idea_scoring', 'opportunity_scan', 'experiment_review');
        """
        
        tasks_result = execute_sql(tasks_sql)
        tasks_stats = (tasks_result.get("rows", [{}])[0] or {})
        
        health = {
            "ideas": {
                "total": ideas_stats.get("total", 0),
                "pending": ideas_stats.get("pending", 0),
                "approved": ideas_stats.get("approved", 0),
                "last_24h": ideas_stats.get("last_24h", 0)
            },
            "experiments": {
                "total": experiments_stats.get("total", 0),
                "running": experiments_stats.get("running", 0),
                "completed": experiments_stats.get("completed", 0),
                "last_24h": experiments_stats.get("last_24h", 0)
            },
            "revenue": {
                "total_cents": revenue_stats.get("total_revenue_cents", 0) or 0,
                "event_count": revenue_stats.get("event_count", 0),
                "last_24h": revenue_stats.get("last_24h", 0)
            },
            "tasks": {
                "total": tasks_stats.get("total", 0),
                "pending": tasks_stats.get("pending", 0),
                "running": tasks_stats.get("running", 0),
                "failed": tasks_stats.get("failed", 0)
            },
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
        
        if ideas_stats.get("last_24h", 0) == 0 and ideas_stats.get("total", 0) == 0:
            log_action(
                "health.no_ideas_generated",
                "Warning: No revenue ideas generated in last 24 hours",
                level="warning",
                output_data={"alert": "no_ideas"}
            )
        
        if experiments_stats.get("running", 0) == 0 and experiments_stats.get("total", 0) > 0:
            log_action(
                "health.no_running_experiments",
                "Warning: No experiments currently running",
                level="info",
                output_data={"total_experiments": experiments_stats.get("total", 0)}
            )
        
        return {"success": True, "health": health}
        
    except Exception as e:
        log_action(
            "health.revenue_check_failed",
            f"Revenue generation health check failed: {str(e)}",
            level="error",
            error_data={"error": str(e)}
        )
        return {"success": False, "error": str(e)}


def check_database_connectivity(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any]
) -> Dict[str, Any]:
    """Check if database is accessible and responsive."""
    try:
        start_time = datetime.now(timezone.utc)
        result = execute_sql("SELECT NOW() as current_time, version() as pg_version;")
        end_time = datetime.now(timezone.utc)
        
        response_time_ms = (end_time - start_time).total_seconds() * 1000
        
        if result.get("rows"):
            db_info = result["rows"][0]
            return {
                "success": True,
                "healthy": True,
                "response_time_ms": response_time_ms,
                "database_time": db_info.get("current_time"),
                "postgres_version": db_info.get("pg_version"),
                "checked_at": end_time.isoformat()
            }
        else:
            return {"success": False, "healthy": False, "error": "No response from database"}
            
    except Exception as e:
        log_action(
            "health.database_check_failed",
            f"Database connectivity check failed: {str(e)}",
            level="error",
            error_data={"error": str(e)}
        )
        return {"success": False, "healthy": False, "error": str(e)}


def run_full_health_check(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any]
) -> Dict[str, Any]:
    """Run all health checks and return comprehensive status."""
    
    log_action(
        "health.check_started",
        "Running full system health check",
        level="info"
    )
    
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {}
    }
    
    results["checks"]["database"] = check_database_connectivity(execute_sql, log_action)
    results["checks"]["workers"] = check_worker_health(execute_sql, log_action)
    results["checks"]["stuck_tasks"] = check_stuck_tasks(execute_sql, log_action)
    results["checks"]["revenue_generation"] = check_revenue_generation(execute_sql, log_action)
    
    all_healthy = all(
        check.get("success") and check.get("healthy", check.get("health", {}).get("healthy", True))
        for check in results["checks"].values()
    )
    
    results["overall_health"] = "healthy" if all_healthy else "degraded"
    results["success"] = True
    
    critical_issues = []
    warnings = []
    
    if not results["checks"]["database"].get("healthy"):
        critical_issues.append("database_unreachable")
    
    worker_check = results["checks"]["workers"].get("health", {})
    if worker_check.get("active_workers", 0) == 0:
        critical_issues.append("no_active_workers")
    elif worker_check.get("stale_workers", 0) > 0:
        warnings.append(f"{worker_check['stale_workers']}_stale_workers")
    
    stuck_check = results["checks"]["stuck_tasks"]
    if stuck_check.get("stuck_tasks", 0) > 5:
        warnings.append(f"{stuck_check['stuck_tasks']}_stuck_tasks")
    
    results["critical_issues"] = critical_issues
    results["warnings"] = warnings
    
    if critical_issues:
        log_action(
            "health.critical_issues_detected",
            f"CRITICAL: System health issues detected: {', '.join(critical_issues)}",
            level="error",
            error_data={"issues": critical_issues}
        )
    elif warnings:
        log_action(
            "health.warnings_detected",
            f"Warnings detected: {', '.join(warnings)}",
            level="warning",
            output_data={"warnings": warnings}
        )
    else:
        log_action(
            "health.check_completed",
            "System health check completed - all systems healthy",
            level="info",
            output_data={"status": "healthy"}
        )
    
    return results


__all__ = [
    "check_worker_health",
    "check_stuck_tasks",
    "check_revenue_generation",
    "check_database_connectivity",
    "run_full_health_check"
]
