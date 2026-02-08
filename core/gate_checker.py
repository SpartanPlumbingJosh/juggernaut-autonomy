"""
Gate Checker Core System
========================

The core engine that checks whether a task can advance through its verification gates.
Evaluates evidence against criteria and determines pass/fail for each gate in the chain.

Gate Types:
- PLAN_APPROVAL: Task plan has been reviewed and approved
- PR_CREATED: Pull request has been created on GitHub
- REVIEW_REQUESTED: Code review has been requested
- REVIEW_PASSED: Code review passed (CodeRabbit or human)
- PR_MERGED: Pull request has been merged to main
- DEPLOYED: Code has been deployed via Railway
- HEALTH_CHECK: Endpoint health check passes
- CUSTOM: Custom verification logic

Usage:
    checker = GateChecker()
    result = checker.check_gate(task_id, gate_definition)
    if result.passed:
        # Advance to next gate
    else:
        # Handle failure
"""

import os
import re
import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from datetime import datetime, timezone
import time

from core.database import query_db


class GateType(Enum):
    """Supported verification gate types."""
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
    checked_at: Optional[str] = None
    retry_after: Optional[int] = None  # Seconds to wait before retry
    
    def __post_init__(self):
        if self.checked_at is None:
            self.checked_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "passed": self.passed,
            "gate_type": self.gate_type,
            "evidence": self.evidence,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "retry_after": self.retry_after
        }


@dataclass
class GateDefinition:
    """Definition of a verification gate."""
    gate_type: str
    gate_name: str
    criteria: str
    evidence_required: str
    verifier: str = "ORCHESTRATOR"
    timeout_minutes: int = 60
    config: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GateDefinition":
        """Create GateDefinition from dictionary."""
        return cls(
            gate_type=data.get("gate_type", "custom"),
            gate_name=data.get("gate_name", "Unknown Gate"),
            criteria=data.get("criteria", ""),
            evidence_required=data.get("evidence_required", ""),
            verifier=data.get("verifier", "ORCHESTRATOR"),
            timeout_minutes=data.get("timeout_minutes", 60),
            config=data.get("config", {})
        )


