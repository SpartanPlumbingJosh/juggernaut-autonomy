"""
Task Completion Validation

Enforces evidence requirements for task completion.
Prevents bulk-marking tasks complete without verification.
"""

from typing import Dict, Optional, Tuple

# Task types that require completion evidence
EVIDENCE_REQUIRED_TYPES = {
    "code",
    "deploy",
    "test",
    "review",
    "migration"
}

# Examples of valid evidence by type
EVIDENCE_EXAMPLES = {
    "code": "Commit SHA | PR # | File paths modified",
    "deploy": "Deployment ID | Service URL | Health check result",
    "test": "Test run ID | Pass/fail count | Coverage %",
    "review": "Review comment ID | Approval status",
    "migration": "Migration ID | Rows affected | Rollback plan"
}


def validate_completion_evidence(
    task_type: str,
    evidence: Optional[str]
) -> Tuple[bool, Optional[str]]:
    """
    Validate that completion evidence is provided for task types that require it.
    
    Args:
        task_type: The type of task being completed
        evidence: The completion evidence string
    
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if evidence is valid or not required
        - error_message: None if valid, otherwise descriptive error
    """
    # Normalize task type
    normalized_type = task_type.lower().strip() if task_type else ""
    
    # Check if this task type requires evidence
    if normalized_type not in EVIDENCE_REQUIRED_TYPES:
        return (True, None)  # No evidence required
    
    # Evidence is required - validate it
    if not evidence or not evidence.strip():
        example = EVIDENCE_EXAMPLES.get(normalized_type, "Specific evidence of completion")
        return (
            False,
            f"Task type '{normalized_type}' requires completion evidence. "
            f"Example: {example}"
        )
    
    # Basic validation - evidence should be meaningful
    if len(evidence.strip()) < 10:
        return (
            False,
            "Completion evidence is too short. Please provide meaningful evidence "
            "(at least 10 characters) such as commit SHA, log ID, or test results."
        )
    
    return (True, None)


def complete_task_with_evidence(
    task_id: str,
    task_type: str,
    evidence: str,
    result: Dict = None
) -> Tuple[bool, Optional[str]]:
    """
    Complete a task with required evidence validation.
    
    Args:
        task_id: UUID of the task to complete
        task_type: Type of the task
        evidence: Completion evidence string
        result: Optional result dict
    
    Returns:
        Tuple of (success, error_message)
    """
    from core.database import query_db
    import json
    
    # Validate evidence
    is_valid, error = validate_completion_evidence(task_type, evidence)
    if not is_valid:
        return (False, error)
    
    # Escape values for SQL
    evidence_esc = evidence.replace("'", "''") if evidence else None
    task_id_esc = task_id.replace("'", "''")
    
    # Build result JSON if provided
    result_sql = "NULL"
    if result:
        result_sql = "'" + json.dumps(result).replace("'", "''") + "'"
    
    # Update task with evidence
    sql = f"""
    UPDATE governance_tasks 
    SET status = 'completed',
        completed_at = NOW(),
        completion_evidence = '{evidence_esc}',
        result = {result_sql}
    WHERE id = '{task_id_esc}'
      AND status = 'in_progress'
    """
    
    try:
        db_result = query_db(sql)
        if db_result.get("rowCount", 0) > 0:
            return (True, None)
        else:
            return (False, "Task not found or not in 'in_progress' status")
    except Exception as e:
        return (False, f"Database error: {e}")


def get_evidence_requirements() -> Dict[str, str]:
    """
    Get the list of task types that require evidence and examples.
    
    Returns:
        Dict mapping task type to example evidence
    """
    return EVIDENCE_EXAMPLES.copy()
