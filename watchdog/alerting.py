import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_worker_id() -> str:
    return os.getenv("WORKER_ID", "WATCHDOG")


def create_fix_task(
    *,
    title: str,
    description: str,
    priority: str,
    service: str,
    issue_key: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a fix task in governance_tasks.

    Uses a simple dedupe mechanism via payload.issue_key.
    """

    try:
        existing = query_db(
            """
            SELECT id
            FROM governance_tasks
            WHERE task_type = 'fix'
              AND payload->>'issue_key' = $1
              AND created_at > NOW() - INTERVAL '24 hours'
            LIMIT 1
            """,
            [issue_key],
        )
        if (existing.get("rows") or []):
            return {"success": True, "skipped_duplicate": True, "issue_key": issue_key}
    except Exception:
        pass

    payload = {
        "issue_key": issue_key,
        "service": service,
        "metadata": metadata or {},
        "detected_by": _env_worker_id(),
        "detected_at": _now_iso(),
    }

    task_id = str(uuid.uuid4())

    try:
        query_db(
            """
            INSERT INTO governance_tasks (
                id, task_type, title, description, priority,
                status, payload, created_by, created_at
            ) VALUES (
                $1, 'fix', $2, $3, $4,
                'pending', $5, $6, NOW()
            )
            """,
            [
                task_id,
                title,
                description,
                priority,
                json.dumps(payload),
                "watchdog",
            ],
        )
        return {"success": True, "task_id": task_id, "issue_key": issue_key}
    except Exception as e:
        return {"success": False, "error": str(e), "issue_key": issue_key}
