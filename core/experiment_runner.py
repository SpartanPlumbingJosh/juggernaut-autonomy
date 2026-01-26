from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional


def create_experiment_from_idea(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
    idea: Dict[str, Any],
    budget: float,
) -> Dict[str, Any]:
    title = str(idea.get("title") or "Revenue Experiment")
    hypothesis = str(idea.get("hypothesis") or "Prove this idea can generate revenue")

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=14)

    config = {
        "idea": {
            "title": title,
            "description": idea.get("description"),
            "estimates": idea.get("estimates"),
        },
        "created_by": "experiment_runner",
    }

    config_json = str(config).replace("'", "''")
    title_esc = title.replace("'", "''")
    hyp_esc = hypothesis.replace("'", "''")

    try:
        res = execute_sql(
            f"""
            INSERT INTO experiments (
                id, name, description, experiment_type, status,
                hypothesis, success_criteria, failure_criteria,
                budget_limit, budget_spent, max_iterations, current_iteration,
                scheduled_end, owner_worker, tags, config, created_by
            ) VALUES (
                gen_random_uuid(),
                '{title_esc}',
                NULL,
                'revenue',
                'running',
                '{hyp_esc}',
                '{{"success": "1 paying customer within 14 days"}}'::jsonb,
                NULL,
                {float(budget)},
                0,
                10,
                1,
                '{end.isoformat()}',
                'EXECUTOR',
                '[]'::jsonb,
                '{config_json}'::jsonb,
                'SYSTEM'
            )
            RETURNING id
            """
        )
        experiment_id = (res.get("rows") or [{}])[0].get("id")
    except Exception as e:
        return {"success": False, "error": str(e)}

    try:
        log_action(
            "experiment.created",
            f"Created experiment from idea: {title}",
            level="info",
            output_data={"experiment_id": experiment_id, "budget": budget},
        )
    except Exception:
        pass

    return {"success": True, "experiment_id": experiment_id}


def link_experiment_to_idea(
    execute_sql: Callable[[str], Dict[str, Any]],
    experiment_id: str,
    idea_id: str,
) -> None:
    try:
        execute_sql(
            f"""
            UPDATE experiments
            SET idea_id = '{str(idea_id).replace("'", "''")}'
            WHERE id = '{str(experiment_id).replace("'", "''")}'
            """
        )
    except Exception:
        pass
