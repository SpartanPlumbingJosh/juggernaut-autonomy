"""
Plan Submission and Approval Flow
=================================

Before a worker starts work on a task, they must submit a plan.
ORCHESTRATOR reviews and approves/rejects the plan.
This prevents workers from diving in without understanding the task.

Plan Structure:
{
    "approach": "How I will solve this",
    "steps": ["Step 1", "Step 2", ...],
    "files_affected": ["file1.py", "file2.py"],
    "risks": ["Risk 1", "Risk 2"],
    "estimated_duration_minutes": 120,
    "verification_approach": "How I will verify my work"
}

Stage Flow:
- decomposed -> plan_submitted (submit_plan)
- plan_submitted -> plan_approved (review_plan approved=True)
- plan_submitted -> plan_submitted (review_plan approved=False, revision needed)
- plan_approved -> in_progress (worker can start)

Usage:
    from core.plan_submission import submit_plan, review_plan, can_start_work
    
    # Worker submits plan
    result = submit_plan(task_id, plan_dict)
    
    # ORCHESTRATOR reviews
    result = review_plan(task_id, approved=True)
    
    # Check before starting work
    if can_start_work(task_id):
        # Begin work
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from core.database import query_db


@dataclass
class PlanValidationResult:
    """Result of plan validation."""
    valid: bool
    errors: List[str]
    warnings: List[str]


@dataclass
class PlanSubmissionResult:
    """Result of plan submission."""
    success: bool
    task_id: str
    stage: Optional[str] = None
    error: Optional[str] = None
    plan_version: int = 1


@dataclass
class PlanReviewResult:
    """Result of plan review."""
    success: bool
    task_id: str
    approved: bool
    stage: Optional[str] = None
    feedback: Optional[str] = None
    error: Optional[str] = None


# Required fields in a plan
REQUIRED_PLAN_FIELDS = ["approach", "steps"]

# Optional but recommended fields
RECOMMENDED_PLAN_FIELDS = [
    "files_affected",
    "risks",
    "estimated_duration_minutes",
    "verification_approach"
]


def validate_plan(plan: Dict[str, Any]) -> PlanValidationResult:
    """
    Validate a plan structure.
    
    Args:
        plan: The plan dictionary to validate
        
    Returns:
        PlanValidationResult with valid flag, errors, and warnings
    """
    errors = []
    warnings = []
    
    if not isinstance(plan, dict):
        return PlanValidationResult(
            valid=False,
            errors=["Plan must be a dictionary"],
            warnings=[]
        )
    
    # Check required fields
    for field in REQUIRED_PLAN_FIELDS:
        if field not in plan:
            errors.append(f"Missing required field: {field}")
        elif field == "approach" and not plan.get("approach"):
            errors.append("Approach cannot be empty")
        elif field == "steps":
            steps = plan.get("steps")
            if not isinstance(steps, list):
                errors.append("Steps must be a list")
            elif len(steps) == 0:
                errors.append("Steps cannot be empty")
    
    # Check recommended fields
    for field in RECOMMENDED_PLAN_FIELDS:
        if field not in plan:
            warnings.append(f"Missing recommended field: {field}")
    
    # Validate specific field types
    if "steps" in plan and isinstance(plan["steps"], list):
        for i, step in enumerate(plan["steps"]):
            if not isinstance(step, str):
                errors.append(f"Step {i+1} must be a string")
    
    if "files_affected" in plan:
        if not isinstance(plan["files_affected"], list):
            errors.append("files_affected must be a list")
    
    if "risks" in plan:
        if not isinstance(plan["risks"], list):
            errors.append("risks must be a list")
    
    if "estimated_duration_minutes" in plan:
        duration = plan["estimated_duration_minutes"]
        if not isinstance(duration, (int, float)) or duration <= 0:
            errors.append("estimated_duration_minutes must be a positive number")
    
    return PlanValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def get_task_stage(task_id: str) -> Optional[str]:
    """Get the current stage of a task."""
    query = f"""
        SELECT stage FROM governance_tasks WHERE id = '{task_id}'::uuid
    """
    result = query_db(query)
    rows = result.get("rows", [])
    
    if not rows:
        return None
    
    return rows[0].get("stage")


def is_valid_stage_transition(from_stage: str, to_stage: str) -> bool:
    """Check if a stage transition is valid using the stage_transitions table."""
    if from_stage is None:
        # Allow initial transitions
        return True
        
    query = f"""
        SELECT 1 FROM stage_transitions 
        WHERE from_stage = '{from_stage}' AND to_stage = '{to_stage}'
    """
    result = query_db(query)
    return len(result.get("rows", [])) > 0


def submit_plan(task_id: str, plan: Dict[str, Any]) -> PlanSubmissionResult:
    """
    Worker submits their execution plan for a task.
    
    This function:
    1. Validates the plan structure
    2. Stores the plan in the task
    3. Transitions stage to 'plan_submitted'
    4. Records the gate transition
    
    Args:
        task_id: The task ID
        plan: The execution plan dictionary
        
    Returns:
        PlanSubmissionResult with success status and any errors
    """
    # Validate plan structure
    validation = validate_plan(plan)
    if not validation.valid:
        return PlanSubmissionResult(
            success=False,
            task_id=task_id,
            error=f"Invalid plan: {'; '.join(validation.errors)}"
        )
    
    # Get current task state
    query = f"""
        SELECT id, stage, plan, metadata
        FROM governance_tasks 
        WHERE id = '{task_id}'::uuid
    """
    result = query_db(query)
    rows = result.get("rows", [])
    
    if not rows:
        return PlanSubmissionResult(
            success=False,
            task_id=task_id,
            error=f"Task {task_id} not found"
        )
    
    task = rows[0]
    current_stage = task.get("stage")
    existing_plan = task.get("plan")
    metadata = task.get("metadata") or {}
    
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    if isinstance(existing_plan, str):
        existing_plan = json.loads(existing_plan)
    
    # Calculate plan version
    plan_version = 1
    if existing_plan:
        plan_version = existing_plan.get("_version", 0) + 1
    
    # Add metadata to plan
    plan_with_meta = {
        **plan,
        "_version": plan_version,
        "_submitted_at": datetime.now(timezone.utc).isoformat(),
        "_previous_feedback": metadata.get("plan_feedback") if plan_version > 1 else None
    }
    
    # Check stage transition validity
    target_stage = "plan_submitted"
    
    # Allow submission from decomposed, plan_submitted (resubmission), or None
    valid_from_stages = [None, "decomposed", "plan_submitted"]
    if current_stage not in valid_from_stages:
        return PlanSubmissionResult(
            success=False,
            task_id=task_id,
            error=f"Cannot submit plan from stage '{current_stage}'. Task must be in decomposed or plan_submitted stage."
        )
    
    # Update task with plan and new stage
    plan_json = json.dumps(plan_with_meta).replace("'", "''")
    
    update_query = f"""
        UPDATE governance_tasks
        SET plan = '{plan_json}'::jsonb,
            stage = '{target_stage}',
            metadata = COALESCE(metadata, '{{}}'::jsonb) || 
                       '{{"plan_submitted_at": "{datetime.now(timezone.utc).isoformat()}", "plan_version": {plan_version}}}'::jsonb
        WHERE id = '{task_id}'::uuid
        RETURNING id, stage
    """
    
    try:
        update_result = query_db(update_query)
        
        if update_result.get("rowCount", 0) == 0:
            return PlanSubmissionResult(
                success=False,
                task_id=task_id,
                error="Failed to update task"
            )
        
        # Log gate transition
        _log_plan_transition(
            task_id=task_id,
            from_stage=current_stage,
            to_stage=target_stage,
            action="plan_submitted",
            details={"plan_version": plan_version}
        )
        
        return PlanSubmissionResult(
            success=True,
            task_id=task_id,
            stage=target_stage,
            plan_version=plan_version
        )
        
    except Exception as e:
        return PlanSubmissionResult(
            success=False,
            task_id=task_id,
            error=f"Database error: {str(e)}"
        )


def review_plan(
    task_id: str, 
    approved: bool, 
    feedback: Optional[str] = None,
    reviewer: str = "ORCHESTRATOR"
) -> PlanReviewResult:
    """
    ORCHESTRATOR reviews a submitted plan.
    
    If approved:
    - Stage transitions to 'plan_approved'
    - Worker can begin work
    
    If rejected:
    - Feedback is added to task metadata
    - Stage remains 'plan_submitted'
    - Worker must revise and resubmit
    
    Args:
        task_id: The task ID
        approved: Whether the plan is approved
        feedback: Optional feedback (required if not approved)
        reviewer: Who is reviewing (default: ORCHESTRATOR)
        
    Returns:
        PlanReviewResult with review outcome
    """
    # Get current task state
    query = f"""
        SELECT id, stage, plan, metadata
        FROM governance_tasks 
        WHERE id = '{task_id}'::uuid
    """
    result = query_db(query)
    rows = result.get("rows", [])
    
    if not rows:
        return PlanReviewResult(
            success=False,
            task_id=task_id,
            approved=False,
            error=f"Task {task_id} not found"
        )
    
    task = rows[0]
    current_stage = task.get("stage")
    plan = task.get("plan")
    metadata = task.get("metadata") or {}
    
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    
    # Verify task is in plan_submitted stage
    if current_stage != "plan_submitted":
        return PlanReviewResult(
            success=False,
            task_id=task_id,
            approved=False,
            error=f"Task must be in 'plan_submitted' stage to review. Current stage: {current_stage}"
        )
    
    # Verify plan exists
    if not plan:
        return PlanReviewResult(
            success=False,
            task_id=task_id,
            approved=False,
            error="No plan submitted for this task"
        )
    
    # Require feedback if rejecting
    if not approved and not feedback:
        return PlanReviewResult(
            success=False,
            task_id=task_id,
            approved=False,
            error="Feedback is required when rejecting a plan"
        )
    
    now = datetime.now(timezone.utc).isoformat()
    
    if approved:
        # Approve the plan
        target_stage = "plan_approved"
        metadata_update = {
            "plan_approved": True,
            "plan_approved_at": now,
            "plan_approved_by": reviewer,
            "plan_feedback": feedback
        }
    else:
        # Reject the plan - stay in plan_submitted
        target_stage = "plan_submitted"
        
        # Track rejection history
        rejection_history = metadata.get("plan_rejection_history", [])
        rejection_history.append({
            "rejected_at": now,
            "rejected_by": reviewer,
            "feedback": feedback
        })
        
        metadata_update = {
            "plan_approved": False,
            "plan_feedback": feedback,
            "plan_rejection_history": rejection_history,
            "plan_revision_needed": True
        }
    
    # Update task
    metadata_json = json.dumps(metadata_update).replace("'", "''")
    
    update_query = f"""
        UPDATE governance_tasks
        SET stage = '{target_stage}',
            metadata = COALESCE(metadata, '{{}}'::jsonb) || '{metadata_json}'::jsonb
        WHERE id = '{task_id}'::uuid
        RETURNING id, stage
    """
    
    try:
        update_result = query_db(update_query)
        
        if update_result.get("rowCount", 0) == 0:
            return PlanReviewResult(
                success=False,
                task_id=task_id,
                approved=approved,
                error="Failed to update task"
            )
        
        # Log gate transition
        action = "plan_approved" if approved else "plan_rejected"
        _log_plan_transition(
            task_id=task_id,
            from_stage=current_stage,
            to_stage=target_stage,
            action=action,
            details={
                "reviewer": reviewer,
                "feedback": feedback,
                "approved": approved
            }
        )
        
        return PlanReviewResult(
            success=True,
            task_id=task_id,
            approved=approved,
            stage=target_stage,
            feedback=feedback
        )
        
    except Exception as e:
        return PlanReviewResult(
            success=False,
            task_id=task_id,
            approved=approved,
            error=f"Database error: {str(e)}"
        )


def get_plan(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the submitted plan for a task.
    
    Args:
        task_id: The task ID
        
    Returns:
        The plan dictionary or None if not found
    """
    query = f"""
        SELECT plan FROM governance_tasks WHERE id = '{task_id}'::uuid
    """
    result = query_db(query)
    rows = result.get("rows", [])
    
    if not rows:
        return None
    
    plan = rows[0].get("plan")
    
    if plan and isinstance(plan, str):
        plan = json.loads(plan)
    
    return plan


