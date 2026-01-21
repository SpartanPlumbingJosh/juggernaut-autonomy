"""
VERCHAIN-08: Dynamic Endpoint Verifier

Verifies that tasks are truly complete by checking their endpoint definitions.
Supports multiple verification types: HTTP, DB queries, file existence, service health,
script execution, URL accessibility, and composite checks.

This module is critical for preventing fake completions - every task must prove
it accomplished what it claimed via verifiable endpoints.
"""

import os
import json
import urllib.request
import urllib.error
import subprocess
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class EndpointType(Enum):
    """Types of endpoint verification supported."""
    HTTP = "http"
    DB_QUERY = "db_query"
    FILE_EXISTS = "file_exists"
    SERVICE_HEALTH = "service_health"
    SCRIPT = "script"
    URL_ACCESSIBLE = "url_accessible"
    COMPOSITE = "composite"


@dataclass
class EndpointResult:
    """Result of an endpoint verification check."""
    verified: bool
    endpoint_type: str
    evidence: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    response_time_ms: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


class EndpointVerifier:
    """
    Verifies task completion by checking endpoint definitions.
    
    Each task can define an endpoint_definition that specifies how to verify
    the task is truly complete. This class executes those verification checks.
    
    Example endpoint_definitions:
    
    HTTP endpoint:
        {"type": "http", "url": "/api/feature", "method": "GET", "expected_status": 200}
    
    Database query:
        {"type": "db_query", "query": "SELECT COUNT(*) FROM users WHERE active = true", 
         "expected_result": {"min_count": 1}}
    
    File exists:
        {"type": "file_exists", "repo": "owner/repo", "path": "src/feature.py", "branch": "main"}
    
    Service health:
        {"type": "service_health", "service_id": "xxx", "platform": "railway",
         "expected_status": "active"}
    
    Script execution:
        {"type": "script", "command": "python verify.py", "expected_exit": 0}
    
    URL accessible:
        {"type": "url_accessible", "url": "https://site.com/page"}
    
    Composite:
        {"type": "composite", "checks": [...], "require": "all|any"}
    """
    
    def __init__(
        self,
        db_executor=None,
        github_token: Optional[str] = None,
        railway_token: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: int = 30
    ):
        """
        Initialize the endpoint verifier.
        
        Args:
            db_executor: Function to execute SQL queries (execute_sql from main.py)
            github_token: GitHub API token for file existence checks
            railway_token: Railway API token for service health checks
            base_url: Base URL for relative HTTP endpoints (e.g., "https://api.example.com")
            timeout_seconds: Default timeout for HTTP requests
        """
        self.db_executor = db_executor
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.railway_token = railway_token or os.getenv("RAILWAY_TOKEN")
        self.base_url = base_url or os.getenv("API_BASE_URL", "")
        self.timeout = timeout_seconds
        
        # Map endpoint types to verification methods
        self._verifiers = {
            EndpointType.HTTP.value: self._verify_http,
            EndpointType.DB_QUERY.value: self._verify_db_query,
            EndpointType.FILE_EXISTS.value: self._verify_file_exists,
            EndpointType.SERVICE_HEALTH.value: self._verify_service_health,
            EndpointType.SCRIPT.value: self._verify_script,
            EndpointType.URL_ACCESSIBLE.value: self._verify_url_accessible,
            EndpointType.COMPOSITE.value: self._verify_composite,
        }
    
    def verify(self, endpoint_definition: Dict[str, Any]) -> EndpointResult:
        """
        Verify an endpoint definition.
        
        Args:
            endpoint_definition: The endpoint specification to verify
            
        Returns:
            EndpointResult with verification status and evidence
        """
        if not endpoint_definition:
            return EndpointResult(
                verified=False,
                endpoint_type="unknown",
                error="No endpoint definition provided"
            )
        
        endpoint_type = endpoint_definition.get("type", "unknown")
        verifier = self._verifiers.get(endpoint_type)
        
        if not verifier:
            return EndpointResult(
                verified=False,
                endpoint_type=endpoint_type,
                error=f"Unknown endpoint type: {endpoint_type}. Supported: {list(self._verifiers.keys())}"
            )
        
        try:
            import time
            start_time = time.time()
            result = verifier(endpoint_definition)
            elapsed_ms = int((time.time() - start_time) * 1000)
            result.response_time_ms = elapsed_ms
            return result
        except Exception as e:
            return EndpointResult(
                verified=False,
                endpoint_type=endpoint_type,
                error=f"Verification error: {str(e)}"
            )
    
    def verify_task(self, task_id: str) -> EndpointResult:
        """
        Verify a task's endpoint definition from the database.
        
        Args:
            task_id: The task ID to verify
            
        Returns:
            EndpointResult with verification status
        """
        if not self.db_executor:
            return EndpointResult(
                verified=False,
                endpoint_type="task_lookup",
                error="No database executor configured"
            )
        
        try:
            # Fetch the endpoint definition from the task
            result = self.db_executor(f"""
                SELECT endpoint_definition, endpoint_verified, title
                FROM governance_tasks
                WHERE id = '{task_id}'
            """)
            
            rows = result.get("rows", [])
            if not rows:
                return EndpointResult(
                    verified=False,
                    endpoint_type="task_lookup",
                    error=f"Task not found: {task_id}"
                )
            
            task = rows[0]
            endpoint_def = task.get("endpoint_definition")
            
            if not endpoint_def:
                return EndpointResult(
                    verified=False,
                    endpoint_type="none",
                    error="Task has no endpoint_definition",
                    details={"task_title": task.get("title")}
                )
            
            # Parse if string
            if isinstance(endpoint_def, str):
                endpoint_def = json.loads(endpoint_def)
            
            # Run the verification
            result = self.verify(endpoint_def)
            
            # Update the task's endpoint_verified status
            if result.verified:
                self.db_executor(f"""
                    UPDATE governance_tasks
                    SET endpoint_verified = TRUE,
                        endpoint_verified_at = NOW(),
                        gate_evidence = COALESCE(gate_evidence, '{{}}'::jsonb) || 
                            jsonb_build_object('endpoint_verification', '{json.dumps({
                                "verified": True,
                                "type": result.endpoint_type,
                                "checked_at": result.checked_at,
                                "response_time_ms": result.response_time_ms
                            })}')
                    WHERE id = '{task_id}'
                """)
            
            return result
            
        except Exception as e:
            return EndpointResult(
                verified=False,
                endpoint_type="task_lookup",
                error=f"Failed to verify task: {str(e)}"
            )
    
    def _verify_http(self, definition: Dict) -> EndpointResult:
        """
        Verify an HTTP endpoint.
        
        Definition format:
        {
            "type": "http",
            "url": "/api/feature" or "https://full.url/path",
            "method": "GET|POST|PUT|DELETE",
            "expected_status": 200,
            "headers": {"Authorization": "Bearer xxx"},
            "body": {...},
            "expected_body_contains": "success",
            "expected_json_path": "$.data.status",
            "expected_json_value": "active"
        }
        """
        url = definition.get("url", "")
        method = definition.get("method", "GET").upper()
        expected_status = definition.get("expected_status", 200)
        headers = definition.get("headers", {})
        body = definition.get("body")
        expected_body_contains = definition.get("expected_body_contains")
        
        # Handle relative URLs
        if url.startswith("/"):
            if not self.base_url:
                return EndpointResult(
                    verified=False,
                    endpoint_type="http",
                    error="Relative URL provided but no base_url configured"
                )
            url = self.base_url.rstrip("/") + url
        
        # Prepare request
        data = None
        if body:
            data = json.dumps(body).encode("utf-8")
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"
        
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8")
                
                # Check status code
                status_match = status_code == expected_status
                
                # Check body contains
                body_match = True
                if expected_body_contains:
                    body_match = expected_body_contains in response_body
                
                verified = status_match and body_match
                
                return EndpointResult(
                    verified=verified,
                    endpoint_type="http",
                    evidence={
                        "url": url,
                        "method": method,
                        "status_code": status_code,
                        "expected_status": expected_status,
                        "body_preview": response_body[:500] if len(response_body) > 500 else response_body
                    },
                    error=None if verified else f"Status {status_code} != {expected_status}" if not status_match else "Body content mismatch"
                )
                
        except urllib.error.HTTPError as e:
            return EndpointResult(
                verified=e.code == expected_status,
                endpoint_type="http",
                evidence={"url": url, "status_code": e.code, "expected_status": expected_status},
                error=f"HTTP {e.code}: {e.reason}" if e.code != expected_status else None
            )
        except urllib.error.URLError as e:
            return EndpointResult(
                verified=False,
                endpoint_type="http",
                error=f"URL Error: {str(e.reason)}"
            )
        except Exception as e:
            return EndpointResult(
                verified=False,
                endpoint_type="http",
                error=f"Request failed: {str(e)}"
            )
    
    def _verify_db_query(self, definition: Dict) -> EndpointResult:
        """
        Verify a database query result.
        
        Definition format:
        {
            "type": "db_query",
            "query": "SELECT COUNT(*) as cnt FROM users WHERE active = true",
            "expected_result": {
                "min_count": 1,          # Minimum row count
                "max_count": 100,        # Maximum row count
                "exact_count": 5,        # Exact row count
                "column_value": {        # Check specific column value
                    "column": "cnt",
                    "operator": ">=",    # >, <, >=, <=, ==, !=
                    "value": 10
                },
                "not_empty": true        # Just check rows exist
            }
        }
        """
        if not self.db_executor:
            return EndpointResult(
                verified=False,
                endpoint_type="db_query",
                error="No database executor configured"
            )
        
        query = definition.get("query", "")
        expected = definition.get("expected_result", {})
        
        if not query:
            return EndpointResult(
                verified=False,
                endpoint_type="db_query",
                error="No query provided"
            )
        
        # Security: Only allow SELECT queries
        query_upper = query.strip().upper()
        if not query_upper.startswith(("SELECT", "WITH")):
            return EndpointResult(
                verified=False,
                endpoint_type="db_query",
                error="Only SELECT queries allowed for verification"
            )
        
        try:
            result = self.db_executor(query)
            rows = result.get("rows", [])
            row_count = result.get("rowCount", len(rows))
            
            verified = True
            failure_reason = None
            
            # Check min_count
            if "min_count" in expected and row_count < expected["min_count"]:
                verified = False
                failure_reason = f"Row count {row_count} < min {expected['min_count']}"
            
            # Check max_count
            if "max_count" in expected and row_count > expected["max_count"]:
                verified = False
                failure_reason = f"Row count {row_count} > max {expected['max_count']}"
            
            # Check exact_count
            if "exact_count" in expected and row_count != expected["exact_count"]:
                verified = False
                failure_reason = f"Row count {row_count} != expected {expected['exact_count']}"
            
            # Check not_empty
            if expected.get("not_empty") and row_count == 0:
                verified = False
                failure_reason = "Expected non-empty result but got 0 rows"
            
            # Check column_value
            if "column_value" in expected and rows:
                col_check = expected["column_value"]
                column = col_check.get("column")
                operator = col_check.get("operator", "==")
                expected_value = col_check.get("value")
                
                if column and rows[0].get(column) is not None:
                    actual_value = rows[0][column]
                    
                    op_map = {
                        "==": lambda a, b: a == b,
                        "!=": lambda a, b: a != b,
                        ">": lambda a, b: a > b,
                        "<": lambda a, b: a < b,
                        ">=": lambda a, b: a >= b,
                        "<=": lambda a, b: a <= b,
                    }
                    
                    if operator in op_map:
                        if not op_map[operator](actual_value, expected_value):
                            verified = False
                            failure_reason = f"Column {column}: {actual_value} {operator} {expected_value} is False"
            
            return EndpointResult(
                verified=verified,
                endpoint_type="db_query",
                evidence={
                    "row_count": row_count,
                    "sample_rows": rows[:3] if rows else [],
                    "expected": expected
                },
                error=failure_reason
            )
            
        except Exception as e:
            return EndpointResult(
                verified=False,
                endpoint_type="db_query",
                error=f"Query failed: {str(e)}"
            )
    
    def _verify_file_exists(self, definition: Dict) -> EndpointResult:
        """
        Verify a file exists in a GitHub repository.
        
        Definition format:
        {
            "type": "file_exists",
            "repo": "owner/repo-name",
            "path": "src/feature.py",
            "branch": "main",
            "contains": "def my_function"  # Optional: check file contains string
        }
        """
        repo = definition.get("repo", "")
        path = definition.get("path", "")
        branch = definition.get("branch", "main")
        contains = definition.get("contains")
        
        if not repo or not path:
            return EndpointResult(
                verified=False,
                endpoint_type="file_exists",
                error="Missing repo or path"
            )
        
        if not self.github_token:
            return EndpointResult(
                verified=False,
                endpoint_type="file_exists",
                error="No GitHub token configured"
            )
        
        try:
            url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {self.github_token}")
            req.add_header("Accept", "application/vnd.github.v3+json")
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                
                file_exists = data.get("type") == "file"
                
                # If content check requested, decode and verify
                content_match = True
                if contains and file_exists and data.get("content"):
                    content = base64.b64decode(data["content"]).decode("utf-8")
                    content_match = contains in content
                
                verified = file_exists and content_match
                
                return EndpointResult(
                    verified=verified,
                    endpoint_type="file_exists",
                    evidence={
                        "repo": repo,
                        "path": path,
                        "branch": branch,
                        "sha": data.get("sha"),
                        "size": data.get("size"),
                        "content_checked": contains is not None
                    },
                    error=None if verified else "File not found or content mismatch"
                )
                
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return EndpointResult(
                    verified=False,
                    endpoint_type="file_exists",
                    error=f"File not found: {repo}/{path} on branch {branch}"
                )
            return EndpointResult(
                verified=False,
                endpoint_type="file_exists",
                error=f"GitHub API error: {e.code}"
            )
        except Exception as e:
            return EndpointResult(
                verified=False,
                endpoint_type="file_exists",
                error=f"Failed to check file: {str(e)}"
            )
    
    def _verify_service_health(self, definition: Dict) -> EndpointResult:
        """
        Verify a service is healthy on a platform.
        
        Definition format:
        {
            "type": "service_health",
            "platform": "railway|vercel",
            "service_id": "service-id-here",
            "expected_status": "active|running|ready"
        }
        """
        platform = definition.get("platform", "railway")
        service_id = definition.get("service_id", "")
        expected_status = definition.get("expected_status", "active")
        
        if not service_id:
            return EndpointResult(
                verified=False,
                endpoint_type="service_health",
                error="No service_id provided"
            )
        
        if platform == "railway":
            return self._check_railway_service(service_id, expected_status)
        elif platform == "vercel":
            return self._check_vercel_service(service_id, expected_status)
        else:
            return EndpointResult(
                verified=False,
                endpoint_type="service_health",
                error=f"Unsupported platform: {platform}"
            )
    
    def _check_railway_service(self, service_id: str, expected_status: str) -> EndpointResult:
        """Check Railway service health via GraphQL API."""
        if not self.railway_token:
            return EndpointResult(
                verified=False,
                endpoint_type="service_health",
                error="No Railway token configured"
            )
        
        query = """
        query GetService($serviceId: String!) {
            service(id: $serviceId) {
                id
                name
                deployments(first: 1) {
                    edges {
                        node {
                            id
                            status
                            createdAt
                        }
                    }
                }
            }
        }
        """
        
        try:
            url = "https://backboard.railway.com/graphql/v2"
            data = json.dumps({
                "query": query,
                "variables": {"serviceId": service_id}
            }).encode("utf-8")
            
            req = urllib.request.Request(url, data=data)
            req.add_header("Authorization", f"Bearer {self.railway_token}")
            req.add_header("Content-Type", "application/json")
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                
                service = result.get("data", {}).get("service")
                if not service:
                    return EndpointResult(
                        verified=False,
                        endpoint_type="service_health",
                        error=f"Service not found: {service_id}"
                    )
                
                deployments = service.get("deployments", {}).get("edges", [])
                if not deployments:
                    return EndpointResult(
                        verified=False,
                        endpoint_type="service_health",
                        error="No deployments found",
                        evidence={"service_name": service.get("name")}
                    )
                
                latest = deployments[0]["node"]
                current_status = latest.get("status", "unknown").lower()
                
                # Map Railway statuses to normalized form
                status_map = {
                    "success": "active",
                    "deploying": "deploying",
                    "failed": "failed",
                    "crashed": "crashed",
                    "removed": "removed"
                }
                normalized = status_map.get(current_status, current_status)
                
                verified = normalized == expected_status.lower()
                
                return EndpointResult(
                    verified=verified,
                    endpoint_type="service_health",
                    evidence={
                        "platform": "railway",
                        "service_id": service_id,
                        "service_name": service.get("name"),
                        "current_status": current_status,
                        "expected_status": expected_status,
                        "deployment_id": latest.get("id")
                    },
                    error=None if verified else f"Status {current_status} != {expected_status}"
                )
                
        except Exception as e:
            return EndpointResult(
                verified=False,
                endpoint_type="service_health",
                error=f"Railway API error: {str(e)}"
            )
    
    def _check_vercel_service(self, service_id: str, expected_status: str) -> EndpointResult:
        """Check Vercel deployment status via REST API."""
        vercel_token = os.getenv("VERCEL_TOKEN")
        if not vercel_token:
            return EndpointResult(
                verified=False,
                endpoint_type="service_health",
                error="No Vercel token configured"
            )
        
        try:
            url = f"https://api.vercel.com/v13/deployments/{service_id}"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {vercel_token}")
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                
                current_status = data.get("readyState", "unknown").lower()
                
                # Map Vercel states
                status_map = {
                    "ready": "active",
                    "building": "deploying",
                    "error": "failed",
                    "canceled": "canceled"
                }
                normalized = status_map.get(current_status, current_status)
                
                verified = normalized == expected_status.lower()
                
                return EndpointResult(
                    verified=verified,
                    endpoint_type="service_health",
                    evidence={
                        "platform": "vercel",
                        "deployment_id": service_id,
                        "current_status": current_status,
                        "expected_status": expected_status,
                        "url": data.get("url")
                    },
                    error=None if verified else f"Status {current_status} != {expected_status}"
                )
                
        except urllib.error.HTTPError as e:
            return EndpointResult(
                verified=False,
                endpoint_type="service_health",
                error=f"Vercel API error: {e.code}"
            )
        except Exception as e:
            return EndpointResult(
                verified=False,
                endpoint_type="service_health",
                error=f"Vercel check failed: {str(e)}"
            )
    
    def _verify_script(self, definition: Dict) -> EndpointResult:
        """
        Verify by running a script/command.
        
        Definition format:
        {
            "type": "script",
            "command": "python verify.py",
            "expected_exit": 0,
            "expected_output": "SUCCESS",
            "timeout": 30,
            "working_dir": "/path/to/dir"
        }
        
        SECURITY NOTE: Script execution is dangerous. Only enable in controlled environments.
        """
        command = definition.get("command", "")
        expected_exit = definition.get("expected_exit", 0)
        expected_output = definition.get("expected_output")
        timeout = definition.get("timeout", 30)
        working_dir = definition.get("working_dir")
        
        if not command:
            return EndpointResult(
                verified=False,
                endpoint_type="script",
                error="No command provided"
            )
        
        # Security: Block dangerous commands
        dangerous_patterns = ["rm -rf", "sudo", "chmod", "chown", "> /dev", "| sh", "| bash"]
        for pattern in dangerous_patterns:
            if pattern in command.lower():
                return EndpointResult(
                    verified=False,
                    endpoint_type="script",
                    error=f"Dangerous command pattern blocked: {pattern}"
                )
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                timeout=timeout,
                cwd=working_dir,
                text=True
            )
            
            exit_match = result.returncode == expected_exit
            output_match = True
            
            if expected_output:
                output_match = expected_output in result.stdout or expected_output in result.stderr
            
            verified = exit_match and output_match
            
            return EndpointResult(
                verified=verified,
                endpoint_type="script",
                evidence={
                    "command": command,
                    "exit_code": result.returncode,
                    "expected_exit": expected_exit,
                    "stdout_preview": result.stdout[:500] if result.stdout else "",
                    "stderr_preview": result.stderr[:500] if result.stderr else ""
                },
                error=None if verified else f"Exit {result.returncode} != {expected_exit}" if not exit_match else "Output mismatch"
            )
            
        except subprocess.TimeoutExpired:
            return EndpointResult(
                verified=False,
                endpoint_type="script",
                error=f"Command timed out after {timeout}s"
            )
        except Exception as e:
            return EndpointResult(
                verified=False,
                endpoint_type="script",
                error=f"Script execution failed: {str(e)}"
            )
    
    def _verify_url_accessible(self, definition: Dict) -> EndpointResult:
        """
        Verify a URL is accessible (returns 2xx status).
        
        Definition format:
        {
            "type": "url_accessible",
            "url": "https://site.com/page",
            "follow_redirects": true,
            "expected_content_type": "text/html"
        }
        """
        url = definition.get("url", "")
        expected_content_type = definition.get("expected_content_type")
        
        if not url:
            return EndpointResult(
                verified=False,
                endpoint_type="url_accessible",
                error="No URL provided"
            )
        
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "JUGGERNAUT-EndpointVerifier/1.0")
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                status_code = response.getcode()
                content_type = response.headers.get("Content-Type", "")
                
                # Success is 2xx status
                is_success = 200 <= status_code < 300
                
                # Check content type if specified
                content_type_match = True
                if expected_content_type:
                    content_type_match = expected_content_type in content_type
                
                verified = is_success and content_type_match
                
                return EndpointResult(
                    verified=verified,
                    endpoint_type="url_accessible",
                    evidence={
                        "url": url,
                        "status_code": status_code,
                        "content_type": content_type,
                        "content_length": response.headers.get("Content-Length")
                    },
                    error=None if verified else f"Status {status_code}" if not is_success else "Content-Type mismatch"
                )
                
        except urllib.error.HTTPError as e:
            return EndpointResult(
                verified=False,
                endpoint_type="url_accessible",
                error=f"HTTP {e.code}: {e.reason}",
                evidence={"url": url, "status_code": e.code}
            )
        except urllib.error.URLError as e:
            return EndpointResult(
                verified=False,
                endpoint_type="url_accessible",
                error=f"URL Error: {str(e.reason)}",
                evidence={"url": url}
            )
        except Exception as e:
            return EndpointResult(
                verified=False,
                endpoint_type="url_accessible",
                error=f"Request failed: {str(e)}"
            )
    
    def _verify_composite(self, definition: Dict) -> EndpointResult:
        """
        Verify multiple checks together.
        
        Definition format:
        {
            "type": "composite",
            "checks": [
                {"type": "http", "url": "/api/health", "expected_status": 200},
                {"type": "db_query", "query": "SELECT 1", "expected_result": {"min_count": 1}},
                {"type": "url_accessible", "url": "https://site.com"}
            ],
            "require": "all|any"  # all = all must pass, any = at least one must pass
        }
        """
        checks = definition.get("checks", [])
        require = definition.get("require", "all").lower()
        
        if not checks:
            return EndpointResult(
                verified=False,
                endpoint_type="composite",
                error="No checks provided in composite definition"
            )
        
        results = []
        passed_count = 0
        failed_count = 0
        
        for check in checks:
            result = self.verify(check)
            results.append({
                "type": check.get("type"),
                "verified": result.verified,
                "error": result.error
            })
            if result.verified:
                passed_count += 1
            else:
                failed_count += 1
        
        # Determine overall result based on require mode
        if require == "all":
            verified = failed_count == 0
        elif require == "any":
            verified = passed_count > 0
        else:
            verified = False
        
        return EndpointResult(
            verified=verified,
            endpoint_type="composite",
            evidence={
                "require": require,
                "total_checks": len(checks),
                "passed": passed_count,
                "failed": failed_count,
                "results": results
            },
            error=None if verified else f"Composite check failed: {failed_count}/{len(checks)} checks failed"
        )


# Convenience function for quick verification
def verify_endpoint(
    endpoint_definition: Dict[str, Any],
    db_executor=None,
    github_token: Optional[str] = None,
    railway_token: Optional[str] = None
) -> EndpointResult:
    """
    Quick verification of an endpoint definition.
    
    Args:
        endpoint_definition: The endpoint spec to verify
        db_executor: Optional SQL executor function
        github_token: Optional GitHub token
        railway_token: Optional Railway token
        
    Returns:
        EndpointResult
    """
    verifier = EndpointVerifier(
        db_executor=db_executor,
        github_token=github_token,
        railway_token=railway_token
    )
    return verifier.verify(endpoint_definition)
