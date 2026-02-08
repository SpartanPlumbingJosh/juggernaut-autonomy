"""
GitHub API Integration

Fetch repositories from GitHub for easy selection.
"""

import json
import logging
import os
from typing import Dict, Any, List
import urllib.request
import urllib.error

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


def fetch_github_repos(owner: str, github_token: str = None) -> List[Dict[str, Any]]:
    """
    Fetch repositories from GitHub for a given owner.
    
    Args:
        owner: GitHub username/organization
        github_token: Optional GitHub token for higher rate limits
        
    Returns:
        List of repository dictionaries
    """
    try:
        if owner:
            url = f"https://api.github.com/users/{owner}/repos?per_page=100&sort=updated"
        else:
            url = "https://api.github.com/user/repos?per_page=100&sort=updated"
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Juggernaut-Autonomy"
        }
        
        if github_token:
            headers["Authorization"] = f"token {github_token}"
        
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=10) as response:
            repos = json.loads(response.read().decode())
            
            # Transform to simpler format
            return [
                {
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo.get("description", ""),
                    "default_branch": repo.get("default_branch", "main"),
                    "private": repo.get("private", False),
                    "language": repo.get("language"),
                    "updated_at": repo.get("updated_at"),
                    "stars": repo.get("stargazers_count", 0)
                }
                for repo in repos
            ]
            
    except urllib.error.HTTPError as e:
        logger.error(f"GitHub API error: {e.code} - {e.reason}")
        raise Exception(f"GitHub API error: {e.code}")
    except Exception as e:
        logger.exception(f"Error fetching GitHub repos: {e}")
        raise


def handle_list_github_repos(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/github/repos
    
    List repositories from GitHub for the configured owner.
    """
    try:
        raw_owner = query_params.get("owner")

        if isinstance(raw_owner, list):
            owner = (raw_owner[0] or "").strip()
        else:
            owner = (raw_owner or "").strip() if isinstance(raw_owner, str) else ""

        github_token = (os.getenv("GITHUB_TOKEN") or "").strip()
        default_owner = (os.getenv("GITHUB_DEFAULT_OWNER") or "").strip()

        # Prefer explicit owner; otherwise fall back to env.
        effective_owner = owner or default_owner
        if not effective_owner:
            return _error_response(400, "owner is required (or set GITHUB_DEFAULT_OWNER)")

        repos = fetch_github_repos(effective_owner, github_token)
        
        return _make_response(200, {
            "success": True,
            "owner": effective_owner,
            "repositories": repos,
            "count": len(repos)
        })
        
    except Exception as e:
        logger.exception(f"Error listing GitHub repos: {e}")
        return _error_response(500, f"Failed to fetch GitHub repos: {str(e)}")


__all__ = [
    "handle_list_github_repos",
    "fetch_github_repos"
]
