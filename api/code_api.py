"""
Code Analysis API Endpoints

REST API for GitHub code crawler and health tracking.

Endpoints:
    POST /api/code/analyze - Trigger code analysis
    GET /api/code/runs - Get analysis runs
    GET /api/code/runs/{id} - Get run details
    GET /api/code/findings - Get findings
    GET /api/code/health - Get health score

Part of Milestone 4: GitHub Code Crawler
"""

import json
import logging
from typing import Dict, Any

from core.code_crawler import get_code_crawler
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


def handle_analyze(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/code/analyze
    
    Trigger code analysis for a repository.
    """
    try:
        owner = body.get("owner")
        repo = body.get("repo")
        branch = body.get("branch", "main")
        
        if not owner or not repo:
            return _error_response(400, "owner and repo required")
        
        # Run analysis
        crawler = get_code_crawler()
        result = crawler.analyze_repository(owner, repo, branch)
        
        if not result.get('success'):
            return _error_response(500, result.get('error', 'Analysis failed'))
        
        return _make_response(200, {
            "success": True,
            "run_id": result.get('run_id'),
            "findings_count": result.get('findings_count', 0),
            "health_score": result.get('health_score', 0),
            "scores": result.get('scores', {})
        })
    except Exception as e:
        logger.exception(f"Error in analyze: {e}")
        return _error_response(500, f"Analysis failed: {str(e)}")


def handle_get_runs(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/code/runs
    
    Get code analysis runs.
    """
    try:
        limit = int(query_params.get("limit", ["10"])[0])
        
        query = """
            SELECT 
                id,
                repository,
                branch,
                commit_sha,
                started_at,
                completed_at,
                status,
                health_score,
                findings_count,
                prs_created,
                tasks_created
            FROM code_analysis_runs
            ORDER BY started_at DESC
            LIMIT %s
        """
        
        runs = fetch_all(query, (limit,))
        
        return _make_response(200, {
            "success": True,
            "runs": runs,
            "count": len(runs)
        })
    except Exception as e:
        logger.exception(f"Error getting runs: {e}")
        return _error_response(500, f"Failed to get runs: {str(e)}")


def handle_get_run_detail(run_id: str) -> Dict[str, Any]:
    """
    Handle GET /api/code/runs/{id}
    
    Get detailed information about an analysis run.
    """
    try:
        # Get run details
        run_query = """
            SELECT *
            FROM code_analysis_runs
            WHERE id = %s
        """
        
        run_results = fetch_all(run_query, (run_id,))
        if not run_results:
            return _error_response(404, "Run not found")
        
        run_data = run_results[0]
        
        # Get findings
        findings_query = """
            SELECT 
                finding_type,
                severity,
                file_path,
                line_number,
                description,
                suggestion,
                auto_fixable,
                fixed
            FROM code_findings
            WHERE run_id = %s
            ORDER BY severity DESC, file_path
        """
        
        findings = fetch_all(findings_query, (run_id,))
        
        # Get metrics
        metrics_query = """
            SELECT 
                metric_type,
                score
            FROM code_health_metrics
            WHERE run_id = %s
        """
        
        metrics = fetch_all(metrics_query, (run_id,))
        
        return _make_response(200, {
            "success": True,
            "run": run_data,
            "findings": findings,
            "metrics": metrics
        })
    except Exception as e:
        logger.exception(f"Error getting run detail: {e}")
        return _error_response(500, f"Failed to get run detail: {str(e)}")


def handle_get_findings(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/code/findings
    
    Get code findings with filters.
    """
    try:
        limit = int(query_params.get("limit", ["50"])[0])
        severity = query_params.get("severity", [None])[0]
        auto_fixable = query_params.get("auto_fixable", [None])[0]
        
        # Build query
        conditions = []
        params = []
        
        if severity:
            conditions.append("severity = %s")
            params.append(severity)
        
        if auto_fixable is not None:
            conditions.append("auto_fixable = %s")
            params.append(auto_fixable == 'true')
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT 
                f.id,
                f.finding_type,
                f.severity,
                f.file_path,
                f.line_number,
                f.description,
                f.suggestion,
                f.auto_fixable,
                f.fixed,
                r.repository,
                r.branch
            FROM code_findings f
            JOIN code_analysis_runs r ON r.id = f.run_id
            WHERE {where_clause}
            ORDER BY f.created_at DESC
            LIMIT %s
        """
        
        params.append(limit)
        findings = fetch_all(query, tuple(params))
        
        return _make_response(200, {
            "success": True,
            "findings": findings,
            "count": len(findings)
        })
    except Exception as e:
        logger.exception(f"Error getting findings: {e}")
        return _error_response(500, f"Failed to get findings: {str(e)}")


def handle_get_health() -> Dict[str, Any]:
    """
    Handle GET /api/code/health
    
    Get current code health status.
    """
    try:
        # Get latest run
        run_query = """
            SELECT 
                id,
                repository,
                health_score,
                findings_count,
                completed_at
            FROM code_analysis_runs
            WHERE status = 'completed'
            ORDER BY completed_at DESC
            LIMIT 1
        """
        
        run_results = fetch_all(run_query)
        if not run_results:
            return _make_response(200, {
                "success": True,
                "health_score": None,
                "message": "No completed analysis runs"
            })
        
        run_data = run_results[0]
        
        # Get metrics for latest run
        metrics_query = """
            SELECT 
                metric_type,
                score
            FROM code_health_metrics
            WHERE run_id = %s
        """
        
        metrics = fetch_all(metrics_query, (run_data['id'],))
        
        # Convert metrics to dict
        metrics_dict = {m['metric_type']: m['score'] for m in metrics}
        
        return _make_response(200, {
            "success": True,
            "repository": run_data['repository'],
            "health_score": run_data['health_score'],
            "findings_count": run_data['findings_count'],
            "last_analyzed": run_data['completed_at'],
            "metrics": metrics_dict
        })
    except Exception as e:
        logger.exception(f"Error getting health: {e}")
        return _error_response(500, f"Failed to get health: {str(e)}")


__all__ = [
    "handle_analyze",
    "handle_get_runs",
    "handle_get_run_detail",
    "handle_get_findings",
    "handle_get_health"
]
