"""
Engine API Endpoints

REST API for autonomy engine control and monitoring.

Endpoints:
    GET /api/engine/status - Get engine status
    POST /api/engine/start - Start autonomy loop
    POST /api/engine/stop - Stop autonomy loop
    GET /api/engine/assignments - Get task assignments
    GET /api/engine/workers - Get worker status

Part of Milestone 5: Engine Autonomy Restoration
"""

import json
import logging
from typing import Dict, Any

from core.autonomy_loop import get_autonomy_loop
from core.database import fetch_all, _db

def _escape_sql_value(val: Any) -> str:
    """Escape a value for SQL insertion."""
    if val is None:
        return "NULL"
    elif isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    elif isinstance(val, (int, float)):
        return str(val)
    elif isinstance(val, (dict, list)):
        return _db._format_value(val)
    else:
        return _db._format_value(str(val))

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


def handle_get_status() -> Dict[str, Any]:
    """
    Handle GET /api/engine/status
    
    Get autonomy engine status.
    """
    try:
        loop = get_autonomy_loop()
        status = loop.get_status()
        
        return _make_response(200, {
            "success": True,
            "status": status
        })
    except Exception as e:
        logger.exception(f"Error getting status: {e}")
        return _error_response(500, f"Failed to get status: {str(e)}")


def handle_start() -> Dict[str, Any]:
    """
    Handle POST /api/engine/start
    
    Start the autonomy loop.
    """
    try:
        loop = get_autonomy_loop()
        success = loop.start()
        
        if success:
            return _make_response(200, {
                "success": True,
                "message": "Autonomy loop started"
            })
        else:
            return _error_response(400, "Failed to start loop (may already be running)")
    except Exception as e:
        logger.exception(f"Error starting loop: {e}")
        return _error_response(500, f"Failed to start loop: {str(e)}")


def handle_stop() -> Dict[str, Any]:
    """
    Handle POST /api/engine/stop
    
    Stop the autonomy loop.
    """
    try:
        loop = get_autonomy_loop()
        success = loop.stop()
        
        if success:
            return _make_response(200, {
                "success": True,
                "message": "Autonomy loop stopped"
            })
        else:
            return _error_response(400, "Failed to stop loop (may not be running)")
    except Exception as e:
        logger.exception(f"Error stopping loop: {e}")
        return _error_response(500, f"Failed to stop loop: {str(e)}")


def handle_get_assignments(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/engine/assignments
    
    Get task assignments.
    """
    try:
        limit = int(query_params.get("limit", ["50"])[0])
        status = query_params.get("status", [None])[0]
        
        # Build query with inlined values for Neon HTTP API
        where_clause = "1=1"
        if status:
            where_clause = f"ta.status = {_escape_sql_value(status)}"
        
        query = f"""
            SELECT 
                ta.id,
                ta.task_id,
                ta.worker_id,
                ta.assigned_at,
                ta.started_at,
                ta.completed_at,
                ta.status,
                ta.retry_count,
                t.task_type,
                t.description,
                t.priority,
                w.worker_id as worker_name
            FROM task_assignments ta
            JOIN governance_tasks t ON t.id = ta.task_id
            LEFT JOIN workers w ON w.id = ta.worker_id
            WHERE {where_clause}
            ORDER BY ta.assigned_at DESC
            LIMIT {limit}
        """
        
        assignments = fetch_all(query)
        
        return _make_response(200, {
            "success": True,
            "assignments": assignments,
            "count": len(assignments)
        })
    except Exception as e:
        logger.exception(f"Error getting assignments: {e}")
        return _error_response(500, f"Failed to get assignments: {str(e)}")


def handle_get_workers() -> Dict[str, Any]:
    """
    Handle GET /api/engine/workers
    
    Get worker status.
    """
    try:
        query = """
            SELECT 
                w.id,
                w.worker_id,
                w.worker_type,
                w.status,
                w.current_task_id,
                w.last_heartbeat,
                w.started_at,
                COUNT(DISTINCT wc.capability) as capability_count,
                COUNT(DISTINCT ta.id) FILTER (WHERE ta.status IN ('assigned', 'running')) as active_tasks
            FROM worker_registry w
            LEFT JOIN worker_capabilities wc ON wc.worker_id = w.worker_id
            LEFT JOIN task_assignments ta ON ta.worker_id = w.worker_id
            GROUP BY w.worker_id
            ORDER BY w.last_heartbeat DESC
        """
        
        workers = fetch_all(query)
        
        # Get capabilities for each worker
        for worker in workers:
            cap_query = f"""
                SELECT capability, proficiency
                FROM worker_capabilities
                WHERE worker_id = {_escape_sql_value(worker['id'])}
            """
            capabilities = fetch_all(cap_query)
            worker['capabilities'] = capabilities
        
        return _make_response(200, {
            "success": True,
            "workers": workers,
            "count": len(workers)
        })
    except Exception as e:
        logger.exception(f"Error getting workers: {e}")
        return _error_response(500, f"Failed to get workers: {str(e)}")


__all__ = [
    "handle_get_status",
    "handle_start",
    "handle_stop",
    "handle_get_assignments",
    "handle_get_workers"
]
