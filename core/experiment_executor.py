from datetime import datetime, timezone
from typing import Any, Callable, Dict


def progress_experiments(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
) -> Dict[str, Any]:
    try:
        res = execute_sql(
            """
            SELECT id, name, status, current_iteration, budget_spent
            FROM experiments
            WHERE status = 'running'
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 50
            """
        )
        experiments = res.get("rows", []) or []
    except Exception as e:
        return {"success": False, "error": str(e)}

    if not experiments:
        try:
            log_action(
                "experiment.no_active_experiments",
                "No running experiments to progress",
                level="info",
                output_data={"running_experiments": 0},
            )
        except Exception:
            pass

        return {"success": True, "running_experiments": 0, "experiments_progressed": 0}

    try:
        log_action(
            "experiment.progress_stub",
            "Experiment progression stub: running experiments detected but no handlers are configured",
            level="warn",
            output_data={
                "running_experiments": len(experiments),
                "example": experiments[0] if experiments else None,
            },
        )
    except Exception:
        pass

    return {
        "success": True,
        "running_experiments": len(experiments),
        "experiments_progressed": 0,
    }
