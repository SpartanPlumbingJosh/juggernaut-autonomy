"""
Internal Dashboard API endpoints for Vercel HQ Dashboard migration.
These endpoints are called by spartan-hq Vercel functions to avoid direct DB access.

All endpoints require Bearer token authentication via INTERNAL_API_SECRET.
"""

import os
import json
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
import httpx

router = APIRouter(prefix="/internal/dashboard", tags=["internal-dashboard"])

# Simple TTL cache
_cache = {}
_cache_ttl = {}
DEFAULT_CACHE_TTL = 30  # seconds


def get_cached(key: str):
    """Get value from cache if not expired."""
    if key in _cache and key in _cache_ttl:
        if time.time() < _cache_ttl[key]:
            return _cache[key]
    return None


def set_cached(key: str, value, ttl: int = DEFAULT_CACHE_TTL):
    """Set value in cache with TTL."""
    _cache[key] = value
    _cache_ttl[key] = time.time() + ttl


def verify_internal_auth(authorization: Optional[str] = Header(None)):
    """Verify internal API authentication."""
    expected_secret = os.environ.get("INTERNAL_API_SECRET")
    if not expected_secret:
        raise HTTPException(status_code=500, detail="INTERNAL_API_SECRET not configured")
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization format")
    
    token = authorization[7:]  # Remove "Bearer " prefix
    if token != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    return True


async def query_neon(sql: str, params: list = None):
    """Execute SQL query against Neon database via HTTP endpoint."""
    http_endpoint = os.environ.get("NEON_HTTP_ENDPOINT") or os.environ.get("HTTP_ENDPOINT")
    if not http_endpoint:
        # Fallback: construct from DATABASE_URL
        db_url = os.environ.get("DATABASE_URL", "")
        if "neon.tech" in db_url:
            # Extract host from connection string
            import re
            match = re.search(r'@([^/]+)/', db_url)
            if match:
                host = match.group(1)
                http_endpoint = f"https://{host}/sql"
    
    if not http_endpoint:
        raise HTTPException(status_code=500, detail="Database endpoint not configured")
    
    # Get credentials from DATABASE_URL
    db_url = os.environ.get("DATABASE_URL", "")
    import re
    match = re.search(r'postgresql://([^:]+):([^@]+)@', db_url)
    if not match:
        raise HTTPException(status_code=500, detail="Invalid DATABASE_URL format")
    
    user, password = match.groups()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            http_endpoint,
            headers={
                "Content-Type": "application/json",
                "Neon-Connection-String": f"postgresql://{user}:{password}@{http_endpoint.replace('https://', '').replace('/sql', '')}/neondb?sslmode=require"
            },
            json={"query": sql, "params": params or []},
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Database error: {response.text}")
        
        return response.json()


# ============== TASKS ==============

