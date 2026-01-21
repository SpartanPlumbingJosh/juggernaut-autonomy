"""
Dynamic Endpoint Verification Module
====================================

This module is the KEY component of the verification chain system (VERCHAIN-08).
Each task defines its own endpoint verification. This system executes whatever
check the task defined to prove it's truly done.

Supported verification types:
- HTTP: Check HTTP endpoints for status and content
- DB Query: Run database queries and verify results
- File Exists: Check if files exist in GitHub repositories
- Service Health: Check Railway/Vercel service health
- Script: Execute verification scripts
- URL Accessible: Simple URL accessibility check
- Composite: Combine multiple checks with all/any logic

Usage:
    verifier = EndpointVerifier()
    
    # Verify a task's endpoint definition
    result = verifier.verify_endpoint(task)
    
    # Check specific endpoint types
    result = verifier.verify_http({"url": "https://api.example.com/health", "expected_status": 200})
    result = verifier.verify_file_exists({"repo": "org/repo", "path": "src/file.py"})
"""

import os
import re
import json
import time
import urllib.request
import urllib.error
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from datetime import datetime, timezone


class EndpointType(Enum):
    """Types of endpoint verification checks."""
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
    passed: bool
    endpoint_type: str
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "passed": self.passed,
            "endpoint_type": self.endpoint_type,
            "details": self.details,
            "error": self.error,
            "checked_at": self.checked_at,
            "duration_ms": self.duration_ms
        }


