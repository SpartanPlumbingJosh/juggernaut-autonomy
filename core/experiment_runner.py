from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Callable, Dict, Optional, Set


def _escape_sql_string(value: Any) -> str:
    return str(value or "").replace("'", "''")


def _get_table_columns(execute_sql: Callable[[str], Dict[str, Any]], table_name: str) -> Set[str]:
    try:
        res = execute_sql(
            f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = '{_escape_sql_string(table_name)}'
            """
        )
        rows = res.get("rows", []) or []
        return {str(r.get("column_name") or "") for r in rows}
    except Exception:
        return set()


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

    config_json = json.dumps(config).replace("'", "''")
    title_esc = _escape_sql_string(title)
    hyp_esc = _escape_sql_string(hypothesis)
    idea_id = str(idea.get("id") or "").strip()

    try:
        cols = _get_table_columns(execute_sql, "experiments")

        insert_cols = []
        insert_vals = []

        if "id" in cols:
            insert_cols.append("id")
            insert_vals.append("gen_random_uuid()")
        if "name" in cols:
            insert_cols.append("name")
            insert_vals.append(f"'{title_esc}'")
        if "description" in cols:
            insert_cols.append("description")
            insert_vals.append("NULL")
        if "experiment_type" in cols:
            insert_cols.append("experiment_type")
            insert_vals.append("'revenue'")
        if "status" in cols:
            insert_cols.append("status")
            insert_vals.append("'draft'")
        if "hypothesis" in cols:
            insert_cols.append("hypothesis")
            insert_vals.append(f"'{hyp_esc}'")
        if "success_criteria" in cols:
            insert_cols.append("success_criteria")
            insert_vals.append("'{\"success\": \"1 paying customer within 14 days\"}'::jsonb")
        if "failure_criteria" in cols:
            insert_cols.append("failure_criteria")
            insert_vals.append("NULL")
        if "budget_limit" in cols:
            insert_cols.append("budget_limit")
            insert_vals.append(str(float(budget)))
        if "budget_spent" in cols:
            insert_cols.append("budget_spent")
            insert_vals.append("0")
        if "max_iterations" in cols:
            insert_cols.append("max_iterations")
            insert_vals.append("10")
        if "current_iteration" in cols:
            insert_cols.append("current_iteration")
            insert_vals.append("0")
        if "scheduled_end" in cols:
            insert_cols.append("scheduled_end")
            insert_vals.append(f"'{end.isoformat()}'")
        if "owner_worker" in cols:
            insert_cols.append("owner_worker")
            insert_vals.append("'EXECUTOR'")
        if "tags" in cols:
            insert_cols.append("tags")
            insert_vals.append("'[]'::jsonb")
        if "config" in cols:
            insert_cols.append("config")
            insert_vals.append(f"'{config_json}'::jsonb")
        if "created_by" in cols:
            insert_cols.append("created_by")
            insert_vals.append("'SYSTEM'")
        if "created_at" in cols:
            insert_cols.append("created_at")
            insert_vals.append("NOW()")
        if "updated_at" in cols:
            insert_cols.append("updated_at")
            insert_vals.append("NOW()")
        if "idea_id" in cols and idea_id:
            insert_cols.append("idea_id")
            insert_vals.append(f"'{_escape_sql_string(idea_id)}'")

        if not insert_cols:
            return {"success": False, "error": "experiments table schema not available"}

        returning = " RETURNING id" if "id" in cols else ""

        res = execute_sql(
            f"""
            INSERT INTO experiments ({', '.join(insert_cols)})
            VALUES ({', '.join(insert_vals)})
            {returning}
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