@router.get("/tasks")
async def get_tasks(
    authorization: Optional[str] = Header(None),
    limit: int = Query(50, ge=1, le=500),
    status: Optional[str] = Query(None)
):
    """Get tasks list with optional status filter."""
    verify_internal_auth(authorization)
    
    cache_key = f"tasks:{status}:{limit}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    where_clause = ""
    if status and status != "all":
        where_clause = f"WHERE status = '{status}'"
    
    sql = f"""
        SELECT id, title, description, status, priority, task_type,
               assigned_worker, parent_task_id, created_at, started_at,
               completed_at, completion_evidence, error_message
        FROM governance_tasks
        {where_clause}
        ORDER BY 
            CASE WHEN status = 'in_progress' THEN 0
                 WHEN status = 'pending' THEN 1
                 WHEN status = 'waiting_approval' THEN 2
                 ELSE 3 END,
            created_at DESC
        LIMIT {limit}
    """
    
    result = await query_neon(sql)
    rows = result.get("rows", [])
    
    # Get total count
    count_sql = f"SELECT COUNT(*) as count FROM governance_tasks {where_clause}"
    count_result = await query_neon(count_sql)
    total = count_result.get("rows", [{}])[0].get("count", 0)
    
    response = {
        "success": True,
        "tasks": rows,
        "total": total,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    set_cached(cache_key, response, ttl=15)
    return response


# ============== WORKERS ==============

@router.get("/workers")
async def get_workers(authorization: Optional[str] = Header(None)):
    """Get worker registry."""
    verify_internal_auth(authorization)
    
    cache_key = "workers"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    sql = """
        SELECT worker_id, status, last_heartbeat, current_task_id,
               capabilities, created_at, tasks_completed, tasks_failed
        FROM worker_registry
        ORDER BY last_heartbeat DESC NULLS LAST
    """
    
    result = await query_neon(sql)
    rows = result.get("rows", [])
    
    response = {
        "success": True,
        "workers": rows,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    set_cached(cache_key, response, ttl=10)
    return response


# ============== LOGS ==============

@router.get("/logs")
async def get_logs(
    authorization: Optional[str] = Header(None),
    limit: int = Query(100, ge=1, le=1000),
    task_id: Optional[str] = Query(None)
):
    """Get execution logs with optional task_id filter."""
    verify_internal_auth(authorization)
    
    # Validate task_id is UUID if provided
    if task_id:
        import re
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
        if not uuid_pattern.match(task_id):
            raise HTTPException(status_code=400, detail="Invalid task_id format (must be UUID)")
    
    cache_key = f"logs:{task_id}:{limit}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    where_clause = ""
    if task_id:
        where_clause = f"WHERE task_id = '{task_id}'"
    
    sql = f"""
        SELECT id, task_id, worker_id, action, level, message,
               error_data, created_at
        FROM execution_logs
        {where_clause}
        ORDER BY created_at DESC
        LIMIT {limit}
    """
    
    result = await query_neon(sql)
    rows = result.get("rows", [])
    
    response = {
        "success": True,
        "logs": rows,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    set_cached(cache_key, response, ttl=10)
    return response


# ============== EXPERIMENTS ==============

@router.get("/experiments")
async def get_experiments(authorization: Optional[str] = Header(None)):
    """Get experiments list."""
    verify_internal_auth(authorization)
    
    cache_key = "experiments"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    sql = """
        SELECT id, name, description, status, hypothesis, 
               start_date, end_date, created_at
        FROM experiments
        ORDER BY created_at DESC
        LIMIT 50
    """
    
    result = await query_neon(sql)
    rows = result.get("rows", [])
    
    response = {
        "success": True,
        "experiments": rows,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    set_cached(cache_key, response, ttl=60)
    return response


# ============== ALERTS ==============

@router.get("/alerts")
async def get_alerts(authorization: Optional[str] = Header(None)):
    """Get system alerts (from escalations table)."""
    verify_internal_auth(authorization)
    
    cache_key = "alerts"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    sql = """
        SELECT id, task_id, level, title, description, 
               source_agent, status, created_at, resolved_at
        FROM escalations
        WHERE status != 'resolved'
        ORDER BY 
            CASE level 
                WHEN 'critical' THEN 0 
                WHEN 'high' THEN 1 
                WHEN 'medium' THEN 2 
                ELSE 3 
            END,
            created_at DESC
        LIMIT 50
    """
    
    result = await query_neon(sql)
    rows = result.get("rows", [])
    
    response = {
        "success": True,
        "alerts": rows,
        "unresolved_count": len(rows),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    set_cached(cache_key, response, ttl=15)
    return response


# ============== REVENUE ==============

@router.get("/revenue/summary")
async def get_revenue_summary(authorization: Optional[str] = Header(None)):
    """Get revenue summary (total, MTD, YTD, monthly breakdown)."""
    verify_internal_auth(authorization)
    
    cache_key = "revenue_summary"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    now = datetime.utcnow()
    year_start = datetime(now.year, 1, 1)
    month_start = datetime(now.year, now.month, 1)
    
    # Total revenue
    total_sql = "SELECT COALESCE(SUM(amount_cents), 0) as total FROM revenue"
    total_result = await query_neon(total_sql)
    total = total_result.get("rows", [{}])[0].get("total", 0) / 100  # cents to dollars
    
    # MTD
    mtd_sql = f"""
        SELECT COALESCE(SUM(amount_cents), 0) as mtd 
        FROM revenue 
        WHERE created_at >= '{month_start.isoformat()}'
    """
    mtd_result = await query_neon(mtd_sql)
    mtd = mtd_result.get("rows", [{}])[0].get("mtd", 0) / 100
    
    # YTD
    ytd_sql = f"""
        SELECT COALESCE(SUM(amount_cents), 0) as ytd 
        FROM revenue 
        WHERE created_at >= '{year_start.isoformat()}'
    """
    ytd_result = await query_neon(ytd_sql)
    ytd = ytd_result.get("rows", [{}])[0].get("ytd", 0) / 100
    
    # Monthly breakdown (last 12 months)
    monthly_sql = """
        SELECT 
            DATE_TRUNC('month', created_at) as month,
            COALESCE(SUM(amount_cents), 0) as amount
        FROM revenue
        WHERE created_at >= NOW() - INTERVAL '12 months'
        GROUP BY DATE_TRUNC('month', created_at)
        ORDER BY month DESC
    """
    monthly_result = await query_neon(monthly_sql)
    monthly_data = [
        {"month": row.get("month"), "amount": row.get("amount", 0) / 100}
        for row in monthly_result.get("rows", [])
    ]
    
    response = {
        "success": True,
        "total": total,
        "mtd": mtd,
        "ytd": ytd,
        "monthlyData": monthly_data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    set_cached(cache_key, response, ttl=300)  # 5 min cache for revenue
    return response


# ============== DLQ ==============

@router.get("/dlq")
async def get_dlq_count(authorization: Optional[str] = Header(None)):
    """Get dead letter queue pending count."""
    verify_internal_auth(authorization)
    
    cache_key = "dlq"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    sql = """
        SELECT COUNT(*) as count 
        FROM dead_letter_queue 
        WHERE status = 'pending'
    """
    
    result = await query_neon(sql)
    count = result.get("rows", [{}])[0].get("count", 0)
    
    response = {
        "success": True,
        "count": count,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    set_cached(cache_key, response, ttl=30)
    return response


# ============== COST ==============

@router.get("/cost")
async def get_cost(authorization: Optional[str] = Header(None)):
    """Get cost metrics from actual_cost_cents."""
    verify_internal_auth(authorization)
    
    cache_key = "cost"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Today's cost
    today_sql = f"""
        SELECT COALESCE(SUM(actual_cost_cents), 0) as today
        FROM governance_tasks
        WHERE completed_at >= '{today_start.isoformat()}'
    """
    today_result = await query_neon(today_sql)
    today = today_result.get("rows", [{}])[0].get("today", 0)
    
    # Total cost
    total_sql = """
        SELECT COALESCE(SUM(actual_cost_cents), 0) as total
        FROM governance_tasks
    """
    total_result = await query_neon(total_sql)
    total = total_result.get("rows", [{}])[0].get("total", 0)
    
    response = {
        "success": True,
        "today": today,  # in cents
        "total": total,  # in cents
        "timestamp": datetime.utcnow().isoformat()
    }
    
    set_cached(cache_key, response, ttl=60)
    return response
