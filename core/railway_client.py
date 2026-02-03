"""
Railway API Client

Fetches logs from Railway API for error detection and monitoring.

Part of Milestone 3: Railway Logs Crawler
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import urllib.request
import urllib.error
import time

logger = logging.getLogger(__name__)


class RailwayClient:
    """Client for Railway GraphQL API."""
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize Railway client.
        
        Args:
            api_token: Railway API token (or use RAILWAY_API_TOKEN env var)
        """
        self.api_token = api_token or os.getenv("RAILWAY_API_TOKEN", "")
        self.api_url = "https://backboard.railway.app/graphql/v2"
        
        if not self.api_token:
            logger.warning("No Railway API token provided")
    
    def _make_request(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make GraphQL request to Railway API.
        
        Args:
            query: GraphQL query string
            variables: Query variables
            
        Returns:
            Response data
        """
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "variables": variables or {}
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(self.api_url, data=data, headers=headers, method='POST')
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                if "errors" in result:
                    raise Exception(f"GraphQL errors: {result['errors']}")
                
                return result.get("data", {})
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            raise Exception(f"HTTP {e.code}: {error_body}")
    
    def get_projects(self) -> List[Dict[str, Any]]:
        """
        Get all projects accessible to this token.
        
        Returns:
            List of projects with id, name, description
        """
        query = """
        query {
            projects {
                edges {
                    node {
                        id
                        name
                        description
                    }
                }
            }
        }
        """
        
        try:
            data = self._make_request(query)
            projects = []
            for edge in data.get("projects", {}).get("edges", []):
                projects.append(edge["node"])
            return projects
        except Exception as e:
            logger.exception(f"Error fetching projects: {e}")
            return []
    
    def get_environments(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Get environments for a project.
        
        Args:
            project_id: Railway project ID
            
        Returns:
            List of environments with id, name
        """
        query = """
        query($projectId: String!) {
            project(id: $projectId) {
                environments {
                    edges {
                        node {
                            id
                            name
                        }
                    }
                }
            }
        }
        """
        
        try:
            data = self._make_request(query, {"projectId": project_id})
            environments = []
            for edge in data.get("project", {}).get("environments", {}).get("edges", []):
                environments.append(edge["node"])
            return environments
        except Exception as e:
            logger.exception(f"Error fetching environments: {e}")
            return []
    
    def get_deployments(self, project_id: str, environment_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent deployments for an environment.
        
        Args:
            project_id: Railway project ID
            environment_id: Environment ID
            limit: Max deployments to fetch
            
        Returns:
            List of deployments
        """
        query = """
        query($projectId: String!, $environmentId: String!) {
            deployments(
                input: {
                    projectId: $projectId
                    environmentId: $environmentId
                }
                first: 10
            ) {
                edges {
                    node {
                        id
                        status
                        createdAt
                        staticUrl
                    }
                }
            }
        }
        """
        
        try:
            data = self._make_request(query, {
                "projectId": project_id,
                "environmentId": environment_id
            })
            deployments = []
            for edge in data.get("deployments", {}).get("edges", []):
                deployments.append(edge["node"])
            return deployments
        except Exception as e:
            logger.exception(f"Error fetching deployments: {e}")
            return []
    
    def get_logs(
        self,
        deployment_id: str,
        limit: int = 100,
        filter_level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get logs for a deployment.
        
        Note: Railway's GraphQL API has limited log access.
        This is a simplified implementation.
        
        Args:
            deployment_id: Deployment ID
            limit: Max logs to fetch
            filter_level: Filter by level (ERROR, WARN, INFO)
            
        Returns:
            List of log entries
        """
        # Note: Railway's actual log API may differ
        # This is a placeholder for the structure
        query = """
        query($deploymentId: String!) {
            deployment(id: $deploymentId) {
                logs {
                    edges {
                        node {
                            message
                            timestamp
                            severity
                        }
                    }
                }
            }
        }
        """
        
        try:
            data = self._make_request(query, {"deploymentId": deployment_id})
            logs = []
            for edge in data.get("deployment", {}).get("logs", {}).get("edges", []):
                log = edge["node"]
                
                # Filter by level if specified
                if filter_level and log.get("severity") != filter_level:
                    continue
                
                logs.append({
                    "message": log.get("message", ""),
                    "timestamp": log.get("timestamp", ""),
                    "level": log.get("severity", "INFO"),
                    "raw": log
                })
                
                if len(logs) >= limit:
                    break
            
            return logs
        except Exception as e:
            logger.exception(f"Error fetching logs: {e}")
            return []
    
    def test_connection(self) -> bool:
        """
        Test if API token is valid.
        
        Returns:
            True if connection successful
        """
        try:
            projects = self.get_projects()
            logger.info(f"Railway API connection successful. Found {len(projects)} projects.")
            return True
        except Exception as e:
            logger.error(f"Railway API connection failed: {e}")
            return False


# Singleton instance
_railway_client = None


def get_railway_client() -> RailwayClient:
    """Get or create Railway client singleton."""
    global _railway_client
    if _railway_client is None:
        _railway_client = RailwayClient()
    return _railway_client


__all__ = ["RailwayClient", "get_railway_client"]
