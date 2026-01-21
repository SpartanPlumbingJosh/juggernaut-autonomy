#!/usr/bin/env python3
"""
PLAN SUBMISSION AND APPROVAL FLOW
=================================
VERCHAIN-05: Plan Submission and Approval Flow

Before a worker starts work, they must submit a plan. ORCHESTRATOR reviews
and approves/rejects. This prevents workers from diving in without understanding
the task.

Plan Structure:
{
    "approach": "How I will solve this",
    "steps": ["Step 1", "Step 2", ...],
    "files_affected": ["file1.py", "file2.py"],
    "risks": ["Risk 1", "Risk 2"],
    "estimated_duration_minutes": 120,
    "verification_approach": "How I will verify my work"
}

Workflow:
1. EXECUTOR claims task → stage becomes 'discovered' or stays as-is
2. EXECUTOR calls submit_plan() → stage becomes 'plan_submitted'
3. ORCHESTRATOR calls review_plan(approved=True) → stage becomes 'plan_approved'
   OR ORCHESTRATOR calls review_plan(approved=False) → feedback added, stage stays
4. EXECUTOR can now start work → stage becomes 'in_progress'
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class PlanStep:
    """A single step in an execution plan."""
    description: str
    estimated_minutes: int = 15
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass 
class ExecutionPlan:
    """Structured execution plan submitted by workers before starting work."""
    approach: str
    steps: List[str]
    files_affected: List[str]
    risks: List[str]
    estimated_duration_minutes: int
    verification_approach: str
    dependencies: List[str] = field(default_factory=list)
    rollback_plan: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionPlan':
        return cls(
            approach=data.get("approach", ""),
            steps=data.get("steps", []),
            files_affected=data.get("files_affected", []),
            risks=data.get("risks", []),
            estimated_duration_minutes=data.get("estimated_duration_minutes", 60),
            verification_approach=data.get("verification_approach", ""),
            dependencies=data.get("dependencies", []),
            rollback_plan=data.get("rollback_plan", ""),
            acceptance_criteria=data.get("acceptance_criteria", [])
        )
    
    def validate(self) -> Tuple[bool, List[str]]:
        errors = []
        if not self.approach or len(self.approach) < 20:
            errors.append("Approach must be at least 20 characters")
        if not self.steps or len(self.steps) < 1:
            errors.append("At least one step is required")
        for i, step in enumerate(self.steps):
            if len(step) < 10:
                errors.append(f"Step {i+1} is too short (min 10 chars)")
        if not self.verification_approach or len(self.verification_approach) < 20:
            errors.append("Verification approach must be at least 20 characters")
        if self.estimated_duration_minutes < 5:
            errors.append("Estimated duration must be at least 5 minutes")
        if self.estimated_duration_minutes > 480:
            errors.append("Estimated duration exceeds 8 hours - consider breaking into subtasks")
        return len(errors) == 0, errors


@dataclass
class PlanReview:
    """Result of a plan review by ORCHESTRATOR."""
    approved: bool
    reviewer: str
    feedback: str
    reviewed_at: str
    revision_required: bool = False
    required_changes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PlanStatus(Enum):
    NONE = "none"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

NEON_HOST = "ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech"
NEON_DATABASE = "neondb"
NEON_USER = "neondb_owner"
NEON_PASSWORD = "npg_OYkCRU4aze2l"
NEON_HTTP_URL = f"https://{NEON_HOST}/sql"


def _execute_sql(sql: str) -> List[Dict]:
    auth_string = f"{NEON_USER}:{NEON_PASSWORD}"
    import base64
    auth_bytes = base64.b64encode(auth_string.encode()).decode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth_bytes}",
        "Neon-Connection-String": f"postgresql://{NEON_USER}:{NEON_PASSWORD}@{NEON_HOST}/{NEON_DATABASE}?sslmode=require"
    }
    payload = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(NEON_HTTP_URL, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return result.get("rows", [])
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        raise Exception(f"SQL error: {error_body}")


def _escape_value(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        return f"'{json.dumps(value).replace(chr(39), chr(39)+chr(39))}'"
    safe = str(value).replace("'", "''")
    return f"'{safe}'"


# ============================================================
# CORE FUNCTIONS
# ============================================================

def submit_plan(task_id: str, plan: Dict[str, Any], worker_id: str = "EXECUTOR") -> Dict[str, Any]:
    """Worker submits their execution plan for review."""
    now = datetime.now(timezone.utc).isoformat()
    
    try:
        exec_plan = ExecutionPlan.from_dict(plan)
        is_valid, errors = exec_plan.validate()
        if not is_valid:
            return {"success": False, "error": "Plan validation failed", "validation_errors": errors, "task_id": task_id}
    except Exception as e:
        return {"success": False, "error": f"Invalid plan structure: {str(e)}", "task_id": task_id}
    
    sql = f"SELECT id, title, status, stage, assigned_worker FROM governance_tasks WHERE id = {_escape_value(task_id)}"
    rows = _execute_sql(sql)
    if not rows:
        return {"success": False, "error": f"Task {task_id} not found", "task_id": task_id}
    
    task = rows[0]
    current_stage = task.get("stage") or "discovered"
    valid_from_stages = ["discovered", "decomposed", "plan_submitted"]
    if current_stage not in valid_from_stages:
        return {"success": False, "error": f"Cannot submit plan from stage '{current_stage}'", "task_id": task_id}
    
    plan_json = json.dumps(exec_plan.to_dict())
    update_sql = f"""
        UPDATE governance_tasks
        SET implementation_plan = {_escape_value(plan_json)},
            stage = 'plan_submitted',
            updated_at = {_escape_value(now)},
            metadata = COALESCE(metadata, '{{}}'::jsonb) || {_escape_value({"plan_submitted_at": now, "plan_submitted_by": worker_id})}
        WHERE id = {_escape_value(task_id)}
    """
    _execute_sql(update_sql)
    
    transition_sql = f"""
        INSERT INTO verification_gate_transitions (task_id, from_gate, to_gate, passed, evidence, verified_by, transitioned_at)
        VALUES ({_escape_value(task_id)}, {_escape_value(current_stage)}, 'plan_submitted', TRUE,
                {_escape_value(json.dumps({"plan_approach": exec_plan.approach[:200], "steps_count": len(exec_plan.steps)}))},
                {_escape_value(worker_id)}, {_escape_value(now)})
    """
    _execute_sql(transition_sql)
    
    return {"success": True, "task_id": task_id, "stage": "plan_submitted", "message": "Plan submitted, awaiting review"}


def review_plan(task_id: str, approved: bool, feedback: str = None, reviewer: str = "ORCHESTRATOR", required_changes: List[str] = None) -> Dict[str, Any]:
    """ORCHESTRATOR reviews a submitted plan."""
    now = datetime.now(timezone.utc).isoformat()
    
    sql = f"SELECT id, title, status, stage, implementation_plan FROM governance_tasks WHERE id = {_escape_value(task_id)}"
    rows = _execute_sql(sql)
    if not rows:
        return {"success": False, "error": f"Task {task_id} not found", "task_id": task_id}
    
    task = rows[0]
    current_stage = task.get("stage") or "discovered"
    impl_plan = task.get("implementation_plan")
    
    if current_stage != "plan_submitted":
        return {"success": False, "error": f"Cannot review plan at stage '{current_stage}'", "task_id": task_id}
    if not impl_plan:
        return {"success": False, "error": "No implementation plan found", "task_id": task_id}
    
    review = PlanReview(approved=approved, reviewer=reviewer, feedback=feedback or ("Approved" if approved else "Needs revision"),
                        reviewed_at=now, revision_required=not approved, required_changes=required_changes or [])
    
    if approved:
        new_stage = "plan_approved"
        update_sql = f"""
            UPDATE governance_tasks SET stage = 'plan_approved', updated_at = {_escape_value(now)},
            metadata = COALESCE(metadata, '{{}}'::jsonb) || {_escape_value({"plan_approved_at": now, "plan_review": review.to_dict()})}
            WHERE id = {_escape_value(task_id)}
        """
    else:
        new_stage = "plan_submitted"
        update_sql = f"""
            UPDATE governance_tasks SET updated_at = {_escape_value(now)},
            metadata = COALESCE(metadata, '{{}}'::jsonb) || {_escape_value({"plan_rejected_at": now, "plan_rejection_feedback": feedback, "plan_review": review.to_dict()})}
            WHERE id = {_escape_value(task_id)}
        """
    _execute_sql(update_sql)
    
    transition_sql = f"""
        INSERT INTO verification_gate_transitions (task_id, from_gate, to_gate, passed, evidence, verified_by, transitioned_at)
        VALUES ({_escape_value(task_id)}, 'plan_submitted', {_escape_value(new_stage)}, {_escape_value(approved)},
                {_escape_value(json.dumps(review.to_dict()))}, {_escape_value(reviewer)}, {_escape_value(now)})
    """
    _execute_sql(transition_sql)
    
    return {"success": True, "task_id": task_id, "approved": approved, "stage": new_stage, "review": review.to_dict()}


def get_plan_status(task_id: str) -> Dict[str, Any]:
    """Get the current plan status for a task."""
    sql = f"SELECT id, stage, implementation_plan, metadata FROM governance_tasks WHERE id = {_escape_value(task_id)}"
    rows = _execute_sql(sql)
    if not rows:
        return {"success": False, "error": f"Task {task_id} not found", "task_id": task_id}
    
    task = rows[0]
    stage = task.get("stage") or "discovered"
    impl_plan = task.get("implementation_plan")
    metadata = task.get("metadata") or {}
    if isinstance(metadata, str):
        try: metadata = json.loads(metadata)
        except: metadata = {}
    
    if stage == "plan_approved": status = PlanStatus.APPROVED
    elif stage == "plan_submitted":
        status = PlanStatus.REJECTED if metadata.get("plan_rejected_at") else PlanStatus.SUBMITTED
    else: status = PlanStatus.NONE
    
    return {"success": True, "task_id": task_id, "stage": stage, "plan_status": status.value,
            "has_plan": impl_plan is not None, "can_start_work": stage == "plan_approved",
            "rejection_feedback": metadata.get("plan_rejection_feedback")}


def can_start_work(task_id: str) -> Tuple[bool, str]:
    """Check if work can be started on a task."""
    status = get_plan_status(task_id)
    if not status["success"]:
        return False, status.get("error", "Unknown error")
    stage = status["stage"]
    if stage == "plan_approved":
        return True, "Plan approved, work can begin"
    if stage == "plan_submitted":
        if status.get("rejection_feedback"):
            return False, f"Plan rejected: {status['rejection_feedback']}"
        return False, "Plan submitted but not yet reviewed"
    if stage in ["in_progress", "pending_review", "review_passed", "deployed"]:
        return True, "Work already in progress"
    return False, "No plan submitted. Submit a plan before starting work."


def get_tasks_awaiting_plan_review(limit: int = 20) -> List[Dict[str, Any]]:
    """Get tasks with submitted plans awaiting review."""
    sql = f"""
        SELECT id, title, implementation_plan, assigned_worker, updated_at
        FROM governance_tasks WHERE stage = 'plan_submitted'
        AND (metadata->>'plan_rejected_at' IS NULL OR metadata->>'plan_rejected_at' < metadata->>'plan_submitted_at')
        ORDER BY updated_at ASC LIMIT {limit}
    """
    rows = _execute_sql(sql)
    return [{"task_id": r["id"], "title": r["title"], "plan": r.get("implementation_plan")} for r in rows]


def get_tasks_needing_plan(worker_id: str = None, limit: int = 20) -> List[Dict[str, Any]]:
    """Get tasks that need plans submitted."""
    where = "WHERE stage IN ('discovered', 'decomposed') AND status NOT IN ('completed', 'failed')"
    if worker_id:
        where += f" AND assigned_worker = {_escape_value(worker_id)}"
    sql = f"SELECT id, title, task_type, priority FROM governance_tasks {where} ORDER BY created_at ASC LIMIT {limit}"
    return [{"task_id": r["id"], "title": r["title"], "needs_plan": True} for r in _execute_sql(sql)]


# ============================================================
# INTEGRATION HELPERS
# ============================================================

def executor_should_submit_plan(task: Dict) -> bool:
    """Check if EXECUTOR should submit a plan."""
    stage = task.get("stage") or "discovered"
    return stage in ["discovered", "decomposed"] and not task.get("implementation_plan")


def executor_should_revise_plan(task: Dict) -> Tuple[bool, Optional[str]]:
    """Check if EXECUTOR should revise their plan."""
    stage = task.get("stage")
    metadata = task.get("metadata") or {}
    if isinstance(metadata, str):
        try: metadata = json.loads(metadata)
        except: metadata = {}
    if stage == "plan_submitted" and metadata.get("plan_rejected_at"):
        if metadata.get("plan_rejected_at", "") > metadata.get("plan_submitted_at", ""):
            return True, metadata.get("plan_rejection_feedback")
    return False, None


def orchestrator_get_plans_to_review() -> List[Dict]:
    """Get plans waiting for review."""
    return get_tasks_awaiting_plan_review()


def orchestrator_auto_review_plan(task_id: str, plan: Dict) -> Dict[str, Any]:
    """Auto-review a plan using heuristics."""
    issues = []
    if len(plan.get("steps", [])) < 2:
        issues.append("Plan has too few steps")
    if plan.get("estimated_duration_minutes", 0) > 240:
        issues.append("Duration exceeds 4 hours")
    if not plan.get("verification_approach"):
        issues.append("Missing verification approach")
    if not plan.get("risks"):
        issues.append("No risks identified")
    
    if not issues:
        return review_plan(task_id, approved=True, feedback="Auto-approved", reviewer="ORCHESTRATOR-AUTO")
    return review_plan(task_id, approved=False, feedback="Needs improvement", reviewer="ORCHESTRATOR-AUTO", required_changes=issues)


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def quick_submit_plan(task_id: str, approach: str, steps: List[str], files_affected: List[str] = None, estimated_minutes: int = 60, worker_id: str = "EXECUTOR") -> Dict[str, Any]:
    """Quick plan submission."""
    plan = {"approach": approach, "steps": steps, "files_affected": files_affected or [], "risks": ["TBD"],
            "estimated_duration_minutes": estimated_minutes, "verification_approach": "Verify against acceptance criteria"}
    return submit_plan(task_id, plan, worker_id)


def approve_plan(task_id: str, feedback: str = None) -> Dict[str, Any]:
    """Approve a plan."""
    return review_plan(task_id, approved=True, feedback=feedback)


def reject_plan(task_id: str, feedback: str, required_changes: List[str] = None) -> Dict[str, Any]:
    """Reject a plan."""
    return review_plan(task_id, approved=False, feedback=feedback, required_changes=required_changes)


__all__ = ["ExecutionPlan", "PlanReview", "PlanStatus", "submit_plan", "review_plan", "get_plan_status",
           "can_start_work", "get_tasks_awaiting_plan_review", "get_tasks_needing_plan",
           "executor_should_submit_plan", "executor_should_revise_plan", "orchestrator_get_plans_to_review",
           "orchestrator_auto_review_plan", "quick_submit_plan", "approve_plan", "reject_plan"]
