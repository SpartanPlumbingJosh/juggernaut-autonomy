"""
Public Pages API - FastAPI Router for Spartan HQ Pages

Provides public (no auth) endpoints for:
- /public/pages/opportunities - Pipeline data
- /public/pages/revenue - Revenue tracking  
- /public/pages/experiments - Experiment results
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from api.dashboard import query_db


router = APIRouter(prefix="/public/pages")


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


# ============================================================================
# OPPORTUNITIES ENDPOINTS
# ============================================================================


@router.get("/opportunities")
def public_opportunities(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """List opportunities with optional filtering."""
    try:
        safe_limit = min(int(limit), 200)
        safe_offset = max(int(offset), 0)
        
        where_clause = ""
        if status:
            safe_status = str(status).replace("'", "''")
            where_clause = f"WHERE status = '{safe_status}'"
        
        sql = f"""
        SELECT 
            id,
            opportunity_type,
            category,
            description,
            source_description,
            estimated_value,
            confidence_score,
            status,
            stage,
            metadata,
            created_at,
            updated_at,
            expires_at
        FROM opportunities
        {where_clause}
        ORDER BY 
            confidence_score DESC NULLS LAST,
            created_at DESC
        LIMIT {safe_limit}
        OFFSET {safe_offset}
        """
        
        result = query_db(sql)
        opportunities = result.get("rows", [])
        
        # Get total count
        count_sql = f"SELECT COUNT(*) as total FROM opportunities {where_clause}"
        count_result = query_db(count_sql)
        total = _to_int((count_result.get("rows", [{}])[0] or {}).get("total"), 0)
        
        return {
            "success": True,
            "opportunities": opportunities,
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/opportunities/stats")
def public_opportunities_stats() -> Dict[str, Any]:
    """Get pipeline statistics."""
    try:
        stats_sql = """
        SELECT 
            COUNT(*) as total_opportunities,
            COUNT(*) FILTER (WHERE status = 'open') as open_count,
            COUNT(*) FILTER (WHERE status = 'won') as won_count,
            COUNT(*) FILTER (WHERE status = 'lost') as lost_count,
            COALESCE(SUM(estimated_value) FILTER (WHERE status = 'open'), 0) as pipeline_value,
            COALESCE(AVG(confidence_score) FILTER (WHERE status = 'open'), 0) as avg_confidence,
            COALESCE(SUM(estimated_value) FILTER (WHERE status = 'won'), 0) as total_revenue
        FROM opportunities
        """
        
        stats_result = query_db(stats_sql)
        stats = (stats_result.get("rows", [{}])[0] or {})
        
        # Calculate win rate
        won = _to_int(stats.get("won_count"), 0)
        lost = _to_int(stats.get("lost_count"), 0)
        total_closed = won + lost
        win_rate = (won / total_closed * 100) if total_closed > 0 else 0
        
        return {
            "success": True,
            "pipelineValue": _to_float(stats.get("pipeline_value"), 0),
            "openCount": _to_int(stats.get("open_count"), 0),
            "wonCount": _to_int(stats.get("won_count"), 0),
            "lostCount": _to_int(stats.get("lost_count"), 0),
            "winRate": round(win_rate, 1),
            "avgConfidence": round(_to_float(stats.get("avg_confidence"), 0) * 100, 1),
            "totalRevenue": _to_float(stats.get("total_revenue"), 0),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/opportunities/{opportunity_id}")
def public_opportunity_detail(opportunity_id: str) -> Dict[str, Any]:
    """Get single opportunity by ID."""
    try:
        safe_id = str(opportunity_id).replace("'", "''")
        sql = f"""
        SELECT 
            id, opportunity_type, category, description, source_description,
            estimated_value, confidence_score, status, stage, metadata,
            created_at, updated_at, expires_at
        FROM opportunities
        WHERE id = '{safe_id}'
        """
        
        result = query_db(sql)
        rows = result.get("rows", [])
        
        if not rows:
            return {"success": False, "error": f"Opportunity not found: {opportunity_id}"}
        
        return {"success": True, "opportunity": rows[0]}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# REVENUE ENDPOINTS
# Actual schema: id, opportunity_id, event_type, revenue_type, gross_amount, 
#                net_amount, currency, source, attribution, description, 
#                external_id, metadata, occurred_at, recorded_at
# ============================================================================


@router.get("/revenue")
def public_revenue(
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """Get revenue summary and recent transactions."""
    try:
        # Summary stats
        summary_sql = """
        SELECT
            COALESCE(SUM(gross_amount), 0) as total,
            COALESCE(SUM(CASE WHEN date_trunc('month', occurred_at) = date_trunc('month', NOW()) THEN gross_amount ELSE 0 END), 0) as mtd,
            COALESCE(SUM(CASE WHEN date_trunc('quarter', occurred_at) = date_trunc('quarter', NOW()) THEN gross_amount ELSE 0 END), 0) as qtd,
            COALESCE(SUM(CASE WHEN date_trunc('year', occurred_at) = date_trunc('year', NOW()) THEN gross_amount ELSE 0 END), 0) as ytd
        FROM revenue_events
        """
        
        summary_result = query_db(summary_sql)
        summary = (summary_result.get("rows", [{}])[0] or {})
        
        # Cost summary - use occurred_at for filtering
        cost_sql = """
        SELECT
            COALESCE(SUM(amount_cents), 0) / 100.0 as total_cost,
            COALESCE(SUM(CASE WHEN occurred_at >= date_trunc('month', NOW()) THEN amount_cents ELSE 0 END), 0) / 100.0 as mtd_cost
        FROM cost_events
        """
        
        cost_result = query_db(cost_sql)
        costs = (cost_result.get("rows", [{}])[0] or {})
        
        # Recent transactions - use actual columns: source (not source_type), opportunity_id (not source_id)
        safe_limit = min(int(limit), 200)
        transactions_sql = f"""
        SELECT 
            id, 
            occurred_at as date,
            revenue_type as type,
            source,
            gross_amount as amount,
            opportunity_id,
            metadata
        FROM revenue_events
        ORDER BY occurred_at DESC
        LIMIT {safe_limit}
        """
        
        transactions_result = query_db(transactions_sql)
        transactions = transactions_result.get("rows", [])
        
        total_revenue = _to_float(summary.get("total"), 0)
        total_cost = _to_float(costs.get("total_cost"), 0)
        
        return {
            "success": True,
            "summary": {
                "total": total_revenue,
                "mtd": _to_float(summary.get("mtd"), 0),
                "qtd": _to_float(summary.get("qtd"), 0),
                "ytd": _to_float(summary.get("ytd"), 0),
                "costs": total_cost,
                "profit": total_revenue - total_cost,
                "mtdCosts": _to_float(costs.get("mtd_cost"), 0)
            },
            "transactions": transactions,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/revenue/by-source")
def public_revenue_by_source() -> Dict[str, Any]:
    """Get revenue breakdown by source."""
    try:
        # Use 'source' column (actual schema) not 'source_type'
        sql = """
        SELECT 
            COALESCE(source, 'unknown') as source,
            COUNT(*) as transaction_count,
            COALESCE(SUM(gross_amount), 0) as total_revenue,
            COALESCE(AVG(gross_amount), 0) as avg_transaction
        FROM revenue_events
        GROUP BY source
        ORDER BY total_revenue DESC
        """
        
        result = query_db(sql)
        sources = result.get("rows", [])
        
        return {
            "success": True,
            "sources": sources,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# EXPERIMENTS ENDPOINTS
# Actual schema: id, name, description, experiment_type, status, hypothesis,
#                success_criteria, failure_criteria, budget_limit, budget_spent,
#                cost_per_iteration, max_iterations, current_iteration,
#                start_date, end_date, scheduled_end, owner_worker, template_id,
#                parent_experiment_id, tags, config, results_summary, conclusion,
#                created_at, updated_at, created_by, hypothesis_id, risk_level, etc.
# ============================================================================


@router.get("/experiments")
def public_experiments(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """List experiments with optional filtering."""
    try:
        safe_limit = min(int(limit), 200)
        
        where_clause = ""
        if status:
            safe_status = str(status).replace("'", "''")
            where_clause = f"WHERE status = '{safe_status}'"
        
        # Use actual columns: budget_limit, budget_spent, start_date, end_date
        sql = f"""
        SELECT 
            id,
            name,
            hypothesis,
            experiment_type as type,
            status,
            COALESCE(budget_limit, 0) as budget,
            COALESCE(budget_spent, 0) as spent,
            0 as revenue,
            CASE 
                WHEN COALESCE(budget_spent, 0) > 0 THEN ((0 - budget_spent)::float / budget_spent * 100)
                ELSE 0
            END as roi,
            risk_level,
            config as metadata,
            created_at,
            start_date as started_at,
            end_date as completed_at
        FROM experiments
        {where_clause}
        ORDER BY created_at DESC
        LIMIT {safe_limit}
        """
        
        result = query_db(sql)
        experiments = result.get("rows", [])
        
        return {
            "success": True,
            "experiments": experiments,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/experiments/stats")
def public_experiments_stats() -> Dict[str, Any]:
    """Get experiment statistics."""
    try:
        # Use actual columns
        sql = """
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'running') as running,
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(*) FILTER (WHERE status = 'success') as successful,
            COUNT(*) FILTER (WHERE status IN ('completed', 'success', 'failed')) as finished,
            COALESCE(SUM(budget_limit), 0) as total_budget,
            COALESCE(SUM(budget_spent), 0) as total_spent,
            0 as total_revenue
        FROM experiments
        """
        
        result = query_db(sql)
        stats = (result.get("rows", [{}])[0] or {})
        
        finished = _to_int(stats.get("finished"), 0)
        successful = _to_int(stats.get("successful"), 0)
        success_rate = (successful / finished * 100) if finished > 0 else 0
        
        total_spent = _to_float(stats.get("total_spent"), 0)
        total_revenue = _to_float(stats.get("total_revenue"), 0)
        avg_roi = ((total_revenue - total_spent) / total_spent * 100) if total_spent > 0 else 0
        
        return {
            "success": True,
            "total": _to_int(stats.get("total"), 0),
            "running": _to_int(stats.get("running"), 0),
            "completed": _to_int(stats.get("completed"), 0),
            "successRate": round(success_rate, 1),
            "avgRoi": round(avg_roi, 1),
            "totalBudget": _to_float(stats.get("total_budget"), 0),
            "totalSpent": total_spent,
            "totalRevenue": total_revenue,
            "avgConfidence": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/experiments/{experiment_id}")
def public_experiment_detail(experiment_id: str) -> Dict[str, Any]:
    """Get single experiment by ID."""
    try:
        safe_id = str(experiment_id).replace("'", "''")
        sql = f"""
        SELECT 
            id, name, hypothesis, experiment_type as type, status,
            COALESCE(budget_limit, 0) as budget,
            COALESCE(budget_spent, 0) as spent,
            0 as revenue,
            CASE 
                WHEN COALESCE(budget_spent, 0) > 0 THEN ((0 - budget_spent)::float / budget_spent * 100)
                ELSE 0
            END as roi,
            risk_level, config as metadata, created_at, start_date as started_at, end_date as completed_at
        FROM experiments
        WHERE id = '{safe_id}'
        """
        
        result = query_db(sql)
        rows = result.get("rows", [])
        
        if not rows:
            return {"success": False, "error": f"Experiment not found: {experiment_id}"}
        
        return {"success": True, "experiment": rows[0]}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
