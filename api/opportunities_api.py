"""
Opportunities API - Expose revenue pipeline data to Spartan HQ.

Endpoints:
- GET /opportunities - List all opportunities with filtering
- GET /opportunities/{id} - Get single opportunity details
- GET /opportunities/stats - Pipeline statistics
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs

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


async def handle_list_opportunities(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    List opportunities with optional filtering.
    
    Query params:
    - status: Filter by status (open, won, lost, etc.)
    - limit: Max results (default 50)
    - offset: Pagination offset
    """
    try:
        # Parse query params
        status = query_params.get("status", [""])[0] if isinstance(query_params.get("status"), list) else query_params.get("status", "")
        limit = int(query_params.get("limit", ["50"])[0] if isinstance(query_params.get("limit"), list) else query_params.get("limit", 50))
        offset = int(query_params.get("offset", ["0"])[0] if isinstance(query_params.get("offset"), list) else query_params.get("offset", 0))
        
        # Build query
        where_clause = ""
        if status:
            where_clause = f"WHERE status = '{status}'"
        
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
            priority,
            metadata,
            created_at,
            updated_at,
            expires_at
        FROM opportunities
        {where_clause}
        ORDER BY 
            CASE priority 
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                ELSE 5
            END,
            created_at DESC
        LIMIT {limit}
        OFFSET {offset}
        """
        
        result = await query_db(sql)
        opportunities = result.get("rows", [])
        
        # Get total count
        count_sql = f"SELECT COUNT(*) as total FROM opportunities {where_clause}"
        count_result = await query_db(count_sql)
        total = count_result.get("rows", [{}])[0].get("total", 0)
        
        return _make_response(200, {
            "opportunities": opportunities,
            "total": total,
            "limit": limit,
            "offset": offset
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch opportunities: {str(e)}")


async def handle_get_opportunity(opportunity_id: str) -> Dict[str, Any]:
    """Get single opportunity by ID."""
    try:
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
            priority,
            metadata,
            created_at,
            updated_at,
            expires_at
        FROM opportunities
        WHERE id = '{opportunity_id}'
        """
        
        result = await query_db(sql)
        rows = result.get("rows", [])
        
        if not rows:
            return _error_response(404, f"Opportunity not found: {opportunity_id}")
        
        return _make_response(200, {"opportunity": rows[0]})
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch opportunity: {str(e)}")


async def handle_opportunity_stats() -> Dict[str, Any]:
    """Get pipeline statistics."""
    try:
        # Overall stats
        stats_sql = """
        SELECT 
            COUNT(*) as total_opportunities,
            COUNT(*) FILTER (WHERE status = 'open') as open_count,
            COUNT(*) FILTER (WHERE status = 'won') as won_count,
            COUNT(*) FILTER (WHERE status = 'lost') as lost_count,
            SUM(estimated_value) FILTER (WHERE status = 'open') as pipeline_value,
            AVG(confidence_score) FILTER (WHERE status = 'open') as avg_confidence,
            SUM(estimated_value) FILTER (WHERE status = 'won') as total_revenue
        FROM opportunities
        """
        
        stats_result = await query_db(stats_sql)
        stats = stats_result.get("rows", [{}])[0]
        
        # By category
        category_sql = """
        SELECT 
            category,
            COUNT(*) as count,
            SUM(estimated_value) as total_value,
            AVG(confidence_score) as avg_confidence
        FROM opportunities
        WHERE status = 'open'
        GROUP BY category
        ORDER BY total_value DESC
        LIMIT 10
        """
        
        category_result = await query_db(category_sql)
        by_category = category_result.get("rows", [])
        
        # By priority
        priority_sql = """
        SELECT 
            priority,
            COUNT(*) as count,
            SUM(estimated_value) as total_value
        FROM opportunities
        WHERE status = 'open'
        GROUP BY priority
        ORDER BY 
            CASE priority 
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                ELSE 5
            END
        """
        
        priority_result = await query_db(priority_sql)
        by_priority = priority_result.get("rows", [])
        
        return _make_response(200, {
            "stats": stats,
            "by_category": by_category,
            "by_priority": by_priority
        })
        
    except Exception as e:
        return _error_response(500, f"Failed to fetch stats: {str(e)}")


def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route opportunities API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # GET /opportunities
    if len(parts) == 1 and parts[0] == "opportunities" and method == "GET":
        return handle_list_opportunities(query_params)
    
    # GET /opportunities/stats
    if len(parts) == 2 and parts[0] == "opportunities" and parts[1] == "stats" and method == "GET":
        return handle_opportunity_stats()
    
    # GET /opportunities/{id}
    if len(parts) == 2 and parts[0] == "opportunities" and method == "GET":
        opportunity_id = parts[1]
        return handle_get_opportunity(opportunity_id)
    
    return _error_response(404, "Not found")


__all__ = ["route_request"]
