import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List


def apply_recent_learnings(
    execute_sql: Callable[[str], Dict[str, Any]],
    escape_value_func: Callable[[Any], str],
    log_action: Callable[..., Any],
) -> Dict[str, Any]:
    try:
        res = execute_sql(
            """
            SELECT id, category, summary, details, created_at
            FROM learnings
            WHERE created_at > NOW() - INTERVAL '7 days'
            ORDER BY created_at DESC
            LIMIT 200
            """
        )
        rows = res.get("rows", []) or []
    except Exception as e:
        return {"success": False, "error": str(e)}

    created = 0
    considered = 0

    for row in rows:
        considered += 1
        category = str(row.get("category") or "")
        summary = str(row.get("summary") or "")
        learning_id = str(row.get("id") or "")
        if not summary:
            continue

        if category not in ("failure_pattern", "optimization_opportunity"):
            continue

        task_title = (
            f"Fix: {summary[:120]}" if category == "failure_pattern" else f"Improve: {summary[:120]}"
        )
        dedupe_key = f"learning:{category}:{learning_id}"

        payload = {
            "category": "self_improvement",
            "dedupe_key": dedupe_key,
            "success_criteria": {"deliverable": "change", "includes": ["root cause", "fix", "verification"]},
            "learning_id": learning_id,
            "learning_category": category,
            "learning_summary": summary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        title_escaped = task_title.replace("'", "''")
        key_escaped = dedupe_key.replace("'", "''")
        payload_escaped = json.dumps(payload).replace("'", "''")

        try:
            existing = execute_sql(
                f"""
                SELECT id
                FROM governance_tasks
                WHERE (payload->>'dedupe_key' = '{key_escaped}'
                       OR title = '{title_escaped}')
                  AND created_at > NOW() - INTERVAL '72 hours'
                LIMIT 1
                """
            )
            if existing.get("rows"):
                continue
        except Exception:
            pass

        try:
            execute_sql(
                f"""
                INSERT INTO governance_tasks (id, task_type, title, description, priority, status, payload, created_by)
                VALUES (gen_random_uuid(), 'analysis', '{title_escaped}', 'Apply a recent learning by turning it into an actionable fix.', 'medium', 'pending', '{payload_escaped}', 'learning')
                """
            )
            created += 1
        except Exception:
            continue

    try:
        log_action(
            "learning.applied",
            f"Applied {considered} learnings, created {created} tasks",
            level="info",
            output_data={"learnings_considered": considered, "tasks_created": created},
        )
    except Exception:
        pass

    return {
        "success": True,
        "learnings_considered": considered,
        "tasks_created": created,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
