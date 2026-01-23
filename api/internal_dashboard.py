import os
import time
import hmac
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request

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
