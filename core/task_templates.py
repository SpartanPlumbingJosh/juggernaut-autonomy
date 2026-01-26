import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class ProposedTask:
    title: str
    task_type: str
    description: str
    priority: str
    payload: Dict[str, Any]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: str) -> str:
    v = (value or "").lower().strip()
    v = re.sub(r"\s+", " ", v)
    v = re.sub(r"[^a-z0-9\s:_\-]", "", v)
    return v


def _title_similarity(a: str, b: str) -> float:
    na = _normalize_text(a)
    nb = _normalize_text(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def fetch_recent_tasks(execute_sql: Callable[[str], Dict[str, Any]], limit: int = 50) -> List[Dict[str, Any]]:
    sql = f"""
        SELECT id, task_type, title, payload, created_at
        FROM governance_tasks
        ORDER BY created_at DESC
        LIMIT {int(limit)}
    """
    try:
        res = execute_sql(sql)
        return res.get("rows", []) or []
    except Exception:
        return []


def is_duplicate_task(
    candidate: ProposedTask,
    recent_tasks: List[Dict[str, Any]],
    dedupe_hours: int = 24,
    title_similarity_threshold: float = 0.92,
) -> Tuple[bool, Optional[str]]:
    cand_key = (candidate.payload or {}).get("dedupe_key")
    cand_type = candidate.task_type
    cand_title = candidate.title

    for t in recent_tasks:
        try:
            t_payload = t.get("payload")
            if isinstance(t_payload, str):
                try:
                    t_payload = json.loads(t_payload)
                except Exception:
                    t_payload = {}
            if not isinstance(t_payload, dict):
                t_payload = {}

            t_key = t_payload.get("dedupe_key")
            if cand_key and t_key and str(cand_key) == str(t_key):
                return True, "dedupe_key"

            if (t.get("task_type") or "") == cand_type:
                sim = _title_similarity(str(t.get("title") or ""), cand_title)
                if sim >= title_similarity_threshold:
                    return True, "title_similarity"
        except Exception:
            continue

    return False, None


def _count_pending_tasks(execute_sql: Callable[[str], Dict[str, Any]]) -> int:
    try:
        res = execute_sql("SELECT COUNT(*)::int as c FROM governance_tasks WHERE status = 'pending'")
        return int((res.get("rows") or [{}])[0].get("c") or 0)
    except Exception:
        return 0


def _pending_category_counts(execute_sql: Callable[[str], Dict[str, Any]]) -> Dict[str, int]:
    sql = """
        SELECT COALESCE(payload->>'category', 'unknown') as category, COUNT(*)::int as c
        FROM governance_tasks
        WHERE status = 'pending'
        GROUP BY COALESCE(payload->>'category', 'unknown')
    """
    try:
        res = execute_sql(sql)
        rows = res.get("rows", []) or []
        out: Dict[str, int] = {}
        for r in rows:
            out[str(r.get("category") or "unknown")] = int(r.get("c") or 0)
        return out
    except Exception:
        return {}


def _top_error_actions(execute_sql: Callable[[str], Dict[str, Any]], days_back: int = 7, limit: int = 5) -> List[Dict[str, Any]]:
    sql = f"""
        SELECT action, COUNT(*)::int as c
        FROM execution_logs
        WHERE created_at >= NOW() - INTERVAL '{int(days_back)} days'
          AND level IN ('error','critical')
        GROUP BY action
        ORDER BY c DESC
        LIMIT {int(limit)}
    """
    try:
        res = execute_sql(sql)
        return res.get("rows", []) or []
    except Exception:
        return []


def build_task_templates(execute_sql: Callable[[str], Dict[str, Any]]) -> Dict[str, List[Callable[[], Optional[ProposedTask]]]]:
    def system_health_worker_perf() -> Optional[ProposedTask]:
        payload = {
            "category": "system_health",
            "dedupe_key": "proactive:system_health:worker_performance_trends:daily",
            "success_criteria": {"deliverable": "analysis report", "includes": ["worker success rate", "top error actions"]},
            "days_back": 30,
        }
        top_errs = _top_error_actions(execute_sql, days_back=7)
        payload["top_error_actions"] = top_errs
        return ProposedTask(
            title="Analyze: Worker performance trends",
            task_type="analysis",
            description="Use DB metrics to identify worker success-rate outliers and error hotspots. Provide a short summary and top remediation actions.",
            priority="medium",
            payload=payload,
        )

    def system_health_error_spike() -> Optional[ProposedTask]:
        payload = {
            "category": "system_health",
            "dedupe_key": "proactive:system_health:error_rate_snapshot:6h",
            "success_criteria": {"deliverable": "analysis summary", "includes": ["error_rate_percent", "top failing actions"]},
            "days_back": 7,
        }
        top_errs = _top_error_actions(execute_sql, days_back=2)
        payload["top_error_actions"] = top_errs
        return ProposedTask(
            title="Audit: Error rate spike detection",
            task_type="analysis",
            description="Analyze execution_logs for recent error spikes and identify the top failing actions and likely causes.",
            priority="high" if len(top_errs) >= 3 else "medium",
            payload=payload,
        )

    def system_health_stale_pending() -> Optional[ProposedTask]:
        sql = """
            SELECT COUNT(*)::int as c
            FROM governance_tasks
            WHERE status = 'pending'
              AND created_at < NOW() - INTERVAL '7 days'
        """
        try:
            res = execute_sql(sql)
            stale = int((res.get("rows") or [{}])[0].get("c") or 0)
        except Exception:
            stale = 0
        if stale <= 0:
            return None
        payload = {
            "category": "system_health",
            "dedupe_key": f"proactive:system_health:stale_pending_tasks:{min(stale,9999)}",
            "success_criteria": {"deliverable": "triage plan", "goal": "reduce stale pending tasks"},
            "stale_pending": stale,
        }
        return ProposedTask(
            title="Triage: Stale pending tasks backlog",
            task_type="workflow",
            description="Identify the oldest pending tasks and propose a concrete triage plan (close, re-scope, or execute) with next actions.",
            priority="high" if stale >= 10 else "medium",
            payload=payload,
        )

    def business_ops_reporting() -> Optional[ProposedTask]:
        payload = {
            "category": "business_ops",
            "dedupe_key": "proactive:business_ops:weekly_ops_report:24h",
            "success_criteria": {"deliverable": "ops report", "includes": ["task throughput", "error rate", "opportunities created"]},
            "days_back": 7,
        }
        return ProposedTask(
            title="Report: Weekly ops snapshot",
            task_type="analysis",
            description="Generate a factual ops snapshot from DB: task throughput, error rate, and opportunity scan outcomes.",
            priority="medium",
            payload=payload,
        )

    def self_improvement_test_gap() -> Optional[ProposedTask]:
        payload = {
            "category": "self_improvement",
            "dedupe_key": "proactive:self_improvement:test_gaps:48h",
            "success_criteria": {"deliverable": "test plan", "includes": ["top modules", "highest risk paths"]},
        }
        return ProposedTask(
            title="Review: Add tests for high-risk paths",
            task_type="analysis",
            description="Use recent failures and critical paths to propose where automated tests should be added next.",
            priority="medium",
            payload=payload,
        )

    def revenue_domain_scan() -> Optional[ProposedTask]:
        payload = {
            "category": "revenue",
            "dedupe_key": "proactive:revenue:domain_flip_scan:48h",
            "success_criteria": {"deliverable": "candidate list", "includes": ["criteria", "next steps"]},
            "scan_type": "domain",
            "source": "expired_domains",
            "config": {"max_results": 20},
        }
        return ProposedTask(
            title="Research: Domain flip opportunities",
            task_type="scan",
            description="Run a domain scan (or validate available sources) and produce a prioritized shortlist of domain flip candidates.",
            priority="low",
            payload=payload,
        )

    return {
        "system_health": [system_health_worker_perf, system_health_error_spike, system_health_stale_pending],
        "business_ops": [business_ops_reporting],
        "self_improvement": [self_improvement_test_gap],
        "revenue": [revenue_domain_scan],
    }


def pick_diverse_tasks(
    execute_sql: Callable[[str], Dict[str, Any]],
    max_tasks: int = 3,
    recent_limit: int = 50,
    dedupe_hours: int = 24,
) -> List[ProposedTask]:
    templates = build_task_templates(execute_sql)
    recent = fetch_recent_tasks(execute_sql, limit=recent_limit)
    pending_counts = _pending_category_counts(execute_sql)

    categories = [c for c in ("system_health", "business_ops", "self_improvement", "revenue") if c in templates]
    categories.sort(key=lambda c: (pending_counts.get(c, 0), c))

    selected: List[ProposedTask] = []
    for cat in categories:
        if len(selected) >= max_tasks:
            break
        generators = templates.get(cat) or []
        for gen in generators:
            if len(selected) >= max_tasks:
                break
            cand = gen()
            if cand is None:
                continue
            cand.payload = cand.payload or {}
            cand.payload.setdefault("category", cat)
            cand.payload.setdefault("generated_at", _now_iso())
            cand.payload.setdefault("dedupe_key", f"proactive:{cat}:{_normalize_text(cand.title)}")

            is_dup, reason = is_duplicate_task(cand, recent, dedupe_hours=dedupe_hours)
            if is_dup:
                continue

            if not cand.title or not cand.task_type or not isinstance(cand.payload, dict):
                continue
            if "dedupe_key" not in cand.payload or "success_criteria" not in cand.payload:
                continue

            selected.append(cand)
            recent.insert(0, {"task_type": cand.task_type, "title": cand.title, "payload": cand.payload})

    return selected


def should_generate_tasks(
    execute_sql: Callable[[str], Dict[str, Any]],
    min_pending: int = 1,
) -> bool:
    return _count_pending_tasks(execute_sql) <= int(min_pending)
