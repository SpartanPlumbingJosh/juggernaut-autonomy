"""
JUGGERNAUT Real-Time Dashboard API

Provides REST endpoints for the command center dashboard to display:
- Live opportunities being tracked
- Real-time activity/scan logs
- Revenue tracking
- Worker/agent status
- System stats

All data comes from the Neon PostgreSQL database.
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

# ============================================================
# CONFIGURATION
# ============================================================

NEON_ENDPOINT = os.getenv(
    "NEON_ENDPOINT",
    "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
)

DATABASE_URL = os.getenv("DATABASE_URL", "")


# ============================================================
# DATABASE CLIENT
# ============================================================

def execute_dashboard_sql(sql: str) -> Dict[str, Any]:
    """Execute SQL query against Neon database."""
    if not DATABASE_URL:
        return {"error": "DATABASE_URL not configured", "rows": []}
    
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": DATABASE_URL
    }
    
    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(
        NEON_ENDPOINT,
        data=data,
        headers=headers,
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode('utf-8')
        return {"error": f"HTTP {exc.code}: {error_body}", "rows": []}
    except Exception as exc:
        return {"error": str(exc), "rows": []}


# ============================================================
# OPPORTUNITIES API
# ============================================================

def get_opportunities(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Get opportunities from the database.
    
    Args:
        status: Filter by status (new, identified, research_complete, etc.)
        limit: Max results to return
        offset: Pagination offset
    
    Returns:
        Dict with opportunities list and metadata
    """
    where_clause = ""
    if status:
        safe_status = status.replace("'", "''")
        where_clause = f"WHERE status = '{safe_status}'"
    
    sql = f"""
        SELECT 
            id, opportunity_type, category, estimated_value,
            confidence_score, status, stage, description,
            notes, metadata, created_by, created_at, updated_at
        FROM opportunities
        {where_clause}
        ORDER BY 
            CASE status 
                WHEN 'research_complete' THEN 1
                WHEN 'identified' THEN 2
                WHEN 'new' THEN 3
                ELSE 4
            END,
            estimated_value DESC,
            created_at DESC
        LIMIT {int(limit)} OFFSET {int(offset)}
    """
    
    result = execute_dashboard_sql(sql)
    
    if "error" in result:
        return {"success": False, "error": result["error"], "opportunities": []}
    
    count_sql = f"SELECT COUNT(*) as total FROM opportunities {where_clause}"
    count_result = execute_dashboard_sql(count_sql)
    total = 0
    if count_result.get("rows"):
        total = int(count_result["rows"][0].get("total", 0))
    
    return {
        "success": True,
        "opportunities": result.get("rows", []),
        "total": total,
        "limit": limit,
        "offset": offset,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def get_opportunity_stats() -> Dict[str, Any]:
    """Get aggregated opportunity statistics."""
    sql = """
        SELECT 
            status,
            COUNT(*) as count,
            COALESCE(SUM(estimated_value), 0) as total_value,
            COALESCE(AVG(confidence_score), 0) as avg_confidence
        FROM opportunities
        GROUP BY status
    """
    
    result = execute_dashboard_sql(sql)
    
    if "error" in result:
        return {"success": False, "error": result["error"]}
    
    stats = {"by_status": {}, "total_count": 0, "total_potential_value": 0}
    
    for row in result.get("rows", []):
        status = row.get("status", "unknown")
        count = int(row.get("count", 0))
        value = float(row.get("total_value", 0))
        
        stats["by_status"][status] = {
            "count": count,
            "total_value": value,
            "avg_confidence": float(row.get("avg_confidence", 0))
        }
        stats["total_count"] += count
        stats["total_potential_value"] += value
    
    return {
        "success": True,
        "stats": stats,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ============================================================
# ACTIVITY/LOGS API
# ============================================================

def get_activity_feed(limit: int = 50) -> Dict[str, Any]:
    """Get recent activity from execution logs."""
    sql = f"""
        SELECT 
            id, worker_id, level, action, message, output_data, created_at
        FROM execution_logs
        WHERE level IN ('info', 'warning', 'error', 'success')
        ORDER BY created_at DESC
        LIMIT {int(limit)}
    """
    
    result = execute_dashboard_sql(sql)
    
    if "error" in result:
        return {"success": False, "error": result["error"], "activity": []}
    
    activity = []
    for row in result.get("rows", []):
        level = row.get("level", "info")
        activity_type = "info"
        if level == "error":
            activity_type = "error"
        elif level == "warning":
            activity_type = "warning"
        elif "scan" in (row.get("action") or "").lower():
            activity_type = "scan"
        elif "found" in (row.get("message") or "").lower():
            activity_type = "found"
        elif "execut" in (row.get("action") or "").lower():
            activity_type = "execute"
        
        activity.append({
            "id": row.get("id"),
            "type": activity_type,
            "message": row.get("message", ""),
            "agent": row.get("worker_id", "System"),
            "timestamp": row.get("created_at"),
            "data": row.get("output_data")
        })
    
    return {
        "success": True,
        "activity": activity,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ============================================================
# REVENUE API
# ============================================================

def get_revenue_summary() -> Dict[str, Any]:
    """Get revenue summary with today, month, and all-time totals."""
    today = datetime.now(timezone.utc).date()
    month_start = today.replace(day=1)
    
    sql = f"""
        SELECT 
            COALESCE(SUM(CASE WHEN DATE(occurred_at) = '{today}' THEN net_amount ELSE 0 END), 0) as today,
            COALESCE(SUM(CASE WHEN DATE(occurred_at) >= '{month_start}' THEN net_amount ELSE 0 END), 0) as month,
            COALESCE(SUM(net_amount), 0) as all_time,
            COUNT(*) as total_events
        FROM revenue_events
    """
    
    result = execute_dashboard_sql(sql)
    
    if "error" in result:
        return {"success": False, "error": result["error"]}
    
    row = result.get("rows", [{}])[0] if result.get("rows") else {}
    
    return {
        "success": True,
        "revenue": {
            "today": float(row.get("today", 0)),
            "month": float(row.get("month", 0)),
            "all_time": float(row.get("all_time", 0)),
            "goal": 100000000,
            "total_events": int(row.get("total_events", 0))
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def record_revenue(
    amount: float,
    source: str,
    description: str,
    opportunity_id: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> Dict[str, Any]:
    """Record a new revenue event."""
    import uuid
    
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    safe_source = source.replace("'", "''")
    safe_desc = description.replace("'", "''")
    meta_json = json.dumps(metadata or {}).replace("'", "''")
    
    opp_value = f"'{opportunity_id}'" if opportunity_id else "NULL"
    
    sql = f"""
        INSERT INTO revenue_events (
            id, opportunity_id, event_type, revenue_type,
            gross_amount, net_amount, currency, source,
            description, metadata, occurred_at, recorded_at
        ) VALUES (
            '{event_id}', {opp_value}, 'sale', 'one_time',
            {float(amount)}, {float(amount)}, 'USD', '{safe_source}',
            '{safe_desc}', '{meta_json}', '{now}', '{now}'
        )
    """
    
    result = execute_dashboard_sql(sql)
    
    if "error" in result:
        return {"success": False, "error": result["error"]}
    
    return {"success": True, "event_id": event_id, "amount": amount, "timestamp": now}


# ============================================================
# WORKERS/AGENTS API
# ============================================================

def get_workers() -> Dict[str, Any]:
    """Get all registered workers and their status."""
    sql = """
        SELECT 
            worker_id, name, description, level, worker_type, status,
            health_score, last_heartbeat, tasks_completed, tasks_failed,
            current_day_cost_cents, capabilities
        FROM worker_registry
        ORDER BY 
            CASE worker_type WHEN 'orchestrator' THEN 1 WHEN 'monitor' THEN 2 ELSE 3 END,
            worker_id
    """
    
    result = execute_dashboard_sql(sql)
    
    if "error" in result:
        return {"success": False, "error": result["error"], "workers": []}
    
    workers = []
    for row in result.get("rows", []):
        last_hb = row.get("last_heartbeat")
        is_online = False
        if last_hb:
            try:
                hb_time = datetime.fromisoformat(last_hb.replace('Z', '+00:00'))
                is_online = (datetime.now(timezone.utc) - hb_time).total_seconds() < 120
            except Exception:
                pass
        
        workers.append({
            "id": row.get("worker_id"),
            "name": row.get("name"),
            "type": row.get("worker_type"),
            "status": row.get("status"),
            "online": is_online,
            "health_score": float(row.get("health_score", 0)),
            "last_heartbeat": last_hb,
            "tasks_completed": int(row.get("tasks_completed", 0)),
            "tasks_failed": int(row.get("tasks_failed", 0)),
        })
    
    return {"success": True, "workers": workers, "timestamp": datetime.now(timezone.utc).isoformat()}


# ============================================================
# EXPERIMENTS API
# ============================================================

def get_experiments(status: Optional[str] = None) -> Dict[str, Any]:
    """Get experiments and their status."""
    where_clause = ""
    if status:
        safe_status = status.replace("'", "''")
        where_clause = f"WHERE status = '{safe_status}'"
    
    sql = f"""
        SELECT 
            id, name, experiment_type, status, hypothesis,
            budget_limit, budget_spent, current_iteration,
            max_iterations, owner_worker, tags, start_date, created_at
        FROM experiments
        {where_clause}
        ORDER BY created_at DESC
        LIMIT 20
    """
    
    result = execute_dashboard_sql(sql)
    
    if "error" in result:
        return {"success": False, "error": result["error"], "experiments": []}
    
    return {"success": True, "experiments": result.get("rows", []), "timestamp": datetime.now(timezone.utc).isoformat()}


# ============================================================
# TASKS API
# ============================================================

def get_tasks(status: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    """Get tasks from governance queue."""
    where_clause = ""
    if status:
        safe_status = status.replace("'", "''")
        where_clause = f"WHERE status = '{safe_status}'"
    
    sql = f"""
        SELECT 
            id, title, description, task_type, priority, status,
            assigned_worker, created_at, started_at, completed_at
        FROM governance_tasks
        {where_clause}
        ORDER BY 
            CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
            created_at DESC
        LIMIT {int(limit)}
    """
    
    result = execute_dashboard_sql(sql)
    
    if "error" in result:
        return {"success": False, "error": result["error"], "tasks": []}
    
    return {"success": True, "tasks": result.get("rows", []), "timestamp": datetime.now(timezone.utc).isoformat()}


def get_task_stats() -> Dict[str, Any]:
    """Get task statistics by status."""
    sql = "SELECT status, COUNT(*) as count FROM governance_tasks GROUP BY status"
    
    result = execute_dashboard_sql(sql)
    
    if "error" in result:
        return {"success": False, "error": result["error"]}
    
    stats = {}
    for row in result.get("rows", []):
        stats[row.get("status", "unknown")] = int(row.get("count", 0))
    
    return {"success": True, "stats": stats, "total": sum(stats.values()), "timestamp": datetime.now(timezone.utc).isoformat()}


# ============================================================
# COMBINED DASHBOARD STATS
# ============================================================

def get_dashboard_stats() -> Dict[str, Any]:
    """Get all stats needed for the main dashboard in one call."""
    opp_stats = get_opportunity_stats()
    revenue = get_revenue_summary()
    tasks = get_task_stats()
    workers = get_workers()
    
    exp_sql = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running,
            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved
        FROM experiments
    """
    exp_result = execute_dashboard_sql(exp_sql)
    exp_row = exp_result.get("rows", [{}])[0] if exp_result.get("rows") else {}
    
    online_workers = sum(1 for w in workers.get("workers", []) if w.get("online"))
    
    return {
        "success": True,
        "stats": {
            "opportunities": {
                "total": opp_stats.get("stats", {}).get("total_count", 0),
                "potential_value": opp_stats.get("stats", {}).get("total_potential_value", 0),
                "by_status": opp_stats.get("stats", {}).get("by_status", {})
            },
            "revenue": revenue.get("revenue", {}),
            "tasks": {
                "total": tasks.get("total", 0),
                "by_status": tasks.get("stats", {}),
                "pending": tasks.get("stats", {}).get("pending", 0),
                "in_progress": tasks.get("stats", {}).get("in_progress", 0),
                "completed": tasks.get("stats", {}).get("completed", 0)
            },
            "workers": {
                "total": len(workers.get("workers", [])),
                "online": online_workers
            },
            "experiments": {
                "total": int(exp_row.get("total", 0)),
                "running": int(exp_row.get("running", 0)),
                "approved": int(exp_row.get("approved", 0))
            }
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ============================================================
# ENDPOINT ROUTING
# ============================================================

DASHBOARD_ENDPOINTS = {
    "stats": get_dashboard_stats,
    "opportunities": get_opportunities,
    "opportunity_stats": get_opportunity_stats,
    "activity": get_activity_feed,
    "revenue": get_revenue_summary,
    "workers": get_workers,
    "experiments": get_experiments,
    "tasks": get_tasks,
    "task_stats": get_task_stats,
}


def handle_dashboard_request(endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """Route dashboard API requests to appropriate handler."""
    params = params or {}
    
    if endpoint not in DASHBOARD_ENDPOINTS:
        return {"success": False, "error": f"Unknown endpoint: {endpoint}", "available": list(DASHBOARD_ENDPOINTS.keys())}
    
    func = DASHBOARD_ENDPOINTS[endpoint]
    
    try:
        import inspect
        sig = inspect.signature(func)
        if sig.parameters:
            valid_params = {k: v for k, v in params.items() if k in sig.parameters}
            return func(**valid_params)
        return func()
    except Exception as exc:
        return {"success": False, "error": str(exc)}
