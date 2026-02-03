"""
Routing API Endpoints

REST API for smart model routing and cost tracking.

Endpoints:
    GET /api/routing/policies - Get routing policies
    GET /api/routing/costs - Get cost statistics
    GET /api/routing/performance - Get model performance
    POST /api/routing/select - Select model for task

Part of Milestone 6: OpenRouter Smart Routing
"""

import json
import logging
from typing import Dict, Any

from core.model_selector import get_model_selector
from core.database import fetch_all

logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def _make_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
        "body": json.dumps(body)
    }


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create error response."""
    return _make_response(status_code, {"error": message, "success": False})


def handle_get_policies() -> Dict[str, Any]:
    """
    Handle GET /api/routing/policies
    
    Get all routing policies.
    """
    try:
        query = """
            SELECT 
                id,
                name,
                description,
                policy_config,
                is_active
            FROM routing_policies
            ORDER BY name
        """
        
        policies = fetch_all(query)
        
        return _make_response(200, {
            "success": True,
            "policies": policies,
            "count": len(policies)
        })
    except Exception as e:
        logger.exception(f"Error getting policies: {e}")
        return _error_response(500, f"Failed to get policies: {str(e)}")


def handle_get_costs() -> Dict[str, Any]:
    """
    Handle GET /api/routing/costs
    
    Get cost statistics.
    """
    try:
        # Get current budget
        budget_query = """
            SELECT 
                budget_type,
                budget_period,
                budget_amount,
                spent_amount,
                alert_threshold,
                period_start,
                period_end
            FROM cost_budgets
            WHERE 
                is_active = TRUE
                AND period_start <= NOW()
                AND period_end > NOW()
            ORDER BY created_at DESC
            LIMIT 1
        """
        
        budget_results = fetch_all(budget_query)
        budget = budget_results[0] if budget_results else None
        
        # Get cost by policy
        policy_query = """
            SELECT 
                policy_name,
                COUNT(*) as request_count,
                SUM(actual_cost) as total_cost,
                AVG(actual_cost) as avg_cost
            FROM model_selections
            WHERE 
                actual_cost IS NOT NULL
                AND created_at > NOW() - INTERVAL '24 hours'
            GROUP BY policy_name
            ORDER BY total_cost DESC
        """
        
        policy_costs = fetch_all(policy_query)
        
        # Get cost by model
        model_query = """
            SELECT 
                selected_model,
                selected_provider,
                COUNT(*) as request_count,
                SUM(actual_cost) as total_cost,
                AVG(actual_cost) as avg_cost
            FROM model_selections
            WHERE 
                actual_cost IS NOT NULL
                AND created_at > NOW() - INTERVAL '24 hours'
            GROUP BY selected_model, selected_provider
            ORDER BY total_cost DESC
        """
        
        model_costs = fetch_all(model_query)
        
        return _make_response(200, {
            "success": True,
            "budget": budget,
            "costs_by_policy": policy_costs,
            "costs_by_model": model_costs
        })
    except Exception as e:
        logger.exception(f"Error getting costs: {e}")
        return _error_response(500, f"Failed to get costs: {str(e)}")


def handle_get_performance() -> Dict[str, Any]:
    """
    Handle GET /api/routing/performance
    
    Get model performance metrics.
    """
    try:
        query = """
            SELECT 
                model_name,
                provider,
                total_requests,
                successful_requests,
                failed_requests,
                avg_response_time_ms,
                total_cost,
                avg_tokens_used,
                window_start,
                window_end
            FROM model_performance
            WHERE window_end > NOW() - INTERVAL '7 days'
            ORDER BY window_end DESC, total_requests DESC
        """
        
        performance = fetch_all(query)
        
        # Calculate success rates
        for perf in performance:
            total = int(perf.get('total_requests', 0))
            successful = int(perf.get('successful_requests', 0))
            perf['success_rate'] = (successful / total * 100) if total > 0 else 0
        
        return _make_response(200, {
            "success": True,
            "performance": performance,
            "count": len(performance)
        })
    except Exception as e:
        logger.exception(f"Error getting performance: {e}")
        return _error_response(500, f"Failed to get performance: {str(e)}")


def handle_select_model(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/routing/select
    
    Select model for a task.
    """
    try:
        task_id = body.get("task_id")
        task_type = body.get("task_type", "generic")
        
        if not task_id:
            return _error_response(400, "task_id required")
        
        # Create task dict for selector
        task = {
            "id": task_id,
            "task_type": task_type
        }
        
        # Select model
        selector = get_model_selector()
        selection = selector.select_model(task)
        
        if not selection:
            return _error_response(500, "Failed to select model")
        
        # Record selection
        selector.record_selection(task_id, selection)
        
        return _make_response(200, {
            "success": True,
            "selection": selection
        })
    except Exception as e:
        logger.exception(f"Error selecting model: {e}")
        return _error_response(500, f"Failed to select model: {str(e)}")


__all__ = [
    "handle_get_policies",
    "handle_get_costs",
    "handle_get_performance",
    "handle_select_model"
]