class EndpointVerifier:
    """
    Dynamic endpoint verification engine.
    
    Verifies that tasks are truly complete by checking the endpoints
    and conditions defined in each task's endpoint_definition.
    """
    
    def __init__(
        self,
        github_token: Optional[str] = None,
        railway_token: Optional[str] = None,
        db_connection_string: Optional[str] = None,
        default_timeout: int = 30
    ):
        """
        Initialize the endpoint verifier.
        
        Args:
            github_token: GitHub API token (or from GITHUB_TOKEN env)
            railway_token: Railway API token (or from RAILWAY_TOKEN env)
            db_connection_string: Database connection string (or from DATABASE_URL env)
            default_timeout: Default timeout for HTTP requests in seconds
        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN", "")
        self.railway_token = railway_token or os.getenv("RAILWAY_API_TOKEN") or os.getenv("RAILWAY_TOKEN", "")
        self.db_connection_string = db_connection_string or os.getenv("DATABASE_URL", "")
        self.default_timeout = default_timeout
        
        self.github_api_url = "https://api.github.com"
        self.railway_api_url = "https://backboard.railway.com/graphql/v2"
        
        # Map endpoint types to handler methods
        self.handlers = {
            EndpointType.HTTP: self._verify_http,
            EndpointType.DB_QUERY: self._verify_db_query,
            EndpointType.FILE_EXISTS: self._verify_file_exists,
            EndpointType.SERVICE_HEALTH: self._verify_service_health,
            EndpointType.SCRIPT: self._verify_script,
            EndpointType.URL_ACCESSIBLE: self._verify_url_accessible,
            EndpointType.COMPOSITE: self._verify_composite,
        }
    
    def verify_endpoint(self, task: Dict[str, Any]) -> EndpointResult:
        """
        Verify a task's endpoint definition.
        
        Args:
            task: Task dictionary with endpoint_definition
            
        Returns:
            EndpointResult with verification outcome
        """
        endpoint_def = task.get("endpoint_definition")
        
        if not endpoint_def:
            return EndpointResult(
                passed=False,
                endpoint_type="none",
                details={},
                error="No endpoint definition found in task"
            )
        
        # Parse endpoint definition if it's a string
        if isinstance(endpoint_def, str):
            try:
                endpoint_def = json.loads(endpoint_def)
            except json.JSONDecodeError as e:
                return EndpointResult(
                    passed=False,
                    endpoint_type="none",
                    details={},
                    error=f"Invalid endpoint definition JSON: {str(e)}"
                )
        
        # Get endpoint type
        type_str = endpoint_def.get("type", "").lower()
        
        try:
            endpoint_type = EndpointType(type_str)
        except ValueError:
            return EndpointResult(
                passed=False,
                endpoint_type=type_str or "unknown",
                details={"definition": endpoint_def},
                error=f"Unknown endpoint type: {type_str}"
            )
        
        # Get handler and execute
        handler = self.handlers.get(endpoint_type)
        if not handler:
            return EndpointResult(
                passed=False,
                endpoint_type=type_str,
                details={"definition": endpoint_def},
                error=f"No handler for endpoint type: {type_str}"
            )
        
        start_time = time.time()
        result = handler(endpoint_def)
        result.duration_ms = int((time.time() - start_time) * 1000)
        
        return result
    
    def _verify_http(self, definition: Dict[str, Any]) -> EndpointResult:
        """
        Verify HTTP endpoint.
        
        Definition format:
        {
            "type": "http",
            "url": "https://api.example.com/health",
            "method": "GET",
            "expected_status": 200,
            "expected_body_contains": "ok",
            "expected_json_path": "$.status",
            "expected_json_value": "healthy",
            "headers": {"Authorization": "Bearer xxx"},
            "timeout": 30,
            "retry_count": 3,
            "retry_delay": 5
        }
        """
        url = definition.get("url")
        if not url:
            return EndpointResult(
                passed=False,
                endpoint_type="http",
                error="No URL specified in HTTP endpoint definition"
            )
        
        method = definition.get("method", "GET").upper()
        expected_status = definition.get("expected_status", 200)
        expected_body_contains = definition.get("expected_body_contains")
        expected_json_path = definition.get("expected_json_path")
        expected_json_value = definition.get("expected_json_value")
        headers = definition.get("headers", {})
        timeout = definition.get("timeout", self.default_timeout)
        retry_count = definition.get("retry_count", 1)
        retry_delay = definition.get("retry_delay", 5)
        body_data = definition.get("body")
        
        details = {
            "url": url,
            "method": method,
            "expected_status": expected_status
        }
        
        last_error = None
        for attempt in range(retry_count):
            try:
                req_data = None
                if body_data:
                    if isinstance(body_data, dict):
                        req_data = json.dumps(body_data).encode("utf-8")
                        if "Content-Type" not in headers:
                            headers["Content-Type"] = "application/json"
                    else:
                        req_data = str(body_data).encode("utf-8")
                
                req = urllib.request.Request(url, data=req_data, method=method)
                req.add_header("User-Agent", "Juggernaut-EndpointVerifier/1.0")
                
                for key, value in headers.items():
                    req.add_header(key, value)
                
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    status_code = response.status
                    body = response.read().decode("utf-8", errors="ignore")
                    
                    details["actual_status"] = status_code
                    details["response_preview"] = body[:500] if body else None
                    
                    # Check status code
                    if status_code != expected_status:
                        last_error = f"Status {status_code}, expected {expected_status}"
                        if attempt < retry_count - 1:
                            time.sleep(retry_delay)
                            continue
                        return EndpointResult(
                            passed=False,
                            endpoint_type="http",
                            details=details,
                            error=last_error
                        )
                    
                    # Check body contains
                    if expected_body_contains and expected_body_contains not in body:
                        last_error = f"Response body does not contain: {expected_body_contains}"
                        if attempt < retry_count - 1:
                            time.sleep(retry_delay)
                            continue
                        return EndpointResult(
                            passed=False,
                            endpoint_type="http",
                            details=details,
                            error=last_error
                        )
                    
                    # Check JSON path if specified
                    if expected_json_path:
                        try:
                            json_body = json.loads(body)
                            actual_value = self._extract_json_path(json_body, expected_json_path)
                            details["json_path_value"] = actual_value
                            
                            if expected_json_value is not None and actual_value != expected_json_value:
                                last_error = f"JSON path {expected_json_path} = {actual_value}, expected {expected_json_value}"
                                if attempt < retry_count - 1:
                                    time.sleep(retry_delay)
                                    continue
                                return EndpointResult(
                                    passed=False,
                                    endpoint_type="http",
                                    details=details,
                                    error=last_error
                                )
                        except json.JSONDecodeError:
                            last_error = "Response is not valid JSON"
                            if attempt < retry_count - 1:
                                time.sleep(retry_delay)
                                continue
                            return EndpointResult(
                                passed=False,
                                endpoint_type="http",
                                details=details,
                                error=last_error
                            )
                    
                    # All checks passed
                    return EndpointResult(
                        passed=True,
                        endpoint_type="http",
                        details=details
                    )
                    
            except urllib.error.HTTPError as e:
                details["actual_status"] = e.code
                last_error = f"HTTP error {e.code}: {e.reason}"
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)
                    continue
                    
            except urllib.error.URLError as e:
                last_error = f"Connection error: {str(e.reason)}"
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)
                    continue
                    
            except Exception as e:
                last_error = f"Error: {str(e)}"
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)
                    continue
        
        return EndpointResult(
            passed=False,
            endpoint_type="http",
            details=details,
            error=last_error
        )
    
    def _extract_json_path(self, data: Any, path: str) -> Any:
        """
        Extract value from JSON using simple path notation.
        
        Supports: $.key.subkey, $.array[0], $.key[*]
        """
        if path.startswith("$."):
            path = path[2:]
        
        parts = re.split(r'\.|\[|\]', path)
        parts = [p for p in parts if p]
        
        current = data
        for part in parts:
            if current is None:
                return None
            
            if part == "*":
                # Return all items in array
                if isinstance(current, list):
                    return current
                return None
            
            if part.isdigit():
                # Array index
                idx = int(part)
                if isinstance(current, list) and idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                # Object key
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None
        
        return current
    
    def _verify_db_query(self, definition: Dict[str, Any]) -> EndpointResult:
        """
        Verify database query result.
        
        Definition format:
        {
            "type": "db_query",
            "query": "SELECT COUNT(*) as count FROM users WHERE active = true",
            "expected": "> 0",
            "expected_exact": null,
            "connection_string": "postgresql://..." (optional, uses env if not provided)
        }
        
        Expected operators: >, <, >=, <=, =, ==, !=, contains, not_contains
        """
        query = definition.get("query")
        if not query:
            return EndpointResult(
                passed=False,
                endpoint_type="db_query",
                error="No query specified"
            )
        
        expected = definition.get("expected")
        expected_exact = definition.get("expected_exact")
        conn_str = definition.get("connection_string") or self.db_connection_string
        
        if not conn_str:
            return EndpointResult(
                passed=False,
                endpoint_type="db_query",
                error="No database connection string available"
            )
        
        details = {"query": query[:200] + "..." if len(query) > 200 else query}
        
        try:
            # Use Neon HTTP API if available
            if "neon.tech" in conn_str or definition.get("use_http_api"):
                result = self._execute_neon_query(query, conn_str)
            else:
                # Fall back to psycopg2 if available
                result = self._execute_psycopg_query(query, conn_str)
            
            details["result"] = result
            
            # Check exact value
            if expected_exact is not None:
                if result == expected_exact:
                    return EndpointResult(
                        passed=True,
                        endpoint_type="db_query",
                        details=details
                    )
                return EndpointResult(
                    passed=False,
                    endpoint_type="db_query",
                    details=details,
                    error=f"Result {result} != expected {expected_exact}"
                )
            
            # Check with operator
            if expected:
                passed, error = self._check_expected(result, expected)
                return EndpointResult(
                    passed=passed,
                    endpoint_type="db_query",
                    details=details,
                    error=error
                )
            
            # No expectation specified, just check query succeeded
            return EndpointResult(
                passed=True,
                endpoint_type="db_query",
                details=details
            )
            
        except Exception as e:
            return EndpointResult(
                passed=False,
                endpoint_type="db_query",
                details=details,
                error=f"Database error: {str(e)}"
            )
    
    def _execute_neon_query(self, query: str, conn_str: str) -> Any:
        """Execute query using Neon HTTP API."""
        # Parse connection string for Neon HTTP endpoint
        # Format: postgresql://user:pass@host/dbname
        import re
        
        # Extract components from connection string
        match = re.match(r'postgresql://([^:]+):([^@]+)@([^/]+)/([^?]+)', conn_str)
        if not match:
            raise ValueError("Invalid connection string format")
        
        user, password, host, dbname = match.groups()
        
        # Construct Neon HTTP URL
        host_parts = host.split('.')
        if 'pooler' in host:
            # Remove -pooler suffix for HTTP API
            host = host.replace('-pooler', '')
        
        http_url = f"https://{host}/sql"
        
        # Make request
        data = json.dumps({"query": query}).encode("utf-8")
        req = urllib.request.Request(http_url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Neon-Connection-String", conn_str)
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        
        # Extract first value from result
        rows = result.get("rows", [])
        if rows and len(rows) > 0:
            first_row = rows[0]
            if isinstance(first_row, dict):
                # Return first column value
                return list(first_row.values())[0] if first_row else None
            return first_row[0] if first_row else None
        
        return None
    
    def _execute_psycopg_query(self, query: str, conn_str: str) -> Any:
        """Execute query using psycopg2."""
        try:
            import psycopg2
        except ImportError:
            raise RuntimeError("psycopg2 not available, use Neon HTTP API instead")
        
        conn = psycopg2.connect(conn_str)
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            conn.close()
    
    def _check_expected(self, actual: Any, expected: str) -> tuple:
        """
        Check if actual value meets expected condition.
        
        Returns: (passed: bool, error: Optional[str])
        """
        expected = expected.strip()
        
        # Parse operator and value
        operators = ['>=', '<=', '!=', '==', '>', '<', '=', 'contains', 'not_contains']
        op = None
        value = None
        
        for operator in operators:
            if expected.startswith(operator):
                op = operator
                value = expected[len(operator):].strip()
                break
        
        if op is None:
            # No operator, treat as equality check
            op = '='
            value = expected
        
        # Convert value to appropriate type
        try:
            if value.lower() == 'null' or value.lower() == 'none':
                value = None
            elif value.lower() == 'true':
                value = True
            elif value.lower() == 'false':
                value = False
            elif '.' in value:
                value = float(value)
            else:
                value = int(value)
        except (ValueError, AttributeError):
            pass  # Keep as string
        
        # Perform comparison
        try:
            if op == '>':
                passed = actual > value
            elif op == '<':
                passed = actual < value
            elif op == '>=':
                passed = actual >= value
            elif op == '<=':
                passed = actual <= value
            elif op in ('=', '=='):
                passed = actual == value
            elif op == '!=':
                passed = actual != value
            elif op == 'contains':
                passed = value in str(actual)
            elif op == 'not_contains':
                passed = value not in str(actual)
            else:
                return False, f"Unknown operator: {op}"
            
            if passed:
                return True, None
            return False, f"Check failed: {actual} {op} {value}"
            
        except Exception as e:
            return False, f"Comparison error: {str(e)}"
    
    def _verify_file_exists(self, definition: Dict[str, Any]) -> EndpointResult:
        """
        Verify file exists in GitHub repository.
        
        Definition format:
        {
            "type": "file_exists",
            "repo": "owner/repo",
            "path": "src/feature.py",
            "branch": "main",
            "content_contains": "def my_function" (optional)
        }
        """
        repo = definition.get("repo")
        path = definition.get("path")
        branch = definition.get("branch", "main")
        content_contains = definition.get("content_contains")
        
        if not repo or not path:
            return EndpointResult(
                passed=False,
                endpoint_type="file_exists",
                error="Both 'repo' and 'path' are required"
            )
        
        details = {
            "repo": repo,
            "path": path,
            "branch": branch
        }
        
        if not self.github_token:
            return EndpointResult(
                passed=False,
                endpoint_type="file_exists",
                details=details,
                error="No GitHub token available"
            )
        
        try:
            url = f"{self.github_api_url}/repos/{repo}/contents/{path}?ref={branch}"
            
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {self.github_token}")
            req.add_header("Accept", "application/vnd.github.v3+json")
            req.add_header("User-Agent", "Juggernaut-EndpointVerifier/1.0")
            
            with urllib.request.urlopen(req, timeout=self.default_timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                
                details["sha"] = result.get("sha")
                details["size"] = result.get("size")
                
                # Check content if required
                if content_contains:
                    content = result.get("content", "")
                    if result.get("encoding") == "base64":
                        import base64
                        content = base64.b64decode(content).decode("utf-8", errors="ignore")
                    
                    if content_contains not in content:
                        return EndpointResult(
                            passed=False,
                            endpoint_type="file_exists",
                            details=details,
                            error=f"File exists but does not contain: {content_contains}"
                        )
                
                return EndpointResult(
                    passed=True,
                    endpoint_type="file_exists",
                    details=details
                )
                
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return EndpointResult(
                    passed=False,
                    endpoint_type="file_exists",
                    details=details,
                    error=f"File not found: {path} in {repo}@{branch}"
                )
            return EndpointResult(
                passed=False,
                endpoint_type="file_exists",
                details=details,
                error=f"GitHub API error {e.code}: {e.reason}"
            )
        except Exception as e:
            return EndpointResult(
                passed=False,
                endpoint_type="file_exists",
                details=details,
                error=f"Error checking file: {str(e)}"
            )
    
    def _verify_service_health(self, definition: Dict[str, Any]) -> EndpointResult:
        """
        Verify service health via Railway or similar platform.
        
        Definition format:
        {
            "type": "service_health",
            "service_id": "xxx",
            "platform": "railway" | "vercel",
            "expected_status": "active" | "running" | "success"
        }
        """
        service_id = definition.get("service_id")
        platform = definition.get("platform", "railway").lower()
        expected_status = definition.get("expected_status", "success").lower()
        
        if not service_id:
            return EndpointResult(
                passed=False,
                endpoint_type="service_health",
                error="No service_id specified"
            )
        
        details = {
            "service_id": service_id,
            "platform": platform,
            "expected_status": expected_status
        }
        
        if platform == "railway":
            return self._check_railway_health(service_id, expected_status, details)
        elif platform == "vercel":
            return self._check_vercel_health(service_id, expected_status, details)
        else:
            return EndpointResult(
                passed=False,
                endpoint_type="service_health",
                details=details,
                error=f"Unknown platform: {platform}"
            )
    
    def _check_railway_health(self, service_id: str, expected_status: str, details: Dict) -> EndpointResult:
        """Check Railway service health."""
        if not self.railway_token:
            return EndpointResult(
                passed=False,
                endpoint_type="service_health",
                details=details,
                error="No Railway API token available"
            )
        
        query = """
        query GetDeployments($serviceId: String!) {
            deployments(first: 1, input: {serviceId: $serviceId}) {
                edges {
                    node {
                        id
                        status
                        createdAt
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
            req.add_header("User-Agent", "Juggernaut-EndpointVerifier/1.0")
            
            with urllib.request.urlopen(req, timeout=self.default_timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            
            if "errors" in result:
                return EndpointResult(
                    passed=False,
                    endpoint_type="service_health",
                    details=details,
                    error=f"Railway API error: {result['errors']}"
                )
            
            edges = result.get("data", {}).get("deployments", {}).get("edges", [])
            
            if not edges:
                return EndpointResult(
                    passed=False,
                    endpoint_type="service_health",
                    details=details,
                    error="No deployments found"
                )
            
            deployment = edges[0].get("node", {})
            status = deployment.get("status", "").lower()
            
            details["actual_status"] = status
            details["deployment_id"] = deployment.get("id")
            
            # Normalize status comparisons
            success_statuses = ["success", "running", "active", "ready"]
            expected_normalized = expected_status.lower()
            
            if expected_normalized in success_statuses:
                passed = status in success_statuses
            else:
                passed = status == expected_normalized
            
            return EndpointResult(
                passed=passed,
                endpoint_type="service_health",
                details=details,
                error=None if passed else f"Status is {status}, expected {expected_status}"
            )
            
        except Exception as e:
            return EndpointResult(
                passed=False,
                endpoint_type="service_health",
                details=details,
                error=f"Railway check error: {str(e)}"
            )
    
    def _check_vercel_health(self, project_id: str, expected_status: str, details: Dict) -> EndpointResult:
        """Check Vercel project health."""
        vercel_token = os.getenv("VERCEL_TOKEN", "")
        
        if not vercel_token:
            return EndpointResult(
                passed=False,
                endpoint_type="service_health",
                details=details,
                error="No Vercel API token available"
            )
        
        try:
            url = f"https://api.vercel.com/v6/deployments?projectId={project_id}&limit=1"
            
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {vercel_token}")
            req.add_header("User-Agent", "Juggernaut-EndpointVerifier/1.0")
            
            with urllib.request.urlopen(req, timeout=self.default_timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            
            deployments = result.get("deployments", [])
            
            if not deployments:
                return EndpointResult(
                    passed=False,
                    endpoint_type="service_health",
                    details=details,
                    error="No deployments found"
                )
            
            deployment = deployments[0]
            state = (deployment.get("readyState") or deployment.get("state", "")).lower()
            
            details["actual_status"] = state
            details["deployment_id"] = deployment.get("uid")
            
            # Normalize status comparisons
            success_statuses = ["ready", "success", "running", "active"]
            expected_normalized = expected_status.lower()
            
            if expected_normalized in success_statuses:
                passed = state in success_statuses
            else:
                passed = state == expected_normalized
            
            return EndpointResult(
                passed=passed,
                endpoint_type="service_health",
                details=details,
                error=None if passed else f"Status is {state}, expected {expected_status}"
            )
            
        except Exception as e:
            return EndpointResult(
                passed=False,
                endpoint_type="service_health",
                details=details,
                error=f"Vercel check error: {str(e)}"
            )
    
    def _verify_script(self, definition: Dict[str, Any]) -> EndpointResult:
        """
        Execute a verification script.
        
        Definition format:
        {
            "type": "script",
            "command": "python verify.py",
            "expected_exit": 0,
            "expected_output_contains": "SUCCESS",
            "timeout": 60,
            "working_dir": "/path/to/dir"
        }
        
        WARNING: Script execution is disabled by default for security.
        Set ALLOW_SCRIPT_VERIFICATION=true to enable.
        """
        if not os.getenv("ALLOW_SCRIPT_VERIFICATION", "").lower() == "true":
            return EndpointResult(
                passed=False,
                endpoint_type="script",
                error="Script verification is disabled. Set ALLOW_SCRIPT_VERIFICATION=true to enable."
            )
        
        command = definition.get("command")
        if not command:
            return EndpointResult(
                passed=False,
                endpoint_type="script",
                error="No command specified"
            )
        
        expected_exit = definition.get("expected_exit", 0)
        expected_output = definition.get("expected_output_contains")
        timeout = definition.get("timeout", 60)
        working_dir = definition.get("working_dir")
        
        details = {
            "command": command,
            "expected_exit": expected_exit
        }
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir
            )
            
            details["exit_code"] = result.returncode
            details["stdout_preview"] = result.stdout[:500] if result.stdout else None
            details["stderr_preview"] = result.stderr[:500] if result.stderr else None
            
            # Check exit code
            if result.returncode != expected_exit:
                return EndpointResult(
                    passed=False,
                    endpoint_type="script",
                    details=details,
                    error=f"Exit code {result.returncode}, expected {expected_exit}"
                )
            
            # Check output
            if expected_output and expected_output not in (result.stdout or ""):
                return EndpointResult(
                    passed=False,
                    endpoint_type="script",
                    details=details,
                    error=f"Output does not contain: {expected_output}"
                )
            
            return EndpointResult(
                passed=True,
                endpoint_type="script",
                details=details
            )
            
        except subprocess.TimeoutExpired:
            return EndpointResult(
                passed=False,
                endpoint_type="script",
                details=details,
                error=f"Script timed out after {timeout}s"
            )
        except Exception as e:
            return EndpointResult(
                passed=False,
                endpoint_type="script",
                details=details,
                error=f"Script execution error: {str(e)}"
            )
    
    def _verify_url_accessible(self, definition: Dict[str, Any]) -> EndpointResult:
        """
        Simple URL accessibility check.
        
        Definition format:
        {
            "type": "url_accessible",
            "url": "https://site.com/page",
            "timeout": 30
        }
        """
        url = definition.get("url")
        if not url:
            return EndpointResult(
                passed=False,
                endpoint_type="url_accessible",
                error="No URL specified"
            )
        
        timeout = definition.get("timeout", self.default_timeout)
        
        details = {"url": url}
        
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "Juggernaut-EndpointVerifier/1.0")
            
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.status
                details["status_code"] = status_code
                
                # Any 2xx or 3xx is considered accessible
                if 200 <= status_code < 400:
                    return EndpointResult(
                        passed=True,
                        endpoint_type="url_accessible",
                        details=details
                    )
                
                return EndpointResult(
                    passed=False,
                    endpoint_type="url_accessible",
                    details=details,
                    error=f"URL returned status {status_code}"
                )
                
        except urllib.error.HTTPError as e:
            details["status_code"] = e.code
            # Some sites don't allow HEAD, try GET
            if e.code == 405:
                try:
                    req = urllib.request.Request(url, method="GET")
                    req.add_header("User-Agent", "Juggernaut-EndpointVerifier/1.0")
                    with urllib.request.urlopen(req, timeout=timeout) as response:
                        details["status_code"] = response.status
                        return EndpointResult(
                            passed=True,
                            endpoint_type="url_accessible",
                            details=details
                        )
                except:
                    pass
            
            return EndpointResult(
                passed=False,
                endpoint_type="url_accessible",
                details=details,
                error=f"HTTP error {e.code}: {e.reason}"
            )
        except Exception as e:
            return EndpointResult(
                passed=False,
                endpoint_type="url_accessible",
                details=details,
                error=f"URL not accessible: {str(e)}"
            )
    
    def _verify_composite(self, definition: Dict[str, Any]) -> EndpointResult:
        """
        Verify multiple checks together.
        
        Definition format:
        {
            "type": "composite",
            "checks": [
                {"type": "http", "url": "...", ...},
                {"type": "file_exists", "repo": "...", ...}
            ],
            "require": "all" | "any"
        }
        """
        checks = definition.get("checks", [])
        require = definition.get("require", "all").lower()
        
        if not checks:
            return EndpointResult(
                passed=False,
                endpoint_type="composite",
                error="No checks specified in composite verification"
            )
        
        results = []
        passed_count = 0
        failed_count = 0
        
        for i, check_def in enumerate(checks):
            check_type = check_def.get("type", "unknown")
            
            try:
                endpoint_type = EndpointType(check_type)
                handler = self.handlers.get(endpoint_type)
                
                if handler and handler != self._verify_composite:
                    result = handler(check_def)
                else:
                    result = EndpointResult(
                        passed=False,
                        endpoint_type=check_type,
                        error=f"Unknown or recursive check type: {check_type}"
                    )
            except ValueError:
                result = EndpointResult(
                    passed=False,
                    endpoint_type=check_type,
                    error=f"Unknown check type: {check_type}"
                )
            
            results.append({
                "index": i,
                "type": check_type,
                "passed": result.passed,
                "error": result.error
            })
            
            if result.passed:
                passed_count += 1
            else:
                failed_count += 1
        
        details = {
            "checks_count": len(checks),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "require": require,
            "results": results
        }
        
        if require == "all":
            passed = failed_count == 0
            error = None if passed else f"{failed_count} of {len(checks)} checks failed"
        elif require == "any":
            passed = passed_count > 0
            error = None if passed else "All checks failed"
        else:
            return EndpointResult(
                passed=False,
                endpoint_type="composite",
                details=details,
                error=f"Unknown require mode: {require}"
            )
        
        return EndpointResult(
            passed=passed,
            endpoint_type="composite",
            details=details,
            error=error
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def verify_http(url: str, expected_status: int = 200, **kwargs) -> EndpointResult:
    """Quick HTTP endpoint verification."""
    verifier = EndpointVerifier()
    definition = {"type": "http", "url": url, "expected_status": expected_status, **kwargs}
    return verifier._verify_http(definition)


def verify_file_exists(repo: str, path: str, branch: str = "main") -> EndpointResult:
    """Quick file existence check."""
    verifier = EndpointVerifier()
    definition = {"type": "file_exists", "repo": repo, "path": path, "branch": branch}
    return verifier._verify_file_exists(definition)


def verify_url_accessible(url: str, timeout: int = 30) -> EndpointResult:
    """Quick URL accessibility check."""
    verifier = EndpointVerifier()
    definition = {"type": "url_accessible", "url": url, "timeout": timeout}
    return verifier._verify_url_accessible(definition)


def verify_service_health(service_id: str, platform: str = "railway") -> EndpointResult:
    """Quick service health check."""
    verifier = EndpointVerifier()
    definition = {"type": "service_health", "service_id": service_id, "platform": platform}
    return verifier._verify_service_health(definition)


def verify_task_endpoint(task: Dict[str, Any]) -> EndpointResult:
    """Verify a task's endpoint definition."""
    verifier = EndpointVerifier()
    return verifier.verify_endpoint(task)
