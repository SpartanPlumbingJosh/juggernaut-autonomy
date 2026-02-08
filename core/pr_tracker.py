"""
PR Lifecycle Tracker (VERCHAIN-06)
==================================

Tracks pull request lifecycle from creation through merge.
Integrates with GitHub API to monitor PR state changes and
automatically advances verification gates when PRs progress.

PR Lifecycle States:
- created: PR has been opened
- review_requested: Reviewers have been assigned
- changes_requested: Reviewers have requested changes
- approved: All required approvals received
- merged: PR has been merged to target branch
- closed: PR was closed without merging

Usage:
    tracker = PRTracker()
    tracker.track_pr(task_id, pr_url)
    status = tracker.get_pr_status(pr_url)
    tracker.sync_all_tracked_prs()
"""

import os
import re
import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum

from core.database import query_db


class PRState(Enum):
    """Possible states of a tracked PR."""
    CREATED = "created"
    REVIEW_REQUESTED = "review_requested"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    MERGED = "merged"
    CLOSED = "closed"


class ReviewStatus(Enum):
    """Review status of a PR."""
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"


@dataclass
class PRStatus:
    """Current status of a tracked PR."""
    pr_number: int
    repo: str
    state: PRState
    review_status: ReviewStatus
    mergeable: Optional[bool]
    title: str
    url: str
    created_at: str
    updated_at: str
    merged_at: Optional[str] = None
    merge_commit_sha: Optional[str] = None
    head_sha: Optional[str] = None
    approvals: List[Dict[str, Any]] = None
    changes_requested_by: List[str] = None
    coderabbit_approved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "pr_number": self.pr_number,
            "repo": self.repo,
            "state": self.state.value,
            "review_status": self.review_status.value,
            "mergeable": self.mergeable,
            "title": self.title,
            "url": self.url,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "merged_at": self.merged_at,
            "merge_commit_sha": self.merge_commit_sha,
            "head_sha": self.head_sha,
            "approvals": self.approvals or [],
            "changes_requested_by": self.changes_requested_by or [],
            "coderabbit_approved": self.coderabbit_approved
        }


