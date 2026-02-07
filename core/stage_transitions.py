#!/usr/bin/env python3
"""
STAGE TRANSITION ENFORCEMENT
============================
VERCHAIN-02: Task Stage State Machine

This module enforces the task stage state machine, ensuring tasks can only
move through valid stages in the correct order with required evidence.

Valid Stages (in order):
- discovered: Task identified
- decomposed: Broken into subtasks
- plan_submitted: Implementation plan ready
- plan_approved: Plan approved by ORCHESTRATOR
- in_progress: Work actively being done
- pending_review: PR created, awaiting review
- review_passed: CodeRabbit/reviewer approved
- pending_deploy: Ready for deployment
- deployed: Successfully deployed
- pending_endpoint: Awaiting endpoint verification
- endpoint_verified: Endpoint checks passed
- complete: Task fully done

Invalid transitions are rejected to prevent fake completions.
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from enum import Enum


class TaskStage(Enum):
    """Valid task stages in order."""
    DISCOVERED = "discovered"
    DECOMPOSED = "decomposed"
    PLAN_SUBMITTED = "plan_submitted"
    PLAN_APPROVED = "plan_approved"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    REVIEW_PASSED = "review_passed"
    PENDING_DEPLOY = "pending_deploy"
    DEPLOYED = "deployed"
    PENDING_ENDPOINT = "pending_endpoint"
    ENDPOINT_VERIFIED = "endpoint_verified"
    COMPLETE = "complete"


@dataclass
class TransitionResult:
    """Result of a stage transition attempt."""
    allowed: bool
    from_stage: str
    to_stage: str
    requires_evidence: bool
    reason: Optional[str] = None
    evidence_provided: Optional[str] = None


# M-06: Centralized DB access via core.database
from core.database import escape_sql_value as _escape_value
from core.database import query_db as _query_db


def _execute_sql(sql: str) -> list:
    """Execute SQL and return rows."""
    result = _query_db(sql)
    return result.get("rows", [])


def validate_stage_transition(
    task_id: str,
    new_stage: str,
    evidence: Optional[str] = None
) -> TransitionResult:
    """
    Validate if a task can transition to a new stage.
    
    Args:
        task_id: The task UUID
        new_stage: The target stage
        evidence: Evidence for the transition (if required)
    
    Returns:
        TransitionResult with allowed=True if valid, False otherwise
    """
    # Get current stage
    sql = f"""
        SELECT stage, title, status FROM governance_tasks 
        WHERE id = {_escape_value(task_id)}
    """
    rows = _execute_sql(sql)
    
    if not rows:
        return TransitionResult(
            allowed=False,
            from_stage="unknown",
            to_stage=new_stage,
            requires_evidence=False,
            reason=f"Task {task_id} not found"
        )
    
    current_stage = rows[0].get("stage") or "discovered"  # Default for tasks without stage
    
    # Check if transition is valid
    sql = f"""
        SELECT requires_evidence FROM stage_transitions
        WHERE from_stage = {_escape_value(current_stage)}
        AND to_stage = {_escape_value(new_stage)}
    """
    transitions = _execute_sql(sql)
    
    if not transitions:
        return TransitionResult(
            allowed=False,
            from_stage=current_stage,
            to_stage=new_stage,
            requires_evidence=False,
            reason=f"Invalid transition: {current_stage} -> {new_stage}. Check stage_transitions table for valid moves."
        )
    
    requires_evidence = transitions[0].get("requires_evidence", True)
    
    # Check evidence if required
    if requires_evidence and not evidence:
        return TransitionResult(
            allowed=False,
            from_stage=current_stage,
            to_stage=new_stage,
            requires_evidence=True,
            reason=f"Transition {current_stage} -> {new_stage} requires evidence"
        )
    
    return TransitionResult(
        allowed=True,
        from_stage=current_stage,
        to_stage=new_stage,
        requires_evidence=requires_evidence,
        evidence_provided=evidence
    )


def transition_stage(
    task_id: str,
    new_stage: str,
    evidence: Optional[str] = None,
    verified_by: Optional[str] = None
) -> TransitionResult:
    """
    Attempt to transition a task to a new stage.
    
    This validates the transition and updates the task if valid.
    Also logs the transition to verification_gate_transitions.
    
    Args:
        task_id: The task UUID
        new_stage: The target stage
        evidence: Evidence for the transition
        verified_by: Who/what verified this transition (e.g., "ORCHESTRATOR", "CodeRabbit")
    
    Returns:
        TransitionResult with the outcome
    """
    # Validate first
    result = validate_stage_transition(task_id, new_stage, evidence)
    
    if not result.allowed:
        return result
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Update the task stage
    sql = f"""
        UPDATE governance_tasks 
        SET stage = {_escape_value(new_stage)},
            updated_at = {_escape_value(now)}
        WHERE id = {_escape_value(task_id)}
    """
    _execute_sql(sql)
    
    # Log the transition
    evidence_json = json.dumps({"evidence": evidence, "timestamp": now}) if evidence else "{}"
    
    log_sql = f"""
        INSERT INTO verification_gate_transitions 
        (task_id, from_gate, to_gate, passed, evidence, verified_by, transitioned_at)
        VALUES (
            {_escape_value(task_id)},
            {_escape_value(result.from_stage)},
            {_escape_value(new_stage)},
            TRUE,
            {_escape_value(evidence_json)},
            {_escape_value(verified_by or 'system')},
            {_escape_value(now)}
        )
    """
    _execute_sql(log_sql)
    
    return result


def get_task_stage(task_id: str) -> Optional[str]:
    """Get the current stage of a task."""
    sql = f"SELECT stage FROM governance_tasks WHERE id = {_escape_value(task_id)}"
    rows = _execute_sql(sql)
    if rows:
        return rows[0].get("stage") or "discovered"
    return None


def get_valid_next_stages(task_id: str) -> List[str]:
    """Get all valid stages a task can transition to from its current stage."""
    current = get_task_stage(task_id)
    if not current:
        return []
    
    sql = f"""
        SELECT to_stage, requires_evidence 
        FROM stage_transitions 
        WHERE from_stage = {_escape_value(current)}
    """
    rows = _execute_sql(sql)
    return [r["to_stage"] for r in rows]


def get_stage_history(task_id: str) -> List[Dict]:
    """Get the transition history for a task."""
    sql = f"""
        SELECT from_gate, to_gate, passed, evidence, verified_by, transitioned_at
        FROM verification_gate_transitions
        WHERE task_id = {_escape_value(task_id)}
        ORDER BY transitioned_at ASC
    """
    return _execute_sql(sql)


def can_complete_task(task_id: str) -> Tuple[bool, str]:
    """
    Check if a task can be marked complete.
    
    A task can only complete if:
    1. It's at the 'endpoint_verified' stage
    2. The endpoint_verified flag is True
    
    Returns:
        (can_complete, reason)
    """
    sql = f"""
        SELECT stage, endpoint_verified, verification_chain, gate_evidence
        FROM governance_tasks
        WHERE id = {_escape_value(task_id)}
    """
    rows = _execute_sql(sql)
    
    if not rows:
        return False, "Task not found"
    
    task = rows[0]
    stage = task.get("stage") or "discovered"
    endpoint_verified = task.get("endpoint_verified", False)
    
    # Must be at endpoint_verified stage
    if stage != "endpoint_verified":
        return False, f"Task is at stage '{stage}', must be at 'endpoint_verified' to complete"
    
    # Endpoint must be verified
    if not endpoint_verified:
        return False, "Endpoint verification has not passed"
    
    return True, "Task ready for completion"


# Mapping from status to stage for backwards compatibility
STATUS_TO_STAGE_MAP = {
    "pending": "discovered",
    "waiting_approval": "plan_submitted",
    "approved": "plan_approved",
    "in_progress": "in_progress",
    "completed": "complete",
    "failed": None,  # Failed tasks don't have a stage
}


def sync_status_to_stage(task_id: str, status: str) -> Optional[str]:
    """
    For backwards compatibility, map a status update to a stage.
    
    This allows existing code that uses status to work with the new
    stage-based system.
    """
    stage = STATUS_TO_STAGE_MAP.get(status)
    if stage:
        # Try to transition, but don't fail if invalid
        result = validate_stage_transition(task_id, stage)
        if result.allowed:
            transition_stage(task_id, stage, evidence=f"Auto-synced from status: {status}")
    return stage
