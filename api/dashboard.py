"""
JUGGERNAUT Dashboard API - Phase 7
REST API for Executive Dashboard, reporting, and notifications.

Deployment: Vercel (Python runtime) or standalone FastAPI
"""

import os
import json
import urllib.request
import urllib.error
import hashlib
import hmac
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
import re
import uuid

# ============================================================
# CONFIGURATION
# ============================================================

NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# API authentication - require secret from environment
API_SECRET = os.getenv("DASHBOARD_API_SECRET")
if not API_SECRET:
    raise ValueError("DASHBOARD_API_SECRET environment variable is required")
API_VERSION = "v1"

# Rate limiting config
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 100

# In-memory rate limit store (use Redis in production)
_rate_limits: Dict[str, List[float]] = {}


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_uuid(value: str) -> bool:
    """Validate that a string is a valid UUID."""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError):
        return False


def sanitize_identifier(value: str) -> str:
    """Sanitize an identifier (alphanumeric + underscore only)."""
    if not value:
        return ""
    return re.sub(r'[^a-zA-Z0-9_-]', '', str(value))


# ============================================================
# DATABASE CLIENT
# ============================================================

class DashboardDB:
    """Neon PostgreSQL client for dashboard queries."""
    
    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string or DATABASE_URL
        self.endpoint = NEON_ENDPOINT
    
    def query(self, sql: str) -> Dict[str, Any]:
        """Execute a SQL query and return results."""
        headers = {
            "Content-Type": "application/json",
            "Neon-Connection-String": self.connection_string
        }
        
        data = json.dumps({"query": sql}).encode('utf-8')
        req = urllib.request.Request(self.endpoint, data=data, headers=headers, method='POST')
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            raise Exception(f"HTTP {e.code}: {error_body}")
        except Exception as e:
            raise Exception(f"Database error: {str(e)}")


_db = DashboardDB()


def query_db(sql: str) -> Dict[str, Any]:
    """Execute raw SQL query."""
    return _db.query(sql)


# ============================================================
# AUTHENTICATION & RATE LIMITING
# ============================================================

