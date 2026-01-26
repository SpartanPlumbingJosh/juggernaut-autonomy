import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


def _parse_money_target(title: str) -> Optional[float]:
    t = (title or "").lower()
    if "first $100" in t:
        return 100.0
    if "$5k" in t or "5k" in t or "$5000" in t:
        return 5000.0
    return None


def update_goal_progress(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
) -> Dict[str, Any]:
    try:
        goals_res = execute_sql(
            """
            SELECT id, title, status, progress, success_criteria, deadline
            FROM goals
            WHERE status IN ('pending', 'assigned', 'in_progress')
            ORDER BY created_at ASC
            LIMIT 200
            """
        )
        goals = goals_res.get("rows", []) or []
    except Exception as e:
        return {"success": False, "error": str(e)}

    updated = 0
    skipped = 0

    revenue_total = None
    try:
        rev_res = execute_sql(
            """
            SELECT COALESCE(SUM(amount), 0)::float as total
            FROM revenue_events
            WHERE created_at >= date_trunc('month', NOW())
            """
        )
        revenue_total = float((rev_res.get("rows") or [{}])[0].get("total") or 0.0)
    except Exception:
        revenue_total = None

    for g in goals:
        goal_id = str(g.get("id") or "")
        title = str(g.get("title") or "")
        if not goal_id:
            continue

        target = _parse_money_target(title)
        progress = None

        if target is not None and revenue_total is not None and target > 0:
            progress = max(0.0, min(100.0, (revenue_total / target) * 100.0))
        else:
            skipped += 1
            continue

        try:
            execute_sql(
                f"""
                UPDATE goals
                SET progress = {float(progress)},
                    updated_at = NOW()
                WHERE id = '{goal_id.replace("'", "''")}'
                """
            )
            updated += 1
            try:
                log_action(
                    "goal.progress_updated",
                    f"{title} now at {progress:.1f}%",
                    level="info",
                    output_data={"goal_id": goal_id, "progress": progress},
                )
            except Exception:
                pass
        except Exception:
            skipped += 1

    return {
        "success": True,
        "goals_checked": len(goals),
        "goals_updated": updated,
        "goals_skipped": skipped,
        "revenue_total_month": revenue_total,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
