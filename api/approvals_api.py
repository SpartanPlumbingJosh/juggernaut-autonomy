import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Query

from api.dashboard import query_db, validate_uuid


_INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET")


def _require_internal_auth(authorization: Optional[str], internal_secret: Optional[str]) -> None:
    if not _INTERNAL_API_SECRET:
        raise HTTPException(status_code=500, detail="INTERNAL_API_SECRET not configured")

    token = ""
    if internal_secret:
        token = str(internal_secret).strip()
    elif authorization:
        token = authorization.replace("Bearer ", "")

    if not token or not hmac.compare_digest(token, _INTERNAL_API_SECRET):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _sql_escape(value: str) -> str:
    return str(value).replace("'", "''")


def _sql_quote(value: Optional[str]) -> str:
    if value is None:
        return "NULL"
    return f"'{_sql_escape(value)}'"


def _sql_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False)
    return f"'{_sql_escape(encoded)}'"


router = APIRouter(prefix="/api/approvals")


@router.get("")
def approvals_list(
    authorization: Optional[str] = Header(default=None),
    x_internal_api_secret: Optional[str] = Header(default=None, alias="X-Internal-Api-Secret"),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    _require_internal_auth(authorization, x_internal_api_secret)

    safe_limit = max(1, min(int(limit), 200))

    sql = f"""
        SELECT
            t.id,
            t.task_type,
            t.title,
            t.description,
            t.status::text as status,
            t.priority::text as priority,
            t.requires_approval,
            t.assigned_worker,
            t.created_at,
            t.updated_at,
            (
                SELECT a.decision
                FROM approvals a
                WHERE a.task_id = t.id
                ORDER BY a.created_at DESC
                LIMIT 1
            ) as approval_decision,
            (
                SELECT a.decided_by
                FROM approvals a
                WHERE a.task_id = t.id
                ORDER BY a.created_at DESC
                LIMIT 1
            ) as approval_decided_by,
            (
                SELECT a.decided_at
                FROM approvals a
                WHERE a.task_id = t.id
                ORDER BY a.created_at DESC
                LIMIT 1
            ) as approval_decided_at,
            (
                SELECT a.decision_notes
                FROM approvals a
                WHERE a.task_id = t.id
                ORDER BY a.created_at DESC
                LIMIT 1
            ) as approval_notes
        FROM governance_tasks t
        WHERE t.status = 'waiting_approval'
        ORDER BY t.created_at ASC
        LIMIT {safe_limit}
    """

    rows = query_db(sql).get("rows", [])
    return {"success": True, "tasks": rows, "count": len(rows)}


@router.post("/{task_id}/approve")
def approvals_approve(
    task_id: str,
    authorization: Optional[str] = Header(default=None),
    x_internal_api_secret: Optional[str] = Header(default=None, alias="X-Internal-Api-Secret"),
    body: Dict[str, Any] = Body(default=None),
) -> Dict[str, Any]:
    _require_internal_auth(authorization, x_internal_api_secret)
    body = body or {}

    if not validate_uuid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task_id")

    approved_by = str(body.get("approved_by") or body.get("approvedBy") or "josh")
    notes = body.get("notes")

    task_rows = query_db(
        f"""
        SELECT id, status, requires_approval
        FROM governance_tasks
        WHERE id = {_sql_quote(task_id)}::uuid
        LIMIT 1
        """
    ).get("rows", [])

    if not task_rows:
        raise HTTPException(status_code=404, detail="Task not found")

    status = (task_rows[0] or {}).get("status")
    if status != "waiting_approval":
        raise HTTPException(status_code=409, detail=f"Task status is '{status}', not waiting_approval")

    now_iso = datetime.now(timezone.utc).isoformat()

    approval_update = f"""
        UPDATE approvals SET
            decision = 'approved',
            decided_by = {_sql_quote(approved_by)},
            decided_at = NOW(),
            decision_notes = {_sql_quote(str(notes)) if notes is not None else 'NULL'}
        WHERE id = (
            SELECT id FROM approvals
            WHERE task_id = {_sql_quote(task_id)}::uuid
            ORDER BY created_at DESC
            LIMIT 1
        )
        RETURNING id
    """

    updated = False
    try:
        update_res = query_db(approval_update)
        updated = bool(update_res.get("rowCount"))
    except Exception:
        updated = False

    if not updated:
        approval_insert = f"""
            INSERT INTO approvals (
                task_id,
                worker_id,
                action_type,
                action_description,
                action_data,
                risk_level,
                estimated_impact,
                decision,
                decided_by,
                decided_at,
                decision_notes,
                created_at
            ) VALUES (
                {_sql_quote(task_id)}::uuid,
                'DASHBOARD_API',
                'task_execution',
                'Manual approval via /api/approvals',
                {_sql_json({"source": "api", "task_id": task_id})},
                'medium',
                'Manual approval via dashboard API',
                'approved',
                {_sql_quote(approved_by)},
                NOW(),
                {_sql_quote(str(notes)) if notes is not None else 'NULL'},
                NOW()
            )
        """

        try:
            query_db(approval_insert)
        except Exception:
            pass

    update_sql = f"""
        UPDATE governance_tasks
        SET
            status = 'pending',
            assigned_worker = NULL,
            updated_at = NOW(),
            requires_approval = TRUE,
            metadata = COALESCE(metadata, '{{}}'::jsonb) || {_sql_json({"approved_by": approved_by, "approved_at": now_iso, "approval_notes": notes})}::jsonb
        WHERE id = {_sql_quote(task_id)}::uuid
          AND status = 'waiting_approval'
        RETURNING id
    """

    rows = query_db(update_sql).get("rows", [])
    if not rows:
        raise HTTPException(status_code=409, detail="Task was not in waiting_approval")

    try:
        query_db(
            f"""
            INSERT INTO execution_logs (worker_id, action, message, level, source, created_at, task_id, output_data)
            VALUES (
                'DASHBOARD_API',
                'approval.approve',
                {_sql_quote(f"Task approved by {approved_by}")},
                'info',
                'dashboard_api',
                NOW(),
                {_sql_quote(task_id)}::uuid,
                {_sql_json({"approved_by": approved_by, "notes": notes})}
            )
            """
        )
    except Exception:
        pass

    return {"success": True, "task_id": task_id, "status": "pending"}


@router.post("/{task_id}/reject")
def approvals_reject(
    task_id: str,
    authorization: Optional[str] = Header(default=None),
    x_internal_api_secret: Optional[str] = Header(default=None, alias="X-Internal-Api-Secret"),
    body: Dict[str, Any] = Body(default=None),
) -> Dict[str, Any]:
    _require_internal_auth(authorization, x_internal_api_secret)
    body = body or {}

    if not validate_uuid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task_id")

    rejected_by = str(body.get("rejected_by") or body.get("rejectedBy") or "josh")
    reason = body.get("reason")

    task_rows = query_db(
        f"""
        SELECT id, status
        FROM governance_tasks
        WHERE id = {_sql_quote(task_id)}::uuid
        LIMIT 1
        """
    ).get("rows", [])

    if not task_rows:
        raise HTTPException(status_code=404, detail="Task not found")

    status = (task_rows[0] or {}).get("status")
    if status != "waiting_approval":
        raise HTTPException(status_code=409, detail=f"Task status is '{status}', not waiting_approval")

    now_iso = datetime.now(timezone.utc).isoformat()

    approval_update = f"""
        UPDATE approvals SET
            decision = 'rejected',
            decided_by = {_sql_quote(rejected_by)},
            decided_at = NOW(),
            decision_notes = {_sql_quote(str(reason)) if reason is not None else 'NULL'}
        WHERE id = (
            SELECT id FROM approvals
            WHERE task_id = {_sql_quote(task_id)}::uuid
            ORDER BY created_at DESC
            LIMIT 1
        )
        RETURNING id
    """

    updated = False
    try:
        update_res = query_db(approval_update)
        updated = bool(update_res.get("rowCount"))
    except Exception:
        updated = False

    if not updated:
        approval_insert = f"""
            INSERT INTO approvals (
                task_id,
                worker_id,
                action_type,
                action_description,
                action_data,
                risk_level,
                estimated_impact,
                decision,
                decided_by,
                decided_at,
                decision_notes,
                created_at
            ) VALUES (
                {_sql_quote(task_id)}::uuid,
                'DASHBOARD_API',
                'task_execution',
                'Manual rejection via /api/approvals',
                {_sql_json({"source": "api", "task_id": task_id})},
                'medium',
                'Manual rejection via dashboard API',
                'rejected',
                {_sql_quote(rejected_by)},
                NOW(),
                {_sql_quote(str(reason)) if reason is not None else 'NULL'},
                NOW()
            )
        """

        try:
            query_db(approval_insert)
        except Exception:
            pass

    update_sql = f"""
        UPDATE governance_tasks
        SET
            status = 'cancelled',
            assigned_worker = NULL,
            updated_at = NOW(),
            metadata = COALESCE(metadata, '{{}}'::jsonb) || {_sql_json({"rejected_by": rejected_by, "rejected_at": now_iso, "rejection_reason": reason})}::jsonb
        WHERE id = {_sql_quote(task_id)}::uuid
          AND status = 'waiting_approval'
        RETURNING id
    """

    rows = query_db(update_sql).get("rows", [])
    if not rows:
        raise HTTPException(status_code=409, detail="Task was not in waiting_approval")

    try:
        query_db(
            f"""
            INSERT INTO execution_logs (worker_id, action, message, level, source, created_at, task_id, output_data)
            VALUES (
                'DASHBOARD_API',
                'approval.reject',
                {_sql_quote(f"Task rejected by {rejected_by}")},
                'warn',
                'dashboard_api',
                NOW(),
                {_sql_quote(task_id)}::uuid,
                {_sql_json({"rejected_by": rejected_by, "reason": reason})}
            )
            """
        )
    except Exception:
        pass

    return {"success": True, "task_id": task_id, "status": "cancelled"}