def generate_api_key(user_id: str) -> str:
    """Generate an API key for a user."""
    timestamp = str(int(time.time()))
    message = f"{user_id}:{timestamp}"
    signature = hmac.new(
        API_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()[:32]
    return f"jug_{user_id}_{timestamp}_{signature}"


def validate_api_key(api_key: str) -> Optional[str]:
    """
    Validate an API key and return the user_id if valid.
    
    Returns:
        user_id if valid, None if invalid
    """
    if not api_key or not api_key.startswith("jug_"):
        return None
    
    try:
        parts = api_key.split("_")
        if len(parts) < 4:
            return None
        
        user_id = parts[1]
        timestamp = parts[2]
        provided_sig = parts[3]
        
        # Verify signature
        message = f"{user_id}:{timestamp}"
        expected_sig = hmac.new(
            API_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()[:32]
        
        if not hmac.compare_digest(provided_sig, expected_sig):
            return None
        
        return user_id
    except Exception:
        return None


def check_rate_limit(client_id: str) -> bool:
    """
    Check if client is within rate limits.
    
    Returns:
        True if allowed, False if rate limited
    """
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    
    # Clean old entries
    if client_id in _rate_limits:
        _rate_limits[client_id] = [
            t for t in _rate_limits[client_id] if t > window_start
        ]
    else:
        _rate_limits[client_id] = []
    
    # Check limit
    if len(_rate_limits[client_id]) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    
    # Record request
    _rate_limits[client_id].append(now)
    return True


# ============================================================
# DASHBOARD DATA MODEL (Phase 7.1)
# ============================================================

class DashboardData:
    """
    Executive Dashboard Data Model
    
    Provides structured access to all dashboard metrics.
    """
    
    @staticmethod
    def get_overview() -> Dict[str, Any]:
        """
        Get high-level dashboard overview.
        
        Returns aggregated metrics for the executive summary.
        """
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "revenue": {},
            "costs": {},
            "profit_loss": {},
            "agents": {},
            "experiments": {},
            "opportunities": {},
            "tasks": {}
        }
        
        # Revenue summary (last 30 days)
        try:
            revenue_sql = """
                SELECT 
                    COALESCE(SUM(gross_amount), 0) as total_revenue,
                    COALESCE(SUM(net_amount), 0) as net_revenue,
                    COUNT(*) as transaction_count
                FROM revenue_events
                WHERE recorded_at >= NOW() - INTERVAL '30 days'
            """
            rev_data = query_db(revenue_sql)
            if rev_data.get("rows"):
                row = rev_data["rows"][0]
                result["revenue"] = {
                    "total_30d": float(row.get("total_revenue", 0)),
                    "net_30d": float(row.get("net_revenue", 0)),
                    "transaction_count": int(row.get("transaction_count", 0))
                }
        except Exception as e:
            result["revenue"]["error"] = str(e)
        
        # Cost summary
        try:
            cost_sql = """
                SELECT 
                    COALESCE(SUM(amount_cents), 0) / 100.0 as total_cost
                FROM cost_events
                WHERE recorded_at >= NOW() - INTERVAL '30 days'
            """
            cost_data = query_db(cost_sql)
            if cost_data.get("rows"):
                result["costs"] = {
                    "total_30d": float(cost_data["rows"][0].get("total_cost", 0))
                }
        except Exception as e:
            result["costs"]["error"] = str(e)
        
        # Calculate profit
        if "error" not in result["revenue"] and "error" not in result["costs"]:
            revenue = result["revenue"].get("net_30d", 0)
            costs = result["costs"].get("total_30d", 0)
            result["profit_loss"] = {
                "net_30d": revenue - costs,
                "profitable": revenue > costs
            }
        
        # Agent status
        try:
            agent_sql = """
                SELECT 
                    status,
                    COUNT(*) as count
                FROM worker_registry
                GROUP BY status
            """
            agent_data = query_db(agent_sql)
            status_counts = {r["status"]: int(r["count"]) for r in agent_data.get("rows", [])}
            result["agents"] = {
                "online": status_counts.get("active", 0),
                "active": status_counts.get("active", 0),
                "degraded": status_counts.get("degraded", 0),
                "paused": status_counts.get("paused", 0),
                "offline": status_counts.get("offline", 0),
                "maintenance": status_counts.get("maintenance", 0),
                "total": sum(status_counts.values())
            }
        except Exception as e:
            result["agents"]["error"] = str(e)
        
        # Experiment status
        try:
            exp_sql = """
                SELECT 
                    status,
                    COUNT(*) as count
                FROM experiments
                GROUP BY status
            """
            exp_data = query_db(exp_sql)
            exp_counts = {r["status"]: int(r["count"]) for r in exp_data.get("rows", [])}
            result["experiments"] = {
                "running": exp_counts.get("running", 0),
                "completed": exp_counts.get("completed", 0),
                "failed": exp_counts.get("failed", 0),
                "total": sum(exp_counts.values())
            }
        except Exception as e:
            result["experiments"]["error"] = str(e)
        
        # Opportunity pipeline
        try:
            opp_sql = """
                SELECT 
                    stage,
                    COUNT(*) as count,
                    COALESCE(SUM(estimated_value), 0) as value
                FROM opportunities
                WHERE status = 'active'
                GROUP BY stage
            """
            opp_data = query_db(opp_sql)
            pipeline = {}
            total_value = 0
            for row in opp_data.get("rows", []):
                stage = row.get("stage", "unknown")
                pipeline[stage] = {
                    "count": int(row.get("count", 0)),
                    "value": float(row.get("value", 0))
                }
                total_value += float(row.get("value", 0))
            result["opportunities"] = {
                "pipeline": pipeline,
                "total_pipeline_value": total_value
            }
        except Exception as e:
            result["opportunities"]["error"] = str(e)
        
        # Task summary
        try:
            task_sql = """
                SELECT 
                    status,
                    COUNT(*) as count
                FROM governance_tasks
                WHERE created_at >= NOW() - INTERVAL '7 days'
                GROUP BY status
            """
            task_data = query_db(task_sql)
            task_counts = {r["status"]: int(r["count"]) for r in task_data.get("rows", [])}
            result["tasks"] = {
                "pending": task_counts.get("pending", 0),
                "running": task_counts.get("running", 0),
                "completed": task_counts.get("completed", 0),
                "failed": task_counts.get("failed", 0)
            }
        except Exception as e:
            result["tasks"]["error"] = str(e)
        
        return result


# ============================================================
# REVENUE VIEWS (Phase 7.1)
# ============================================================

def get_revenue_summary(
    days: int = 30,
    group_by: str = "day"
) -> Dict[str, Any]:
    """
    Get revenue summary over time.
    
    Args:
        days: Number of days to look back
        group_by: Grouping period ('day', 'week', 'month')
    
    Returns:
        Revenue data grouped by time period
    """
    if group_by == "week":
        date_trunc = "week"
    elif group_by == "month":
        date_trunc = "month"
    else:
        date_trunc = "day"
    
    sql = f"""
        SELECT 
            DATE_TRUNC('{date_trunc}', recorded_at) as period,
            COUNT(*) as transactions,
            COALESCE(SUM(gross_amount), 0) as gross_revenue,
            COALESCE(SUM(net_amount), 0) as net_revenue,
            COALESCE(SUM(gross_amount - net_amount), 0) as total_fees
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '{days} days'
        GROUP BY DATE_TRUNC('{date_trunc}', recorded_at)
        ORDER BY period DESC
    """
    
    try:
        result = query_db(sql)
        return {
            "success": True,
            "period": f"last_{days}_days",
            "group_by": group_by,
            "data": [
                {
                    "period": row["period"],
                    "transactions": int(row["transactions"]),
                    "gross_revenue": float(row["gross_revenue"]),
                    "net_revenue": float(row["net_revenue"]),
                    "total_fees": float(row["total_fees"])
                }
                for row in result.get("rows", [])
            ]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_revenue_by_source(days: int = 30) -> Dict[str, Any]:
    """
    Get revenue breakdown by source.
    
    Args:
        days: Number of days to look back
    
    Returns:
        Revenue grouped by source
    """
    sql = f"""
        SELECT 
            source,
            COUNT(*) as transactions,
            COALESCE(SUM(gross_amount), 0) as gross_revenue,
            COALESCE(SUM(net_amount), 0) as net_revenue
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '{days} days'
        GROUP BY source
        ORDER BY gross_revenue DESC
    """
    
    try:
        result = query_db(sql)
        return {
            "success": True,
            "period": f"last_{days}_days",
            "data": [
                {
                    "source": row["source"],
                    "transactions": int(row["transactions"]),
                    "gross_revenue": float(row["gross_revenue"]),
                    "net_revenue": float(row["net_revenue"])
                }
                for row in result.get("rows", [])
            ]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# EXPERIMENT STATUS VIEWS (Phase 7.1)
# ============================================================

def get_experiment_status() -> Dict[str, Any]:
    """
    Get status of all experiments.
    
    Returns:
        List of experiments with their current status and metrics
    """
    sql = """
        SELECT 
            e.id,
            e.name,
            e.hypothesis,
            e.status,
            e.created_at,
            e.start_date as started_at,
            e.end_date as completed_at,
            e.budget_limit,
            e.budget_spent,
            COALESCE(
                (SELECT SUM(net_amount) FROM revenue_events WHERE attribution->>'experiment_id' = e.id::text),
                0
            ) as revenue_generated
        FROM experiments e
        ORDER BY 
            CASE e.status 
                WHEN 'running' THEN 1 
                WHEN 'pending' THEN 2 
                ELSE 3 
            END,
            e.created_at DESC
        LIMIT 50
    """
    
    try:
        result = query_db(sql)
        experiments = []
        for row in result.get("rows", []):
            spent = float(row.get("budget_spent", 0) or 0)
            revenue = float(row.get("revenue_generated", 0))
            budget = float(row.get("budget_limit", 0) or 0)
            
            experiments.append({
                "id": row["id"],
                "name": row["name"],
                "hypothesis": row.get("hypothesis"),
                "status": row["status"],
                "created_at": row["created_at"],
                "started_at": row.get("started_at"),
                "completed_at": row.get("completed_at"),
                "budget": budget,
                "spent": spent,
                "revenue": revenue,
                "roi": ((revenue - spent) / spent * 100) if spent > 0 else 0,
                "budget_remaining": budget - spent
            })
        
        return {
            "success": True,
            "count": len(experiments),
            "experiments": experiments
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_experiment_details(experiment_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific experiment.
    
    Args:
        experiment_id: UUID of the experiment
    
    Returns:
        Detailed experiment data including variants, results, and checkpoints
    """
    # Validate UUID to prevent SQL injection
    if not validate_uuid(experiment_id):
        return {"success": False, "error": "Invalid experiment_id format"}
    
    # Get base experiment
    exp_sql = f"""
        SELECT * FROM experiments WHERE id = '{experiment_id}'
    """
    
    # Get variants
    variants_sql = f"""
        SELECT * FROM experiment_variants WHERE experiment_id = '{experiment_id}'
    """
    
    # Get results
    results_sql = f"""
        SELECT * FROM experiment_results 
        WHERE experiment_id = '{experiment_id}'
        ORDER BY recorded_at DESC
        LIMIT 100
    """
    
    # Get checkpoints
    checkpoints_sql = f"""
        SELECT * FROM experiment_checkpoints 
        WHERE experiment_id = '{experiment_id}'
        ORDER BY created_at DESC
    """
    
    try:
        exp_result = query_db(exp_sql)
        if not exp_result.get("rows"):
            return {"success": False, "error": "Experiment not found"}
        
        experiment = exp_result["rows"][0]
        variants = query_db(variants_sql).get("rows", [])
        results = query_db(results_sql).get("rows", [])
        checkpoints = query_db(checkpoints_sql).get("rows", [])
        
        return {
            "success": True,
            "experiment": experiment,
            "variants": variants,
            "results": results,
            "checkpoints": checkpoints
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# AGENT HEALTH VIEWS (Phase 7.1)
# ============================================================

def get_agent_health() -> Dict[str, Any]:
    """
    Get health status of all agents.
    
    Returns:
        Agent health data including status, metrics, and recent activity
    """
    # Get all workers
    workers_sql = """
        SELECT 
            w.worker_id,
            w.worker_type,
            w.status::text as status,
            w.capabilities,
            w.last_heartbeat,
            w.created_at,
            w.tasks_completed,
            w.tasks_failed,
            w.health_score
        FROM worker_registry w
        ORDER BY w.worker_id
    """
    
    # Get recent task activity per worker
    activity_sql = """
        SELECT 
            assigned_worker as worker_id,
            COUNT(*) FILTER (WHERE status::text = 'completed') as completed_24h,
            COUNT(*) FILTER (WHERE status::text = 'failed') as failed_24h,
            COUNT(*) FILTER (WHERE status::text = 'running') as running
        FROM governance_tasks
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        GROUP BY assigned_worker
    """
    
    try:
        workers_result = query_db(workers_sql)
        activity_result = query_db(activity_sql)
        
        # Build activity lookup
        activity_map = {
            r["worker_id"]: r for r in activity_result.get("rows", [])
        }
        
        agents = []
        for worker in workers_result.get("rows", []):
            worker_id = worker["worker_id"]
            activity = activity_map.get(worker_id, {})
            
            # Calculate health score
            completed = int(worker.get("tasks_completed", 0) or 0)
            failed = int(worker.get("tasks_failed", 0) or 0)
            total = completed + failed
            success_rate = (completed / total * 100) if total > 0 else 100
            
            # Check heartbeat freshness
            last_heartbeat = worker.get("last_heartbeat")
            heartbeat_stale = False
            if last_heartbeat:
                try:
                    hb_time = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
                    heartbeat_stale = (datetime.now(timezone.utc) - hb_time).total_seconds() > 300
                except (ValueError, TypeError):
                    # If heartbeat can't be parsed, treat it as stale
                    heartbeat_stale = True
            
            agents.append({
                "worker_id": worker_id,
                "worker_type": worker.get("worker_type"),
                "status": worker.get("status", "unknown"),
                "capabilities": worker.get("capabilities", []),
                "last_heartbeat": last_heartbeat,
                "heartbeat_stale": heartbeat_stale,
                "tasks_completed": completed,
                "tasks_failed": failed,
                "success_rate": round(success_rate, 1),
                "health_score": float(worker.get("health_score") or 0),
                "activity_24h": {
                    "completed": int(activity.get("completed_24h", 0) or 0),
                    "failed": int(activity.get("failed_24h", 0) or 0),
                    "running": int(activity.get("running", 0) or 0)
                }
            })
        
        # Calculate overall health
        online = sum(1 for a in agents if a["status"] == "active")
        total_agents = len(agents)
        avg_success = sum(a["success_rate"] for a in agents) / total_agents if total_agents > 0 else 0
        
        return {
            "success": True,
            "summary": {
                "total_agents": total_agents,
                "online": online,
                "offline": total_agents - online,
                "average_success_rate": round(avg_success, 1),
                "stale_heartbeats": sum(1 for a in agents if a["heartbeat_stale"])
            },
            "agents": agents
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# GOAL PROGRESS VIEWS (Phase 7.1)
# ============================================================

def get_goal_progress() -> Dict[str, Any]:
    """
    Get progress on all active goals.
    
    Returns:
        Goals with their progress, sub-goals, and task completion status
    """
    # Get top-level goals
    goals_sql = """
        SELECT 
            g.id,
            g.title,
            g.description,
            g.status,
            g.progress,
            g.assigned_worker_id,
            g.created_at,
            g.deadline,
            g.parent_goal_id,
            (SELECT COUNT(*) FROM goals sg WHERE sg.parent_goal_id = g.id) as sub_goal_count,
            (SELECT COUNT(*) FROM governance_tasks t WHERE t.goal_id = g.id) as task_count,
            (SELECT COUNT(*) FROM governance_tasks t WHERE t.goal_id = g.id AND t.status::text = 'completed') as tasks_completed
        FROM goals g
        WHERE g.status IN ('active', 'in_progress', 'blocked')
        ORDER BY g.created_at DESC
        LIMIT 50
    """
    
    try:
        result = query_db(goals_sql)
        goals = []
        
        for row in result.get("rows", []):
            task_count = int(row.get("task_count", 0) or 0)
            tasks_completed = int(row.get("tasks_completed", 0) or 0)
            
            # Calculate effective progress
            if row.get("progress") is not None:
                progress = float(row["progress"])
            elif task_count > 0:
                progress = (tasks_completed / task_count) * 100
            else:
                progress = 0
            
            goals.append({
                "id": row["id"],
                "title": row["title"],
                "description": row.get("description"),
                "status": row["status"],
                "progress": round(progress, 1),
                "assigned_worker_id": row.get("assigned_worker_id"),
                "created_at": row["created_at"],
                "deadline": row.get("deadline"),
                "is_sub_goal": row.get("parent_goal_id") is not None,
                "sub_goal_count": int(row.get("sub_goal_count", 0) or 0),
                "task_count": task_count,
                "tasks_completed": tasks_completed
            })
        
        # Calculate summary
        total_progress = sum(g["progress"] for g in goals) / len(goals) if goals else 0
        
        return {
            "success": True,
            "summary": {
                "total_goals": len(goals),
                "average_progress": round(total_progress, 1),
                "by_status": {
                    "active": sum(1 for g in goals if g["status"] == "active"),
                    "in_progress": sum(1 for g in goals if g["status"] == "in_progress"),
                    "blocked": sum(1 for g in goals if g["status"] == "blocked")
                }
            },
            "goals": goals
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# PROFIT/LOSS ANALYSIS (Phase 7.1)
# ============================================================

def get_profit_loss(days: int = 30, experiment_id: str = None) -> Dict[str, Any]:
    """
    Get profit/loss analysis.
    
    Args:
        days: Number of days to analyze
        experiment_id: Optional filter by experiment
    
    Returns:
        Detailed P&L breakdown
    """
    exp_filter = f"AND experiment_id = '{experiment_id}'" if experiment_id else ""
    
    # Revenue
    revenue_sql = f"""
        SELECT 
            COALESCE(SUM(gross_amount), 0) as gross_revenue,
            COALESCE(SUM(net_amount), 0) as net_revenue,
            COALESCE(SUM(gross_amount - net_amount), 0) as fees,
            COUNT(*) as transactions
        FROM revenue_events
        WHERE recorded_at >= NOW() - INTERVAL '{days} days'
        {exp_filter}
    """
    
    # Costs by category
    costs_sql = f"""
        SELECT 
            category,
            COALESCE(SUM(amount_cents), 0) / 100.0 as total
        FROM cost_events
        WHERE recorded_at >= NOW() - INTERVAL '{days} days'
        {exp_filter}
        GROUP BY category
    """
    
    try:
        revenue_result = query_db(revenue_sql)
        costs_result = query_db(costs_sql)
        
        revenue_row = revenue_result.get("rows", [{}])[0]
        gross_revenue = float(revenue_row.get("gross_revenue", 0))
        net_revenue = float(revenue_row.get("net_revenue", 0))
        fees = float(revenue_row.get("fees", 0))
        
        costs_by_category = {
            row["category"]: float(row["total"])
            for row in costs_result.get("rows", [])
        }
        total_costs = sum(costs_by_category.values())
        
        net_profit = net_revenue - total_costs
        margin = (net_profit / gross_revenue * 100) if gross_revenue > 0 else 0
        
        return {
            "success": True,
            "period_days": days,
            "experiment_id": experiment_id,
            "revenue": {
                "gross": gross_revenue,
                "net": net_revenue,
                "fees": fees,
                "transactions": int(revenue_row.get("transactions", 0))
            },
            "costs": {
                "total": total_costs,
                "by_category": costs_by_category
            },
            "profit_loss": {
                "net_profit": net_profit,
                "margin_percent": round(margin, 2),
                "profitable": net_profit > 0
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# PENDING APPROVALS VIEW (Phase 7.1)
# ============================================================

def get_pending_approvals() -> Dict[str, Any]:
    """
    Get all pending approval requests.
    
    Returns:
        List of items awaiting human approval
    """
    sql = """
        SELECT 
            a.id,
            a.worker_id,
            a.action_type,
            a.action_data,
            a.action_description,
            a.risk_level,
            a.decision::text as status,
            a.created_at,
            a.expires_at,
            CASE 
                WHEN a.expires_at IS NOT NULL AND a.expires_at < NOW() THEN true 
                ELSE false 
            END as is_expired
        FROM approvals a
        WHERE a.decision IS NULL OR a.decision::text = 'pending'
        ORDER BY 
            CASE 
                WHEN a.expires_at IS NOT NULL AND a.expires_at < NOW() + INTERVAL '1 hour' THEN 0
                ELSE 1
            END,
            a.created_at DESC
    """
    
    try:
        result = query_db(sql)
        approvals = []
        
        for row in result.get("rows", []):
            approvals.append({
                "id": row["id"],
                "worker_id": row["worker_id"],
                "action_type": row["action_type"],
                "action_details": row.get("action_data"),
                "reason": row.get("action_description"),
                "risk_level": row.get("risk_level"),
                "status": row.get("status", "pending"),
                "created_at": row["created_at"],
                "expires_at": row.get("expires_at"),
                "is_expired": row.get("is_expired", False),
                "is_urgent": row.get("expires_at") is not None
            })
        
        return {
            "success": True,
            "count": len(approvals),
            "expired_count": sum(1 for a in approvals if a["is_expired"]),
            "urgent_count": sum(1 for a in approvals if a["is_urgent"] and not a["is_expired"]),
            "approvals": approvals
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# SYSTEM ALERTS VIEW (Phase 7.1)
# ============================================================

def get_system_alerts(
    severity: str = None,
    acknowledged: bool = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Get system alerts.
    
    Args:
        severity: Filter by severity (info, warning, error, critical)
        acknowledged: Filter by acknowledgment status
        limit: Maximum number of alerts
    
    Returns:
        List of system alerts
    """
    conditions = []
    if severity:
        conditions.append(f"severity = '{severity}'")
    if acknowledged is not None:
        if acknowledged:
            conditions.append("acknowledged_at IS NOT NULL")
        else:
            conditions.append("acknowledged_at IS NULL")
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    sql = f"""
        SELECT 
            id,
            alert_type,
            severity,
            title,
            message,
            source,
            status,
            metadata,
            acknowledged_by,
            acknowledged_at,
            created_at
        FROM system_alerts
        {where}
        ORDER BY 
            CASE severity 
                WHEN 'critical' THEN 0 
                WHEN 'error' THEN 1 
                WHEN 'warning' THEN 2 
                ELSE 3 
            END,
            created_at DESC
        LIMIT {limit}
    """
    
    try:
        result = query_db(sql)
        alerts = result.get("rows", [])
        
        # Count by severity
        severity_counts = {}
        for alert in alerts:
            sev = alert.get("severity", "info")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        return {
            "success": True,
            "count": len(alerts),
            "by_severity": severity_counts,
            "unacknowledged": sum(1 for a in alerts if not a.get("acknowledged_at")),
            "alerts": alerts
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# EXPORT FUNCTIONS FOR API
# ============================================================

# All the dashboard functions available for the API
DASHBOARD_FUNCTIONS = {
    "overview": DashboardData.get_overview,
    "revenue_summary": get_revenue_summary,
    "revenue_by_source": get_revenue_by_source,
    "experiment_status": get_experiment_status,
    "experiment_details": get_experiment_details,
    "agent_health": get_agent_health,
    "goal_progress": get_goal_progress,
    "profit_loss": get_profit_loss,
    "pending_approvals": get_pending_approvals,
    "system_alerts": get_system_alerts
}


def get_dashboard_endpoint(endpoint: str, params: Dict = None) -> Dict[str, Any]:
    """
    Universal endpoint handler for dashboard API.
    
    Args:
        endpoint: Which dashboard view to get
        params: Optional parameters for the view
    
    Returns:
        Dashboard data or error
    """
    params = params or {}
    
    if endpoint not in DASHBOARD_FUNCTIONS:
        return {
            "success": False,
            "error": f"Unknown endpoint: {endpoint}",
            "available_endpoints": list(DASHBOARD_FUNCTIONS.keys())
        }
    
    func = DASHBOARD_FUNCTIONS[endpoint]
    
    try:
        # Call function with params if it accepts them
        import inspect
        sig = inspect.signature(func)
        if sig.parameters:
            # Filter params to only those accepted by the function
            valid_params = {k: v for k, v in params.items() if k in sig.parameters}
            return func(**valid_params)
        else:
            return func()
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# VERCEL/FASTAPI HANDLER
# ============================================================

def handle_request(
    method: str,
    path: str,
    headers: Dict[str, str],
    query_params: Dict[str, str] = None,
    body: Dict = None
) -> Dict[str, Any]:
    """
    Main request handler for the dashboard API.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path
        headers: Request headers
        query_params: URL query parameters
        body: Request body (for POST)
    
    Returns:
        Response dict with status, headers, and body
    """
    # Extract API key
    api_key = headers.get("Authorization", "").replace("Bearer ", "")
    if not api_key:
        api_key = query_params.get("api_key") if query_params else None
    
    # Validate API key
    user_id = validate_api_key(api_key)
    if not user_id:
        return {
            "status": 401,
            "body": {"error": "Invalid or missing API key"}
        }
    
    # Check rate limit
    if not check_rate_limit(user_id):
        return {
            "status": 429,
            "body": {"error": "Rate limit exceeded", "retry_after": RATE_LIMIT_WINDOW}
        }
    
    # Parse path
    path_parts = path.strip("/").split("/")
    if len(path_parts) < 2 or path_parts[0] != API_VERSION:
        return {
            "status": 404,
            "body": {"error": f"Invalid path. Use /{API_VERSION}/<endpoint>"}
        }
    
    endpoint = path_parts[1]
    
    # Handle request
    params = query_params or {}
    if body:
        params.update(body)
    
    # Add path parameters (e.g., experiment_id from /v1/experiment/123)
    if len(path_parts) > 2:
        if endpoint == "experiment_details":
            params["experiment_id"] = path_parts[2]
    
    result = get_dashboard_endpoint(endpoint, params)
    
    return {
        "status": 200 if result.get("success", True) else 500,
        "body": result
    }


# ============================================================
# QUICK TEST
# ============================================================

if __name__ == "__main__":
    # Generate test API key
    test_key = generate_api_key("test_user")
    print(f"Test API Key: {test_key}")
    
    # Test validation
    user = validate_api_key(test_key)
    print(f"Validated User: {user}")
    
    # Test dashboard overview
    print("\n=== Dashboard Overview ===")
    overview = DashboardData.get_overview()
    print(json.dumps(overview, indent=2, default=str))
