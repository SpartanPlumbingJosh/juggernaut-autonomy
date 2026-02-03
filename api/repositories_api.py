"""
Repositories API Endpoints

REST API for managing tracked repositories for code health monitoring.

Endpoints:
    GET /api/repositories - List tracked repositories
    POST /api/repositories - Add new repository
    PUT /api/repositories/{id} - Update repository
    DELETE /api/repositories/{id} - Remove repository

Part of Milestone 4: Code Health Monitoring
"""

import json
import logging
from typing import Dict, Any
from datetime import datetime, timezone

from core.database import fetch_all, execute_sql

logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
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


def handle_list_repositories() -> Dict[str, Any]:
    """
    Handle GET /api/repositories
    
    List all tracked repositories.
    """
    try:
        query = """
            SELECT 
                r.id,
                r.owner,
                r.repo,
                r.display_name,
                r.default_branch,
                r.enabled,
                r.last_analyzed,
                r.created_at,
                COUNT(DISTINCT c.id) as analysis_count,
                MAX(c.health_score) as latest_health_score
            FROM tracked_repositories r
            LEFT JOIN code_analysis_runs c 
                ON c.repository = r.owner || '/' || r.repo
                AND c.status = 'completed'
            GROUP BY r.id, r.owner, r.repo, r.display_name, r.default_branch, 
                     r.enabled, r.last_analyzed, r.created_at
            ORDER BY r.enabled DESC, r.last_analyzed DESC NULLS LAST
        """
        
        repositories = fetch_all(query)
        
        return _make_response(200, {
            "success": True,
            "repositories": repositories,
            "count": len(repositories)
        })
    except Exception as e:
        logger.exception(f"Error listing repositories: {e}")
        return _error_response(500, f"Failed to list repositories: {str(e)}")


def handle_add_repository(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/repositories
    
    Add a new tracked repository.
    """
    try:
        owner = body.get("owner")
        repo = body.get("repo")
        
        if not owner or not repo:
            return _error_response(400, "owner and repo are required")
        
        display_name = body.get("display_name") or f"{owner}/{repo}"
        default_branch = body.get("default_branch", "main")
        
        query = """
            INSERT INTO tracked_repositories (
                owner,
                repo,
                display_name,
                default_branch,
                enabled
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id, owner, repo, display_name, default_branch, enabled, created_at
        """
        
        result = fetch_all(query, (owner, repo, display_name, default_branch, True))
        
        if result:
            return _make_response(201, {
                "success": True,
                "repository": result[0]
            })
        else:
            return _error_response(500, "Failed to create repository")
            
    except Exception as e:
        logger.exception(f"Error adding repository: {e}")
        if "duplicate key" in str(e).lower():
            return _error_response(409, "Repository already exists")
        return _error_response(500, f"Failed to add repository: {str(e)}")


def handle_update_repository(repo_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle PUT /api/repositories/{id}
    
    Update repository settings.
    """
    try:
        updates = []
        params = []
        
        if "display_name" in body:
            updates.append("display_name = %s")
            params.append(body["display_name"])
        
        if "default_branch" in body:
            updates.append("default_branch = %s")
            params.append(body["default_branch"])
        
        if "enabled" in body:
            updates.append("enabled = %s")
            params.append(body["enabled"])
        
        if not updates:
            return _error_response(400, "No fields to update")
        
        updates.append("updated_at = %s")
        params.append(datetime.now(timezone.utc).isoformat())
        
        params.append(repo_id)
        
        query = f"""
            UPDATE tracked_repositories
            SET {", ".join(updates)}
            WHERE id = %s
            RETURNING id, owner, repo, display_name, default_branch, enabled, updated_at
        """
        
        result = fetch_all(query, tuple(params))
        
        if result:
            return _make_response(200, {
                "success": True,
                "repository": result[0]
            })
        else:
            return _error_response(404, "Repository not found")
            
    except Exception as e:
        logger.exception(f"Error updating repository: {e}")
        return _error_response(500, f"Failed to update repository: {str(e)}")


def handle_delete_repository(repo_id: str) -> Dict[str, Any]:
    """
    Handle DELETE /api/repositories/{id}
    
    Remove a tracked repository.
    """
    try:
        query = """
            DELETE FROM tracked_repositories
            WHERE id = %s
            RETURNING id, owner, repo
        """
        
        result = fetch_all(query, (repo_id,))
        
        if result:
            return _make_response(200, {
                "success": True,
                "message": f"Repository {result[0]['owner']}/{result[0]['repo']} removed"
            })
        else:
            return _error_response(404, "Repository not found")
            
    except Exception as e:
        logger.exception(f"Error deleting repository: {e}")
        return _error_response(500, f"Failed to delete repository: {str(e)}")


__all__ = [
    "handle_list_repositories",
    "handle_add_repository",
    "handle_update_repository",
    "handle_delete_repository"
]