def can_start_work(task_id: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a task has an approved plan and can start work.
    
    This enforces the rule that workers cannot begin work
    (transition to 'in_progress') without an approved plan.
    
    Args:
        task_id: The task ID
        
    Returns:
        Tuple of (can_start, reason)
    """
    query = f"""
        SELECT stage, plan, metadata
        FROM governance_tasks 
        WHERE id = '{task_id}'::uuid
    """
    result = query_db(query)
    rows = result.get("rows", [])
    
    if not rows:
        return (False, f"Task {task_id} not found")
    
    task = rows[0]
    stage = task.get("stage")
    plan = task.get("plan")
    metadata = task.get("metadata") or {}
    
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    
    # Check if plan exists
    if not plan:
        return (False, "No plan submitted. Worker must submit a plan first.")
    
    # Check if plan is approved
    plan_approved = metadata.get("plan_approved", False)
    
    if not plan_approved:
        return (False, "Plan not approved. Waiting for ORCHESTRATOR review.")
    
    # Check stage is appropriate for starting work
    if stage == "plan_approved":
        return (True, "Plan approved. Work can begin.")
    elif stage == "in_progress":
        return (True, "Work already in progress.")
    elif stage in ["pending_review", "review_passed", "pending_deploy", "deployed"]:
        return (True, "Task has progressed past planning stage.")
    else:
        return (False, f"Task in stage '{stage}' - must be plan_approved to start work.")


def get_tasks_pending_plan_review() -> List[Dict[str, Any]]:
    """
    Get all tasks that have submitted plans awaiting review.
    
    This is used by ORCHESTRATOR to find plans to review.
    
    Returns:
        List of tasks in plan_submitted stage
    """
    query = """
        SELECT id, title, description, plan, metadata, assigned_to, created_at
        FROM governance_tasks 
        WHERE stage = 'plan_submitted'
        ORDER BY created_at ASC
    """
    result = query_db(query)
    rows = result.get("rows", [])
    
    # Parse JSON fields
    for row in rows:
        if row.get("plan") and isinstance(row["plan"], str):
            row["plan"] = json.loads(row["plan"])
        if row.get("metadata") and isinstance(row["metadata"], str):
            row["metadata"] = json.loads(row["metadata"])
    
    return rows


def get_tasks_needing_plan() -> List[Dict[str, Any]]:
    """
    Get all tasks assigned to workers that don't have a plan yet.
    
    This is used by EXECUTOR to find tasks that need plans.
    
    Returns:
        List of tasks in decomposed stage with assigned_to set
    """
    query = """
        SELECT id, title, description, assigned_to, metadata
        FROM governance_tasks 
        WHERE stage = 'decomposed' 
        AND assigned_to IS NOT NULL
        AND (plan IS NULL OR plan = '{}')
        ORDER BY priority DESC, created_at ASC
    """
    result = query_db(query)
    rows = result.get("rows", [])
    
    # Parse JSON fields
    for row in rows:
        if row.get("metadata") and isinstance(row["metadata"], str):
            row["metadata"] = json.loads(row["metadata"])
    
    return rows


def start_work_on_task(task_id: str, worker_id: str) -> Tuple[bool, str]:
    """
    Attempt to start work on a task.
    
    This enforces the plan approval requirement before transitioning
    to 'in_progress' stage.
    
    Args:
        task_id: The task ID
        worker_id: The worker starting the work
        
    Returns:
        Tuple of (success, message)
    """
    # First check if work can start
    can_start, reason = can_start_work(task_id)
    
    if not can_start:
        return (False, reason)
    
    # Get current stage
    current_stage = get_task_stage(task_id)
    
    if current_stage == "in_progress":
        return (True, "Task already in progress")
    
    if current_stage != "plan_approved":
        return (False, f"Task must be in plan_approved stage. Current: {current_stage}")
    
    # Transition to in_progress
    now = datetime.now(timezone.utc).isoformat()
    
    update_query = f"""
        UPDATE governance_tasks
        SET stage = 'in_progress',
            status = 'in_progress',
            started_at = COALESCE(started_at, '{now}'::timestamptz),
            metadata = COALESCE(metadata, '{{}}'::jsonb) || 
                       '{{"work_started_at": "{now}", "work_started_by": "{worker_id}"}}'::jsonb
        WHERE id = '{task_id}'::uuid
        RETURNING id, stage
    """
    
    try:
        result = query_db(update_query)
        
        if result.get("rowCount", 0) == 0:
            return (False, "Failed to update task")
        
        # Log transition
        _log_plan_transition(
            task_id=task_id,
            from_stage="plan_approved",
            to_stage="in_progress",
            action="work_started",
            details={"worker_id": worker_id}
        )
        
        return (True, "Work started successfully")
        
    except Exception as e:
        return (False, f"Database error: {str(e)}")


def _log_plan_transition(
    task_id: str,
    from_stage: Optional[str],
    to_stage: str,
    action: str,
    details: Dict[str, Any]
) -> None:
    """Log a plan-related stage transition."""
    evidence_json = json.dumps({
        "action": action,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }).replace("'", "''")
    
    from_stage_sql = f"'{from_stage}'" if from_stage else "NULL"
    
    query = f"""
        INSERT INTO verification_gate_transitions (
            task_id, from_gate, to_gate, passed, evidence, verified_by
        ) VALUES (
            '{task_id}'::uuid,
            {from_stage_sql},
            '{to_stage}',
            true,
            '{evidence_json}'::jsonb,
            'PlanSubmission'
        )
    """
    
    try:
        query_db(query)
    except Exception as e:
        print(f"[PLAN_SUBMISSION] Error logging transition: {e}")


# =============================================================================
# CONVENIENCE FUNCTIONS FOR WORKERS
# =============================================================================

def executor_submit_plan(task_id: str, plan: Dict[str, Any]) -> PlanSubmissionResult:
    """
    Convenience function for EXECUTOR to submit a plan.
    
    Args:
        task_id: The task ID
        plan: The execution plan
        
    Returns:
        PlanSubmissionResult
    """
    return submit_plan(task_id, plan)


def orchestrator_review_plan(
    task_id: str, 
    approved: bool, 
    feedback: Optional[str] = None
) -> PlanReviewResult:
    """
    Convenience function for ORCHESTRATOR to review a plan.
    
    Args:
        task_id: The task ID
        approved: Whether to approve the plan
        feedback: Optional feedback
        
    Returns:
        PlanReviewResult
    """
    return review_plan(task_id, approved, feedback, reviewer="ORCHESTRATOR")


def generate_plan_template(task_title: str, task_description: str) -> Dict[str, Any]:
    """
    Generate a plan template for a task.
    
    Workers can use this as a starting point for their plan.
    
    Args:
        task_title: The task title
        task_description: The task description
        
    Returns:
        A plan template dictionary
    """
    return {
        "approach": f"[Describe how you will approach: {task_title}]",
        "steps": [
            "[Step 1: ...]",
            "[Step 2: ...]",
            "[Step 3: ...]"
        ],
        "files_affected": [
            "[List files that will be created/modified]"
        ],
        "risks": [
            "[Potential risk 1]",
            "[Potential risk 2]"
        ],
        "estimated_duration_minutes": 60,
        "verification_approach": "[How you will verify your work is complete and correct]"
    }
