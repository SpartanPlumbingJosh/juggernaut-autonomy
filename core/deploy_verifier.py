"""
Deployment Verifier Module
==========================

Verifies that code changes have been successfully deployed and are operational.
Supports Railway, Vercel, and generic HTTP health checks.

This module is part of the verification chain system (VERCHAIN-07).

Usage:
    verifier = DeployVerifier()
    
    # Wait for deployment after merge
    result = verifier.wait_for_deploy(service_id, commit_sha, timeout=300)
    
    # Check specific platform status
    result = verifier.check_railway_status(service_id)
    result = verifier.check_vercel_status(project_id)
    
    # Run health check
    passed = verifier.run_health_check(url, expected_status=200)
    
    # Full verification for a task
    result = verifier.verify_deployment(task)
"""

import os
import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime, timezone


class DeployStatus(Enum):
    """Deployment status states."""
    PENDING = "pending"
    BUILDING = "building"
    DEPLOYING = "deploying"
    SUCCESS = "success"
    FAILED = "failed"
    CRASHED = "crashed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"
    
    @classmethod
    def from_railway(cls, status: str) -> "DeployStatus":
        """Map Railway status to DeployStatus."""
        status_map = {
            "QUEUED": cls.PENDING,
            "INITIALIZING": cls.PENDING,
            "BUILDING": cls.BUILDING,
            "DEPLOYING": cls.DEPLOYING,
            "SUCCESS": cls.SUCCESS,
            "RUNNING": cls.SUCCESS,
            "FAILED": cls.FAILED,
            "CRASHED": cls.CRASHED,
            "CANCELLED": cls.CANCELLED,
            "REMOVED": cls.CANCELLED,
        }
        return status_map.get(status.upper(), cls.UNKNOWN)
    
    @classmethod
    def from_vercel(cls, state: str, readyState: str = None) -> "DeployStatus":
        """Map Vercel status to DeployStatus."""
        # Vercel uses 'state' for deployment state and 'readyState' for build state
        state_map = {
            "QUEUED": cls.PENDING,
            "BUILDING": cls.BUILDING,
            "INITIALIZING": cls.DEPLOYING,
            "READY": cls.SUCCESS,
            "ERROR": cls.FAILED,
            "CANCELED": cls.CANCELLED,
        }
        return state_map.get((readyState or state or "").upper(), cls.UNKNOWN)


@dataclass
class DeployResult:
    """Result of a deployment verification check."""
    status: DeployStatus
    service_id: Optional[str] = None
    deployment_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    health_check_passed: bool = False
    health_check_response_ms: Optional[int] = None
    commit_sha: Optional[str] = None
    deployed_at: Optional[str] = None
    platform: str = "unknown"
    raw_data: Dict[str, Any] = field(default_factory=dict)
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @property
    def is_success(self) -> bool:
        """Check if deployment was successful."""
        return self.status == DeployStatus.SUCCESS
    
    @property
    def is_pending(self) -> bool:
        """Check if deployment is still in progress."""
        return self.status in [DeployStatus.PENDING, DeployStatus.BUILDING, DeployStatus.DEPLOYING]
    
    @property
    def is_failed(self) -> bool:
        """Check if deployment failed."""
        return self.status in [DeployStatus.FAILED, DeployStatus.CRASHED, DeployStatus.CANCELLED]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "service_id": self.service_id,
            "deployment_id": self.deployment_id,
            "url": self.url,
            "error": self.error,
            "health_check_passed": self.health_check_passed,
            "health_check_response_ms": self.health_check_response_ms,
            "commit_sha": self.commit_sha,
            "deployed_at": self.deployed_at,
            "platform": self.platform,
            "checked_at": self.checked_at,
        }


