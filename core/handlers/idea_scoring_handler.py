import json
import logging
from typing import Any, Dict, List, Optional

from core.idea_scorer import IdeaScorer

from .base import BaseHandler, HandlerResult

logger = logging.getLogger(__name__)


class IdeaScoringHandler(BaseHandler):
    task_type = "idea_scoring"

    def execute(self, task: Dict[str, Any]) -> HandlerResult:
        self._execution_logs = []
        task_id = task.get("id")
        payload = task.get("payload") or {}

        limit_raw = payload.get("limit")
        try:
            limit = int(limit_raw) if limit_raw is not None else 50
        except Exception:
            limit = 50
        limit = max(1, min(500, limit))

        self._log(
            "handler.idea_scoring.starting",
            f"Starting idea scoring (limit={limit})",
            task_id=task_id,
        )

        try:
            schema_res = self.execute_sql(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'revenue_ideas'
                  AND column_name IN ('score', 'score_breakdown')
                """
            )
            schema_rows = schema_res.get("rows", []) or []
            cols = {str(r.get("column_name") or "") for r in schema_rows}
            has_score_col = "score" in cols
            has_breakdown_col = "score_breakdown" in cols
        except Exception:
            has_score_col = False
            has_breakdown_col = False

        try:
            res = self.execute_sql(
                f"""
                SELECT id, title, description, hypothesis, estimates
                FROM revenue_ideas
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT {int(limit)}
                """
            )
            rows = res.get("rows", []) or []
        except Exception as e:
            msg = str(e)
            self._log(
                "handler.idea_scoring.failed",
                f"Failed to load pending ideas: {msg[:200]}",
                level="error",
                task_id=task_id,
            )
            return HandlerResult(success=False, data={"executed": True}, error=msg, logs=self._execution_logs)

        scorer = IdeaScorer()
        scored = 0
        failed = 0
        failures: List[Dict[str, Any]] = []

        for r in rows:
            idea_id = str(r.get("id") or "")
            if not idea_id:
                continue

            estimates = r.get("estimates")
            if not isinstance(estimates, dict):
                estimates = {}

            idea = {
                "title": r.get("title"),
                "description": r.get("description"),
                "hypothesis": r.get("hypothesis"),
                "estimates": estimates,
            }

            try:
                result = scorer.score_idea(idea)
            except Exception as e:
                failed += 1
                failures.append({"id": idea_id, "error": str(e)[:200]})
                continue

            score = result.get("score")
            breakdown = result.get("breakdown") or {}

            new_estimates = dict(estimates)
            new_estimates["score"] = score
            new_estimates["score_breakdown"] = breakdown

            estimates_json = json.dumps(new_estimates).replace("'", "''")
            breakdown_json = json.dumps(breakdown).replace("'", "''")

            idea_id_esc = idea_id.replace("'", "''")

            update_parts = [
                "status = 'scored'",
                f"estimates = '{estimates_json}'::jsonb",
                "updated_at = NOW()",
            ]

            if has_score_col:
                try:
                    update_parts.append(f"score = {float(score or 0.0)}")
                except Exception:
                    update_parts.append("score = 0.0")

            if has_breakdown_col:
                update_parts.append(f"score_breakdown = '{breakdown_json}'::jsonb")

            try:
                self.execute_sql(
                    f"""
                    UPDATE revenue_ideas
                    SET {', '.join(update_parts)}
                    WHERE id = '{idea_id_esc}'
                    """
                )
                scored += 1
            except Exception as e:
                failed += 1
                failures.append({"id": idea_id, "error": str(e)[:200]})

        data: Dict[str, Any] = {
            "executed": True,
            "considered": len(rows),
            "scored": scored,
            "failed": failed,
        }
        if failures:
            data["failures_preview"] = failures[:10]

        self._log(
            "handler.idea_scoring.complete",
            f"Idea scoring complete: scored={scored} failed={failed} considered={len(rows)}",
            task_id=task_id,
            output_data={"scored": scored, "failed": failed, "considered": len(rows)},
        )

        return HandlerResult(success=True, data=data, logs=self._execution_logs)
