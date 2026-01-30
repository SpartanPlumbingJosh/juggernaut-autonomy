import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict


def generate_executive_report(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    report_date = now.date().isoformat()

    tasks_completed = 0
    tasks_failed = 0
    errors_24h = 0
    workers_active = 0
    running_experiments = 0
    goals_active = 0

    try:
        t = execute_sql(
            """
            SELECT
              SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)::int as completed,
              SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END)::int as failed
            FROM governance_tasks
            WHERE updated_at > NOW() - INTERVAL '24 hours'
            """
        )
        row = (t.get("rows") or [{}])[0]
        tasks_completed = int(row.get("completed") or 0)
        tasks_failed = int(row.get("failed") or 0)
    except Exception:
        pass

    try:
        e = execute_sql(
            """
            SELECT COUNT(*)::int as c
            FROM execution_logs
            WHERE created_at > NOW() - INTERVAL '24 hours'
              AND level IN ('error', 'critical')
            """
        )
        errors_24h = int((e.get("rows") or [{}])[0].get("c") or 0)
    except Exception:
        pass

    try:
        w = execute_sql(
            """
            SELECT COUNT(*)::int as c
            FROM worker_registry
            WHERE status IN ('active', 'busy', 'degraded')
              AND last_heartbeat > NOW() - INTERVAL '10 minutes'
            """
        )
        workers_active = int((w.get("rows") or [{}])[0].get("c") or 0)
    except Exception:
        pass

    try:
        ex = execute_sql("SELECT COUNT(*)::int as c FROM experiments WHERE status = 'running'")
        running_experiments = int((ex.get("rows") or [{}])[0].get("c") or 0)
    except Exception:
        pass

    try:
        g = execute_sql("SELECT COUNT(*)::int as c FROM goals WHERE status IN ('pending','assigned','in_progress')")
        goals_active = int((g.get("rows") or [{}])[0].get("c") or 0)
    except Exception:
        pass

    details = {
        "tasks_completed_24h": tasks_completed,
        "tasks_failed_24h": tasks_failed,
        "errors_24h": errors_24h,
        "workers_active_10m": workers_active,
        "running_experiments": running_experiments,
        "active_goals": goals_active,
        "generated_at": now.isoformat(),
    }

    try:
        details_json = json.dumps(details).replace("'", "''")
        execute_sql(
            f"""
            INSERT INTO audit_reports (report_type, report_date, details)
            VALUES ('executive_daily', '{report_date}', '{details_json}'::jsonb)
            """
        )
    except Exception:
        pass

    try:
        log_action(
            "executive.report_generated",
            f"Daily report for {report_date}",
            level="info",
            output_data=details,
        )
    except Exception:
        pass

    return {"success": True, "report_date": report_date, "details": details}
