import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List


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

    created_tasks = 0
    progressed = 0
    skipped = 0

    for exp in experiments:
        exp_id = str(exp.get("id") or "")
        exp_name = str(exp.get("name") or "")
        if not exp_id:
            continue

        try:
            log_action(
                "experiment.progress_check",
                f"Experiment progression check: {exp_name}",
                level="debug",
                output_data={"experiment_id": exp_id, "experiment_name": exp_name},
            )
        except Exception:
            pass

        if exp_name.strip().lower().startswith("revenue-exp-01") or "domain flip" in exp_name.lower():
            task_title = "Research: Find domains under $20 for flipping"
            dedupe_key = f"experiment:{exp_id}:domain_flip:find_candidates"
            now_iso = datetime.now(timezone.utc).isoformat()
            payload = {
                "category": "revenue",
                "experiment_id": exp_id,
                "experiment_name": exp_name,
                "dedupe_key": dedupe_key,
                "success_criteria": {
                    "deliverable": "shortlist",
                    "includes": ["domain", "price", "why it might flip", "next step"],
                },
                "generated_at": now_iso,
                "source": "experiment_progression",
                "hint": {
                    "provider": "expired_domains",
                    "max_price_usd": 20,
                    "note": "If you have an ExpiredDomains.net (or similar) API key configured, use it. Otherwise do a web-based scan and produce a shortlist.",
                },
            }

            title_escaped = task_title.replace("'", "''")
            dedupe_key_escaped = dedupe_key.replace("'", "''")
            payload_escaped = json.dumps(payload).replace("'", "''")

            try:
                existing = execute_sql(
                    f"""
                    SELECT id
                    FROM governance_tasks
                    WHERE payload->>'dedupe_key' = '{dedupe_key_escaped}'
                      AND status IN ('pending', 'in_progress', 'assigned')
                      AND created_at > NOW() - INTERVAL '24 hours'
                    LIMIT 1
                    """
                )
                if existing.get("rows"):
                    skipped += 1
                    continue
            except Exception:
                pass

            try:
                execute_sql(
                    f"""
                    INSERT INTO governance_tasks (id, task_type, title, description, priority, status, payload, created_by)
                    VALUES (gen_random_uuid(), 'research', '{title_escaped}', 'Generate a shortlist of candidate domains under $20 with flip potential.', 'medium', 'pending', '{payload_escaped}', 'experiment')
                    """
                )
                created_tasks += 1

                try:
                    log_action(
                        "experiment.step_executed",
                        "REVENUE-EXP-01 searched for domains",
                        level="info",
                        output_data={"experiment_id": exp_id, "task_title": task_title},
                    )
                except Exception:
                    pass

                try:
                    execute_sql(
                        f"""
                        UPDATE experiments
                        SET current_iteration = COALESCE(current_iteration, 0) + 1,
                            updated_at = NOW()
                        WHERE id = '{exp_id.replace("'", "''")}'
                        """
                    )
                except Exception:
                    pass

                progressed += 1
            except Exception as e:
                try:
                    log_action(
                        "experiment.step_failed",
                        "Experiment step failed to create task",
                        level="warn",
                        error_data={"error": str(e), "experiment_id": exp_id},
                    )
                except Exception:
                    pass
        else:
            skipped += 1

    return {
        "success": True,
        "running_experiments": len(experiments),
        "experiments_progressed": progressed,
        "tasks_created": created_tasks,
        "skipped": skipped,
    }