class GateChecker:
    """
    Core gate checking engine.
    
    Evaluates whether tasks can advance through their verification gates
    by checking real evidence against defined criteria.
    """
    
    def __init__(self):
        """Initialize the gate checker with API credentials."""
        self.github_token = os.getenv("GITHUB_TOKEN", "")
        self.github_repo = (os.getenv("GITHUB_REPO") or "").strip()
        self.railway_token = os.getenv("RAILWAY_TOKEN", "")
        
        # Map gate types to their checker functions
        self.checkers = {
            GateType.PLAN_APPROVAL: self._check_plan_approval,
            GateType.PR_CREATED: self._check_pr_created,
            GateType.REVIEW_REQUESTED: self._check_review_requested,
            GateType.REVIEW_PASSED: self._check_review_passed,
            GateType.PR_MERGED: self._check_pr_merged,
            GateType.DEPLOYED: self._check_deployed,
            GateType.HEALTH_CHECK: self._check_health_check,
            GateType.CUSTOM: self._check_custom,
        }
    
    def check_gate(self, task_id: str, gate: Dict[str, Any]) -> GateResult:
        """
        Check if a task passes a specific verification gate.
        
        Args:
            task_id: The task ID to check
            gate: Gate definition dictionary
            
        Returns:
            GateResult indicating pass/fail with evidence
        """
        gate_def = GateDefinition.from_dict(gate)
        
        try:
            gate_type = GateType(gate_def.gate_type)
        except ValueError:
            gate_type = GateType.CUSTOM
        
        checker_fn = self.checkers.get(gate_type, self._check_custom)
        
        try:
            return checker_fn(task_id, gate_def)
        except Exception as e:
            return GateResult(
                passed=False,
                gate_type=gate_def.gate_type,
                reason=f"Gate check error: {str(e)}",
                evidence={"error": str(e)}
            )
    
    def check_all_gates(self, task_id: str) -> List[GateResult]:
        """
        Check all gates for a task and return results.
        
        Args:
            task_id: The task ID to check
            
        Returns:
            List of GateResult for each gate in the verification chain
        """
        # Get task verification chain from database
        query = f"""
            SELECT verification_chain, gate_evidence
            FROM governance_tasks
            WHERE id = '{task_id}'::uuid
        """
        result = query_db(query)
        rows = result.get("rows", [])
        
        if not rows:
            return [GateResult(
                passed=False,
                gate_type="unknown",
                reason=f"Task {task_id} not found"
            )]
        
        task = rows[0]
        verification_chain = task.get("verification_chain") or []
        
        if isinstance(verification_chain, str):
            verification_chain = json.loads(verification_chain)
        
        results = []
        for gate in verification_chain:
            result = self.check_gate(task_id, gate)
            results.append(result)
        
        return results
    
    def get_current_gate(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current gate a task is at.
        
        Args:
            task_id: The task ID
            
        Returns:
            Current gate definition or None
        """
        query = f"""
            SELECT verification_chain, current_gate, gate_evidence
            FROM governance_tasks
            WHERE id = '{task_id}'::uuid
        """
        result = query_db(query)
        rows = result.get("rows", [])
        
        if not rows:
            return None
        
        task = rows[0]
        current_gate_name = task.get("current_gate")
        verification_chain = task.get("verification_chain") or []
        
        if isinstance(verification_chain, str):
            verification_chain = json.loads(verification_chain)
        
        # Find current gate in chain
        for gate in verification_chain:
            if gate.get("gate_type") == current_gate_name:
                return gate
        
        # Return first gate if no current gate set
        return verification_chain[0] if verification_chain else None
    
    def advance_gate(self, task_id: str) -> Tuple[bool, Optional[str], GateResult]:
        """
        Try to advance a task to its next gate.
        
        Args:
            task_id: The task ID
            
        Returns:
            Tuple of (advanced, next_gate_name, result)
        """
        # Get task data
        query = f"""
            SELECT verification_chain, current_gate, gate_evidence
            FROM governance_tasks
            WHERE id = '{task_id}'::uuid
        """
        result = query_db(query)
        rows = result.get("rows", [])
        
        if not rows:
            return (False, None, GateResult(
                passed=False,
                gate_type="unknown",
                reason=f"Task {task_id} not found"
            ))
        
        task = rows[0]
        current_gate_name = task.get("current_gate")
        verification_chain = task.get("verification_chain") or []
        gate_evidence = task.get("gate_evidence") or {}
        
        if isinstance(verification_chain, str):
            verification_chain = json.loads(verification_chain)
        if isinstance(gate_evidence, str):
            gate_evidence = json.loads(gate_evidence)
        
        # Find current gate index
        current_idx = -1
        for i, gate in enumerate(verification_chain):
            if gate.get("gate_type") == current_gate_name:
                current_idx = i
                break
        
        # If no current gate, start at first gate
        if current_idx == -1:
            current_idx = 0
            current_gate_name = verification_chain[0].get("gate_type") if verification_chain else None
        
        if not current_gate_name or current_idx >= len(verification_chain):
            return (False, None, GateResult(
                passed=True,
                gate_type="complete",
                reason="All gates passed"
            ))
        
        # Check current gate
        current_gate = verification_chain[current_idx]
        check_result = self.check_gate(task_id, current_gate)
        
        if not check_result.passed:
            return (False, current_gate_name, check_result)
        
        # Gate passed - record evidence and advance
        gate_evidence[current_gate_name] = check_result.to_dict()
        
        # Determine next gate
        next_idx = current_idx + 1
        next_gate_name = None
        
        if next_idx < len(verification_chain):
            next_gate_name = verification_chain[next_idx].get("gate_type")
        
        # Update database
        gate_evidence_json = json.dumps(gate_evidence).replace("'", "''")
        next_gate_sql = f"'{next_gate_name}'" if next_gate_name else "NULL"
        
        update_query = f"""
            UPDATE governance_tasks
            SET current_gate = {next_gate_sql},
                gate_evidence = '{gate_evidence_json}'::jsonb
            WHERE id = '{task_id}'::uuid
        """
        query_db(update_query)
        
        # Log transition
        self._log_gate_transition(
            task_id=task_id,
            from_gate=current_gate_name,
            to_gate=next_gate_name,
            passed=True,
            evidence=check_result.to_dict(),
            verified_by=current_gate.get("verifier", "GateChecker")
        )
        
        return (True, next_gate_name, check_result)
    
    def _log_gate_transition(
        self,
        task_id: str,
        from_gate: Optional[str],
        to_gate: Optional[str],
        passed: bool,
        evidence: Dict[str, Any],
        verified_by: str
    ) -> None:
        """Log a gate transition to the database."""
        evidence_json = json.dumps(evidence).replace("'", "''")
        from_gate_sql = f"'{from_gate}'" if from_gate else "NULL"
        to_gate_sql = f"'{to_gate}'" if to_gate else "NULL"
        
        query = f"""
            INSERT INTO verification_gate_transitions (
                task_id, from_gate, to_gate, passed, evidence, verified_by
            ) VALUES (
                '{task_id}'::uuid,
                {from_gate_sql},
                {to_gate_sql},
                {str(passed).lower()},
                '{evidence_json}'::jsonb,
                '{verified_by}'
            )
        """
        try:
            query_db(query)
        except Exception as e:
            print(f"[GATE_CHECKER] Error logging transition: {e}")
    
    # =========================================================================
    # GATE CHECKER IMPLEMENTATIONS
    # =========================================================================
    
    def _check_plan_approval(self, task_id: str, gate: GateDefinition) -> GateResult:
        """
        Check if the task's plan has been approved.
        
        Looks for:
        - Plan field populated
        - plan_approved_at timestamp set
        - Or explicit approval in task metadata
        """
        query = f"""
            SELECT plan, metadata, status, stage
            FROM governance_tasks
            WHERE id = '{task_id}'::uuid
        """
        result = query_db(query)
        rows = result.get("rows", [])
        
        if not rows:
            return GateResult(
                passed=False,
                gate_type="plan_approval",
                reason="Task not found"
            )
        
        task = rows[0]
        plan = task.get("plan")
        metadata = task.get("metadata") or {}
        stage = task.get("stage")
        
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        # Check if plan exists and is approved
        plan_approved = metadata.get("plan_approved", False)
        plan_approved_at = metadata.get("plan_approved_at")
        plan_approved_by = metadata.get("plan_approved_by")
        
        # Also check stage
        if stage in ["plan_approved", "in_progress", "pending_review", "review_passed", 
                     "pending_deploy", "deployed", "pending_endpoint", "endpoint_verified", "complete"]:
            plan_approved = True
        
        if plan_approved or plan_approved_at:
            return GateResult(
                passed=True,
                gate_type="plan_approval",
                evidence={
                    "plan_exists": bool(plan),
                    "plan_approved": True,
                    "approved_at": plan_approved_at,
                    "approved_by": plan_approved_by,
                    "stage": stage
                },
                reason="Plan approved"
            )
        
        # Check if plan exists but not approved
        if plan:
            return GateResult(
                passed=False,
                gate_type="plan_approval",
                reason="Plan exists but not yet approved",
                evidence={"plan_exists": True, "plan_approved": False}
            )
        
        return GateResult(
            passed=False,
            gate_type="plan_approval",
            reason="No plan submitted",
            evidence={"plan_exists": False}
        )
    
    def _check_pr_created(self, task_id: str, gate: GateDefinition) -> GateResult:
        """
        Check if a PR has been created for this task.
        
        Looks for:
        - PR URL in task metadata
        - PR number in completion_evidence
        - GitHub API check for PR existence
        """
        # First check task metadata for PR info
        query = f"""
            SELECT metadata, completion_evidence
            FROM governance_tasks
            WHERE id = '{task_id}'::uuid
        """
        result = query_db(query)
        rows = result.get("rows", [])
        
        if not rows:
            return GateResult(
                passed=False,
                gate_type="pr_created",
                reason="Task not found"
            )
        
        task = rows[0]
        metadata = task.get("metadata") or {}
        evidence_text = task.get("completion_evidence") or ""
        
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        # Check metadata for PR info
        pr_url = metadata.get("pr_url")
        pr_number = metadata.get("pr_number")
        
        # Extract PR number from evidence text
        if not pr_number and evidence_text:
            pr_match = re.search(r'PR #?(\d+)', evidence_text, re.IGNORECASE)
            if pr_match:
                pr_number = int(pr_match.group(1))
            
            url_match = re.search(r'github\.com/.+/pull/(\d+)', evidence_text)
            if url_match:
                pr_number = int(url_match.group(1))
                pr_url = url_match.group(0)
        
        if pr_number:
            # Verify PR exists via GitHub API
            pr_data = self._get_github_pr(pr_number)
            
            if pr_data:
                return GateResult(
                    passed=True,
                    gate_type="pr_created",
                    evidence={
                        "pr_number": pr_number,
                        "pr_url": pr_data.get("html_url"),
                        "pr_title": pr_data.get("title"),
                        "pr_state": pr_data.get("state"),
                        "created_at": pr_data.get("created_at")
                    },
                    reason=f"PR #{pr_number} exists"
                )
            else:
                return GateResult(
                    passed=False,
                    gate_type="pr_created",
                    reason=f"PR #{pr_number} not found in GitHub",
                    evidence={"pr_number": pr_number, "verified": False}
                )
        
        return GateResult(
            passed=False,
            gate_type="pr_created",
            reason="No PR found for task",
            evidence={"pr_number": None}
        )
    
    def _check_review_requested(self, task_id: str, gate: GateDefinition) -> GateResult:
        """
        Check if code review has been requested on the PR.
        """
        # Get PR number from task
        pr_number = self._get_task_pr_number(task_id)
        
        if not pr_number:
            return GateResult(
                passed=False,
                gate_type="review_requested",
                reason="No PR found for task"
            )
        
        # Check PR for review requests
        pr_data = self._get_github_pr(pr_number)
        
        if not pr_data:
            return GateResult(
                passed=False,
                gate_type="review_requested",
                reason=f"PR #{pr_number} not found"
            )
        
        # Check for requested reviewers
        requested_reviewers = pr_data.get("requested_reviewers", [])
        requested_teams = pr_data.get("requested_teams", [])
        
        # Also check for existing reviews (review was requested and completed)
        reviews = self._get_pr_reviews(pr_number)
        
        if requested_reviewers or requested_teams or reviews:
            return GateResult(
                passed=True,
                gate_type="review_requested",
                evidence={
                    "pr_number": pr_number,
                    "requested_reviewers": [r.get("login") for r in requested_reviewers],
                    "requested_teams": [t.get("name") for t in requested_teams],
                    "existing_reviews": len(reviews)
                },
                reason="Review requested"
            )
        
        return GateResult(
            passed=False,
            gate_type="review_requested",
            reason="No reviewers requested on PR",
            evidence={"pr_number": pr_number}
        )
    
    def _check_review_passed(self, task_id: str, gate: GateDefinition) -> GateResult:
        """
        Check if code review has passed.
        
        Looks for:
        - CodeRabbit approval
        - Human reviewer approval
        - No changes requested
        """
        pr_number = self._get_task_pr_number(task_id)
        
        if not pr_number:
            return GateResult(
                passed=False,
                gate_type="review_passed",
                reason="No PR found for task"
            )
        
        reviews = self._get_pr_reviews(pr_number)
        
        if not reviews:
            return GateResult(
                passed=False,
                gate_type="review_passed",
                reason="No reviews found",
                evidence={"pr_number": pr_number, "reviews": []}
            )
        
        # Analyze reviews
        approvals = []
        changes_requested = []
        
        for review in reviews:
            state = review.get("state", "").upper()
            reviewer = review.get("user", {}).get("login", "unknown")
            
            if state == "APPROVED":
                approvals.append({
                    "reviewer": reviewer,
                    "submitted_at": review.get("submitted_at")
                })
            elif state == "CHANGES_REQUESTED":
                changes_requested.append({
                    "reviewer": reviewer,
                    "submitted_at": review.get("submitted_at")
                })
        
        # Check for CodeRabbit specifically
        coderabbit_approved = any(
            a["reviewer"].lower() in ["coderabbitai", "coderabbit"] 
            for a in approvals
        )
        
        # Need at least one approval and no outstanding change requests
        # (Change requests can be dismissed by subsequent approval)
        latest_by_reviewer = {}
        for review in reviews:
            reviewer = review.get("user", {}).get("login", "unknown")
            submitted_at = review.get("submitted_at", "")
            
            if reviewer not in latest_by_reviewer or submitted_at > latest_by_reviewer[reviewer]["submitted_at"]:
                latest_by_reviewer[reviewer] = {
                    "state": review.get("state"),
                    "submitted_at": submitted_at
                }
        
        outstanding_changes = [
            r for r, data in latest_by_reviewer.items() 
            if data["state"] == "CHANGES_REQUESTED"
        ]
        
        if approvals and not outstanding_changes:
            return GateResult(
                passed=True,
                gate_type="review_passed",
                evidence={
                    "pr_number": pr_number,
                    "approvals": approvals,
                    "coderabbit_approved": coderabbit_approved,
                    "total_reviews": len(reviews)
                },
                reason=f"Approved by {len(approvals)} reviewer(s)"
            )
        
        if outstanding_changes:
            return GateResult(
                passed=False,
                gate_type="review_passed",
                reason=f"Changes requested by: {', '.join(outstanding_changes)}",
                evidence={
                    "pr_number": pr_number,
                    "changes_requested_by": outstanding_changes
                }
            )
        
        return GateResult(
            passed=False,
            gate_type="review_passed",
            reason="No approvals yet",
            evidence={"pr_number": pr_number, "reviews": len(reviews)}
        )
    
    def _check_pr_merged(self, task_id: str, gate: GateDefinition) -> GateResult:
        """
        Check if the PR has been merged.
        """
        pr_number = self._get_task_pr_number(task_id)
        
        if not pr_number:
            return GateResult(
                passed=False,
                gate_type="merged",
                reason="No PR found for task"
            )
        
        pr_data = self._get_github_pr(pr_number)
        
        if not pr_data:
            return GateResult(
                passed=False,
                gate_type="merged",
                reason=f"PR #{pr_number} not found"
            )
        
        merged = pr_data.get("merged", False)
        merged_at = pr_data.get("merged_at")
        merge_commit_sha = pr_data.get("merge_commit_sha")
        merged_by = pr_data.get("merged_by", {}).get("login") if pr_data.get("merged_by") else None
        
        if merged:
            return GateResult(
                passed=True,
                gate_type="merged",
                evidence={
                    "pr_number": pr_number,
                    "merged": True,
                    "merged_at": merged_at,
                    "merge_commit_sha": merge_commit_sha,
                    "merged_by": merged_by
                },
                reason=f"PR #{pr_number} merged"
            )
        
        # Check if PR is still open or closed without merge
        state = pr_data.get("state", "unknown")
        
        return GateResult(
            passed=False,
            gate_type="merged",
            reason=f"PR #{pr_number} not merged (state: {state})",
            evidence={
                "pr_number": pr_number,
                "merged": False,
                "state": state
            }
        )
    
    def _check_deployed(self, task_id: str, gate: GateDefinition) -> GateResult:
        """
        Check if the code has been deployed via Railway.
        
        Looks for:
        - Recent successful deployment after merge
        - Service health status
        """
        # Get deployment info from task or config
        service_id = gate.config.get("service_id") or os.getenv("RAILWAY_SERVICE_ID")
        
        if not service_id:
            # Try to get from task metadata
            query = f"""
                SELECT metadata FROM governance_tasks WHERE id = '{task_id}'::uuid
            """
            result = query_db(query)
            rows = result.get("rows", [])
            
            if rows:
                metadata = rows[0].get("metadata") or {}
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                service_id = metadata.get("railway_service_id")
        
        if not service_id:
            return GateResult(
                passed=False,
                gate_type="deployed",
                reason="No Railway service ID configured",
                evidence={"service_id": None}
            )
        
        # Check Railway deployment status
        deployment = self._get_railway_deployment(service_id)
        
        if not deployment:
            return GateResult(
                passed=False,
                gate_type="deployed",
                reason="Could not fetch Railway deployment status",
                evidence={"service_id": service_id}
            )
        
        status = deployment.get("status", "unknown")
        
        if status.lower() in ["success", "deployed", "running"]:
            return GateResult(
                passed=True,
                gate_type="deployed",
                evidence={
                    "service_id": service_id,
                    "deployment_id": deployment.get("id"),
                    "status": status,
                    "deployed_at": deployment.get("createdAt")
                },
                reason="Deployment successful"
            )
        
        return GateResult(
            passed=False,
            gate_type="deployed",
            reason=f"Deployment status: {status}",
            evidence={
                "service_id": service_id,
                "status": status
            },
            retry_after=60  # Retry in 60 seconds
        )
    
    def _check_health_check(self, task_id: str, gate: GateDefinition) -> GateResult:
        """
        Run an HTTP health check against a configured endpoint.
        """
        # Get health check config
        url = gate.config.get("url")
        method = gate.config.get("method", "GET").upper()
        expected_status = gate.config.get("expected_status", 200)
        timeout = gate.config.get("timeout", 30)
        
        if not url:
            # Try to get from task endpoint_definition
            query = f"""
                SELECT endpoint_definition FROM governance_tasks WHERE id = '{task_id}'::uuid
            """
            result = query_db(query)
            rows = result.get("rows", [])
            
            if rows:
                endpoint_def = rows[0].get("endpoint_definition") or {}
                if isinstance(endpoint_def, str):
                    endpoint_def = json.loads(endpoint_def)
                
                url = endpoint_def.get("url")
                method = endpoint_def.get("method", "GET")
                expected_status = endpoint_def.get("expected_status", 200)
        
        if not url:
            return GateResult(
                passed=False,
                gate_type="health_check",
                reason="No health check URL configured"
            )
        
        # Perform health check
        try:
            req = urllib.request.Request(url, method=method)
            req.add_header("User-Agent", "Juggernaut-GateChecker/1.0")
            
            start_time = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.status
                response_time = time.time() - start_time
                body = response.read().decode("utf-8", errors="ignore")[:500]
            
            if status_code == expected_status:
                return GateResult(
                    passed=True,
                    gate_type="health_check",
                    evidence={
                        "url": url,
                        "method": method,
                        "status_code": status_code,
                        "expected_status": expected_status,
                        "response_time_ms": int(response_time * 1000)
                    },
                    reason=f"Health check passed ({status_code})"
                )
            else:
                return GateResult(
                    passed=False,
                    gate_type="health_check",
                    reason=f"Status {status_code}, expected {expected_status}",
                    evidence={
                        "url": url,
                        "status_code": status_code,
                        "expected_status": expected_status
                    }
                )
                
        except urllib.error.HTTPError as e:
            return GateResult(
                passed=False,
                gate_type="health_check",
                reason=f"HTTP error: {e.code}",
                evidence={"url": url, "error": str(e)}
            )
        except urllib.error.URLError as e:
            return GateResult(
                passed=False,
                gate_type="health_check",
                reason=f"Connection error: {str(e.reason)}",
                evidence={"url": url, "error": str(e)}
            )
        except Exception as e:
            return GateResult(
                passed=False,
                gate_type="health_check",
                reason=f"Health check failed: {str(e)}",
                evidence={"url": url, "error": str(e)}
            )
    
    def _check_custom(self, task_id: str, gate: GateDefinition) -> GateResult:
        """
        Handle custom verification logic.
        
        Custom gates can specify:
        - script: Command to run
        - query: SQL query that should return rows
        - webhook: URL to call for verification
        """
        config = gate.config
        
        # SQL query check
        if "query" in config:
            try:
                result = query_db(config["query"])
                rows = result.get("rows", [])
                
                if rows:
                    return GateResult(
                        passed=True,
                        gate_type="custom",
                        evidence={"query_result": rows[:5]},  # Limit evidence size
                        reason=f"Query returned {len(rows)} rows"
                    )
                else:
                    return GateResult(
                        passed=False,
                        gate_type="custom",
                        reason="Query returned no rows"
                    )
            except Exception as e:
                return GateResult(
                    passed=False,
                    gate_type="custom",
                    reason=f"Query error: {str(e)}"
                )
        
        # Webhook check
        if "webhook" in config:
            try:
                webhook_url = config["webhook"]
                data = json.dumps({"task_id": task_id}).encode("utf-8")
                
                req = urllib.request.Request(webhook_url, data=data, method="POST")
                req.add_header("Content-Type", "application/json")
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    
                    passed = result.get("passed", False)
                    return GateResult(
                        passed=passed,
                        gate_type="custom",
                        evidence=result.get("evidence"),
                        reason=result.get("reason", "Webhook check complete")
                    )
            except Exception as e:
                return GateResult(
                    passed=False,
                    gate_type="custom",
                    reason=f"Webhook error: {str(e)}"
                )
        
        # Manual approval check (look in metadata)
        query = f"""
            SELECT metadata FROM governance_tasks WHERE id = '{task_id}'::uuid
        """
        result = query_db(query)
        rows = result.get("rows", [])
        
        if rows:
            metadata = rows[0].get("metadata") or {}
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            
            gate_name = gate.gate_name.lower().replace(" ", "_")
            
            if metadata.get(f"{gate_name}_approved"):
                return GateResult(
                    passed=True,
                    gate_type="custom",
                    evidence={"manual_approval": True},
                    reason=f"Manually approved: {gate.gate_name}"
                )
        
        return GateResult(
            passed=False,
            gate_type="custom",
            reason=f"Custom gate '{gate.gate_name}' not passed"
        )
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _get_task_pr_number(self, task_id: str) -> Optional[int]:
        """Get PR number associated with a task."""
        query = f"""
            SELECT metadata, completion_evidence
            FROM governance_tasks
            WHERE id = '{task_id}'::uuid
        """
        result = query_db(query)
        rows = result.get("rows", [])
        
        if not rows:
            return None
        
        task = rows[0]
        metadata = task.get("metadata") or {}
        evidence = task.get("completion_evidence") or ""
        
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        # Check metadata first
        pr_number = metadata.get("pr_number")
        if pr_number:
            return int(pr_number)
        
        # Extract from evidence
        pr_match = re.search(r'PR #?(\d+)', evidence, re.IGNORECASE)
        if pr_match:
            return int(pr_match.group(1))
        
        url_match = re.search(r'github\.com/.+/pull/(\d+)', evidence)
        if url_match:
            return int(url_match.group(1))
        
        return None
    
    def _get_github_pr(self, pr_number: int) -> Optional[Dict[str, Any]]:
        """Fetch PR data from GitHub API."""
        if not self.github_token:
            return None
        
        url = f"https://api.github.com/repos/{self.github_repo}/pulls/{pr_number}"
        
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"token {self.github_token}")
            req.add_header("Accept", "application/vnd.github.v3+json")
            req.add_header("User-Agent", "Juggernaut-GateChecker")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            print(f"[GATE_CHECKER] GitHub API error: {e}")
            return None
    
    def _get_pr_reviews(self, pr_number: int) -> List[Dict[str, Any]]:
        """Fetch PR reviews from GitHub API."""
        if not self.github_token:
            return []
        
        url = f"https://api.github.com/repos/{self.github_repo}/pulls/{pr_number}/reviews"
        
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"token {self.github_token}")
            req.add_header("Accept", "application/vnd.github.v3+json")
            req.add_header("User-Agent", "Juggernaut-GateChecker")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            print(f"[GATE_CHECKER] GitHub reviews API error: {e}")
            return []
    
    def _get_railway_deployment(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Fetch latest deployment from Railway API."""
        if not self.railway_token:
            # Return mock success for testing if no token
            return {"status": "unknown", "id": None}
        
        # Railway GraphQL API
        url = "https://backboard.railway.app/graphql/v2"
        
        query_gql = """
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
                "query": query_gql,
                "variables": {"serviceId": service_id}
            }).encode("utf-8")
            
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Authorization", f"Bearer {self.railway_token}")
            req.add_header("Content-Type", "application/json")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                edges = result.get("data", {}).get("deployments", {}).get("edges", [])
                
                if edges:
                    return edges[0].get("node")
                return None
        except Exception as e:
            print(f"[GATE_CHECKER] Railway API error: {e}")
            return None


# =========================================================================
# CONVENIENCE FUNCTIONS
# =========================================================================

def check_task_gates(task_id: str) -> List[GateResult]:
    """Check all gates for a task."""
    checker = GateChecker()
    return checker.check_all_gates(task_id)


def advance_task_gate(task_id: str) -> Tuple[bool, Optional[str], GateResult]:
    """Try to advance a task to its next gate."""
    checker = GateChecker()
    return checker.advance_gate(task_id)


def get_blocking_gate(task_id: str) -> Optional[str]:
    """Get the gate that's blocking task progress."""
    checker = GateChecker()
    current_gate = checker.get_current_gate(task_id)
    
    if not current_gate:
        return None
    
    result = checker.check_gate(task_id, current_gate)
    
    if not result.passed:
        return current_gate.get("gate_type")
    
    return None
