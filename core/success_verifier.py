"""
Success Criteria Verifier
=========================

Executes programmatic verification checks to validate task completion.

This is the ENFORCEMENT layer that prevents fake completions.
When a task has success_criteria defined, ALL checks must pass
before the task can transition to 'completed' status.

Supported Check Types:
- shell: Run shell command, check exit code or output
- file_exists: Verify file exists at path
- file_contains: Verify file contains pattern
- file_not_contains: Verify file does NOT contain pattern
- db_query: Run SQL query, check result
- pr_merged: Check if GitHub PR is merged
- pr_approved: Check if GitHub PR has approvals
- http_status: Check HTTP endpoint returns expected status
- json_path: Check JSON response contains expected value

Example success_criteria JSON:
{
    "checks": [
        {"type": "file_contains", "path": "main.py", "pattern": "from core.new_module import"},
        {"type": "shell", "command": "pytest tests/test_new.py -v", "expect": "exit_code_0"},
        {"type": "pr_merged", "pr_number": 123}
    ],
    "require_all": true,
    "timeout_seconds": 300
}
"""

import os
import re
import json
import subprocess
import urllib.request
import urllib.error
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Database configuration
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
NEON_CONNECTION_STRING = "postgresql://neondb_owner:npg_OYkCRU4aze2l@ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"

# GitHub configuration
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "SpartanPlumbingJosh/juggernaut-autonomy")


def _db_query(sql: str) -> Dict[str, Any]:
    """Execute SQL query via HTTP."""
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": NEON_CONNECTION_STRING
    }
    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {"error": str(e)}


def _format_value(v: Any) -> str:
    """Format value for SQL."""
    if v is None:
        return "NULL"
    elif isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    elif isinstance(v, (int, float)):
        return str(v)
    elif isinstance(v, (dict, list)):
        json_str = json.dumps(v).replace("'", "''")
        return f"'{json_str}'"
    else:
        escaped = str(v).replace("'", "''")
        return f"'{escaped}'"


@dataclass
class CheckResult:
    """Result of a single verification check."""
    check_type: str
    check_name: str
    passed: bool
    expected: Any = None
    actual: Any = None
    error: Optional[str] = None
    duration_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_type": self.check_type,
            "check_name": self.check_name,
            "passed": self.passed,
            "expected": self.expected,
            "actual": self.actual,
            "error": self.error,
            "duration_ms": self.duration_ms
        }


@dataclass
class VerificationResult:
    """Result of verifying all success criteria for a task."""
    task_id: str
    passed: bool
    checks_total: int
    checks_passed: int
    checks_failed: int
    check_results: List[CheckResult] = field(default_factory=list)
    error: Optional[str] = None
    verified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "passed": self.passed,
            "checks_total": self.checks_total,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "check_results": [c.to_dict() for c in self.check_results],
            "error": self.error,
            "verified_at": self.verified_at
        }


