"""
JUGGERNAUT Public Dashboard API - No Auth Required

These endpoints are safe to call directly from the browser.
They are READ-ONLY mirrors of the internal dashboard endpoints.
Write operations still require auth through /internal/dashboard/*.
"""

import time
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request

from api.dashboard import query_db, validate_uuid


class _TTLCache:
    """Simple TTL cache for reducing database load."""

    def __init__(self) -> None:
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, value = item
        if time.time() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._store[key] = (time.time() + ttl_seconds, value)


_cache = _TTLCache()
router = APIRouter(prefix="/public/dashboard")


def _sql_escape(value: str) -> str:
    return str(value).replace("'", "''")


def _sql_quote(value: Optional[str]) -> str:
    if value is None:
        return "NULL"
    return f"'{_sql_escape(value)}'"


# ============================================================================
# READ-ONLY PUBLIC ENDPOINTS (No Auth Required)
# ============================================================================


@router.get("/tasks")
def public_tasks(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    """Get task list - no auth required."""
    safe_limit = max(1, min(int(limit), 200))
    safe_status = (status or "").replace("'", "''")
    cache_key = f"pub_tasks:{safe_limit}:{safe_status}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    where = f"WHERE status::text = '{safe_status}'" if safe_status else ""

    sql = f"""
        SELECT
            id,
            title,
            description,
            status::text as status,
            priority::text as priority,
            assigned_worker,
            created_at,
            updated_at,
            completed_at
        FROM governance_tasks
        {where}
        ORDER BY created_at DESC
        LIMIT {safe_limit}
    """

    count_sql = f"SELECT COUNT(*) as total FROM governance_tasks {where}"

    rows = query_db(sql).get("rows", [])
    count_rows = query_db(count_sql).get("rows", [])
    total = int((count_rows[0] or {}).get("total", 0)) if count_rows else 0

    result = {
        "success": True,
        "tasks": rows,
        "total": total,
    }
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/tasks/{task_id}")
def public_task_get(
    task_id: str,
    cache_seconds: int = 2,
) -> Dict[str, Any]:
    """Get single task details - no auth required."""
    cache_key = f"pub_task:{task_id}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    rows = query_db(f"SELECT * FROM governance_tasks WHERE id = {_sql_quote(task_id)} LIMIT 1").get("rows", [])
    if not rows:
        return {"success": False, "error": "Task not found"}

    result = {"success": True, "task": rows[0]}
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/tasks/{task_id}/children")
def public_task_children(
    task_id: str,
    cache_seconds: int = 2,
) -> Dict[str, Any]:
    """Get task children - no auth required."""
    cache_key = f"pub_task_children:{task_id}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    sql = f"""
        SELECT
          id,
          title,
          description,
          status::text as status,
          priority::text as priority,
          assigned_worker,
          parent_task_id,
          root_task_id,
          created_at,
          updated_at,
          started_at,
          completed_at,
          (SELECT COUNT(*)::int FROM governance_tasks c WHERE c.parent_task_id = governance_tasks.id) as child_count
        FROM governance_tasks
        WHERE parent_task_id = {_sql_quote(task_id)}
        ORDER BY created_at ASC
    """
    rows = query_db(sql).get("rows", [])
    result = {"success": True, "tasks": rows}
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/workers")
def public_workers(
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    """Get worker list - no auth required."""
    cache_key = "pub_workers"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    sql = """
        SELECT
            worker_id,
            worker_type,
            status::text as status,
            capabilities,
            last_heartbeat,
            tasks_completed,
            tasks_failed,
            health_score,
            created_at
        FROM worker_registry
        ORDER BY worker_id
    """

    rows = query_db(sql).get("rows", [])
    result = {
        "success": True,
        "workers": rows,
    }
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/workers/{worker_id}/activity")
def public_worker_activity(
    worker_id: str,
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    """Get worker activity - no auth required."""
    cache_key = f"pub_worker_activity:{worker_id}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    workers = query_db(
        f"""
        SELECT worker_id, status::text as status, tasks_completed, tasks_failed, last_heartbeat, health_score
        FROM worker_registry
        WHERE worker_id = {_sql_quote(worker_id)}
        LIMIT 1
        """
    ).get("rows", [])

    if not workers:
        return {"success": False, "error": "Worker not found"}
    w = workers[0]

    current_task = query_db(
        f"""
        SELECT id, title
        FROM governance_tasks
        WHERE assigned_worker = {_sql_quote(worker_id)}
          AND status IN ('in_progress','running','claimed')
        ORDER BY updated_at DESC
        LIMIT 1
        """
    ).get("rows", [])

    recent_tools = query_db(
        f"""
        SELECT DISTINCT action
        FROM execution_logs
        WHERE worker_id = {_sql_quote(worker_id)}
          AND created_at > NOW() - INTERVAL '5 minutes'
          AND action IS NOT NULL
        LIMIT 10
        """
    ).get("rows", [])

    result = {
        "success": True,
        "worker_id": w.get("worker_id"),
        "status": w.get("status"),
        "current_task_id": (current_task[0] or {}).get("id") if current_task else None,
        "current_task_title": (current_task[0] or {}).get("title") if current_task else None,
        "active_tools": [r.get("action") for r in recent_tools if r.get("action")],
        "last_heartbeat": w.get("last_heartbeat"),
        "tasks_completed": int(w.get("tasks_completed") or 0),
        "tasks_failed": int(w.get("tasks_failed") or 0),
        "health_score": float(w.get("health_score") or 1.0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/logs")
def public_logs(
    limit: int = Query(20, ge=1, le=200),
    task_id: Optional[str] = None,
    cache_seconds: int = 2,
) -> Dict[str, Any]:
    """Get execution logs - no auth required."""
    safe_limit = max(1, min(int(limit), 200))
    safe_task_id = (task_id or "").strip()
    if safe_task_id and not validate_uuid(safe_task_id):
        return {"success": False, "error": "Invalid task_id format"}

    cache_key = f"pub_logs:{safe_limit}:{safe_task_id}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    where = f"WHERE task_id = '{safe_task_id}'" if safe_task_id else ""
    sql = f"""
        SELECT
            id,
            task_id,
            worker_id,
            level,
            action,
            message,
            output_data,
            created_at
        FROM execution_logs
        {where}
        ORDER BY created_at DESC
        LIMIT {safe_limit}
    """

    rows = query_db(sql).get("rows", [])
    result = {
        "success": True,
        "logs": rows,
    }
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/stats")
def public_stats(
    cache_seconds: int = 10,
) -> Dict[str, Any]:
    """Get task statistics - no auth required."""
    cache_key = "pub_stats"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    by_status_rows = query_db(
        "SELECT status::text as status, COUNT(*)::int as count FROM governance_tasks GROUP BY status"
    ).get("rows", [])
    tasks_by_status: Dict[str, int] = {
        (r.get("status") or "unknown"): int(r.get("count") or 0) for r in by_status_rows
    }

    recent = query_db(
        """
        SELECT id, title, completed_at, assigned_worker
        FROM governance_tasks
        WHERE completed_at IS NOT NULL
        ORDER BY completed_at DESC
        LIMIT 10
        """
    ).get("rows", [])

    result = {
        "success": True,
        "tasksByStatus": tasks_by_status,
        "recentCompletions": [
            {
                "id": r.get("id"),
                "title": r.get("title"),
                "completed_at": r.get("completed_at"),
                "worker": r.get("assigned_worker"),
            }
            for r in recent
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/tree")
def public_tree(
    rootId: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    """Get task tree - no auth required."""
    safe_limit = max(1, min(int(limit), 500))
    safe_root = (rootId or "").strip()
    safe_status = (status or "").strip()
    cache_key = f"pub_tree:{safe_root}:{safe_status}:{safe_limit}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    where_parts = []
    if safe_root:
        where_parts.append(f"(id = {_sql_quote(safe_root)} OR root_task_id = {_sql_quote(safe_root)})")
    elif safe_status:
        where_parts.append(f"status::text = {_sql_quote(safe_status)}")
    else:
        where_parts.append(
            "(parent_task_id IS NULL OR status::text IN ('running','pending_verify','approved','claimed','in_progress'))"
        )

    where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    rows = query_db(
        f"""
        SELECT
          id,
          title,
          status::text as status,
          task_type,
          parent_task_id,
          root_task_id,
          cost_spent,
          assigned_worker,
          created_at
        FROM governance_tasks
        {where}
        ORDER BY created_at
        LIMIT {safe_limit}
        """
    ).get("rows", [])

    nodes = []
    for r in rows:
        nodes.append(
            {
                "id": str(r.get("id")),
                "title": r.get("title") or "Untitled",
                "status": r.get("status") or "pending",
                "taskType": r.get("task_type") or "standard",
                "depth": 0,
                "parentId": str(r.get("parent_task_id")) if r.get("parent_task_id") else None,
                "rootId": str(r.get("root_task_id")) if r.get("root_task_id") else None,
                "confidence": None,
                "cost": float(r.get("cost_spent") or 0) if r.get("cost_spent") is not None else None,
                "workerId": r.get("assigned_worker"),
                "createdAt": r.get("created_at"),
            }
        )

    edges = [
        {
            "id": f"e-{n['parentId']}-{n['id']}",
            "source": n["parentId"],
            "target": n["id"],
            "animated": n["status"] in ("running", "claimed", "in_progress"),
        }
        for n in nodes
        if n.get("parentId")
    ]

    status_counts: Dict[str, int] = {}
    for n in nodes:
        status_key = n.get("status") or "pending"
        status_counts[status_key] = status_counts.get(status_key, 0) + 1

    result = {
        "success": True,
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "totalNodes": len(nodes),
            "totalEdges": len(edges),
            "statusCounts": status_counts,
            "maxDepth": 0,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/tree/{root_id}")
def public_tree_root(
    root_id: str,
    limit: int = Query(500, ge=1, le=500),
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    """Get task tree for specific root - no auth required."""
    return public_tree(
        rootId=root_id,
        limit=limit,
        cache_seconds=cache_seconds,
    )


@router.get("/dlq")
def public_dlq_count(
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    """Get DLQ count - no auth required."""
    cache_key = "pub_dlq"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    rows = query_db("SELECT COUNT(*) as count FROM dead_letter_queue WHERE status = 'pending'").get("rows", [])
    count = int((rows[0] or {}).get("count", 0)) if rows else 0
    result = {
        "success": True,
        "count": count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/dlq/list")
def public_dlq_list(
    show_reviewed: bool = False,
    limit: int = Query(100, ge=1, le=200),
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    """Get DLQ items - no auth required."""
    safe_limit = max(1, min(int(limit), 200))
    cache_key = f"pub_dlq_list:{show_reviewed}:{safe_limit}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    where = "" if show_reviewed else "WHERE resolved_at IS NULL"
    rows = query_db(
        f"SELECT * FROM dead_letter_queue {where} ORDER BY created_at DESC LIMIT {safe_limit}"
    ).get("rows", [])

    total_rows = query_db("SELECT COUNT(*) as total FROM dead_letter_queue").get("rows", [])
    pending_rows = query_db(
        "SELECT COUNT(*) as pending FROM dead_letter_queue WHERE resolved_at IS NULL"
    ).get("rows", [])
    total = int((total_rows[0] or {}).get("total", 0)) if total_rows else 0
    pending = int((pending_rows[0] or {}).get("pending", 0)) if pending_rows else 0

    result = {
        "success": True,
        "items": rows,
        "counts": {"total": total, "pending": pending, "reviewed": total - pending},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/cost")
def public_cost(
    cache_seconds: int = 10,
) -> Dict[str, Any]:
    """Get cost metrics - no auth required."""
    cache_key = "pub_cost"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    sql = f"""
        SELECT
          COALESCE(SUM(CASE WHEN completed_at >= '{today_start.isoformat()}' THEN actual_cost_cents ELSE 0 END), 0) as today,
          COALESCE(SUM(actual_cost_cents), 0) as total
        FROM governance_tasks
    """
    rows = query_db(sql).get("rows", [])
    row = (rows[0] or {}) if rows else {}

    result = {
        "success": True,
        "today": float(row.get("today", 0) or 0),
        "total": float(row.get("total", 0) or 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/revenue/summary")
def public_revenue_summary(
    cache_seconds: int = 60,
) -> Dict[str, Any]:
    """Get revenue summary - no auth required."""
    cache_key = "pub_revenue_summary"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    summary_sql = """
        SELECT
          COALESCE(SUM(CASE WHEN date_trunc('month', occurred_at) = date_trunc('month', NOW()) THEN gross_amount ELSE 0 END), 0) as mtd,
          COALESCE(SUM(CASE WHEN date_trunc('year', occurred_at) = date_trunc('year', NOW()) THEN gross_amount ELSE 0 END), 0) as ytd,
          COALESCE(SUM(gross_amount), 0) as total
        FROM revenue_events
        WHERE occurred_at >= NOW() - INTERVAL '1 year'
    """

    monthly_sql = """
        SELECT
          TO_CHAR(date_trunc('month', occurred_at), 'Mon YYYY') as period,
          COALESCE(SUM(gross_amount), 0) as revenue,
          COUNT(*) as jobs,
          COALESCE(AVG(gross_amount), 0) as "avgTicket",
          0 as change
        FROM revenue_events
        WHERE occurred_at >= NOW() - INTERVAL '12 months'
        GROUP BY date_trunc('month', occurred_at)
        ORDER BY date_trunc('month', occurred_at) DESC
        LIMIT 12
    """

    summary_rows = query_db(summary_sql).get("rows", [])
    monthly_rows = query_db(monthly_sql).get("rows", [])
    summary = (summary_rows[0] or {}) if summary_rows else {}

    result = {
        "success": True,
        "total": float(summary.get("total", 0) or 0),
        "mtd": float(summary.get("mtd", 0) or 0),
        "ytd": float(summary.get("ytd", 0) or 0),
        "monthlyData": monthly_rows,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/alerts")
def public_alerts(
    severity: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=100),
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    """Get system alerts - no auth required."""
    from api.dashboard import get_system_alerts

    cache_key = f"pub_alerts:{severity or ''}:{acknowledged}:{limit}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    result = get_system_alerts(severity=severity, acknowledged=acknowledged, limit=limit)
    _cache.set(cache_key, result, int(cache_seconds))
    return result
