"""
VERCHAIN Gate Checker Core System
==================================

Core engine that checks whether a task can advance through its verification gates.
Evaluates evidence against criteria and determines pass/fail for each gate type.

Gate Types:
- PLAN_APPROVAL: Plan was reviewed and approved by ORCHESTRATOR
- PR_CREATED: Pull request exists in GitHub
- REVIEW_REQUESTED: Code review has been requested
- REVIEW_PASSED: CodeRabbit or reviewer approved
- PR_MERGED: Pull request was merged to main
- DEPLOYED: Railway deployment succeeded
- HEALTH_CHECK: Endpoint returns expected response
- CUSTOM: User-defined verification logic
"""

import os
import re
import json
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from datetime import datetime, timezone

from core.database import query_db


class GateType(Enum):
    """Types of verification gates a task can pass through."""
    PLAN_APPROVAL = "plan_approval"
    PR_CREATED = "pr_created"
    REVIEW_REQUESTED = "review_requested"
    REVIEW_PASSED = "review_passed"
    PR_MERGED = "merged"
    DEPLOYED = "deployed"
    HEALTH_CHECK = "health_check"
    CUSTOM = "custom"


@dataclass
class GateResult:
    """Result of checking a verification gate."""
    passed: bool
    gate_type: str
    evidence: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    checked_at: Optional[str] = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GateChecker:
    """
    Core engine for checking verification gates.
    
    Checks whether a task can advance through its gates by evaluating
    evidence against criteria and determining pass/fail.
    """
    
    # GitHub configuration - tokens loaded from environment
    GITHUB_API_BASE = "https://api.github.com"
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO = os.getenv("GITHUB_REPO", "SpartanPlumbingJosh/juggernaut-autonomy")
    
    # Railway configuration - tokens loaded from environment
    RAILWAY_API_URL = "https://backboard.railway.com/graphql/v2"
    RAILWAY_TOKEN = os.getenv("RAILWAY_TOKEN", "")
    
    def __init__(self):
        """Initialize the gate checker with type-to-checker mapping."""
        self.checkers = {
            GateType.PLAN_APPROVAL: self._check_plan_approval,
            GateType.PR_CREATED: self._check_pr_created,
            GateType.REVIEW_REQUESTED: self._check_review_requested,
            GateType.REVIEW_PASSED: self._check_review_passed,
            GateType.PR_MERGED: self._check_pr_merged,
            GateType.DEPLOYED: self._check_deployed,
            GateType.HEALTH_CHECK: self._check_health,
            GateType.CUSTOM: self._check_custom,
        }
    
    def check_gate(self, task: Dict, gate_definition: Dict) -> GateResult:
        """
        Check if a specific gate passes for a task.
        
        Args:
            task: Task data dictionary with id, verification_chain, gate_evidence, etc.
            gate_definition: Gate configuration with gate_type, criteria, evidence_required
            
        Returns:
            GateResult with passed status, evidence, and reason
        """
        gate_type_str = gate_definition.get("gate_type", "custom")
        
        try:
            gate_type = GateType(gate_type_str)
        except ValueError:
            gate_type = GateType.CUSTOM
        
        checker = self.checkers.get(gate_type, self._check_custom)
        
        try:
            return checker(task, gate_definition)
        except Exception as e:
            return GateResult(
                passed=False,
                gate_type=gate_type_str,
                reason=f"Gate check failed with error: {str(e)}"
            )
    
    def check_current_gate(self, task: Dict) -> GateResult:
        """Check the task's current gate in its verification chain."""
        verification_chain = task.get("verification_chain", [])
        current_gate = task.get("current_gate")
        
        if not verification_chain:
            return GateResult(passed=True, gate_type="none", reason="No verification chain defined")
        
        for gate_def in verification_chain:
            if gate_def.get("gate_type") == current_gate or gate_def.get("gate_name") == current_gate:
                return self.check_gate(task, gate_def)
        
        if not current_gate and verification_chain:
            return self.check_gate(task, verification_chain[0])
        
        return GateResult(passed=False, gate_type=current_gate or "unknown",
                         reason=f"Gate '{current_gate}' not found in verification chain")
    
    def advance_task(self, task_id: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Try to advance a task to its next gate."""
        query = f"SELECT id, title, verification_chain, current_gate, gate_evidence, stage FROM governance_tasks WHERE id = '{task_id}'::uuid"
        result = query_db(query)
        
        if not result.get("rows"):
            return (False, None, f"Task {task_id} not found")
        
        task = result["rows"][0]
        verification_chain = task.get("verification_chain")
        if isinstance(verification_chain, str):
            try:
                verification_chain = json.loads(verification_chain)
            except json.JSONDecodeError:
                verification_chain = []
        
        if not verification_chain:
            return (True, None, "No verification chain - task can proceed")
        
        task["verification_chain"] = verification_chain
        current_gate = task.get("current_gate")
        current_result = self.check_current_gate(task)
        
        if not current_result.passed:
            return (False, current_gate, f"Current gate not passed: {current_result.reason}")
        
        current_index = -1
        for i, gate_def in enumerate(verification_chain):
            if gate_def.get("gate_type") == current_gate or gate_def.get("gate_name") == current_gate:
                current_index = i
                break
        
        if current_index == -1:
            next_gate = verification_chain[0].get("gate_type") or verification_chain[0].get("gate_name")
        elif current_index >= len(verification_chain) - 1:
            return (True, "complete", "All gates passed")
        else:
            next_gate = verification_chain[current_index + 1].get("gate_type") or verification_chain[current_index + 1].get("gate_name")
        
        try:
            update_query = f"UPDATE governance_tasks SET current_gate = '{next_gate}' WHERE id = '{task_id}'::uuid"
            query_db(update_query)
            self._log_gate_transition(task_id, current_gate, next_gate, True, current_result.evidence)
            return (True, next_gate, f"Advanced to gate: {next_gate}")
        except Exception as e:
            return (False, current_gate, f"Failed to update task: {str(e)}")
    
    def get_blocker(self, task: Dict) -> Optional[str]:
        """Return why task can't advance, or None if it can."""
        result = self.check_current_gate(task)
        if result.passed:
            return None
        return result.reason or f"Gate {result.gate_type} did not pass"
    
    def check_all_gates(self, task: Dict) -> List[GateResult]:
        """Check status of all gates for a task."""
        verification_chain = task.get("verification_chain", [])
        if isinstance(verification_chain, str):
            try:
                verification_chain = json.loads(verification_chain)
            except json.JSONDecodeError:
                verification_chain = []
        return [self.check_gate(task, gate_def) for gate_def in verification_chain]
    
    # Individual Gate Checkers
    
    def _check_plan_approval(self, task: Dict, gate_def: Dict) -> GateResult:
        """Check if plan was approved by ORCHESTRATOR."""
        task_id = task.get("id")
        query = f"SELECT implementation_plan, plan_approved_at, plan_approved_by, stage FROM governance_tasks WHERE id = '{task_id}'::uuid"
        result = query_db(query)
        
        if not result.get("rows"):
            return GateResult(passed=False, gate_type="plan_approval", reason="Task not found")
        
        row = result["rows"][0]
        if not row.get("implementation_plan"):
            return GateResult(passed=False, gate_type="plan_approval", reason="No implementation plan submitted")
        
        if row.get("stage") == "plan_approved" or row.get("plan_approved_at"):
            return GateResult(passed=True, gate_type="plan_approval",
                            evidence={"plan_approved_at": row.get("plan_approved_at"),
                                     "plan_approved_by": row.get("plan_approved_by")})
        
        return GateResult(passed=False, gate_type="plan_approval", reason="Plan submitted but not yet approved")
    
    def _check_pr_created(self, task: Dict, gate_def: Dict) -> GateResult:
        """Check if PR exists in GitHub."""
        pr_number = self._get_pr_number(task)
        
        if pr_number:
            pr_data = self._fetch_github_pr(pr_number)
            if pr_data:
                return GateResult(passed=True, gate_type="pr_created",
                                evidence={"pr_number": pr_number, "pr_url": pr_data.get("html_url"),
                                         "pr_title": pr_data.get("title"), "pr_state": pr_data.get("state")})
        
        search_result = self._search_github_prs(str(task.get("id")))
        if search_result:
            return GateResult(passed=True, gate_type="pr_created",
                            evidence={"pr_number": search_result.get("number"),
                                     "pr_url": search_result.get("html_url")})
        
        return GateResult(passed=False, gate_type="pr_created", reason="No pull request found for this task")
    
    def _check_review_requested(self, task: Dict, gate_def: Dict) -> GateResult:
        """Check if code review has been requested."""
        pr_number = self._get_pr_number(task)
        if not pr_number:
            return GateResult(passed=False, gate_type="review_requested", reason="No PR found")
        
        pr_data = self._fetch_github_pr(pr_number)
        if not pr_data:
            return GateResult(passed=False, gate_type="review_requested", reason=f"PR #{pr_number} not found")
        
        reviews = self._fetch_github_reviews(pr_number)
        if pr_data.get("requested_reviewers") or reviews:
            return GateResult(passed=True, gate_type="review_requested",
                            evidence={"pr_number": pr_number, "review_count": len(reviews)})
        
        return GateResult(passed=False, gate_type="review_requested", reason="No reviewers requested")
    
    def _check_review_passed(self, task: Dict, gate_def: Dict) -> GateResult:
        """Check if CodeRabbit or reviewer approved."""
        pr_number = self._get_pr_number(task)
        if not pr_number:
            return GateResult(passed=False, gate_type="review_passed", reason="No PR found")
        
        reviews = self._fetch_github_reviews(pr_number)
        if not reviews:
            return GateResult(passed=False, gate_type="review_passed", reason="No reviews submitted yet")
        
        reviewer_states = {}
        for review in reviews:
            reviewer = review.get("user", {}).get("login", "unknown")
            state = review.get("state")
            submitted_at = review.get("submitted_at")
            if reviewer not in reviewer_states or submitted_at > reviewer_states[reviewer].get("submitted_at", ""):
                reviewer_states[reviewer] = {"state": state, "submitted_at": submitted_at}
        
        approvals = [r for r, d in reviewer_states.items() if d["state"] == "APPROVED"]
        changes_requested = [r for r, d in reviewer_states.items() if d["state"] == "CHANGES_REQUESTED"]
        
        if changes_requested and not any("coderabbit" in r.lower() for r in approvals):
            return GateResult(passed=False, gate_type="review_passed",
                            reason=f"Changes requested by: {', '.join(changes_requested)}")
        
        if approvals:
            return GateResult(passed=True, gate_type="review_passed",
                            evidence={"pr_number": pr_number, "approved_by": approvals})
        
        return GateResult(passed=False, gate_type="review_passed", reason="No approvals yet")
    
    def _check_pr_merged(self, task: Dict, gate_def: Dict) -> GateResult:
        """Check if PR was merged."""
        pr_number = self._get_pr_number(task)
        if not pr_number:
            return GateResult(passed=False, gate_type="merged", reason="No PR found")
        
        pr_data = self._fetch_github_pr(pr_number)
        if not pr_data:
            return GateResult(passed=False, gate_type="merged", reason=f"PR #{pr_number} not found")
        
        if pr_data.get("merged"):
            return GateResult(passed=True, gate_type="merged",
                            evidence={"pr_number": pr_number, "merged_at": pr_data.get("merged_at"),
                                     "merge_commit_sha": pr_data.get("merge_commit_sha")})
        
        if pr_data.get("state") == "closed":
            return GateResult(passed=False, gate_type="merged", reason="PR was closed without merging")
        
        return GateResult(passed=False, gate_type="merged", reason="PR is still open")
    
    def _check_deployed(self, task: Dict, gate_def: Dict) -> GateResult:
        """Check if deployment succeeded on Railway."""
        service_id = gate_def.get("service_id") or os.getenv("RAILWAY_SERVICE_ID")
        if not service_id:
            gate_evidence = task.get("gate_evidence", {})
            if isinstance(gate_evidence, str):
                try:
                    gate_evidence = json.loads(gate_evidence)
                except:
                    gate_evidence = {}
            service_id = gate_evidence.get("service_id")
        
        if not service_id:
            return GateResult(passed=False, gate_type="deployed", reason="No Railway service_id configured")
        
        deployment = self._fetch_railway_deployment(service_id)
        if not deployment:
            return GateResult(passed=False, gate_type="deployed", reason="Could not fetch deployment status")
        
        status = deployment.get("status")
        if status == "SUCCESS":
            return GateResult(passed=True, gate_type="deployed",
                            evidence={"service_id": service_id, "status": status})
        
        return GateResult(passed=False, gate_type="deployed", reason=f"Deployment status: {status}")
    
    def _check_health(self, task: Dict, gate_def: Dict) -> GateResult:
        """Run health check against endpoint."""
        url = gate_def.get("url")
        if not url:
            endpoint_def = task.get("endpoint_definition", {})
            if isinstance(endpoint_def, str):
                try:
                    endpoint_def = json.loads(endpoint_def)
                except:
                    endpoint_def = {}
            url = endpoint_def.get("url")
        
        if not url:
            return GateResult(passed=False, gate_type="health_check", reason="No URL configured")
        
        expected_status = gate_def.get("expected_status", 200)
        try:
            req = urllib.request.Request(url, method=gate_def.get("method", "GET"))
            req.add_header("User-Agent", "Juggernaut-GateChecker/1.0")
            with urllib.request.urlopen(req, timeout=gate_def.get("timeout", 30)) as response:
                status_code = response.getcode()
                if status_code == expected_status:
                    return GateResult(passed=True, gate_type="health_check",
                                    evidence={"url": url, "status_code": status_code})
                return GateResult(passed=False, gate_type="health_check",
                                reason=f"Expected status {expected_status}, got {status_code}")
        except Exception as e:
            return GateResult(passed=False, gate_type="health_check", reason=f"Health check failed: {str(e)}")
    
    def _check_custom(self, task: Dict, gate_def: Dict) -> GateResult:
        """Execute custom verification logic."""
        custom_type = gate_def.get("custom_type", "evidence_check")
        
        if custom_type == "sql":
            sql = gate_def.get("sql")
            if not sql:
                return GateResult(passed=False, gate_type="custom", reason="No SQL query provided")
            try:
                result = query_db(sql)
                rows = result.get("rows", [])
                expected_count = gate_def.get("expected_count")
                if expected_count is not None:
                    return GateResult(passed=len(rows) >= expected_count, gate_type="custom",
                                    evidence={"row_count": len(rows)})
                return GateResult(passed=len(rows) > 0, gate_type="custom", evidence={"row_count": len(rows)})
            except Exception as e:
                return GateResult(passed=False, gate_type="custom", reason=f"SQL error: {str(e)}")
        
        elif custom_type == "file_exists":
            file_path = gate_def.get("path")
            if not file_path:
                return GateResult(passed=False, gate_type="custom", reason="No file path provided")
            url = f"{self.GITHUB_API_BASE}/repos/{self.GITHUB_REPO}/contents/{file_path}"
            try:
                req = urllib.request.Request(url)
                req.add_header("Authorization", f"Bearer {self.GITHUB_TOKEN}")
                with urllib.request.urlopen(req, timeout=10):
                    return GateResult(passed=True, gate_type="custom", evidence={"file_path": file_path})
            except:
                return GateResult(passed=False, gate_type="custom", reason=f"File not found: {file_path}")
        
        else:
            pattern = gate_def.get("pattern")
            field = gate_def.get("field", "completion_evidence")
            value = task.get(field, "")
            if not pattern:
                return GateResult(passed=bool(value), gate_type="custom")
            if re.search(pattern, str(value), re.IGNORECASE):
                return GateResult(passed=True, gate_type="custom", evidence={"matched": True})
            return GateResult(passed=False, gate_type="custom", reason=f"Pattern not matched")
    
    # Helper Methods
    
    def _get_pr_number(self, task: Dict) -> Optional[int]:
        """Extract PR number from task data."""
        gate_evidence = task.get("gate_evidence", {})
        if isinstance(gate_evidence, str):
            try:
                gate_evidence = json.loads(gate_evidence)
            except:
                gate_evidence = {}
        
        pr_number = gate_evidence.get("pr_number")
        if pr_number:
            return int(pr_number)
        
        completion_evidence = task.get("completion_evidence", "")
        if completion_evidence:
            pr_match = re.search(r'PR #(\d+)', completion_evidence)
            if pr_match:
                return int(pr_match.group(1))
            url_match = re.search(r'github\.com/.*/pull/(\d+)', completion_evidence)
            if url_match:
                return int(url_match.group(1))
        return None
    
    def _fetch_github_pr(self, pr_number: int) -> Optional[Dict]:
        """Fetch PR data from GitHub API."""
        url = f"{self.GITHUB_API_BASE}/repos/{self.GITHUB_REPO}/pulls/{pr_number}"
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {self.GITHUB_TOKEN}")
            req.add_header("Accept", "application/vnd.github.v3+json")
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except:
            return None
    
    def _fetch_github_reviews(self, pr_number: int) -> List[Dict]:
        """Fetch reviews for a PR."""
        url = f"{self.GITHUB_API_BASE}/repos/{self.GITHUB_REPO}/pulls/{pr_number}/reviews"
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {self.GITHUB_TOKEN}")
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except:
            return []
    
    def _search_github_prs(self, task_id: str) -> Optional[Dict]:
        """Search for PRs mentioning task ID."""
        query = f"repo:{self.GITHUB_REPO} {task_id} in:title,body is:pr"
        url = f"{self.GITHUB_API_BASE}/search/issues?q={urllib.parse.quote(query)}"
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {self.GITHUB_TOKEN}")
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                items = data.get("items", [])
                return items[0] if items else None
        except:
            return None
    
    def _fetch_railway_deployment(self, service_id: str) -> Optional[Dict]:
        """Fetch latest deployment from Railway."""
        query = """query($serviceId: String!) { deployments(first: 1, input: {serviceId: $serviceId}) { edges { node { id status createdAt } } } }"""
        try:
            data = json.dumps({"query": query, "variables": {"serviceId": service_id}}).encode('utf-8')
            req = urllib.request.Request(self.RAILWAY_API_URL, data=data,
                                        headers={"Authorization": f"Bearer {self.RAILWAY_TOKEN}",
                                                "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                edges = result.get("data", {}).get("deployments", {}).get("edges", [])
                return edges[0].get("node") if edges else None
        except:
            return None
    
    def _log_gate_transition(self, task_id: str, from_gate: Optional[str], to_gate: str,
                           passed: bool, evidence: Optional[Dict] = None) -> None:
        """Log gate transition to database."""
        try:
            evidence_json = json.dumps(evidence or {}).replace("'", "''")
            from_gate_sql = f"'{from_gate}'" if from_gate else "NULL"
            query = f"""INSERT INTO verification_gate_transitions (task_id, from_gate, to_gate, passed, evidence, transitioned_at)
                       VALUES ('{task_id}'::uuid, {from_gate_sql}, '{to_gate}', {passed}, '{evidence_json}'::jsonb, NOW())"""
            query_db(query)
        except Exception as e:
            print(f"[GATE_CHECKER] Failed to log transition: {e}")


# Convenience functions

def check_task_gates(task_id: str) -> List[GateResult]:
    """Check all gates for a task."""
    checker = GateChecker()
    query = f"SELECT * FROM governance_tasks WHERE id = '{task_id}'::uuid"
    result = query_db(query)
    if not result.get("rows"):
        return []
    return checker.check_all_gates(result["rows"][0])


def try_advance_task(task_id: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Try to advance a task to its next gate."""
    return GateChecker().advance_task(task_id)


def get_task_blocker(task_id: str) -> Optional[str]:
    """Get the reason a task can't advance, if any."""
    checker = GateChecker()
    query = f"SELECT * FROM governance_tasks WHERE id = '{task_id}'::uuid"
    result = query_db(query)
    if not result.get("rows"):
        return "Task not found"
    return checker.get_blocker(result["rows"][0])