class SuccessCriteriaVerifier:
    """
    Verifies task success criteria by executing programmatic checks.
    
    This is the gatekeeper that prevents tasks from being marked complete
    without actually meeting their defined success criteria.
    """
    
    def __init__(self, working_dir: str = None):
        """
        Initialize the verifier.
        
        Args:
            working_dir: Base directory for file operations (default: repo root)
        """
        self.working_dir = working_dir or os.getcwd()
        self.github_token = GITHUB_TOKEN
        self.github_repo = GITHUB_REPO
    
    # =========================================================
    # CHECK EXECUTORS
    # =========================================================
    
    def _check_shell(self, check: Dict[str, Any]) -> CheckResult:
        """
        Execute a shell command and verify result.
        
        Supports:
        - expect: "exit_code_0" - command exits with 0
        - expect: "exit_code_N" - command exits with N
        - expect: "contains:text" - stdout contains text
        - expect: "not_contains:text" - stdout doesn't contain text
        - expect: "matches:regex" - stdout matches regex
        """
        command = check.get("command", "")
        expect = check.get("expect", "exit_code_0")
        timeout = check.get("timeout", 60)
        
        start = datetime.now()
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.working_dir
            )
            
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            stdout = result.stdout
            exit_code = result.returncode
            
            # Evaluate expectation
            passed = False
            actual = f"exit_code={exit_code}"
            
            if expect.startswith("exit_code_"):
                expected_code = int(expect.replace("exit_code_", ""))
                passed = (exit_code == expected_code)
                actual = f"exit_code={exit_code}"
                
            elif expect.startswith("contains:"):
                expected_text = expect.replace("contains:", "")
                passed = expected_text in stdout
                actual = f"stdout_length={len(stdout)}, found={passed}"
                
            elif expect.startswith("not_contains:"):
                expected_text = expect.replace("not_contains:", "")
                passed = expected_text not in stdout
                actual = f"stdout_length={len(stdout)}, absent={passed}"
                
            elif expect.startswith("matches:"):
                pattern = expect.replace("matches:", "")
                passed = bool(re.search(pattern, stdout))
                actual = f"matched={passed}"
            
            return CheckResult(
                check_type="shell",
                check_name=command[:50],
                passed=passed,
                expected=expect,
                actual=actual,
                duration_ms=duration_ms
            )
            
        except subprocess.TimeoutExpired:
            return CheckResult(
                check_type="shell",
                check_name=command[:50],
                passed=False,
                expected=expect,
                error=f"Command timed out after {timeout}s",
                duration_ms=timeout * 1000
            )
        except Exception as e:
            return CheckResult(
                check_type="shell",
                check_name=command[:50],
                passed=False,
                expected=expect,
                error=str(e)
            )
    
    def _check_file_exists(self, check: Dict[str, Any]) -> CheckResult:
        """Check if a file exists at the given path."""
        path = check.get("path", "")
        full_path = os.path.join(self.working_dir, path) if not path.startswith("/") else path
        
        exists = os.path.exists(full_path)
        
        return CheckResult(
            check_type="file_exists",
            check_name=path,
            passed=exists,
            expected="exists",
            actual="exists" if exists else "not_found"
        )
    
    def _check_file_contains(self, check: Dict[str, Any]) -> CheckResult:
        """Check if a file contains a pattern."""
        path = check.get("path", "")
        pattern = check.get("pattern", "")
        is_regex = check.get("regex", False)
        
        full_path = os.path.join(self.working_dir, path) if not path.startswith("/") else path
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if is_regex:
                found = bool(re.search(pattern, content))
            else:
                found = pattern in content
            
            return CheckResult(
                check_type="file_contains",
                check_name=f"{path} contains '{pattern[:30]}'",
                passed=found,
                expected=f"contains: {pattern[:50]}",
                actual="found" if found else "not_found"
            )
            
        except FileNotFoundError:
            return CheckResult(
                check_type="file_contains",
                check_name=f"{path} contains '{pattern[:30]}'",
                passed=False,
                expected=f"contains: {pattern[:50]}",
                error=f"File not found: {path}"
            )
        except Exception as e:
            return CheckResult(
                check_type="file_contains",
                check_name=f"{path} contains '{pattern[:30]}'",
                passed=False,
                error=str(e)
            )
    
    def _check_file_not_contains(self, check: Dict[str, Any]) -> CheckResult:
        """Check if a file does NOT contain a pattern."""
        path = check.get("path", "")
        pattern = check.get("pattern", "")
        is_regex = check.get("regex", False)
        
        full_path = os.path.join(self.working_dir, path) if not path.startswith("/") else path
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if is_regex:
                found = bool(re.search(pattern, content))
            else:
                found = pattern in content
            
            return CheckResult(
                check_type="file_not_contains",
                check_name=f"{path} not contains '{pattern[:30]}'",
                passed=not found,
                expected=f"not contains: {pattern[:50]}",
                actual="absent" if not found else "found (FAIL)"
            )
            
        except FileNotFoundError:
            # File not existing means pattern isn't there - pass
            return CheckResult(
                check_type="file_not_contains",
                check_name=f"{path} not contains '{pattern[:30]}'",
                passed=True,
                expected=f"not contains: {pattern[:50]}",
                actual="file_not_found (pattern absent)"
            )
        except Exception as e:
            return CheckResult(
                check_type="file_not_contains",
                check_name=f"{path} not contains '{pattern[:30]}'",
                passed=False,
                error=str(e)
            )
    
    def _check_db_query(self, check: Dict[str, Any]) -> CheckResult:
        """
        Execute a database query and verify result.
        
        Supports:
        - expect: "> 0" - row count greater than 0
        - expect: "= 5" - row count equals 5
        - expect: "value:foo" - first cell equals "foo"
        - expect: "contains:bar" - any cell contains "bar"
        """
        query = check.get("query", "")
        expect = check.get("expect", "> 0")
        
        start = datetime.now()
        
        try:
            result = _db_query(query)
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            
            if "error" in result:
                return CheckResult(
                    check_type="db_query",
                    check_name=query[:50],
                    passed=False,
                    expected=expect,
                    error=result["error"],
                    duration_ms=duration_ms
                )
            
            rows = result.get("rows", [])
            row_count = len(rows)
            
            passed = False
            actual = f"rows={row_count}"
            
            if expect.startswith(">"):
                threshold = int(expect.replace(">", "").strip())
                passed = row_count > threshold
                actual = f"rows={row_count}"
                
            elif expect.startswith(">="):
                threshold = int(expect.replace(">=", "").strip())
                passed = row_count >= threshold
                actual = f"rows={row_count}"
                
            elif expect.startswith("="):
                expected_count = int(expect.replace("=", "").strip())
                passed = row_count == expected_count
                actual = f"rows={row_count}"
                
            elif expect.startswith("value:"):
                expected_value = expect.replace("value:", "")
                if rows and rows[0]:
                    first_key = list(rows[0].keys())[0]
                    actual_value = str(rows[0][first_key])
                    passed = actual_value == expected_value
                    actual = f"value={actual_value}"
                else:
                    actual = "no_rows"
                    
            elif expect.startswith("contains:"):
                search_value = expect.replace("contains:", "")
                for row in rows:
                    for value in row.values():
                        if search_value in str(value):
                            passed = True
                            break
                    if passed:
                        break
                actual = f"rows={row_count}, found={passed}"
            
            return CheckResult(
                check_type="db_query",
                check_name=query[:50],
                passed=passed,
                expected=expect,
                actual=actual,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            return CheckResult(
                check_type="db_query",
                check_name=query[:50],
                passed=False,
                expected=expect,
                error=str(e)
            )
    
    def _check_pr_merged(self, check: Dict[str, Any]) -> CheckResult:
        """Check if a GitHub PR is merged."""
        pr_number = check.get("pr_number")
        repo = check.get("repo", self.github_repo)
        
        if not pr_number:
            return CheckResult(
                check_type="pr_merged",
                check_name=f"PR #{pr_number}",
                passed=False,
                error="No pr_number specified"
            )
        
        try:
            url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Juggernaut-Verifier"
            }
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                pr_data = json.loads(response.read().decode('utf-8'))
            
            merged = pr_data.get("merged", False)
            state = pr_data.get("state", "unknown")
            
            return CheckResult(
                check_type="pr_merged",
                check_name=f"PR #{pr_number}",
                passed=merged,
                expected="merged=true",
                actual=f"merged={merged}, state={state}"
            )
            
        except urllib.error.HTTPError as e:
            return CheckResult(
                check_type="pr_merged",
                check_name=f"PR #{pr_number}",
                passed=False,
                error=f"GitHub API error: {e.code}"
            )
        except Exception as e:
            return CheckResult(
                check_type="pr_merged",
                check_name=f"PR #{pr_number}",
                passed=False,
                error=str(e)
            )
    
    def _check_pr_approved(self, check: Dict[str, Any]) -> CheckResult:
        """Check if a GitHub PR has required approvals."""
        pr_number = check.get("pr_number")
        repo = check.get("repo", self.github_repo)
        min_approvals = check.get("min_approvals", 1)
        
        if not pr_number:
            return CheckResult(
                check_type="pr_approved",
                check_name=f"PR #{pr_number}",
                passed=False,
                error="No pr_number specified"
            )
        
        try:
            url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Juggernaut-Verifier"
            }
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                reviews = json.loads(response.read().decode('utf-8'))
            
            # Count unique approvals (latest state per reviewer)
            reviewer_states = {}
            for review in reviews:
                reviewer = review.get("user", {}).get("login", "unknown")
                state = review.get("state", "")
                reviewer_states[reviewer] = state
            
            approvals = sum(1 for state in reviewer_states.values() if state == "APPROVED")
            
            passed = approvals >= min_approvals
            
            return CheckResult(
                check_type="pr_approved",
                check_name=f"PR #{pr_number}",
                passed=passed,
                expected=f"approvals >= {min_approvals}",
                actual=f"approvals={approvals}"
            )
            
        except Exception as e:
            return CheckResult(
                check_type="pr_approved",
                check_name=f"PR #{pr_number}",
                passed=False,
                error=str(e)
            )
    
    def _check_http_status(self, check: Dict[str, Any]) -> CheckResult:
        """Check if an HTTP endpoint returns expected status."""
        url = check.get("url", "")
        expected_status = check.get("expect", 200)
        method = check.get("method", "GET")
        timeout = check.get("timeout", 30)
        
        start = datetime.now()
        
        try:
            req = urllib.request.Request(url, method=method)
            req.add_header("User-Agent", "Juggernaut-Verifier")
            
            with urllib.request.urlopen(req, timeout=timeout) as response:
                actual_status = response.getcode()
            
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            passed = actual_status == expected_status
            
            return CheckResult(
                check_type="http_status",
                check_name=url[:50],
                passed=passed,
                expected=f"status={expected_status}",
                actual=f"status={actual_status}",
                duration_ms=duration_ms
            )
            
        except urllib.error.HTTPError as e:
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            passed = e.code == expected_status
            
            return CheckResult(
                check_type="http_status",
                check_name=url[:50],
                passed=passed,
                expected=f"status={expected_status}",
                actual=f"status={e.code}",
                duration_ms=duration_ms
            )
        except Exception as e:
            return CheckResult(
                check_type="http_status",
                check_name=url[:50],
                passed=False,
                expected=f"status={expected_status}",
                error=str(e)
            )
    
    def _check_github_file_exists(self, check: Dict[str, Any]) -> CheckResult:
        """Check if a file exists in the GitHub repo (on a specific branch)."""
        path = check.get("path", "")
        branch = check.get("branch", "main")
        repo = check.get("repo", self.github_repo)
        
        try:
            url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Juggernaut-Verifier"
            }
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                # If we get here, file exists
                data = json.loads(response.read().decode('utf-8'))
                file_type = data.get("type", "unknown")
            
            return CheckResult(
                check_type="github_file_exists",
                check_name=f"{path} on {branch}",
                passed=True,
                expected="exists",
                actual=f"type={file_type}"
            )
            
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return CheckResult(
                    check_type="github_file_exists",
                    check_name=f"{path} on {branch}",
                    passed=False,
                    expected="exists",
                    actual="not_found"
                )
            return CheckResult(
                check_type="github_file_exists",
                check_name=f"{path} on {branch}",
                passed=False,
                error=f"GitHub API error: {e.code}"
            )
        except Exception as e:
            return CheckResult(
                check_type="github_file_exists",
                check_name=f"{path} on {branch}",
                passed=False,
                error=str(e)
            )
    
    def _check_github_file_contains(self, check: Dict[str, Any]) -> CheckResult:
        """Check if a file in GitHub repo contains a pattern."""
        path = check.get("path", "")
        pattern = check.get("pattern", "")
        branch = check.get("branch", "main")
        repo = check.get("repo", self.github_repo)
        is_regex = check.get("regex", False)
        
        try:
            url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Juggernaut-Verifier"
            }
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            # Decode base64 content
            import base64
            content = base64.b64decode(data.get("content", "")).decode('utf-8', errors='ignore')
            
            if is_regex:
                found = bool(re.search(pattern, content))
            else:
                found = pattern in content
            
            return CheckResult(
                check_type="github_file_contains",
                check_name=f"{path} contains '{pattern[:30]}'",
                passed=found,
                expected=f"contains: {pattern[:50]}",
                actual="found" if found else "not_found"
            )
            
        except urllib.error.HTTPError as e:
            return CheckResult(
                check_type="github_file_contains",
                check_name=f"{path} contains '{pattern[:30]}'",
                passed=False,
                error=f"GitHub API error: {e.code}"
            )
        except Exception as e:
            return CheckResult(
                check_type="github_file_contains",
                check_name=f"{path} contains '{pattern[:30]}'",
                passed=False,
                error=str(e)
            )
    
    # =========================================================
    # MAIN VERIFICATION ENGINE
    # =========================================================
    
    def execute_check(self, check: Dict[str, Any]) -> CheckResult:
        """
        Execute a single verification check.
        
        Args:
            check: Check definition with 'type' and type-specific params
            
        Returns:
            CheckResult with pass/fail and details
        """
        check_type = check.get("type", "unknown")
        
        check_handlers = {
            "shell": self._check_shell,
            "file_exists": self._check_file_exists,
            "file_contains": self._check_file_contains,
            "file_not_contains": self._check_file_not_contains,
            "db_query": self._check_db_query,
            "pr_merged": self._check_pr_merged,
            "pr_approved": self._check_pr_approved,
            "http_status": self._check_http_status,
            "github_file_exists": self._check_github_file_exists,
            "github_file_contains": self._check_github_file_contains,
        }
        
        handler = check_handlers.get(check_type)
        
        if not handler:
            return CheckResult(
                check_type=check_type,
                check_name="unknown",
                passed=False,
                error=f"Unknown check type: {check_type}"
            )
        
        try:
            return handler(check)
        except Exception as e:
            return CheckResult(
                check_type=check_type,
                check_name=str(check)[:50],
                passed=False,
                error=f"Check execution failed: {str(e)}"
            )
    
    def verify_task(self, task_id: str, success_criteria: Dict[str, Any]) -> VerificationResult:
        """
        Verify all success criteria for a task.
        
        Args:
            task_id: The task being verified
            success_criteria: JSON object with 'checks' array
            
        Returns:
            VerificationResult with overall pass/fail and details
        """
        checks = success_criteria.get("checks", [])
        require_all = success_criteria.get("require_all", True)
        
        if not checks:
            # No criteria defined = auto-pass (legacy behavior)
            return VerificationResult(
                task_id=task_id,
                passed=True,
                checks_total=0,
                checks_passed=0,
                checks_failed=0,
                error="No success criteria defined - auto-pass"
            )
        
        check_results = []
        
        for check in checks:
            result = self.execute_check(check)
            check_results.append(result)
            logger.info(
                "[VERIFY] Task %s check '%s': %s",
                task_id[:8], result.check_name, "PASS" if result.passed else "FAIL"
            )
        
        checks_passed = sum(1 for r in check_results if r.passed)
        checks_failed = len(check_results) - checks_passed
        
        if require_all:
            overall_passed = checks_failed == 0
        else:
            # At least one must pass
            overall_passed = checks_passed > 0
        
        return VerificationResult(
            task_id=task_id,
            passed=overall_passed,
            checks_total=len(check_results),
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            check_results=check_results
        )


