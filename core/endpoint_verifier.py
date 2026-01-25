"""
<<<<<<< HEAD
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
from typing import Callable, Dict, Any, Optional, List, Union
from enum import Enum
from datetime import datetime, timezone


class EndpointType(Enum):
    """Types of endpoint verification checks."""
=======
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
>>>>>>> origin/main
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
<<<<<<< HEAD
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
=======
    verified: bool
    endpoint_type: str
    evidence: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    response_time_ms: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
>>>>>>> origin/main


class EndpointVerifier:
    """
<<<<<<< HEAD
    Dynamic endpoint verification engine.
    
    Verifies that tasks are truly complete by checking the endpoints
    and conditions defined in each task's endpoint_definition.
=======
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
>>>>>>> origin/main
    """
    
    def __init__(
        self,
<<<<<<< HEAD
        github_token: Optional[str] = None,
        railway_token: Optional[str] = None,
        db_connection_string: Optional[str] = None,
        default_timeout: int = 30
    ) -> None:
=======
        db_executor=None,
        github_token: Optional[str] = None,
        railway_token: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: int = 30
    ):
>>>>>>> origin/main
        """
        Initialize the endpoint verifier.
        
        Args:
<<<<<<< HEAD
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
        self.handlers: Dict[EndpointType, Callable[[Dict[str, Any]], EndpointResult]] = {
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
=======
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
>>>>>>> origin/main
        
        Definition format:
        {
            "type": "http",
<<<<<<< HEAD
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
        headers = dict(definition.get("headers") or {})
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
=======
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
>>>>>>> origin/main
        
        Definition format:
        {
            "type": "db_query",
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
            )
            
        except Exception as e:
            return EndpointResult(
<<<<<<< HEAD
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
=======
                verified=False,
                endpoint_type="db_query",
                error=f"Query failed: {str(e)}"
            )
    
    def _verify_file_exists(self, definition: Dict) -> EndpointResult:
        """
        Verify a file exists in a GitHub repository.
>>>>>>> origin/main
        
        Definition format:
        {
            "type": "file_exists",
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
                )
                
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return EndpointResult(
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
        
        Definition format:
        {
            "type": "service_health",
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
                    }
                }
            }
        }
        """
        
        try:
<<<<<<< HEAD
=======
            url = "https://backboard.railway.com/graphql/v2"
>>>>>>> origin/main
            data = json.dumps({
                "query": query,
                "variables": {"serviceId": service_id}
            }).encode("utf-8")
            
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
        
        Definition format:
        {
            "type": "script",
            "command": "python verify.py",
            "expected_exit": 0,
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
            )
            
        except subprocess.TimeoutExpired:
            return EndpointResult(
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
        
        Definition format:
        {
            "type": "url_accessible",
            "url": "https://site.com/page",
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
        """
        Verify multiple checks together.
        
        Definition format:
        {
            "type": "composite",
            "checks": [
<<<<<<< HEAD
                {"type": "http", "url": "...", ...},
                {"type": "file_exists", "repo": "...", ...}
            ],
            "require": "all" | "any"
=======
                {"type": "http", "url": "/api/health", "expected_status": 200},
                {"type": "db_query", "query": "SELECT 1", "expected_result": {"min_count": 1}},
                {"type": "url_accessible", "url": "https://site.com"}
            ],
            "require": "all|any"  # all = all must pass, any = at least one must pass
>>>>>>> origin/main
        }
        """
        checks = definition.get("checks", [])
        require = definition.get("require", "all").lower()
        
        if not checks:
            return EndpointResult(
<<<<<<< HEAD
                passed=False,
                endpoint_type="composite",
                error="No checks specified in composite verification"
=======
                verified=False,
                endpoint_type="composite",
                error="No checks provided in composite definition"
>>>>>>> origin/main
            )
        
        results = []
        passed_count = 0
        failed_count = 0
        
<<<<<<< HEAD
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
=======
        for check in checks:
            result = self.verify(check)
            results.append({
                "type": check.get("type"),
                "verified": result.verified,
                "error": result.error
            })
            if result.verified:
>>>>>>> origin/main
                passed_count += 1
            else:
                failed_count += 1
        
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
