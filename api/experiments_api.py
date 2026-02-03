"""
Experiments API - Expose A/B testing and experimentation data to Spartan HQ.

Endpoints:
- GET /experiments - List all experiments
- GET /experiments/{id} - Get single experiment details
- GET /experiments/stats - Experiment statistics
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import query_db


def _make_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(body)
    }


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create error response."""
    return _make_response(status_code, {"error": message})


async def handle_list_experiments(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """List experiments with optional filtering."""
    try:
        status = query_params.get("status", [""])[0] if isinstance(query_params.get("status"), list) else query_params.get("status", "")
        limit = int(query_params.get("limit", ["50"])[0] if isinstance(query_params.get("limit"), list) else query_params.get("limit", 50))
        offset = int(query_params.get("offset", ["0"])[0] if isinstance(query_params.get("offset"), list) else query_params.get("offset", 0))
        
        where_clause = ""
        if status:
            where_clause = f"WHERE status = '{status}'"
        
        sql = f"""
        SELECT 
            id,
            name,
            hypothesis,
            experiment_type,
            status,
            success_criteria,
            budget_allocated,
            actual_cost,
            revenue_generated,
            roi,
            confidence_level,
            metadata,
            started_at,
            completed_at,
            created_at
        FROM experiments
        {where_clause}
        ORDER BY created_at DESC
        LIMIT {limit}
        OFFSET {offset}
        """
        
        result = await query_db(sql)
        experiments = result.get("rows", [])
        
        # Calculate ROI for each experiment
        for exp in experiments:
            revenue = float(exp.get("revenue_generated") or 0)
            cost = float(exp.get("actual_cost") or 0)
            if cost > 0:
                exp["calculated_roi"] = ((revenue - cost) / cost) * 100
            else:
                exp["calculated_roi"] = 0 if revenue == 0 else float('inf')
        
        # Get total count
        count_sql = f"SELECT COUNT(*) as total FROM experiments {where_clause}"
        count_result = await query_db(count_sql)
        total = count_result.get("rows", [{}])[0].get("total", 0)
        
        return _make_response(200, {
            "experiments": experiments,
            "total": total,
            "limit": limit,
            "offset": offset
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch experiments: {str(e)}")


async def handle_get_experiment(experiment_id: str) -> Dict[str, Any]:
    """Get single experiment with detailed metrics."""
    try:
        # Get experiment details
        exp_sql = f"""
        SELECT 
            id,
            name,
            hypothesis,
            experiment_type,
            status,
            success_criteria,
            budget_allocated,
            actual_cost,
            revenue_generated,
            roi,
            confidence_level,
            metadata,
            started_at,
            completed_at,
            created_at
        FROM experiments
        WHERE id = '{experiment_id}'
        """
        
        exp_result = await query_db(exp_sql)
        rows = exp_result.get("rows", [])
        
        if not rows:
            return _error_response(404, f"Experiment not found: {experiment_id}")
        
        experiment = rows[0]
        
        # Get associated metrics
        metrics_sql = f"""
        SELECT 
            metric_name,
            metric_value,
            metric_type,
            recorded_at
        FROM experiment_metrics
        WHERE experiment_id = '{experiment_id}'
        ORDER BY recorded_at DESC
        LIMIT 100
        """
        
        metrics_result = await query_db(metrics_sql)
        metrics = metrics_result.get("rows", [])
        
        # Get associated tasks
        tasks_sql = f"""
        SELECT 
            t.id,
            t.title,
            t.task_type,
            t.status,
            t.created_at,
            t.completed_at
        FROM governance_tasks t
        WHERE t.metadata->>'experiment_id' = '{experiment_id}'
        ORDER BY t.created_at DESC
        LIMIT 50
        """
        
        tasks_result = await query_db(tasks_sql)
        tasks = tasks_result.get("rows", [])
        
        # Calculate ROI
        revenue = float(experiment.get("revenue_generated") or 0)
        cost = float(experiment.get("actual_cost") or 0)
        if cost > 0:
            experiment["calculated_roi"] = ((revenue - cost) / cost) * 100
        else:
            experiment["calculated_roi"] = 0 if revenue == 0 else float('inf')
        
        return _make_response(200, {
            "experiment": experiment,
            "metrics": metrics,
            "tasks": tasks
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch experiment: {str(e)}")


async def handle_experiment_stats() -> Dict[str, Any]:
    """Get experiment statistics."""
    try:
        # Overall stats
        stats_sql = """
        SELECT 
            COUNT(*) as total_experiments,
            COUNT(*) FILTER (WHERE status = 'running') as running_count,
            COUNT(*) FILTER (WHERE status = 'completed') as completed_count,
            COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
            SUM(budget_allocated) as total_budget,
            SUM(actual_cost) as total_cost,
            SUM(revenue_generated) as total_revenue,
            AVG(roi) FILTER (WHERE roi IS NOT NULL) as avg_roi,
            AVG(confidence_level) FILTER (WHERE confidence_level IS NOT NULL) as avg_confidence
        FROM experiments
        """
        
        stats_result = await query_db(stats_sql)
        stats = stats_result.get("rows", [{}])[0]
        
        # By type
        type_sql = """
        SELECT 
            experiment_type,
            COUNT(*) as count,
            AVG(roi) as avg_roi,
            SUM(revenue_generated) as total_revenue
        FROM experiments
        WHERE experiment_type IS NOT NULL
        GROUP BY experiment_type
        ORDER BY total_revenue DESC
        """
        
        type_result = await query_db(type_sql)
        by_type = type_result.get("rows", [])
        
        # Recent completions
        recent_sql = """
        SELECT 
            id,
            name,
            roi,
            revenue_generated,
            actual_cost,
            completed_at
        FROM experiments
        WHERE status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 10
        """
        
        recent_result = await query_db(recent_sql)
        recent = recent_result.get("rows", [])
        
        # Success rate (experiments with positive ROI)
        success_sql = """
        SELECT 
            COUNT(*) FILTER (WHERE roi > 0) as successful,
            COUNT(*) as total
        FROM experiments
        WHERE status = 'completed' AND roi IS NOT NULL
        """
        
        success_result = await query_db(success_sql)
        success_data = success_result.get("rows", [{}])[0]
        
        success_rate = 0
        if success_data.get("total", 0) > 0:
            success_rate = (success_data.get("successful", 0) / success_data.get("total")) * 100
        
        return _make_response(200, {
            "stats": {
                **stats,
                "success_rate": success_rate
            },
            "by_type": by_type,
            "recent_completions": recent
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch experiment stats: {str(e)}")


def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route experiments API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # GET /experiments
    if len(parts) == 1 and parts[0] == "experiments" and method == "GET":
        return handle_list_experiments(query_params)
    
    # GET /experiments/stats
    if len(parts) == 2 and parts[0] == "experiments" and parts[1] == "stats" and method == "GET":
        return handle_experiment_stats()
    
    # GET /experiments/{id}
    if len(parts) == 2 and parts[0] == "experiments" and method == "GET":
        experiment_id = parts[1]
        return handle_get_experiment(experiment_id)
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