# =========================================================
# TASK COMPLETION GATE
# =========================================================

def verify_task_completion(task_id: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify a task can be marked complete.
    
    This is the GATE function called before any task status change to 'completed'.
    
    Args:
        task_id: Task to verify
        
    Returns:
        Tuple of (can_complete, verification_details)
    """
    # Get task with success_criteria
    result = _db_query(f"""
        SELECT id, title, success_criteria, status, completion_evidence
        FROM governance_tasks
        WHERE id = {_format_value(task_id)}
    """)
    
    if not result.get("rows"):
        return (False, {"error": f"Task {task_id} not found"})
    
    task = result["rows"][0]
    success_criteria = task.get("success_criteria")
    
    # If no success_criteria, allow completion (legacy behavior)
    if not success_criteria:
        logger.info("[VERIFY] Task %s has no success_criteria - allowing completion", task_id[:8])
        return (True, {"message": "No success criteria defined"})
    
    # Parse criteria if it's a string
    if isinstance(success_criteria, str):
        try:
            success_criteria = json.loads(success_criteria)
        except json.JSONDecodeError:
            return (False, {"error": "Invalid success_criteria JSON"})
    
    # Run verification
    verifier = SuccessCriteriaVerifier()
    verification = verifier.verify_task(task_id, success_criteria)
    
    # Store verification result in database
    _db_query(f"""
        UPDATE governance_tasks
        SET 
            verification_status = {_format_value('passed' if verification.passed else 'failed')},
            verification_result = {_format_value(verification.to_dict())},
            verified_at = NOW()
        WHERE id = {_format_value(task_id)}
    """)
    
    if verification.passed:
        logger.info(
            "[VERIFY] Task %s PASSED verification (%d/%d checks)",
            task_id[:8], verification.checks_passed, verification.checks_total
        )
    else:
        logger.warning(
            "[VERIFY] Task %s FAILED verification (%d/%d checks failed)",
            task_id[:8], verification.checks_failed, verification.checks_total
        )
    
    return (verification.passed, verification.to_dict())


def get_subtask_completion_status(parent_task_id: str) -> Dict[str, Any]:
    """
    Check if all subtasks of a parent task are complete and verified.
    
    This enables hierarchical task verification - a parent task can only
    complete when all its children are complete and verified.
    
    Args:
        parent_task_id: The parent task ID
        
    Returns:
        Dict with completion status and details
    """
    result = _db_query(f"""
        SELECT 
            id, title, status, verification_status,
            completed_at, completion_evidence
        FROM governance_tasks
        WHERE parent_task_id = {_format_value(parent_task_id)}
        ORDER BY created_at
    """)
    
    subtasks = result.get("rows", [])
    
    if not subtasks:
        return {
            "parent_task_id": parent_task_id,
            "has_subtasks": False,
            "can_complete": True,
            "message": "No subtasks - parent can complete"
        }
    
    total = len(subtasks)
    completed = sum(1 for t in subtasks if t.get("status") == "completed")
    verified = sum(1 for t in subtasks if t.get("verification_status") == "passed")
    failed = sum(1 for t in subtasks if t.get("status") == "failed")
    pending = total - completed - failed
    
    all_complete = completed == total
    all_verified = verified == total
    
    return {
        "parent_task_id": parent_task_id,
        "has_subtasks": True,
        "total_subtasks": total,
        "completed": completed,
        "verified": verified,
        "failed": failed,
        "pending": pending,
        "can_complete": all_complete and all_verified,
        "subtasks": [
            {
                "id": t["id"],
                "title": t["title"],
                "status": t["status"],
                "verification_status": t.get("verification_status")
            }
            for t in subtasks
        ]
    }


def reject_task_completion(
    task_id: str,
    reason: str,
    verification_result: Dict[str, Any] = None
) -> bool:
    """
    Reject a task completion attempt and reset to in_progress.
    
    Args:
        task_id: Task to reject
        reason: Reason for rejection
        verification_result: Optional verification details
        
    Returns:
        True if rejection was recorded
    """
    result = _db_query(f"""
        UPDATE governance_tasks
        SET 
            status = 'in_progress',
            verification_status = 'failed',
            verification_result = {_format_value(verification_result or {})},
            error_message = CONCAT(
                COALESCE(error_message, ''),
                '[VERIFICATION REJECTED] ',
                {_format_value(reason)},
                ' '
            ),
            updated_at = NOW()
        WHERE id = {_format_value(task_id)}
    """)
    
    logger.warning("[VERIFY] Task %s completion REJECTED: %s", task_id[:8], reason)
    
    return result.get("rowCount", 0) > 0


# =========================================================
# EXPORTS
# =========================================================

__all__ = [
    "SuccessCriteriaVerifier",
    "CheckResult",
    "VerificationResult",
    "verify_task_completion",
    "get_subtask_completion_status",
    "reject_task_completion",
]