class DeployVerifier:
    """
    Deployment verification engine.
    
    Verifies that code has been successfully deployed and is operational
    across multiple platforms (Railway, Vercel) and via health checks.
    """
    
    def __init__(
        self,
        railway_token: Optional[str] = None,
        vercel_token: Optional[str] = None,
        github_token: Optional[str] = None,
    ):
        """
        Initialize the deployment verifier.
        
        Args:
            railway_token: Railway API token (or from RAILWAY_API_TOKEN env)
            vercel_token: Vercel API token (or from VERCEL_TOKEN env)
            github_token: GitHub token for commit verification (or from GITHUB_TOKEN env)
        """
        self.railway_token = railway_token or os.getenv("RAILWAY_API_TOKEN") or os.getenv("RAILWAY_TOKEN", "")
        self.vercel_token = vercel_token or os.getenv("VERCEL_TOKEN", "")
        self.github_token = github_token or os.getenv("GITHUB_TOKEN", "")
        
        self.railway_api_url = "https://backboard.railway.com/graphql/v2"
        self.vercel_api_url = "https://api.vercel.com"
    
    def wait_for_deploy(
        self,
        service_id: str,
        commit_sha: Optional[str] = None,
        timeout: int = 300,
        poll_interval: int = 10,
        platform: str = "railway"
    ) -> DeployResult:
        """
        Wait for a deployment to complete, polling until success or timeout.
        
        Args:
            service_id: The service/project ID to check
            commit_sha: Optional commit SHA to verify was deployed
            timeout: Maximum seconds to wait (default 300 = 5 minutes)
            poll_interval: Seconds between status checks (default 10)
            platform: Platform to check ("railway" or "vercel")
            
        Returns:
            DeployResult with final deployment status
        """
        start_time = time.time()
        last_result = None
        
        while (time.time() - start_time) < timeout:
            if platform.lower() == "vercel":
                result = self.check_vercel_status(service_id)
            else:
                result = self.check_railway_status(service_id)
            
            last_result = result
            
            # Check if we're looking for a specific commit
            if commit_sha and result.commit_sha:
                if result.commit_sha != commit_sha and result.commit_sha[:7] != commit_sha[:7]:
                    # Not the right commit yet, keep waiting
                    time.sleep(poll_interval)
                    continue
            
            # Check deployment status
            if result.is_success:
                return result
            elif result.is_failed:
                return result
            elif result.is_pending:
                # Still in progress, wait and retry
                time.sleep(poll_interval)
                continue
            else:
                # Unknown status, wait and retry
                time.sleep(poll_interval)
                continue
        
        # Timeout reached
        if last_result:
            last_result.error = f"Timeout after {timeout}s waiting for deployment"
            return last_result
        
        return DeployResult(
            status=DeployStatus.UNKNOWN,
            service_id=service_id,
            error=f"Timeout after {timeout}s waiting for deployment",
            platform=platform
        )
    
    def check_railway_status(self, service_id: str) -> DeployResult:
        """
        Check the current deployment status of a Railway service.
        
        Args:
            service_id: Railway service ID
            
        Returns:
            DeployResult with current status
        """
        if not self.railway_token:
            return DeployResult(
                status=DeployStatus.UNKNOWN,
                service_id=service_id,
                error="No Railway API token configured",
                platform="railway"
            )
        
        # GraphQL query to get latest deployment
        query = """
        query GetDeployments($serviceId: String!) {
            deployments(first: 1, input: {serviceId: $serviceId}) {
                edges {
                    node {
                        id
                        status
                        createdAt
                        staticUrl
                        meta
                    }
                }
            }
        }
        """
        
        try:
            data = json.dumps({
                "query": query,
                "variables": {"serviceId": service_id}
            }).encode("utf-8")
            
            req = urllib.request.Request(
                self.railway_api_url,
                data=data,
                method="POST"
            )
            req.add_header("Authorization", f"Bearer {self.railway_token}")
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "Juggernaut-DeployVerifier/1.0")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
            
            # Check for errors
            if "errors" in result:
                return DeployResult(
                    status=DeployStatus.UNKNOWN,
                    service_id=service_id,
                    error=str(result["errors"]),
                    platform="railway",
                    raw_data=result
                )
            
            edges = result.get("data", {}).get("deployments", {}).get("edges", [])
            
            if not edges:
                return DeployResult(
                    status=DeployStatus.UNKNOWN,
                    service_id=service_id,
                    error="No deployments found",
                    platform="railway"
                )
            
            deployment = edges[0].get("node", {})
            status_str = deployment.get("status", "UNKNOWN")
            meta = deployment.get("meta") or {}
            
            # Extract commit SHA from meta if available
            commit_sha = None
            if isinstance(meta, dict):
                commit_sha = meta.get("commitSha") or meta.get("commit_sha")
            elif isinstance(meta, str):
                try:
                    meta_dict = json.loads(meta)
                    commit_sha = meta_dict.get("commitSha") or meta_dict.get("commit_sha")
                except:
                    pass
            
            return DeployResult(
                status=DeployStatus.from_railway(status_str),
                service_id=service_id,
                deployment_id=deployment.get("id"),
                url=deployment.get("staticUrl"),
                commit_sha=commit_sha,
                deployed_at=deployment.get("createdAt"),
                platform="railway",
                raw_data=deployment
            )
            
        except urllib.error.HTTPError as e:
            return DeployResult(
                status=DeployStatus.UNKNOWN,
                service_id=service_id,
                error=f"HTTP error {e.code}: {e.reason}",
                platform="railway"
            )
        except urllib.error.URLError as e:
            return DeployResult(
                status=DeployStatus.UNKNOWN,
                service_id=service_id,
                error=f"Connection error: {str(e.reason)}",
                platform="railway"
            )
        except Exception as e:
            return DeployResult(
                status=DeployStatus.UNKNOWN,
                service_id=service_id,
                error=f"Error checking Railway: {str(e)}",
                platform="railway"
            )
    
    def check_vercel_status(self, project_id: str, team_id: Optional[str] = None) -> DeployResult:
        """
        Check the current deployment status of a Vercel project.
        
        Args:
            project_id: Vercel project ID or name
            team_id: Optional Vercel team ID
            
        Returns:
            DeployResult with current status
        """
        if not self.vercel_token:
            return DeployResult(
                status=DeployStatus.UNKNOWN,
                service_id=project_id,
                error="No Vercel API token configured",
                platform="vercel"
            )
        
        try:
            # Build URL with optional team parameter
            url = f"{self.vercel_api_url}/v6/deployments?projectId={project_id}&limit=1"
            if team_id:
                url += f"&teamId={team_id}"
            
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {self.vercel_token}")
            req.add_header("User-Agent", "Juggernaut-DeployVerifier/1.0")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
            
            deployments = result.get("deployments", [])
            
            if not deployments:
                return DeployResult(
                    status=DeployStatus.UNKNOWN,
                    service_id=project_id,
                    error="No deployments found",
                    platform="vercel"
                )
            
            deployment = deployments[0]
            state = deployment.get("state", "")
            ready_state = deployment.get("readyState", "")
            
            # Extract commit info
            meta = deployment.get("meta", {}) or {}
            commit_sha = meta.get("githubCommitSha") or meta.get("gitlabCommitSha") or meta.get("bitbucketCommitSha")
            
            return DeployResult(
                status=DeployStatus.from_vercel(state, ready_state),
                service_id=project_id,
                deployment_id=deployment.get("uid"),
                url=deployment.get("url"),
                commit_sha=commit_sha,
                deployed_at=deployment.get("createdAt"),
                platform="vercel",
                raw_data=deployment
            )
            
        except urllib.error.HTTPError as e:
            return DeployResult(
                status=DeployStatus.UNKNOWN,
                service_id=project_id,
                error=f"HTTP error {e.code}: {e.reason}",
                platform="vercel"
            )
        except urllib.error.URLError as e:
            return DeployResult(
                status=DeployStatus.UNKNOWN,
                service_id=project_id,
                error=f"Connection error: {str(e.reason)}",
                platform="vercel"
            )
        except Exception as e:
            return DeployResult(
                status=DeployStatus.UNKNOWN,
                service_id=project_id,
                error=f"Error checking Vercel: {str(e)}",
                platform="vercel"
            )
    
    def run_health_check(
        self,
        url: str,
        expected_status: int = 200,
        timeout: int = 30,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        expected_body_contains: Optional[str] = None,
        retry_count: int = 3,
        retry_delay: int = 5
    ) -> bool:
        """
        Perform an HTTP health check against an endpoint.
        
        Args:
            url: The URL to check
            expected_status: Expected HTTP status code (default 200)
            timeout: Request timeout in seconds (default 30)
            method: HTTP method (default GET)
            headers: Optional additional headers
            expected_body_contains: Optional string that must be in response body
            retry_count: Number of retries on failure (default 3)
            retry_delay: Seconds between retries (default 5)
            
        Returns:
            True if health check passed, False otherwise
        """
        for attempt in range(retry_count):
            try:
                req = urllib.request.Request(url, method=method)
                req.add_header("User-Agent", "Juggernaut-DeployVerifier/1.0")
                
                if headers:
                    for key, value in headers.items():
                        req.add_header(key, value)
                
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    status_code = response.status
                    body = response.read().decode("utf-8", errors="ignore")
                    
                    if status_code != expected_status:
                        if attempt < retry_count - 1:
                            time.sleep(retry_delay)
                            continue
                        return False
                    
                    if expected_body_contains and expected_body_contains not in body:
                        if attempt < retry_count - 1:
                            time.sleep(retry_delay)
                            continue
                        return False
                    
                    return True
                    
            except Exception as e:
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)
                    continue
                return False
        
        return False
    
    def run_health_check_detailed(
        self,
        url: str,
        expected_status: int = 200,
        timeout: int = 30,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        expected_body_contains: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform a health check and return detailed results.
        
        Args:
            url: The URL to check
            expected_status: Expected HTTP status code
            timeout: Request timeout in seconds
            method: HTTP method
            headers: Optional additional headers
            expected_body_contains: Optional string that must be in response body
            
        Returns:
            Dictionary with detailed health check results
        """
        result = {
            "url": url,
            "method": method,
            "expected_status": expected_status,
            "passed": False,
            "status_code": None,
            "response_time_ms": None,
            "body_preview": None,
            "error": None,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            req = urllib.request.Request(url, method=method)
            req.add_header("User-Agent", "Juggernaut-DeployVerifier/1.0")
            
            if headers:
                for key, value in headers.items():
                    req.add_header(key, value)
            
            start_time = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as response:
                response_time = time.time() - start_time
                status_code = response.status
                body = response.read().decode("utf-8", errors="ignore")
                
                result["status_code"] = status_code
                result["response_time_ms"] = int(response_time * 1000)
                result["body_preview"] = body[:500] if body else None
                
                if status_code != expected_status:
                    result["error"] = f"Status {status_code}, expected {expected_status}"
                    return result
                
                if expected_body_contains and expected_body_contains not in body:
                    result["error"] = f"Response body does not contain: {expected_body_contains}"
                    return result
                
                result["passed"] = True
                return result
                
        except urllib.error.HTTPError as e:
            result["status_code"] = e.code
            result["error"] = f"HTTP error: {e.code} {e.reason}"
            return result
        except urllib.error.URLError as e:
            result["error"] = f"Connection error: {str(e.reason)}"
            return result
        except Exception as e:
            result["error"] = f"Health check error: {str(e)}"
            return result
    
    def verify_deployment(
        self,
        task: Dict[str, Any],
        run_health_check: bool = True
    ) -> DeployResult:
        """
        Full deployment verification for a task.
        
        Checks:
        1. Deployment platform status (Railway or Vercel)
        2. Optionally runs health check against endpoint
        
        Args:
            task: Task dictionary with deployment metadata
            run_health_check: Whether to run health check after deployment status
            
        Returns:
            DeployResult with full verification status
        """
        # Extract deployment info from task
        metadata = task.get("metadata") or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        endpoint_def = task.get("endpoint_definition") or {}
        if isinstance(endpoint_def, str):
            endpoint_def = json.loads(endpoint_def)
        
        # Determine platform and service ID
        platform = metadata.get("deploy_platform", "railway").lower()
        service_id = (
            metadata.get("railway_service_id") or
            metadata.get("vercel_project_id") or
            metadata.get("service_id") or
            os.getenv("RAILWAY_SERVICE_ID")
        )
        
        if not service_id:
            return DeployResult(
                status=DeployStatus.UNKNOWN,
                error="No service ID found in task metadata",
                platform=platform
            )
        
        # Check deployment status
        if platform == "vercel":
            result = self.check_vercel_status(service_id)
        else:
            result = self.check_railway_status(service_id)
        
        # If deployment not successful, return early
        if not result.is_success:
            return result
        
        # Run health check if configured
        if run_health_check and endpoint_def:
            health_url = endpoint_def.get("url")
            
            if health_url:
                # If URL is relative, combine with deployment URL
                if health_url.startswith("/") and result.url:
                    base_url = result.url.rstrip("/")
                    if not base_url.startswith("http"):
                        base_url = f"https://{base_url}"
                    health_url = f"{base_url}{health_url}"
                
                health_result = self.run_health_check_detailed(
                    url=health_url,
                    expected_status=endpoint_def.get("expected_status", 200),
                    method=endpoint_def.get("method", "GET"),
                    expected_body_contains=endpoint_def.get("expected_body_contains")
                )
                
                result.health_check_passed = health_result["passed"]
                result.health_check_response_ms = health_result.get("response_time_ms")
                
                if not health_result["passed"]:
                    result.error = f"Health check failed: {health_result.get('error')}"
        
        return result


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def check_railway_deployment(service_id: str) -> DeployResult:
    """Quick check of Railway deployment status."""
    verifier = DeployVerifier()
    return verifier.check_railway_status(service_id)


def check_vercel_deployment(project_id: str) -> DeployResult:
    """Quick check of Vercel deployment status."""
    verifier = DeployVerifier()
    return verifier.check_vercel_status(project_id)


def wait_for_railway_deploy(
    service_id: str,
    commit_sha: Optional[str] = None,
    timeout: int = 300
) -> DeployResult:
    """Wait for Railway deployment to complete."""
    verifier = DeployVerifier()
    return verifier.wait_for_deploy(
        service_id=service_id,
        commit_sha=commit_sha,
        timeout=timeout,
        platform="railway"
    )


def wait_for_vercel_deploy(
    project_id: str,
    commit_sha: Optional[str] = None,
    timeout: int = 300
) -> DeployResult:
    """Wait for Vercel deployment to complete."""
    verifier = DeployVerifier()
    return verifier.wait_for_deploy(
        service_id=project_id,
        commit_sha=commit_sha,
        timeout=timeout,
        platform="vercel"
    )


def run_health_check(
    url: str,
    expected_status: int = 200,
    timeout: int = 30
) -> bool:
    """Run a simple health check against a URL."""
    verifier = DeployVerifier()
    return verifier.run_health_check(url, expected_status, timeout)
