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

        # Extract parameters
        payload = task.get("payload", {})
        days_back = payload.get("days_back", 7)
        max_workers = payload.get("max_workers", 10)

        # Determine what to analyze based on task title/description
        title = (task.get("title") or "").lower()
        description = (task.get("description") or "").lower()
        combined_text = f"{title}\n{description}".lower()
        category = (payload.get("category") or payload.get("dedupe_key") or "").lower()

        # Enhanced pattern matching for more specific analysis
        wants_worker_perf = any(k in combined_text or k in category for k in
            ["worker", "performance", "success rate", "comparison", "compare", "throughput", "efficiency"])
        wants_error_analysis = any(k in combined_text or k in category for k in
            ["error", "failure", "spike", "incident", "alert", "bug", "crash", "exception"])
        wants_task_analysis = any(k in combined_text or k in category for k in
            ["task", "pipeline", "queue", "backlog", "completion", "pending"])
        wants_cost_analysis = any(k in combined_text or k in category for k in
            ["cost", "budget", "spend", "expense", "revenue", "roi"])
        wants_experiment_analysis = any(k in combined_text or k in category for k in
            ["experiment", "iteration", "hypothesis", "test"])
        wants_learning_analysis = any(k in combined_text or k in category for k in
            ["learning", "pattern", "insight", "discovery"])

        # Extract specific timeframe if mentioned
        if "last hour" in combined_text or "1 hour" in combined_text:
            days_back = 0.042  # ~1 hour in days
        elif "last day" in combined_text or "24 hour" in combined_text or "1 day" in combined_text:
            days_back = 1
        elif "last week" in combined_text or "7 day" in combined_text:
            days_back = 7
        elif "last month" in combined_text or "30 day" in combined_text:
            days_back = 30

        # If nothing matched, default to worker perf + error rate
        if not any([wants_worker_perf, wants_error_analysis, wants_task_analysis, wants_cost_analysis, wants_experiment_analysis, wants_learning_analysis]):
            wants_worker_perf = True
            wants_error_analysis = True

        self._log(
            "handler.analysis.starting",
            f"Starting analysis for task '{title[:80]}' (days_back={days_back})",
            task_id=task_id,
        )

        try:
            insights: Dict[str, Any] = {}
            sql_used: Dict[str, str] = {}

            if wants_error_analysis:
                sql = f"""
                    SELECT level, COUNT(*)::int as count,
                           COUNT(DISTINCT action) as distinct_actions
                    FROM execution_logs
                    WHERE created_at >= NOW() - INTERVAL '{days_back} days'
                      AND level IN ('error','critical','warn')
                    GROUP BY level ORDER BY count DESC
                """
                sql_used["error_breakdown"] = sql
                res = self.execute_sql(sql)
                insights["error_breakdown"] = res.get("rows", []) or []

                sql = f"""
                    SELECT action, COUNT(*)::int as count,
                           MAX(created_at) as last_seen
                    FROM execution_logs
                    WHERE created_at >= NOW() - INTERVAL '{days_back} days'
                      AND level IN ('error','critical')
                    GROUP BY action ORDER BY count DESC LIMIT 10
                """
                sql_used["top_errors_by_action"] = sql
                res = self.execute_sql(sql)
                insights["top_errors"] = res.get("rows", []) or []

            if wants_task_analysis:
                sql = f"""
                    SELECT status, COUNT(*)::int as count
                    FROM governance_tasks
                    WHERE created_at >= NOW() - INTERVAL '{days_back} days'
                    GROUP BY status ORDER BY count DESC
                """
                sql_used["task_status_breakdown"] = sql
                res = self.execute_sql(sql)
                insights["task_pipeline"] = res.get("rows", []) or []

                sql = f"""
                    SELECT task_type, COUNT(*)::int as count,
                           COUNT(*) FILTER (WHERE status = 'completed')::int as completed,
                           COUNT(*) FILTER (WHERE status = 'failed')::int as failed
                    FROM governance_tasks
                    WHERE created_at >= NOW() - INTERVAL '{days_back} days'
                    GROUP BY task_type ORDER BY count DESC LIMIT 15
                """
                sql_used["task_type_breakdown"] = sql
                res = self.execute_sql(sql)
                insights["task_types"] = res.get("rows", []) or []

            if wants_cost_analysis:
                sql = f"""
                    SELECT category,
                           SUM(amount_cents)::int as total_cents,
                           COUNT(*)::int as event_count
                    FROM cost_events
                    WHERE created_at >= NOW() - INTERVAL '{days_back} days'
                    GROUP BY category ORDER BY total_cents DESC
                """
                sql_used["cost_by_category"] = sql
                res = self.execute_sql(sql)
                insights["cost_breakdown"] = res.get("rows", []) or []

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
            
            if wants_experiment_analysis:
                sql = f"""
                    SELECT 
                        status,
                        COUNT(*)::int as count,
                        AVG(EXTRACT(EPOCH FROM (completed_at - created_at))/86400)::float as avg_duration_days
                    FROM experiments
                    WHERE created_at >= NOW() - INTERVAL '{days_back} days'
                    GROUP BY status
                    ORDER BY count DESC
                """
                sql_used["experiment_status"] = sql
                res = self.execute_sql(sql)
                insights["experiments"] = res.get("rows", []) or []
            
            if wants_learning_analysis:
                sql = f"""
                    SELECT 
                        category,
                        COUNT(*)::int as count,
                        AVG(confidence_score)::float as avg_confidence,
                        SUM(applied_count)::int as total_applications
                    FROM learnings
                    WHERE created_at >= NOW() - INTERVAL '{days_back} days'
                    GROUP BY category
                    ORDER BY count DESC
                    LIMIT 10
                """
                sql_used["learning_patterns"] = sql
                res = self.execute_sql(sql)
                insights["learnings"] = res.get("rows", []) or []

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
            
            # Add experiment summary if analyzed
            exp = insights.get("experiments") or []
            if isinstance(exp, list) and exp:
                exp_summary = ", ".join([f"{e.get('status')}={e.get('count')}" for e in exp[:3]])
                summary_parts.append(f"Experiments: {exp_summary}")
            
            # Add learning summary if analyzed
            learn = insights.get("learnings") or []
            if isinstance(learn, list) and learn:
                total_learnings = sum(l.get('count', 0) for l in learn)
                summary_parts.append(f"Learnings: {total_learnings} patterns captured")

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
