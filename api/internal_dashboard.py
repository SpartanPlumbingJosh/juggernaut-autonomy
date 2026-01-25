import os
import time
import hmac
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Header, HTTPException, Request

from api.dashboard import (
    DashboardData,
    get_agent_health,
    get_experiment_details,
    get_experiment_status,
    get_goal_progress,
    get_pending_approvals,
    get_profit_loss,
    get_revenue_by_source,
    get_revenue_summary,
    get_system_alerts,
    query_db,
    validate_uuid,
)


_INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET")


def _require_internal_auth(authorization: Optional[str]) -> None:
    if not _INTERNAL_API_SECRET:
        raise HTTPException(status_code=500, detail="INTERNAL_API_SECRET not configured")

    token = ""
    if authorization:
        token = authorization.replace("Bearer ", "")

    if not token or not hmac.compare_digest(token, _INTERNAL_API_SECRET):
        raise HTTPException(status_code=401, detail="Unauthorized")


class _TTLCache:
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
router = APIRouter(prefix="/internal/dashboard")


def _sql_escape(value: str) -> str:
    return str(value).replace("'", "''")


def _sql_quote(value: Optional[str]) -> str:
    if value is None:
        return "NULL"
    return f"'{_sql_escape(value)}'"


@router.get("/overview")
def internal_overview(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    cache_seconds: int = 10,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = "overview"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    result = DashboardData.get_overview()
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/dlq/list")
def internal_dead_letter_queue_list(
    authorization: Optional[str] = Header(default=None),
    show_reviewed: bool = False,
    limit: int = 100,
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    safe_limit = max(1, min(int(limit), 200))
    cache_key = f"dlq_list:{show_reviewed}:{safe_limit}"
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


@router.patch("/dlq/{dlq_id}/resolve")
def internal_dead_letter_queue_resolve(
    dlq_id: str,
    authorization: Optional[str] = Header(default=None),
    body: Dict[str, Any] = Body(default=None),
) -> Dict[str, Any]:
    _require_internal_auth(authorization)
    body = body or {}

    resolution = body.get("resolution")
    resolved_by = body.get("resolvedBy") or body.get("resolved_by") or "dashboard"

    if not resolution:
        raise HTTPException(status_code=400, detail="Missing resolution")

    sql = f"""
        UPDATE dead_letter_queue
        SET status = 'resolved',
            resolution = {_sql_quote(str(resolution))},
            resolved_by = {_sql_quote(str(resolved_by))},
            resolved_at = NOW()
        WHERE id = {_sql_quote(dlq_id)}
        RETURNING id
    """
    rows = query_db(sql).get("rows", [])
    if not rows:
        raise HTTPException(status_code=404, detail="DLQ item not found")
    return {"success": True, "id": dlq_id, "resolution": resolution}


@router.get("/revenue")
def internal_revenue(
    authorization: Optional[str] = Header(default=None),
    days: int = 30,
    group_by: str = "day",
    cache_seconds: int = 30,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = f"revenue:{days}:{group_by}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    result = get_revenue_summary(days=days, group_by=group_by)
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/revenue/by_source")
def internal_revenue_by_source(
    authorization: Optional[str] = Header(default=None),
    days: int = 30,
    cache_seconds: int = 30,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = f"revenue_by_source:{days}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    result = get_revenue_by_source(days=days)
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/revenue/summary")
def internal_revenue_summary(
    authorization: Optional[str] = Header(default=None),
    cache_seconds: int = 60,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = "revenue_summary"
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


@router.get("/experiments")
def internal_experiments(
    authorization: Optional[str] = Header(default=None),
    cache_seconds: int = 15,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = "experiments"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    result = get_experiment_status()
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/experiments/{experiment_id}")
def internal_experiment_details(
    experiment_id: str,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    _require_internal_auth(authorization)
    return get_experiment_details(experiment_id=experiment_id)


@router.get("/agents")
def internal_agents(
    authorization: Optional[str] = Header(default=None),
    cache_seconds: int = 10,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = "agent_health"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    result = get_agent_health()
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/goals")
def internal_goals(
    authorization: Optional[str] = Header(default=None),
    cache_seconds: int = 20,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = "goals"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    result = get_goal_progress()
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/pl")
def internal_profit_loss(
    authorization: Optional[str] = Header(default=None),
    days: int = 30,
    experiment_id: Optional[str] = None,
    cache_seconds: int = 30,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = f"pl:{days}:{experiment_id or ''}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    result = get_profit_loss(days=days, experiment_id=experiment_id)
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/approvals")
def internal_approvals(
    authorization: Optional[str] = Header(default=None),
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = "approvals"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    result = get_pending_approvals()
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/alerts")
def internal_alerts(
    authorization: Optional[str] = Header(default=None),
    severity: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    limit: int = 50,
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = f"alerts:{severity or ''}:{acknowledged}:{limit}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    result = get_system_alerts(severity=severity, acknowledged=acknowledged, limit=limit)
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.patch("/alerts")
def internal_alerts_patch(
    authorization: Optional[str] = Header(default=None),
    body: Dict[str, Any] = Body(default=None),
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    body = body or {}
    ids = body.get("ids")
    action = body.get("action")

    if not ids or not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="Missing or invalid ids array")

    if action not in ("resolve", "unresolve"):
        raise HTTPException(status_code=400, detail="Invalid action. Use 'resolve' or 'unresolve'")

    # NOTE: Column names assumed to match spartan-hq schema conventions.
    # system_alerts.resolved (bool), system_alerts.resolved_at (timestamptz)
    id_list = ",".join(_sql_quote(str(i)) for i in ids)
    if action == "resolve":
        sql = f"""
            UPDATE system_alerts
            SET resolved = TRUE, resolved_at = NOW()
            WHERE id IN ({id_list})
            RETURNING id
        """
        rows = query_db(sql).get("rows", [])
        return {"success": True, "resolved": len(rows)}

    sql = f"""
        UPDATE system_alerts
        SET resolved = FALSE, resolved_at = NULL
        WHERE id IN ({id_list})
        RETURNING id
    """
    rows = query_db(sql).get("rows", [])
    return {"success": True, "unresolved": len(rows)}


@router.get("/dlq")
def internal_dead_letter_queue(
    authorization: Optional[str] = Header(default=None),
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = "dlq"
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


@router.get("/cost")
def internal_cost(
    authorization: Optional[str] = Header(default=None),
    cache_seconds: int = 10,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = "cost"
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


@router.get("/stats")
def internal_stats(
    authorization: Optional[str] = Header(default=None),
    cache_seconds: int = 10,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = "stats"
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
def internal_tree(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    rootId: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    safe_limit = max(1, min(int(limit), 500))
    safe_root = (rootId or "").strip()
    safe_status = (status or "").strip()
    cache_key = f"tree:{safe_root}:{safe_status}:{safe_limit}"
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
def internal_tree_root(
    root_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    limit: int = 500,
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    return internal_tree(
        request=request,
        authorization=authorization,
        rootId=root_id,
        limit=limit,
        cache_seconds=cache_seconds,
    )


@router.post("/tasks")
def internal_tasks_create(
    authorization: Optional[str] = Header(default=None),
    body: Dict[str, Any] = Body(default=None),
) -> Dict[str, Any]:
    _require_internal_auth(authorization)
    body = body or {}

    title = body.get("title")
    description = body.get("description") or ""
    task_type = body.get("taskType") or body.get("task_type") or "standard"
    priority = body.get("priority") or "medium"
    parent_task_id = body.get("parentTaskId") or body.get("parent_task_id")
    root_task_id = body.get("rootTaskId") or body.get("root_task_id")
    auto_approve = body.get("autoApprove") is True or body.get("autoApprove") == "true"

    if not title:
        raise HTTPException(status_code=400, detail="Missing required field: title")

    initial_status = "approved" if auto_approve else "pending"
    sql = f"""
        INSERT INTO governance_tasks (
          title,
          description,
          task_type,
          status,
          priority,
          parent_task_id,
          root_task_id,
          created_at,
          updated_at
        ) VALUES (
          {_sql_quote(str(title))},
          {_sql_quote(str(description))},
          {_sql_quote(str(task_type))},
          {_sql_quote(initial_status)},
          {_sql_quote(str(priority))},
          {_sql_quote(str(parent_task_id)) if parent_task_id else 'NULL'},
          {_sql_quote(str(root_task_id)) if root_task_id else 'NULL'},
          NOW(),
          NOW()
        )
        RETURNING *
    """
    rows = query_db(sql).get("rows", [])
    if not rows:
        raise HTTPException(status_code=500, detail="Failed to create task")

    return {
        "success": True,
        "task": rows[0],
        "message": "Task created and approved - worker will pick it up" if auto_approve else "Task created - awaiting approval",
    }


@router.post("/tasks/claim")
def internal_tasks_claim(
    authorization: Optional[str] = Header(default=None),
    body: Dict[str, Any] = Body(default=None),
) -> Dict[str, Any]:
    _require_internal_auth(authorization)
    body = body or {}
    worker_id = body.get("workerId") or body.get("worker_id")
    if not worker_id:
        raise HTTPException(status_code=400, detail="Missing required field: workerId")

    claim_sql = f"""
        UPDATE governance_tasks
        SET status = 'claimed',
            claimed_by = {_sql_quote(str(worker_id))},
            claimed_at = NOW(),
            updated_at = NOW()
        WHERE id = (
          SELECT id FROM governance_tasks
          WHERE status = 'approved'
            AND (expires_at IS NULL OR expires_at > NOW())
          ORDER BY
            CASE priority
              WHEN 'critical' THEN 0
              WHEN 'urgent' THEN 1
              WHEN 'high' THEN 2
              WHEN 'medium' THEN 3
              ELSE 4
            END,
            created_at ASC
          LIMIT 1
          FOR UPDATE SKIP LOCKED
        )
        RETURNING *
    """
    rows = query_db(claim_sql).get("rows", [])
    if not rows:
        return {"success": True, "task": None, "message": "No tasks available"}

    return {"success": True, "task": rows[0], "message": "Task claimed successfully"}


@router.post("/tasks/{task_id}/start")
def internal_tasks_start(
    task_id: str,
    authorization: Optional[str] = Header(default=None),
    body: Dict[str, Any] = Body(default=None),
) -> Dict[str, Any]:
    _require_internal_auth(authorization)
    body = body or {}
    worker_id = body.get("workerId") or body.get("worker_id")
    if not worker_id:
        raise HTTPException(status_code=400, detail="Missing required field: workerId")

    sql = f"""
        UPDATE governance_tasks
        SET status = 'running',
            started_at = NOW(),
            heartbeat_at = NOW(),
            updated_at = NOW()
        WHERE id = {_sql_quote(task_id)}
          AND status = 'claimed'
          AND claimed_by = {_sql_quote(str(worker_id))}
        RETURNING *
    """
    rows = query_db(sql).get("rows", [])
    if not rows:
        raise HTTPException(status_code=409, detail="Task not found, not claimed, or wrong worker")
    return {"success": True, "task": rows[0], "message": "Task started successfully"}


@router.post("/tasks/{task_id}/cancel")
def internal_tasks_cancel(
    task_id: str,
    authorization: Optional[str] = Header(default=None),
    body: Dict[str, Any] = Body(default=None),
) -> Dict[str, Any]:
    _require_internal_auth(authorization)
    body = body or {}
    reason = body.get("reason") or "Cancelled by user"
    force = bool(body.get("force") is True or body.get("force") == "true")

    task_rows = query_db(
        f"SELECT id, status::text as status FROM governance_tasks WHERE id = {_sql_quote(task_id)}"
    ).get("rows", [])
    if not task_rows:
        raise HTTPException(status_code=404, detail="Task not found")
    status = (task_rows[0] or {}).get("status")
    terminal = {"completed", "failed", "dead", "cancelled"}
    if status in terminal and not force:
        raise HTTPException(status_code=400, detail=f"Cannot cancel task in '{status}' status")

    is_running = status in ("running", "claimed")
    new_status = "cancellation_requested" if is_running else "cancelled"
    update_sql = f"""
        UPDATE governance_tasks
        SET status = '{new_status}',
            failure_reason = {_sql_quote(str(reason))},
            completed_at = {'NULL' if is_running else 'NOW()'},
            updated_at = NOW()
        WHERE id = {_sql_quote(task_id)}
        RETURNING *
    """
    rows = query_db(update_sql).get("rows", [])
    return {
        "success": True,
        "task": rows[0] if rows else None,
        "message": "Cancellation requested - worker will stop gracefully" if is_running else "Task cancelled successfully",
    }


@router.post("/tasks/{task_id}/complete")
def internal_tasks_complete(
    task_id: str,
    authorization: Optional[str] = Header(default=None),
    body: Dict[str, Any] = Body(default=None),
) -> Dict[str, Any]:
    _require_internal_auth(authorization)
    body = body or {}

    evidence = body.get("evidence") or body.get("completionEvidence") or body.get("completion_evidence")
    worker_id = body.get("workerId") or body.get("worker_id")

    sql = f"""
        UPDATE governance_tasks
        SET status = 'pending_verify',
            completion_evidence = {_sql_quote(str(evidence)) if evidence is not None else 'NULL'},
            completed_at = NOW(),
            updated_at = NOW()
        WHERE id = {_sql_quote(task_id)}
        RETURNING *
    """
    rows = query_db(sql).get("rows", [])
    if not rows:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "success": True,
        "task": rows[0],
        "message": "Task completed - pending verification",
        "workerId": worker_id,
    }


@router.post("/tasks/{task_id}/verify")
def internal_tasks_verify(
    task_id: str,
    authorization: Optional[str] = Header(default=None),
    body: Dict[str, Any] = Body(default=None),
) -> Dict[str, Any]:
    _require_internal_auth(authorization)
    body = body or {}

    action = body.get("action")
    feedback = body.get("feedback")
    verified_by = body.get("verifiedBy") or body.get("verified_by") or "human"
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'approve' or 'reject'")

    task_rows = query_db(
        f"SELECT id, status::text as status FROM governance_tasks WHERE id = {_sql_quote(task_id)}"
    ).get("rows", [])
    if not task_rows:
        raise HTTPException(status_code=404, detail="Task not found")
    if (task_rows[0] or {}).get("status") != "pending_verify":
        raise HTTPException(status_code=400, detail="Task is not pending verification")

    passed = action == "approve"
    new_status = "completed" if passed else "failed"
    verification_status = "passed" if passed else "failed"

    try:
        query_db(
            f"""
            INSERT INTO verification_results (
              task_id,
              verification_level,
              schema_check_passed,
              existence_check_passed,
              content_check_passed,
              overall_passed,
              semantic_feedback,
              verified_by,
              verified_at
            ) VALUES (
              {_sql_quote(task_id)},
              'human_review',
              {str(passed).lower()},
              {str(passed).lower()},
              {str(passed).lower()},
              {str(passed).lower()},
              {_sql_quote(str(feedback)) if feedback else 'NULL'},
              {_sql_quote(str(verified_by))},
              NOW()
            )
            """
        )
    except Exception:
        pass

    update_sql = f"""
        UPDATE governance_tasks
        SET status = '{new_status}',
            verification_status = '{verification_status}',
            failure_reason = {('NULL' if passed else _sql_quote(str(feedback or 'Rejected by human review')))},
            completed_at = NOW(),
            updated_at = NOW()
        WHERE id = {_sql_quote(task_id)}
        RETURNING *
    """
    rows = query_db(update_sql).get("rows", [])
    return {
        "success": True,
        "action": action,
        "task": rows[0] if rows else None,
        "message": f"Task {'approved and completed' if passed else 'rejected and failed'}",
        "verifiedBy": verified_by,
    }


@router.get("/tasks/{task_id}")
def internal_task_get(
    task_id: str,
    authorization: Optional[str] = Header(default=None),
    cache_seconds: int = 2,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = f"task:{task_id}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    rows = query_db(f"SELECT * FROM governance_tasks WHERE id = {_sql_quote(task_id)} LIMIT 1").get("rows", [])
    if not rows:
        raise HTTPException(status_code=404, detail="Task not found")

    result = {"success": True, "task": rows[0]}
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/tasks/{task_id}/children")
def internal_task_children(
    task_id: str,
    authorization: Optional[str] = Header(default=None),
    cache_seconds: int = 2,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = f"task_children:{task_id}"
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
          NULL::text as stage,
          (SELECT COUNT(*)::int FROM governance_tasks c WHERE c.parent_task_id = governance_tasks.id) as child_count
        FROM governance_tasks
        WHERE parent_task_id = {_sql_quote(task_id)}
        ORDER BY created_at ASC
    """
    rows = query_db(sql).get("rows", [])
    result = {"success": True, "tasks": rows}
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.patch("/tasks/{task_id}")
def internal_task_patch(
    task_id: str,
    authorization: Optional[str] = Header(default=None),
    body: Dict[str, Any] = Body(default=None),
) -> Dict[str, Any]:
    _require_internal_auth(authorization)
    body = body or {}

    allowed_fields = {
        "status": "status",
        "isApproved": "is_approved",
        "interventionNeeded": "intervention_needed",
        "interventionReason": "intervention_reason",
        "actualOutputs": "actual_outputs",
        "verificationStatus": "verification_status",
        "aiReasoning": "ai_reasoning",
        "failureReason": "failure_reason",
    }

    sets = []
    for k, col in allowed_fields.items():
        if k in body:
            val = body.get(k)
            if isinstance(val, bool):
                sets.append(f"{col} = {str(val).lower()}")
            else:
                sets.append(f"{col} = {_sql_quote(str(val)) if val is not None else 'NULL'}")

    if not sets:
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    sets.append("updated_at = NOW()")
    sql = f"""
        UPDATE governance_tasks
        SET {', '.join(sets)}
        WHERE id = {_sql_quote(task_id)}
        RETURNING *
    """
    rows = query_db(sql).get("rows", [])
    if not rows:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "task": rows[0]}


@router.post("/tasks/{task_id}/{action}")
def internal_task_action(
    task_id: str,
    action: str,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    now_iso = datetime.now(timezone.utc).isoformat()

    if action == "reset":
        query_db(
            f"""
            UPDATE governance_tasks
            SET status = 'pending',
                assigned_worker = NULL,
                started_at = NULL,
                completed_at = NULL,
                updated_at = NOW()
            WHERE id = {_sql_quote(task_id)}
            """
        )
        return {"success": True, "message": "Task reset to pending"}

    if action == "approve":
        query_db(
            f"""
            UPDATE governance_tasks
            SET status = 'approved',
                updated_at = NOW()
            WHERE id = {_sql_quote(task_id)}
            """
        )
        return {"success": True, "message": "Task approved"}

    if action == "breakdown":
        parent_rows = query_db(
            f"SELECT id, title, root_task_id FROM governance_tasks WHERE id = {_sql_quote(task_id)} LIMIT 1"
        ).get("rows", [])
        if not parent_rows:
            raise HTTPException(status_code=404, detail="Task not found")
        parent = parent_rows[0]
        root_task_id = parent.get("root_task_id") or parent.get("id")
        title = parent.get("title") or task_id
        insert_sql = f"""
            INSERT INTO governance_tasks (
              title,
              description,
              task_type,
              priority,
              status,
              parent_task_id,
              root_task_id,
              created_at,
              updated_at
            ) VALUES (
              {_sql_quote(f"Decompose task: {title}")},
              {_sql_quote(f"Break down parent task into subtasks. Parent ID: {task_id}")},
              'decomposition',
              'high',
              'pending',
              {_sql_quote(task_id)},
              {_sql_quote(str(root_task_id))},
              NOW(),
              NOW()
            )
            RETURNING id
        """
        query_db(insert_sql)
        return {"success": True, "message": "Decomposition task created"}

    raise HTTPException(status_code=400, detail=f"Unknown action: {action}")


@router.get("/workers/{worker_id}/activity")
def internal_worker_activity(
    worker_id: str,
    authorization: Optional[str] = Header(default=None),
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = f"worker_activity:{worker_id}"
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
        raise HTTPException(status_code=404, detail="Worker not found")
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

    cost_rows = query_db(
        f"""
        SELECT COALESCE(SUM(actual_cost_cents), 0) as total_cost
        FROM governance_tasks
        WHERE assigned_worker = {_sql_quote(worker_id)}
          AND status::text = 'completed'
        """
    ).get("rows", [])
    total_cost = float((cost_rows[0] or {}).get("total_cost", 0)) if cost_rows else 0.0

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
        "total_cost": total_cost,
        "health_score": float(w.get("health_score") or 1.0),
        "context_loaded": {"facts": 0, "memories": 0, "tools": 48},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _cache.set(cache_key, result, int(cache_seconds))
    return result


@router.get("/tasks")
def internal_tasks(
    authorization: Optional[str] = Header(default=None),
    limit: int = 50,
    status: Optional[str] = None,
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    safe_limit = max(1, min(int(limit), 200))
    safe_status = (status or "").replace("'", "''")
    cache_key = f"tasks:{safe_limit}:{safe_status}"
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


@router.get("/workers")
def internal_workers(
    authorization: Optional[str] = Header(default=None),
    cache_seconds: int = 5,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    cache_key = "workers"
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


@router.get("/logs")
def internal_logs(
    authorization: Optional[str] = Header(default=None),
    limit: int = 20,
    task_id: Optional[str] = None,
    cache_seconds: int = 2,
) -> Dict[str, Any]:
    _require_internal_auth(authorization)

    safe_limit = max(1, min(int(limit), 200))
    safe_task_id = (task_id or "").strip()
    if safe_task_id and not validate_uuid(safe_task_id):
        raise HTTPException(status_code=400, detail="Invalid task_id format")

    cache_key = f"logs:{safe_limit}:{safe_task_id}"
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


@router.post("/logs")
def internal_logs_create(
    authorization: Optional[str] = Header(default=None),
    body: Dict[str, Any] = Body(default=None),
) -> Dict[str, Any]:
    _require_internal_auth(authorization)
    body = body or {}

    task_id = body.get("task_id") or body.get("taskId") or body.get("taskId")
    worker_id = body.get("worker_id") or body.get("workerId")
    level = body.get("level")
    action = body.get("action")
    message = body.get("message")
    output_data = body.get("metadata") or body.get("output_data") or {}

    if not worker_id or not level or not message:
        raise HTTPException(status_code=400, detail="Missing required fields: workerId, level, message")

    sql = f"""
        INSERT INTO execution_logs (
          task_id,
          worker_id,
          level,
          action,
          message,
          output_data,
          created_at
        ) VALUES (
          {(_sql_quote(str(task_id)) if task_id else 'NULL')},
          {_sql_quote(str(worker_id))},
          {_sql_quote(str(level))},
          {(_sql_quote(str(action)) if action else 'NULL')},
          {_sql_quote(str(message))},
          {_sql_quote(str(output_data))},
          NOW()
        )
        RETURNING id, created_at
    """
    rows = query_db(sql).get("rows", [])
    row = rows[0] if rows else {}
    return {"success": True, "log_id": row.get("id"), "created_at": row.get("created_at")}
