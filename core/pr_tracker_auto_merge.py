"""
Auto-Merge Extension for PR Tracker

Adds auto-merge capability for approved auto-fix PRs.
Integrates with PR tracker to merge PRs after CodeRabbit approval.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


def try_auto_merge(
    task_id: str,
    repo: str,
    pr_number: int,
    status: Any,
    execute_sql,
    log_action
) -> Optional[Dict[str, Any]]:
    """Attempt to auto-merge an approved PR if it's auto-generated.
    
    Args:
        task_id: Task ID associated with PR
        repo: Repository (owner/name)
        pr_number: PR number
        status: PR status object
        execute_sql: SQL execution function
        log_action: Logging function
    
    Returns:
        Dict with merge result or None if not eligible.
    """
    try:
        # Check if task is auto-generated (code_fix type)
        task_query = f"""
            SELECT task_type, payload::text as payload_text
            FROM governance_tasks
            WHERE id = '{task_id}'::uuid
        """
        result = execute_sql(task_query)
        rows = result.get("rows", [])
        
        if not rows:
            return None
        
        task = rows[0]
        task_type = task.get("task_type", "")
        
        # Only auto-merge code_fix tasks
        if task_type != "code_fix":
            log_action(
                "pr_tracker.auto_merge_skipped",
                f"PR #{pr_number} not eligible for auto-merge (task_type: {task_type})",
                level="info",
                output_data={"repo": repo, "pr_number": pr_number, "task_id": task_id}
            )
            return None
        
        # Check if PR is approved and mergeable
        if not status.mergeable:
            log_action(
                "pr_tracker.auto_merge_not_mergeable",
                f"PR #{pr_number} approved but not mergeable",
                level="warn",
                output_data={"repo": repo, "pr_number": pr_number}
            )
            return None
        
        # Merge the PR
        log_action(
            "pr_tracker.auto_merge_attempting",
            f"Attempting auto-merge for PR #{pr_number}",
            level="info",
            output_data={"repo": repo, "pr_number": pr_number, "task_id": task_id}
        )
        
        merge_result = _merge_pr_via_github(repo, pr_number)
        
        if merge_result["success"]:
            log_action(
                "pr_tracker.auto_merge_success",
                f"Auto-merged PR #{pr_number}: {merge_result['sha']}",
                level="info",
                output_data={
                    "repo": repo,
                    "pr_number": pr_number,
                    "task_id": task_id,
                    "merge_sha": merge_result["sha"]
                }
            )
            
            # Update PR tracking
            execute_sql(f"""
                UPDATE pr_tracking
                SET merged_at = NOW(),
                    current_state = 'merged',
                    metadata = COALESCE(metadata, '{{}}'::jsonb) || 
                               '{{"auto_merged": true}}'::jsonb
                WHERE repo = '{repo}' AND pr_number = {pr_number}
            """)
            
            return {
                "success": True,
                "sha": merge_result["sha"],
                "message": merge_result["message"]
            }
        else:
            log_action(
                "pr_tracker.auto_merge_failed",
                f"Failed to auto-merge PR #{pr_number}: {merge_result['error']}",
                level="error",
                output_data={
                    "repo": repo,
                    "pr_number": pr_number,
                    "error": merge_result["error"]
                }
            )
            return {
                "success": False,
                "error": merge_result["error"]
            }
        
    except Exception as e:
        logger.exception(f"Auto-merge error for PR #{pr_number}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def _merge_pr_via_github(repo: str, pr_number: int) -> Dict[str, Any]:
    """Merge PR via GitHub API.
    
    Args:
        repo: Repository (owner/name)
        pr_number: PR number
    
    Returns:
        Dict with success status and merge SHA or error.
    """
    try:
        import requests
        
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/merge"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {
            "commit_title": f"Auto-merge PR #{pr_number}",
            "commit_message": "Merged by JUGGERNAUT self-healing system",
            "merge_method": "squash"  # Squash commits for cleaner history
        }
        
        response = requests.put(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return {
                "success": True,
                "sha": result.get("sha", ""),
                "message": result.get("message", "")
            }
        else:
            return {
                "success": False,
                "error": f"GitHub API error: {response.status_code} - {response.text}"
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
