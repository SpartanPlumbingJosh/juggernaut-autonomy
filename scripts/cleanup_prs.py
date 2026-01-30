import json
from typing import Any, Dict, List

from core.database import query_db
from src.github_automation import GitHubClient


def cleanup_pr_mess(*, dry_run: bool = True, max_tasks: int = 50) -> Dict[str, Any]:
    duplicates = query_db(
        f"""
        SELECT task_id::text as task_id,
               array_agg(pr_number ORDER BY created_at DESC) as prs
        FROM pr_tracking
        GROUP BY task_id
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
        LIMIT {int(max_tasks)}
        """
    ).get("rows", []) or []

    closed_prs: List[Dict[str, Any]] = []

    for row in duplicates:
        task_id = str(row.get("task_id") or "")
        prs = row.get("prs") or []
        if not task_id or not prs or len(prs) < 2:
            continue

        keep_pr = prs[0]
        close_prs = prs[1:]

        pr_nums: List[int] = []
        for p in prs:
            try:
                pr_nums.append(int(p))
            except Exception:
                continue
        in_list = ", ".join([str(p) for p in pr_nums])
        pr_rows = []
        if in_list:
            pr_rows = query_db(
                f"""
                SELECT repo, pr_number
                FROM pr_tracking
                WHERE task_id = '{task_id}'::uuid
                  AND pr_number IN ({in_list})
                """
            ).get("rows", []) or []

        repo_by_pr = {
            int(r.get("pr_number")): str(r.get("repo") or "")
            for r in pr_rows
            if r.get("pr_number") is not None
        }

        for pr_num in close_prs:
            try:
                pr_num_int = int(pr_num)
            except Exception:
                continue
            repo = repo_by_pr.get(pr_num_int) or "SpartanPlumbingJosh/juggernaut-autonomy"

            if dry_run:
                closed_prs.append({"task_id": task_id, "repo": repo, "pr_number": pr_num_int, "kept_pr": keep_pr, "dry_run": True})
                continue

            try:
                gh = GitHubClient(repo=repo)
                gh.close_pr(pr_num_int)
            except Exception:
                pass

            try:
                query_db(
                    """
                    UPDATE pr_tracking
                    SET current_state = 'closed', updated_at = NOW()
                    WHERE repo = $1 AND pr_number = $2
                    """,
                    [repo, pr_num_int],
                )
            except Exception:
                pass

            closed_prs.append({"task_id": task_id, "repo": repo, "pr_number": pr_num_int, "kept_pr": keep_pr, "dry_run": False})

    # Reset stuck in_progress tasks that already have an open PR
    reset_sql = """
        UPDATE governance_tasks t
        SET status = 'awaiting_pr_merge',
            updated_at = NOW()
        FROM pr_tracking p
        WHERE t.id = p.task_id
          AND t.status = 'in_progress'
          AND p.current_state NOT IN ('merged', 'closed')
    """

    reset_count = 0
    if not dry_run:
        try:
            res = query_db(reset_sql)
            reset_count = int(res.get("rowCount", 0) or 0)
        except Exception:
            reset_count = 0

    # Orphaned PRs: tracking without matching task
    orphan_count = 0
    try:
        orphan_count = int(
            (query_db(
                """
                SELECT COUNT(*)::int as c
                FROM pr_tracking p
                WHERE NOT EXISTS (SELECT 1 FROM governance_tasks t WHERE t.id = p.task_id)
                """
            ).get("rows") or [{}])[0].get("c")
            or 0
        )
    except Exception:
        orphan_count = 0

    return {
        "success": True,
        "dry_run": bool(dry_run),
        "duplicate_tasks": len(duplicates),
        "prs_closed": len([x for x in closed_prs if not x.get("dry_run")]),
        "prs_to_close": len([x for x in closed_prs if x.get("dry_run")]),
        "closed_prs": closed_prs,
        "reset_stuck_tasks": reset_count,
        "orphan_pr_count": orphan_count,
    }


if __name__ == "__main__":
    result = cleanup_pr_mess(dry_run=True)
    print(json.dumps(result, indent=2, default=str))
