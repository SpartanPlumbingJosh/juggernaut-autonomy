"""
Logs API Endpoints

REST API for Railway logs crawler and error tracking.

Endpoints:
    POST /api/logs/crawl - Trigger manual crawl
    GET /api/logs/errors - Get error fingerprints
    GET /api/logs/errors/{fingerprint} - Get error details
    GET /api/logs/stats - Get error statistics

Part of Milestone 3: Railway Logs Crawler
"""

import json
import logging
from typing import Dict, Any

from core.log_crawler import get_log_crawler
from core.alert_rules import get_alert_engine
from core.task_creator import get_task_creator
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


def handle_crawl(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/logs/crawl
    
    Trigger manual log crawl.
    """
    try:
        project_id = body.get("project_id")
        environment_id = body.get("environment_id")
        
        if not project_id or not environment_id:
            return _error_response(400, "project_id and environment_id required")
        
        # Run crawler
        crawler = get_log_crawler()
        result = crawler.crawl(project_id, environment_id)
        
        if not result.get('success'):
            return _error_response(500, result.get('error', 'Crawl failed'))
        
        # Evaluate alert rules
        alert_engine = get_alert_engine()
        triggered_rules = alert_engine.evaluate_all_rules()
        
        # Create tasks for triggered alerts
        task_creator = get_task_creator()
        tasks_created = task_creator.process_alert_triggers(triggered_rules)
        
        return _make_response(200, {
            "success": True,
            "logs_processed": result.get('logs_processed', 0),
            "errors_found": result.get('errors_found', 0),
            "tasks_created": tasks_created,
            "duration_ms": result.get('duration_ms', 0)
        })
    except Exception as e:
        logger.exception(f"Error in crawl: {e}")
        return _error_response(500, f"Crawl failed: {str(e)}")


def handle_get_errors(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/logs/errors
    
    Get error fingerprints with pagination.
    """
    try:
        limit = int(query_params.get("limit", ["20"])[0])
        status = query_params.get("status", ["active"])[0]
        
        query = """
            SELECT 
                id,
                fingerprint,
                normalized_message,
                error_type,
                first_seen,
                last_seen,
                occurrence_count,
                status,
                task_created,
                task_id
            FROM error_fingerprints
            WHERE status = %s
            ORDER BY last_seen DESC
            LIMIT %s
        """
        
        errors = fetch_all(query, (status, limit))
        
        return _make_response(200, {
            "success": True,
            "errors": errors,
            "count": len(errors)
        })
    except Exception as e:
        logger.exception(f"Error getting errors: {e}")
        return _error_response(500, f"Failed to get errors: {str(e)}")


def handle_get_error_detail(fingerprint: str) -> Dict[str, Any]:
    """
    Handle GET /api/logs/errors/{fingerprint}
    
    Get detailed information about an error fingerprint.
    """
    try:
        # Get fingerprint details
        fp_query = """
            SELECT 
                f.*,
                l.message as sample_message,
                l.timestamp as sample_timestamp
            FROM error_fingerprints f
            LEFT JOIN railway_logs l ON l.id = f.sample_log_id
            WHERE f.fingerprint = %s
        """
        
        fp_results = fetch_all(fp_query, (fingerprint,))
        if not fp_results:
            return _error_response(404, "Fingerprint not found")
        
        fingerprint_data = fp_results[0]
        
        # Get recent occurrences
        occ_query = """
            SELECT 
                o.occurred_at,
                l.message,
                l.log_level
            FROM error_occurrences o
            JOIN railway_logs l ON l.id = o.log_id
            WHERE o.fingerprint_id = %s
            ORDER BY o.occurred_at DESC
            LIMIT 10
        """
        
        occurrences = fetch_all(occ_query, (fingerprint_data['id'],))
        
        return _make_response(200, {
            "success": True,
            "fingerprint": fingerprint_data,
            "recent_occurrences": occurrences
        })
    except Exception as e:
        logger.exception(f"Error getting error detail: {e}")
        return _error_response(500, f"Failed to get error detail: {str(e)}")


def handle_get_stats() -> Dict[str, Any]:
    """
    Handle GET /api/logs/stats
    
    Get error statistics.
    """
    try:
        # Total active errors
        total_query = """
            SELECT COUNT(*) as count
            FROM error_fingerprints
            WHERE status = 'active'
        """
        total_result = fetch_all(total_query)
        total_errors = int(total_result[0]['count']) if total_result else 0
        
        # New errors today
        new_query = """
            SELECT COUNT(*) as count
            FROM error_fingerprints
            WHERE 
                status = 'active'
                AND first_seen > NOW() - INTERVAL '24 hours'
        """
        new_result = fetch_all(new_query)
        new_today = int(new_result[0]['count']) if new_result else 0
        
        # Total occurrences today
        occ_query = """
            SELECT COUNT(*) as count
            FROM error_occurrences
            WHERE occurred_at > NOW() - INTERVAL '24 hours'
        """
        occ_result = fetch_all(occ_query)
        occurrences_today = int(occ_result[0]['count']) if occ_result else 0
        
        # Tasks created
        task_query = """
            SELECT COUNT(*) as count
            FROM error_fingerprints
            WHERE task_created = TRUE
        """
        task_result = fetch_all(task_query)
        tasks_created = int(task_result[0]['count']) if task_result else 0
        
        return _make_response(200, {
            "success": True,
            "stats": {
                "total_active_errors": total_errors,
                "new_errors_today": new_today,
                "occurrences_today": occurrences_today,
                "tasks_created": tasks_created
            }
        })
    except Exception as e:
        logger.exception(f"Error getting stats: {e}")
        return _error_response(500, f"Failed to get stats: {str(e)}")


__all__ = [
    "handle_crawl",
    "handle_get_errors",
    "handle_get_error_detail",
    "handle_get_stats"
]
