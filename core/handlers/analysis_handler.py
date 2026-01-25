import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import BaseHandler, HandlerResult

logger = logging.getLogger(__name__)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


class AnalysisHandler(BaseHandler):
    task_type = "analysis"

    def execute(self, task: Dict[str, Any]) -> HandlerResult:
        self._execution_logs = []
        task_id = task.get("id")
        payload = task.get("payload") or {}
        title = task.get("title") or ""
        description = task.get("description") or ""

        days_back = _to_int(payload.get("days_back"), 30)
        max_workers = _to_int(payload.get("max_workers"), 20)

        self._log(
            "handler.analysis.starting",
            f"Starting analysis for task '{title[:80]}' (days_back={days_back})",
            task_id=task_id,
        )

        try:
            insights: Dict[str, Any] = {}
            sql_used: Dict[str, str] = {}

            # Default: worker performance snapshot (success rates + counts)
            wants_worker_perf = True
            combined_text = f"{title}\n{description}".lower()
            if any(k in combined_text for k in ["worker", "performance", "success rate", "comparison", "compare"]):
                wants_worker_perf = True

            if wants_worker_perf:
                sql = f"""
                    SELECT
                      assigned_worker as worker_id,
                      COUNT(*) FILTER (WHERE status = 'completed')::int as completed,
                      COUNT(*) FILTER (WHERE status = 'failed')::int as failed,
                      COUNT(*)::int as total
                    FROM governance_tasks
                    WHERE assigned_worker IS NOT NULL
                      AND created_at >= NOW() - INTERVAL '{days_back} days'
                      AND status IN ('completed','failed')
                    GROUP BY assigned_worker
                    HAVING COUNT(*) > 0
                    ORDER BY total DESC
                    LIMIT {max_workers}
                """
                sql_used["worker_task_outcomes"] = sql
                res = self.execute_sql(sql)
                rows = res.get("rows", []) or []

                workers: List[Dict[str, Any]] = []
                for r in rows:
                    completed = _to_int(r.get("completed"))
                    failed = _to_int(r.get("failed"))
                    total = _to_int(r.get("total"))
                    denom = total if total > 0 else (completed + failed)
                    success_rate = (completed / denom) if denom > 0 else 0.0
                    workers.append(
                        {
                            "worker_id": r.get("worker_id"),
                            "completed": completed,
                            "failed": failed,
                            "total": total,
                            "success_rate": round(success_rate * 100.0, 1),
                        }
                    )

                insights["worker_performance"] = workers

            # Basic log volume + error rate (from execution_logs)
            sql = f"""
                SELECT
                  COUNT(*)::int as total_logs,
                  COUNT(*) FILTER (WHERE level IN ('error','critical'))::int as error_logs
                FROM execution_logs
                WHERE created_at >= NOW() - INTERVAL '{days_back} days'
            """
            sql_used["execution_log_error_rate"] = sql
            res = self.execute_sql(sql)
            row = (res.get("rows") or [{}])[0] or {}
            total_logs = _to_int(row.get("total_logs"))
            error_logs = _to_int(row.get("error_logs"))
            error_rate = (error_logs / total_logs) if total_logs > 0 else 0.0
            insights["execution_logs"] = {
                "total_logs": total_logs,
                "error_logs": error_logs,
                "error_rate_percent": round(error_rate * 100.0, 2),
            }

            # Worker registry snapshot (online-ish workers)
            sql = """
                SELECT
                  worker_id,
                  status,
                  last_heartbeat
                FROM worker_registry
                ORDER BY last_heartbeat DESC NULLS LAST
                LIMIT 50
            """
            sql_used["worker_registry"] = sql
            res = self.execute_sql(sql)
            insights["worker_registry"] = res.get("rows", []) or []

            # Produce a factual, human-readable summary (no AI numbers)
            summary_parts: List[str] = []
            wp = insights.get("worker_performance") or []
            if isinstance(wp, list) and wp:
                top = wp[0]
                summary_parts.append(
                    f"Top worker by volume (last {days_back}d): {top.get('worker_id')} "
                    f"success_rate={top.get('success_rate')}% total={top.get('total')}"
                )

            el = insights.get("execution_logs") or {}
            if isinstance(el, dict):
                summary_parts.append(
                    f"Execution logs (last {days_back}d): total={el.get('total_logs')} "
                    f"errors={el.get('error_logs')} error_rate={el.get('error_rate_percent')}%"
                )

            summary = " | ".join([p for p in summary_parts if p])
            if not summary:
                summary = f"Analysis complete using live DB queries (last {days_back} days)."

            data = {
                "executed": True,
                "summary": summary,
                "insights": insights,
                "sql_used": sql_used,
                "days_back": days_back,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

            self._log(
                "handler.analysis.complete",
                "Analysis completed successfully",
                task_id=task_id,
                output_data={"days_back": days_back},
            )

            return HandlerResult(success=True, data=data, logs=self._execution_logs)

        except Exception as e:
            msg = str(e)
            self._log(
                "handler.analysis.failed",
                f"Analysis failed: {msg[:200]}",
                level="error",
                task_id=task_id,
            )
            return HandlerResult(success=False, data={"executed": True}, error=msg, logs=self._execution_logs)
