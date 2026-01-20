"""
JUGGERNAUT Human-in-the-Loop Approval Queue

Enables human approval for sensitive tasks.
"""

from typing import Dict, List, Any, Optional
from core.database import query_db, log_execution


# ============================================================
# APPROVAL QUEUE FUNCTIONS
# ============================================================

def submit_for_approval(task_id: str, approval_reason: str = None) -> bool:
    """
    Submit a task for human approval.
    
    Task must have requires_approval=TRUE and be in pending/in_progress status.
    
    Args:
        task_id: Task UUID to submit
        approval_reason: Optional reason why approval is needed
    
    Returns:
        True if task was submitted, False if not eligible
    """
    reason_sql = f"'{approval_reason.replace(chr(39), chr(39)*2)}'" if approval_reason else "NULL"
    sql = f"SELECT submit_for_approval('{task_id}'::uuid, {reason_sql});"
    
    try:
        result = query_db(sql)
        success = result.get("rows", [{}])[0].get("submit_for_approval", False)
        
        if success:
            log_execution(
                worker_id="APPROVAL_QUEUE",
                action="approval.submit",
                message=f"Task {task_id} submitted for approval",
                level="info",
                task_id=task_id,
                input_data={"approval_reason": approval_reason}
            )
        
        return success
    except Exception as e:
        log_execution(
            worker_id="APPROVAL_QUEUE",
            action="approval.submit.error",
            message=f"Failed to submit task {task_id} for approval: {e}",
            level="error",
            task_id=task_id,
            error_data={"error": str(e)}
        )
        return False


def approve_task(task_id: str, approved_by: str = "josh") -> bool:
    """
    Approve a task in the approval queue.
    
    Moves task from waiting_approval back to pending so it can be executed.
    
    Args:
        task_id: Task UUID to approve
        approved_by: Who approved the task
    
    Returns:
        True if task was approved, False if not in waiting_approval status
    """
    approver_sql = f"'{approved_by.replace(chr(39), chr(39)*2)}'"
    sql = f"SELECT approve_task('{task_id}'::uuid, {approver_sql});"
    
    try:
        result = query_db(sql)
        success = result.get("rows", [{}])[0].get("approve_task", False)
        
        if success:
            log_execution(
                worker_id="APPROVAL_QUEUE",
                action="approval.approve",
                message=f"Task {task_id} approved by {approved_by}",
                level="info",
                task_id=task_id,
                output_data={"approved_by": approved_by}
            )
        
        return success
    except Exception as e:
        log_execution(
            worker_id="APPROVAL_QUEUE",
            action="approval.approve.error",
            message=f"Failed to approve task {task_id}: {e}",
            level="error",
            task_id=task_id,
            error_data={"error": str(e)}
        )
        return False


def reject_task(task_id: str, rejected_by: str = "josh", reason: str = None) -> bool:
    """
    Reject a task in the approval queue.
    
    Moves task from waiting_approval to failed status.
    
    Args:
        task_id: Task UUID to reject
        rejected_by: Who rejected the task
        reason: Optional reason for rejection
    
    Returns:
        True if task was rejected, False if not in waiting_approval status
    """
    rejecter_sql = f"'{rejected_by.replace(chr(39), chr(39)*2)}'"
    reason_sql = f"'{reason.replace(chr(39), chr(39)*2)}'" if reason else "NULL"
    sql = f"SELECT reject_task('{task_id}'::uuid, {rejecter_sql}, {reason_sql});"
    
    try:
        result = query_db(sql)
        success = result.get("rows", [{}])[0].get("reject_task", False)
        
        if success:
            log_execution(
                worker_id="APPROVAL_QUEUE",
                action="approval.reject",
                message=f"Task {task_id} rejected by {rejected_by}",
                level="warn",
                task_id=task_id,
                output_data={"rejected_by": rejected_by, "reason": reason}
            )
        
        return success
    except Exception as e:
        log_execution(
            worker_id="APPROVAL_QUEUE",
            action="approval.reject.error",
            message=f"Failed to reject task {task_id}: {e}",
            level="error",
            task_id=task_id,
            error_data={"error": str(e)}
        )
        return False


def list_pending_approvals() -> List[Dict[str, Any]]:
    """
    Get all tasks waiting for human approval.
    
    Returns:
        List of tasks with id, title, description, priority, task_type,
        approval_reason, created_by, created_at, estimated_cost_cents
    """
    sql = "SELECT * FROM list_pending_approvals();"
    
    try:
        result = query_db(sql)
        return result.get("rows", [])
    except Exception as e:
        log_execution(
            worker_id="APPROVAL_QUEUE",
            action="approval.list.error",
            message=f"Failed to list pending approvals: {e}",
            level="error",
            error_data={"error": str(e)}
        )
        return []


def get_approval_stats() -> Dict[str, Any]:
    """
    Get statistics about the approval queue.
    
    Returns:
        Dict with pending_count, approved_today, rejected_today
    """
    try:
        # Count pending
        pending_sql = """
            SELECT COUNT(*) as count 
            FROM governance_tasks 
            WHERE status = 'waiting_approval'
        """
        
        # Count approved today
        approved_sql = """
            SELECT COUNT(*) as count 
            FROM governance_tasks 
            WHERE metadata->>'approved_at' IS NOT NULL
            AND (metadata->>'approved_at')::timestamp >= CURRENT_DATE
        """
        
        # Count rejected today
        rejected_sql = """
            SELECT COUNT(*) as count 
            FROM governance_tasks 
            WHERE metadata->>'rejected_at' IS NOT NULL
            AND (metadata->>'rejected_at')::timestamp >= CURRENT_DATE
        """
        
        pending = query_db(pending_sql).get("rows", [{}])[0].get("count", 0)
        approved = query_db(approved_sql).get("rows", [{}])[0].get("count", 0)
        rejected = query_db(rejected_sql).get("rows", [{}])[0].get("count", 0)
        
        return {
            "pending_count": int(pending),
            "approved_today": int(approved),
            "rejected_today": int(rejected)
        }
    except Exception as e:
        return {"pending_count": 0, "approved_today": 0, "rejected_today": 0, "error": str(e)}
