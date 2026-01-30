"""PR Merge Monitor

Polls tasks in awaiting_pr_merge and updates their status when the linked PR is merged/closed.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional


def _hours_since(ts: Any) -> Optional[float]:
    if not ts:
        return None
    try:
        if isinstance(ts, str):
            s = ts
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
        else:
            dt = ts
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    except Exception:
        return None


def monitor_pending_prs(
    *,
    execute_sql,
    log_action,
    enable_auto_merge: bool = False,
    repo_allowlist: Optional[List[str]] = None,
    limit: int = 25,
) -> Dict[str, Any]:
    repo_allowlist = repo_allowlist or []

    try:
        from core.pr_tracker import PRTracker
    except Exception as e:
        return {"success": False, "error": f"PRTracker unavailable: {e}"}

    try:
        from src.github_automation import GitHubClient
    except Exception:
        GitHubClient = None  # type: ignore

    sql = f"""
        SELECT
            t.id as task_id,
            t.title,
            t.status,
            p.repo,
            p.pr_number,
            p.pr_url,
            p.current_state,
            p.created_at as pr_created_at,
            p.updated_at as pr_updated_at
        FROM governance_tasks t
        JOIN pr_tracking p ON p.task_id = t.id
        WHERE t.status = 'awaiting_pr_merge'
          AND p.current_state NOT IN ('merged', 'closed')
        ORDER BY p.updated_at ASC NULLS FIRST
        LIMIT {int(limit)}
    """

    rows = []
    try:
        rows = (execute_sql(sql) or {}).get("rows", []) or []
    except Exception as e:
        return {"success": False, "error": str(e)}

    tracker = PRTracker()

    processed = 0
    merged = 0
    closed = 0
    failed_conflict = 0
    escalated = 0
    auto_merge_attempted = 0

    for r in rows:
        processed += 1
        task_id = str(r.get("task_id") or "")
        pr_url = str(r.get("pr_url") or "")
        repo = str(r.get("repo") or "")
        pr_number = r.get("pr_number")

        if not task_id or not pr_url:
            continue

        try:
            status = tracker.get_pr_status(pr_url)
            if not status:
                continue

            if status.state.value == "merged" or bool(status.merged_at):
                evidence = {
                    "type": "pr_merged",
                    "verified": True,
                    "pr_number": status.pr_number,
                    "pr_url": status.url,
                    "repo": status.repo,
                    "merged_at": status.merged_at,
                    "merge_commit_sha": status.merge_commit_sha,
                    "coderabbit_approved": bool(status.coderabbit_approved),
                }

                evidence_json = json.dumps(evidence, default=str)
                evidence_esc = evidence_json.replace("'", "''")

                execute_sql(
                    f"""
                    UPDATE governance_tasks
                    SET status = 'completed',
                        completed_at = NOW(),
                        completion_evidence = '{evidence_esc}',
                        result = '{evidence_esc}'::jsonb,
                        updated_at = NOW()
                    WHERE id = '{task_id}'::uuid
                    """
                )

                execute_sql(
                    f"""
                    UPDATE pr_tracking
                    SET current_state = 'merged',
                        merged_at = COALESCE(merged_at, NOW()),
                        updated_at = NOW()
                    WHERE repo = '{status.repo.replace("'", "''")}'
                      AND pr_number = {int(status.pr_number)}
                    """
                )

                try:
                    log_action(
                        "pr_monitor.merged",
                        f"PR merged; completed task {task_id}",
                        level="info",
                        task_id=task_id,
                        output_data={"repo": status.repo, "pr_number": status.pr_number},
                    )
                except Exception:
                    pass

                merged += 1
                continue

            if status.state.value == "closed":
                execute_sql(
                    f"""
                    UPDATE governance_tasks
                    SET status = 'failed',
                        error_message = 'PR closed without merge',
                        updated_at = NOW()
                    WHERE id = '{task_id}'::uuid
                    """
                )

                execute_sql(
                    f"""
                    UPDATE pr_tracking
                    SET current_state = 'closed',
                        updated_at = NOW()
                    WHERE repo = '{status.repo.replace("'", "''")}'
                      AND pr_number = {int(status.pr_number)}
                    """
                )

                closed += 1
                continue

            if status.mergeable is False:
                execute_sql(
                    f"""
                    UPDATE governance_tasks
                    SET status = 'failed',
                        error_message = 'PR has merge conflicts',
                        updated_at = NOW()
                    WHERE id = '{task_id}'::uuid
                    """
                )

                failed_conflict += 1
                continue

            age_h = _hours_since(r.get("pr_created_at") or r.get("pr_updated_at"))
            if age_h is not None and age_h > 48:
                try:
                    from core.orchestration import create_escalation

                    create_escalation(task_id, f"PR open > 48h without merge: {pr_url}")
                    escalated += 1
                except Exception:
                    pass

            if (
                enable_auto_merge
                and repo
                and (repo in set(repo_allowlist))
                and bool(status.coderabbit_approved)
                and status.mergeable is True
                and GitHubClient is not None
                and pr_number is not None
            ):
                try:
                    auto_merge_attempted += 1
                    gh = GitHubClient(repo=repo)
                    gh_status = gh.get_pr_status(int(pr_number))
                    if getattr(gh_status, "checks_passed", False):
                        tracker.merge_pr(pr_url, merge_method="squash")
                except Exception:
                    pass

        except Exception as e:
            try:
                log_action(
                    "pr_monitor.error",
                    f"PR monitor error: {e}",
                    level="warn",
                    task_id=task_id,
                    error_data={"repo": repo, "pr_number": pr_number, "pr_url": pr_url},
                )
            except Exception:
                pass

    return {
        "success": True,
        "processed": processed,
        "merged": merged,
        "closed": closed,
        "failed_conflict": failed_conflict,
        "escalated": escalated,
        "auto_merge_attempted": auto_merge_attempted,
    }