class PRTracker:
    """
    Tracks PR lifecycle and syncs state changes with verification gates.
    
    Monitors PRs from creation through merge/close, updating task gates
    as the PR progresses through the review and merge process.
    """
    
    def __init__(self):
        """Initialize the PR tracker with GitHub credentials."""
        self.github_token = os.getenv("GITHUB_TOKEN", "")
        self.default_repo = os.getenv("GITHUB_REPO", "SpartanPlumbingJosh/juggernaut-autonomy")
    
    def track_pr(self, task_id: str, pr_url: str) -> Optional[Dict[str, Any]]:
        """
        Start tracking a PR for a task.
        
        Args:
            task_id: The governance task ID
            pr_url: Full GitHub PR URL or just PR number
            
        Returns:
            Dict with tracking info or None if failed
        """
        # Parse PR URL or number
        pr_info = self._parse_pr_url(pr_url)
        if not pr_info:
            print(f"[PR_TRACKER] Could not parse PR URL: {pr_url}")
            return None
        
        repo = pr_info.get("repo", self.default_repo)
        pr_number = pr_info["pr_number"]
        
        # Fetch current PR status from GitHub
        status = self.get_pr_status(f"https://github.com/{repo}/pull/{pr_number}")
        
        if not status:
            print(f"[PR_TRACKER] Could not fetch PR #{pr_number} from GitHub")
            return None
        
        # Insert or update tracking record
        coderabbit_json = json.dumps({"comments": []}).replace("'", "''")
        
        query = f"""
            INSERT INTO pr_tracking (
                task_id, repo, pr_number, pr_url, current_state, 
                review_status, mergeable, coderabbit_comments, merged_at
            ) VALUES (
                '{task_id}'::uuid,
                '{repo}',
                {pr_number},
                '{status.url}',
                '{status.state.value}',
                '{status.review_status.value}',
                {str(status.mergeable).lower() if status.mergeable is not None else 'NULL'},
                '{coderabbit_json}'::jsonb,
                {'NULL' if not status.merged_at else f"'{status.merged_at}'"}
            )
            ON CONFLICT (repo, pr_number) DO UPDATE SET
                task_id = EXCLUDED.task_id,
                pr_url = EXCLUDED.pr_url,
                current_state = EXCLUDED.current_state,
                review_status = EXCLUDED.review_status,
                mergeable = EXCLUDED.mergeable,
                merged_at = EXCLUDED.merged_at,
                updated_at = NOW()
            RETURNING id, task_id, repo, pr_number, current_state, review_status;
        """
        
        try:
            result = query_db(query)
            rows = result.get("rows", [])
            
            if rows:
                tracking = rows[0]
                
                # Also update task metadata with PR info
                self._update_task_pr_metadata(task_id, status)
                
                return {
                    "tracking_id": tracking.get("id"),
                    "task_id": task_id,
                    "repo": repo,
                    "pr_number": pr_number,
                    "state": status.state.value,
                    "review_status": status.review_status.value
                }
        except Exception as e:
            print(f"[PR_TRACKER] Error tracking PR: {e}")
        
        return None
    
    def get_pr_status(self, pr_url: str) -> Optional[PRStatus]:
        """
        Get current PR status from GitHub.
        
        Args:
            pr_url: GitHub PR URL
            
        Returns:
            PRStatus object or None if fetch failed
        """
        pr_info = self._parse_pr_url(pr_url)
        if not pr_info:
            return None
        
        repo = pr_info.get("repo", self.default_repo)
        pr_number = pr_info["pr_number"]
        
        # Fetch PR data
        pr_data = self._github_request(f"/repos/{repo}/pulls/{pr_number}")
        if not pr_data:
            return None
        
        # Fetch reviews
        reviews = self._github_request(f"/repos/{repo}/pulls/{pr_number}/reviews") or []
        
        # Analyze review state
        review_analysis = self._analyze_reviews(reviews)
        
        # Determine PR state
        pr_state = self._determine_pr_state(pr_data, review_analysis)
        
        return PRStatus(
            pr_number=pr_number,
            repo=repo,
            state=pr_state,
            review_status=review_analysis["status"],
            mergeable=pr_data.get("mergeable"),
            title=pr_data.get("title", ""),
            url=pr_data.get("html_url", ""),
            created_at=pr_data.get("created_at", ""),
            updated_at=pr_data.get("updated_at", ""),
            merged_at=pr_data.get("merged_at"),
            merge_commit_sha=pr_data.get("merge_commit_sha"),
            head_sha=pr_data.get("head", {}).get("sha"),
            approvals=review_analysis["approvals"],
            changes_requested_by=review_analysis["changes_requested_by"],
            coderabbit_approved=review_analysis["coderabbit_approved"]
        )
    
    def check_review_status(self, pr_url: str) -> Dict[str, Any]:
        """
        Check CodeRabbit and reviewer status for a PR.
        
        Args:
            pr_url: GitHub PR URL
            
        Returns:
            Dict with review status details
        """
        status = self.get_pr_status(pr_url)
        
        if not status:
            return {
                "review_status": "unknown",
                "coderabbit_approved": False,
                "approvals": [],
                "changes_requested_by": []
            }
        
        return {
            "review_status": status.review_status.value,
            "coderabbit_approved": status.coderabbit_approved,
            "approvals": status.approvals,
            "changes_requested_by": status.changes_requested_by,
            "total_approvals": len(status.approvals) if status.approvals else 0
        }
    
    def is_mergeable(self, pr_url: str) -> bool:
        """
        Check if PR can be merged.
        
        Args:
            pr_url: GitHub PR URL
            
        Returns:
            True if PR is mergeable
        """
        status = self.get_pr_status(pr_url)
        
        if not status:
            return False
        
        # PR must be approved, not have outstanding change requests, and be mergeable
        return (
            status.state == PRState.APPROVED and
            status.review_status == ReviewStatus.APPROVED and
            status.mergeable is True
        )
    
    def merge_pr(self, pr_url: str, merge_method: str = "squash") -> Dict[str, Any]:
        """
        Merge the PR.
        
        Args:
            pr_url: GitHub PR URL
            merge_method: squash, merge, or rebase
            
        Returns:
            Dict with merge result
        """
        pr_info = self._parse_pr_url(pr_url)
        if not pr_info:
            return {"success": False, "error": "Invalid PR URL"}
        
        repo = pr_info.get("repo", self.default_repo)
        pr_number = pr_info["pr_number"]
        
        # Check if mergeable first
        if not self.is_mergeable(pr_url):
            return {"success": False, "error": "PR is not mergeable"}
        
        # Attempt merge via GitHub API
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/merge"
        
        try:
            data = json.dumps({
                "merge_method": merge_method
            }).encode("utf-8")
            
            req = urllib.request.Request(url, data=data, method="PUT")
            req.add_header("Authorization", f"token {self.github_token}")
            req.add_header("Accept", "application/vnd.github.v3+json")
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "Juggernaut-PRTracker")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                
                # Update tracking record
                self._update_tracking_state(repo, pr_number, PRState.MERGED)
                
                return {
                    "success": True,
                    "sha": result.get("sha"),
                    "merged": result.get("merged"),
                    "message": result.get("message")
                }
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            return {"success": False, "error": f"HTTP {e.code}: {error_body}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def sync_all_tracked_prs(self) -> List[Dict[str, Any]]:
        """
        Update status of all tracked PRs.
        
        Returns:
            List of PRs that changed state
        """
        # Get all active (non-merged, non-closed) tracked PRs
        query = """
            SELECT id, task_id, repo, pr_number, current_state, review_status
            FROM pr_tracking
            WHERE current_state NOT IN ('merged', 'closed')
            ORDER BY updated_at ASC
            LIMIT 50;
        """
        
        result = query_db(query)
        tracked_prs = result.get("rows", [])
        
        changed_prs = []
        
        for pr in tracked_prs:
            repo = pr.get("repo")
            pr_number = pr.get("pr_number")
            old_state = pr.get("current_state")
            old_review_status = pr.get("review_status")
            task_id = pr.get("task_id")
            
            # Fetch current status
            pr_url = f"https://github.com/{repo}/pull/{pr_number}"
            status = self.get_pr_status(pr_url)
            
            if not status:
                continue
            
            new_state = status.state.value
            new_review_status = status.review_status.value
            
            # Check if state changed
            if new_state != old_state or new_review_status != old_review_status:
                # Update tracking record
                self._update_tracking_state(repo, pr_number, status.state, status)
                
                # Update task metadata
                if task_id:
                    self._update_task_pr_metadata(task_id, status)
                    
                    # Attempt to advance gates if PR progressed
                    if self._should_advance_gate(old_state, new_state):
                        self._try_advance_task_gate(task_id)
                
                change_record = {
                    "repo": repo,
                    "pr_number": pr_number,
                    "task_id": task_id,
                    "old_state": old_state,
                    "new_state": new_state,
                    "old_review_status": old_review_status,
                    "new_review_status": new_review_status
                }
                
                # If changes were requested, try Aider review iteration
                if new_state == "changes_requested" and old_state != "changes_requested":
                    aider_result = self._try_aider_review_iteration(
                        task_id, repo, pr_number, status
                    )
                    if aider_result:
                        change_record["aider_iteration"] = aider_result
                
                # Auto-merge if approved and auto-generated
                if new_state == "approved" and old_state != "approved":
                    from core.pr_tracker_auto_merge import try_auto_merge
                    merge_result = try_auto_merge(
                        task_id, repo, pr_number, status,
                        self.execute_sql, self.log_action
                    )
                    if merge_result:
                        change_record["auto_merged"] = merge_result
                
                changed_prs.append(change_record)
        
        return changed_prs
    
    def get_tracked_prs_for_task(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get all tracked PRs for a task.
        
        Args:
            task_id: The governance task ID
            
        Returns:
            List of tracked PR records
        """
        query = f"""
            SELECT id, repo, pr_number, pr_url, current_state, 
                   review_status, mergeable, merged_at, created_at, updated_at
            FROM pr_tracking
            WHERE task_id = '{task_id}'::uuid
            ORDER BY created_at DESC;
        """
        
        result = query_db(query)
        return result.get("rows", [])
    
    # =========================================================================
    # AIDER REVIEW ITERATION
    # =========================================================================
    
    MAX_REVIEW_ITERATIONS = int(os.getenv("MAX_REVIEW_ITERATIONS", "3"))
    
    def _try_aider_review_iteration(
        self,
        task_id: str,
        repo: str,
        pr_number: int,
        status: PRStatus,
    ) -> Optional[Dict[str, Any]]:
        """
        When a PR gets changes_requested, fetch review comments and
        re-run Aider to address them.
        
        Returns result dict or None if Aider is unavailable.
        """
        try:
            from core.aider_executor import AiderExecutor, is_aider_available
            
            if not is_aider_available():
                print(f"[PR_TRACKER] Aider not available for review iteration on PR #{pr_number}")
                return None
            
            # Check iteration count to prevent infinite loops
            iteration_count = self._get_review_iteration_count(repo, pr_number)
            if iteration_count >= self.MAX_REVIEW_ITERATIONS:
                print(
                    f"[PR_TRACKER] PR #{pr_number} hit max review iterations "
                    f"({self.MAX_REVIEW_ITERATIONS}), skipping Aider re-run"
                )
                return {"skipped": True, "reason": "max_iterations_reached", "count": iteration_count}
            
            # Fetch review comments from GitHub
            review_comments = self._fetch_review_comments(repo, pr_number)
            if not review_comments:
                print(f"[PR_TRACKER] No actionable review comments for PR #{pr_number}")
                return None
            
            # Get the branch name from PR data
            pr_data = self._github_request(f"/repos/{repo}/pulls/{pr_number}")
            if not pr_data:
                return None
            branch = pr_data.get("head", {}).get("ref")
            if not branch:
                return None
            
            # Get changed files for targeted Aider run
            files_data = self._github_request(f"/repos/{repo}/pulls/{pr_number}/files") or []
            target_files = [f.get("filename") for f in files_data if f.get("filename")]
            
            print(
                f"[PR_TRACKER] Running Aider review iteration #{iteration_count + 1} "
                f"on PR #{pr_number} ({len(review_comments)} comments, {len(target_files)} files)"
            )
            
            # Run Aider with review feedback
            aider = AiderExecutor()
            result = aider.run_with_review_feedback(
                repo=repo,
                branch=branch,
                review_comments=review_comments,
                task_id=task_id,
                target_files=target_files[:10] if target_files else None,
            )
            
            # Record the iteration
            self._record_review_iteration(repo, pr_number, iteration_count + 1, result.success)
            
            return {
                "success": result.success,
                "iteration": iteration_count + 1,
                "files_changed": result.files_changed,
                "error": result.error,
            }
            
        except ImportError:
            return None
        except Exception as e:
            print(f"[PR_TRACKER] Aider review iteration error: {e}")
            return {"success": False, "error": str(e)}
    
    def _fetch_review_comments(self, repo: str, pr_number: int) -> str:
        """
        Fetch all review comments from a PR and format them for Aider.
        
        Returns a formatted string of review feedback, or empty string.
        """
        # Get review comments (inline)
        comments = self._github_request(f"/repos/{repo}/pulls/{pr_number}/comments") or []
        # Get issue-level comments 
        issue_comments = self._github_request(f"/repos/{repo}/issues/{pr_number}/comments") or []
        # Get reviews with bodies
        reviews = self._github_request(f"/repos/{repo}/pulls/{pr_number}/reviews") or []
        
        feedback_parts = []
        
        # Process review-level feedback (e.g., CodeRabbit summary)
        for review in reviews:
            state = (review.get("state") or "").upper()
            body = (review.get("body") or "").strip()
            reviewer = review.get("user", {}).get("login", "unknown")
            
            if state == "CHANGES_REQUESTED" and body:
                feedback_parts.append(f"## Review by {reviewer} (changes requested):\n{body}")
        
        # Process inline code comments
        for comment in comments:
            body = (comment.get("body") or "").strip()
            path = comment.get("path", "")
            line = comment.get("line") or comment.get("original_line", "")
            reviewer = comment.get("user", {}).get("login", "unknown")
            
            if body:
                location = f" ({path}:{line})" if path else ""
                feedback_parts.append(f"- {reviewer}{location}: {body}")
        
        # Process issue-level comments from CodeRabbit (usually summaries)
        for comment in issue_comments:
            body = (comment.get("body") or "").strip()
            reviewer = comment.get("user", {}).get("login", "unknown")
            
            if reviewer.lower() in ("coderabbitai", "coderabbit[bot]") and body:
                # Truncate long CodeRabbit summaries
                if len(body) > 2000:
                    body = body[:2000] + "\n... (truncated)"
                feedback_parts.append(f"## CodeRabbit feedback:\n{body}")
        
        return "\n\n".join(feedback_parts)
    
    def _get_review_iteration_count(self, repo: str, pr_number: int) -> int:
        """Get how many review iterations have been run for this PR."""
        try:
            result = query_db(
                f"SELECT COALESCE((metadata->>'review_iterations')::int, 0) as count "
                f"FROM pr_tracking WHERE repo = '{repo}' AND pr_number = {pr_number}"
            )
            rows = result.get("rows", [])
            return int((rows[0] or {}).get("count", 0)) if rows else 0
        except Exception:
            return 0
    
    def _record_review_iteration(self, repo: str, pr_number: int, iteration: int, success: bool) -> None:
        """Record that a review iteration was performed."""
        try:
            meta = json.dumps({"review_iterations": iteration, "last_iteration_success": success})
            query_db(
                f"UPDATE pr_tracking "
                f"SET metadata = COALESCE(metadata, '{{}}'::jsonb) || "
                f"'{meta}'::jsonb, "
                f"updated_at = NOW() "
                f"WHERE repo = '{repo}' AND pr_number = {pr_number}"
            )
        except Exception as e:
            print(f"[PR_TRACKER] Error recording review iteration: {e}")
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _parse_pr_url(self, pr_url: str) -> Optional[Dict[str, Any]]:
        """Parse PR URL or number into components."""
        if not pr_url:
            return None
        
        # Handle just a number
        if str(pr_url).isdigit():
            return {"pr_number": int(pr_url), "repo": self.default_repo}
        
        # Parse full URL
        match = re.search(r'github\.com/([^/]+/[^/]+)/pull/(\d+)', pr_url)
        if match:
            return {
                "repo": match.group(1),
                "pr_number": int(match.group(2))
            }
        
        # Try to extract just the number
        num_match = re.search(r'#?(\d+)', pr_url)
        if num_match:
            return {"pr_number": int(num_match.group(1)), "repo": self.default_repo}
        
        return None
    
    def _github_request(self, endpoint: str) -> Optional[Any]:
        """Make a GitHub API request."""
        if not self.github_token:
            print("[PR_TRACKER] No GitHub token configured")
            return None
        
        url = f"https://api.github.com{endpoint}"
        
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"token {self.github_token}")
            req.add_header("Accept", "application/vnd.github.v3+json")
            req.add_header("User-Agent", "Juggernaut-PRTracker")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"[PR_TRACKER] GitHub API error: {e.code} for {endpoint}")
            return None
        except Exception as e:
            print(f"[PR_TRACKER] GitHub request error: {e}")
            return None
    
    def _analyze_reviews(self, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze PR reviews to determine approval status."""
        approvals = []
        changes_requested_by = []
        coderabbit_approved = False
        
        # Track latest review state per reviewer
        latest_by_reviewer = {}
        
        for review in reviews:
            reviewer = review.get("user", {}).get("login", "unknown")
            state = review.get("state", "").upper()
            submitted_at = review.get("submitted_at", "")
            
            if reviewer not in latest_by_reviewer or submitted_at > latest_by_reviewer[reviewer]["submitted_at"]:
                latest_by_reviewer[reviewer] = {
                    "state": state,
                    "submitted_at": submitted_at
                }
        
        # Process latest review per reviewer
        for reviewer, data in latest_by_reviewer.items():
            state = data["state"]
            
            if state == "APPROVED":
                approvals.append({
                    "reviewer": reviewer,
                    "submitted_at": data["submitted_at"]
                })
                
                # Check for CodeRabbit
                if reviewer.lower() in ["coderabbitai", "coderabbit", "coderabbit[bot]"]:
                    coderabbit_approved = True
                    
            elif state == "CHANGES_REQUESTED":
                changes_requested_by.append(reviewer)
        
        # Determine overall status
        if changes_requested_by:
            status = ReviewStatus.CHANGES_REQUESTED
        elif approvals:
            status = ReviewStatus.APPROVED
        else:
            status = ReviewStatus.PENDING
        
        return {
            "status": status,
            "approvals": approvals,
            "changes_requested_by": changes_requested_by,
            "coderabbit_approved": coderabbit_approved
        }
    
    def _determine_pr_state(self, pr_data: Dict[str, Any], review_analysis: Dict[str, Any]) -> PRState:
        """Determine the overall PR state."""
        # Check if merged
        if pr_data.get("merged"):
            return PRState.MERGED
        
        # Check if closed without merge
        if pr_data.get("state") == "closed":
            return PRState.CLOSED
        
        # Check review status
        if review_analysis["changes_requested_by"]:
            return PRState.CHANGES_REQUESTED
        
        if review_analysis["status"] == ReviewStatus.APPROVED:
            return PRState.APPROVED
        
        # Check if reviewers assigned
        requested_reviewers = pr_data.get("requested_reviewers", [])
        requested_teams = pr_data.get("requested_teams", [])
        
        if requested_reviewers or requested_teams or review_analysis["approvals"]:
            return PRState.REVIEW_REQUESTED
        
        return PRState.CREATED
    
    def _update_tracking_state(
        self, 
        repo: str, 
        pr_number: int, 
        state: PRState,
        status: Optional[PRStatus] = None
    ) -> None:
        """Update tracking record state."""
        merged_at_sql = "NULL"
        review_status = "pending"
        
        if status:
            if status.merged_at:
                merged_at_sql = f"'{status.merged_at}'"
            review_status = status.review_status.value
        
        query = f"""
            UPDATE pr_tracking
            SET current_state = '{state.value}',
                review_status = '{review_status}',
                merged_at = {merged_at_sql},
                updated_at = NOW()
            WHERE repo = '{repo}' AND pr_number = {pr_number};
        """
        
        try:
            query_db(query)
        except Exception as e:
            print(f"[PR_TRACKER] Error updating tracking state: {e}")
    
    def _update_task_pr_metadata(self, task_id: str, status: PRStatus) -> None:
        """Update task metadata with PR information."""
        metadata_update = {
            "pr_number": status.pr_number,
            "pr_url": status.url,
            "pr_state": status.state.value,
            "pr_review_status": status.review_status.value,
            "pr_coderabbit_approved": status.coderabbit_approved,
            "pr_merged_at": status.merged_at,
            "pr_merge_commit_sha": status.merge_commit_sha,
            "pr_updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        metadata_json = json.dumps(metadata_update).replace("'", "''")
        
        query = f"""
            UPDATE governance_tasks
            SET metadata = COALESCE(metadata, '{{}}'::jsonb) || '{metadata_json}'::jsonb
            WHERE id = '{task_id}'::uuid;
        """
        
        try:
            query_db(query)
        except Exception as e:
            print(f"[PR_TRACKER] Error updating task metadata: {e}")
    
    def _should_advance_gate(self, old_state: str, new_state: str) -> bool:
        """Determine if gate should be advanced based on state change."""
        # Define state progression
        state_order = {
            "created": 1,
            "review_requested": 2,
            "changes_requested": 2,  # Same level as review_requested
            "approved": 3,
            "merged": 4,
            "closed": 0  # Terminal state, don't advance
        }
        
        old_order = state_order.get(old_state, 0)
        new_order = state_order.get(new_state, 0)
        
        # Advance if progressing forward (not to closed)
        return new_order > old_order and new_state != "closed"
    
    def _try_advance_task_gate(self, task_id: str) -> None:
        """Try to advance task verification gate."""
        try:
            from core.gate_checker import GateChecker
            
            checker = GateChecker()
            advanced, next_gate, result = checker.advance_gate(task_id)
            
            if advanced:
                print(f"[PR_TRACKER] Advanced task {task_id} to gate: {next_gate}")
            else:
                print(f"[PR_TRACKER] Task {task_id} gate not ready: {result.reason if result else 'unknown'}")
                
        except Exception as e:
            print(f"[PR_TRACKER] Error advancing gate: {e}")


# =========================================================================
# CONVENIENCE FUNCTIONS
# =========================================================================

def track_pr_for_task(task_id: str, pr_url: str) -> Optional[Dict[str, Any]]:
    """Start tracking a PR for a task."""
    tracker = PRTracker()
    return tracker.track_pr(task_id, pr_url)


def get_pr_status(pr_url: str) -> Optional[PRStatus]:
    """Get current PR status."""
    tracker = PRTracker()
    return tracker.get_pr_status(pr_url)


def sync_tracked_prs() -> List[Dict[str, Any]]:
    """Sync all tracked PRs and return changes."""
    tracker = PRTracker()
    return tracker.sync_all_tracked_prs()


def is_pr_mergeable(pr_url: str) -> bool:
    """Check if a PR is mergeable."""
    tracker = PRTracker()
    return tracker.is_mergeable(pr_url)


def merge_pr(pr_url: str, method: str = "squash") -> Dict[str, Any]:
    """Merge a PR."""
    tracker = PRTracker()
    return tracker.merge_pr(pr_url, method)
