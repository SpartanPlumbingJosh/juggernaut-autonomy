"""
GitHub Automation Module for JUGGERNAUT

Provides programmatic GitHub operations for autonomous PR workflows.
Uses GitHub REST API for branch management, commits, PRs, and merges.
"""

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# Configure module logger
logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY_SECONDS = 2
GITHUB_API_BASE = "https://api.github.com"


class GitHubError(Exception):
    """Base exception for GitHub operations."""
    pass


class GitHubAuthError(GitHubError):
    """Authentication error."""
    pass


class GitHubRateLimitError(GitHubError):
    """Rate limit exceeded."""
    pass


class GitHubConflictError(GitHubError):
    """Merge conflict or resource conflict."""
    pass


@dataclass
class PRStatus:
    """Pull request status information."""
    number: int
    state: str
    mergeable: Optional[bool]
    mergeable_state: str
    reviews_approved: int
    reviews_pending: int
    checks_passed: bool
    url: str


class GitHubClient:
    """
    Client for GitHub API operations.
    
    Handles authentication, retries, and error handling for
    common GitHub operations needed for autonomous development.
    """
    
    def __init__(
        self,
        repo: Optional[str] = None,
        token: Optional[str] = None,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS
    ):
        """
        Initialize GitHub client.
        
        Args:
            repo: Repository in "owner/repo" format. Defaults to GITHUB_REPO env var.
            token: GitHub personal access token. Defaults to GITHUB_TOKEN env var.
            retry_attempts: Number of retry attempts for failed requests.
            retry_delay: Delay between retries in seconds.
        """
        self.repo = repo or (os.getenv("GITHUB_REPO") or "").strip()
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay

        if not self.repo:
            raise ValueError("GITHUB_REPO is required (or pass repo=...) for GitHubClient")
        self._default_branch: Optional[str] = None
        
        if not self.token:
            logger.warning("No GITHUB_TOKEN found - API calls may fail")
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Make an authenticated request to GitHub API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint path (without base URL).
            data: Request body data (will be JSON encoded).
            headers: Additional headers.
            
        Returns:
            Tuple of (status_code, response_data).
            
        Raises:
            GitHubAuthError: If authentication fails.
            GitHubRateLimitError: If rate limit exceeded.
            GitHubError: For other API errors.
        """
        url = f"{GITHUB_API_BASE}{endpoint}"
        
        request_headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Juggernaut-Autonomy"
        }
        
        if self.token:
            request_headers["Authorization"] = f"Bearer {self.token}"
        
        if headers:
            request_headers.update(headers)
        
        body = None
        if data:
            body = json.dumps(data).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        
        last_error = None
        
        for attempt in range(self.retry_attempts):
            try:
                req = urllib.request.Request(
                    url,
                    data=body,
                    headers=request_headers,
                    method=method
                )
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    response_body = response.read().decode("utf-8")
                    if response_body:
                        return response.status, json.loads(response_body)
                    return response.status, {}
                    
            except urllib.error.HTTPError as e:
                status = e.code
                try:
                    error_body = json.loads(e.read().decode("utf-8"))
                except (json.JSONDecodeError, AttributeError):
                    error_body = {"message": str(e)}
                
                if status == 401:
                    raise GitHubAuthError(
                        f"Authentication failed: {error_body.get('message', 'Unknown')}"
                    )
                elif status == 403 and "rate limit" in str(error_body).lower():
                    raise GitHubRateLimitError(
                        f"Rate limit exceeded: {error_body.get('message', 'Unknown')}"
                    )
                elif status == 409:
                    raise GitHubConflictError(
                        f"Conflict: {error_body.get('message', 'Unknown')}"
                    )
                elif status >= 500:
                    last_error = GitHubError(
                        f"Server error {status}: {error_body.get('message', 'Unknown')}"
                    )
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    return status, error_body
                    
            except urllib.error.URLError as e:
                last_error = GitHubError(f"Connection error: {e}")
                time.sleep(self.retry_delay * (attempt + 1))
                continue
        
        if last_error:
            raise last_error
        raise GitHubError("Max retries exceeded")
    
    def get_default_branch(self) -> str:
        """
        Get the default branch name for the repository.
        
        Returns:
            Default branch name (e.g., "main" or "master").
            
        Raises:
            GitHubError: If repo not found or API error.
        """
        if self._default_branch:
            return self._default_branch
        
        status, data = self._make_request(
            "GET",
            f"/repos/{self.repo}"
        )
        
        if status == 200:
            self._default_branch = data.get("default_branch", "main")
            logger.info(f"Default branch for {self.repo}: {self._default_branch}")
            return self._default_branch
        elif status == 404:
            raise GitHubError(f"Repository '{self.repo}' not found")
        else:
            raise GitHubError(f"Failed to get repo info: {data.get('message', 'Unknown')}")
    
    def get_main_sha(self, branch: Optional[str] = None) -> str:
        """
        Get the SHA of the latest commit on a branch.
        
        Args:
            branch: Branch name. Defaults to the repo's default branch.
            
        Returns:
            Commit SHA string.
            
        Raises:
            GitHubError: If branch not found or API error.
        """
        used_default = False
        if branch is None:
            branch = self.get_default_branch()
            used_default = True
        
        status, data = self._make_request(
            "GET",
            f"/repos/{self.repo}/git/ref/heads/{branch}"
        )
        
        if status == 200:
            return data["object"]["sha"]
        elif status == 404:
            # If the repo's default branch changed (or we cached a stale value), refresh and retry.
            if used_default:
                try:
                    self._default_branch = None
                    refreshed = self.get_default_branch()
                    if refreshed and refreshed != branch:
                        status2, data2 = self._make_request(
                            "GET",
                            f"/repos/{self.repo}/git/ref/heads/{refreshed}"
                        )
                        if status2 == 200:
                            return data2["object"]["sha"]
                except Exception:
                    pass

                # Conservative fallback for repos that still use master.
                fallback = "master" if branch == "main" else "main"
                try:
                    status3, data3 = self._make_request(
                        "GET",
                        f"/repos/{self.repo}/git/ref/heads/{fallback}"
                    )
                    if status3 == 200:
                        self._default_branch = fallback
                        logger.info(f"Default branch fallback for {self.repo}: {fallback}")
                        return data3["object"]["sha"]
                except Exception:
                    pass

            raise GitHubError(f"Branch '{branch}' not found")
        else:
            raise GitHubError(f"Failed to get branch SHA: {data.get('message', 'Unknown')}")
    
    def create_branch(self, name: str, from_sha: Optional[str] = None) -> bool:
        """
        Create a new branch from a commit SHA.
        
        Args:
            name: New branch name (without refs/heads/ prefix).
            from_sha: Base commit SHA. Defaults to default branch HEAD.
            
        Returns:
            True if branch created successfully.
            
        Raises:
            GitHubError: If branch creation fails.
        """
        if from_sha is None:
            from_sha = self.get_main_sha()
        
        status, data = self._make_request(
            "POST",
            f"/repos/{self.repo}/git/refs",
            {"ref": f"refs/heads/{name}", "sha": from_sha}
        )
        
        if status == 201:
            logger.info(f"Created branch '{name}' from SHA {from_sha[:8]}")
            return True
        elif status == 422 and "already exists" in str(data).lower():
            logger.warning(f"Branch '{name}' already exists")
            return True
        else:
            raise GitHubError(f"Failed to create branch: {data.get('message', 'Unknown')}")
    
    def get_file_sha(self, path: str, branch: Optional[str] = None) -> Optional[str]:
        """
        Get the SHA of a file for update operations.
        
        Args:
            path: File path in repository.
            branch: Branch to check. Defaults to default branch.
            
        Returns:
            File SHA if exists, None if file doesn't exist.
        """
        if branch is None:
            branch = self.get_default_branch()
        
        status, data = self._make_request(
            "GET",
            f"/repos/{self.repo}/contents/{path}?ref={branch}"
        )
        
        if status == 200:
            return data.get("sha")
        return None
    
    def commit_file(
        self,
        branch: str,
        path: str,
        content: str,
        message: str,
        encoding: str = "utf-8"
    ) -> bool:
        """
        Commit a file to a branch.
        
        Args:
            branch: Target branch name.
            path: File path in repository.
            content: File content (string).
            message: Commit message.
            encoding: Content encoding.
            
        Returns:
            True if commit successful.
            
        Raises:
            GitHubError: If commit fails.
        """
        encoded_content = base64.b64encode(content.encode(encoding)).decode("ascii")
        existing_sha = self.get_file_sha(path, branch)
        
        request_data = {
            "message": message,
            "content": encoded_content,
            "branch": branch
        }
        
        if existing_sha:
            request_data["sha"] = existing_sha
        
        status, data = self._make_request(
            "PUT",
            f"/repos/{self.repo}/contents/{path}",
            request_data
        )
        
        if status in (200, 201):
            commit_sha = data.get("commit", {}).get("sha", "unknown")[:8]
            logger.info(f"Committed {path} to {branch} (commit: {commit_sha})")
            return True
        else:
            raise GitHubError(f"Failed to commit file: {data.get('message', 'Unknown')}")
    
    def create_pr(
        self,
        branch: str,
        title: str,
        body: str,
        base: Optional[str] = None,
        draft: bool = False
    ) -> int:
        """
        Create a pull request.
        
        Args:
            branch: Head branch (source).
            title: PR title.
            body: PR description.
            base: Base branch (target). Defaults to repo's default branch.
            draft: Create as draft PR.
            
        Returns:
            PR number.
            
        Raises:
            GitHubError: If PR creation fails.
        """
        if base is None:
            base = self.get_default_branch()
        
        status, data = self._make_request(
            "POST",
            f"/repos/{self.repo}/pulls",
            {
                "title": title,
                "body": body,
                "head": branch,
                "base": base,
                "draft": draft
            }
        )
        
        if status == 201:
            pr_number = data["number"]
            logger.info(f"Created PR #{pr_number}: {title}")
            return pr_number
        elif status == 422 and "already exists" in str(data).lower():
            existing_prs = self.list_prs(state="open", head=branch)
            if existing_prs:
                return existing_prs[0]["number"]
            raise GitHubError("PR exists but couldn't find it")
        else:
            raise GitHubError(f"Failed to create PR: {data.get('message', 'Unknown')}")
    
    def list_prs(
        self,
        state: str = "open",
        head: Optional[str] = None,
        base: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List pull requests.
        
        Args:
            state: PR state filter (open, closed, all).
            head: Filter by head branch.
            base: Filter by base branch.
            
        Returns:
            List of PR dictionaries.
        """
        params = [f"state={state}"]
        if head:
            params.append(f"head={self.repo.split('/')[0]}:{head}")
        if base:
            params.append(f"base={base}")
        
        query = "&".join(params)
        status, data = self._make_request(
            "GET",
            f"/repos/{self.repo}/pulls?{query}"
        )
        
        if status == 200:
            return data if isinstance(data, list) else []
        return []
    
    def get_pr_status(self, pr_number: int) -> PRStatus:
        """
        Get detailed PR status including review and check status.
        
        Args:
            pr_number: Pull request number.
            
        Returns:
            PRStatus object with current state.
            
        Raises:
            GitHubError: If PR not found or API error.
        """
        status, pr_data = self._make_request(
            "GET",
            f"/repos/{self.repo}/pulls/{pr_number}"
        )
        
        if status != 200:
            raise GitHubError(f"PR #{pr_number} not found")
        
        _, reviews_data = self._make_request(
            "GET",
            f"/repos/{self.repo}/pulls/{pr_number}/reviews"
        )
        
        reviews = reviews_data if isinstance(reviews_data, list) else []
        approved = sum(1 for r in reviews if r.get("state") == "APPROVED")
        pending = sum(1 for r in reviews if r.get("state") == "PENDING")
        
        head_sha = pr_data.get("head", {}).get("sha", "")
        checks_passed = True
        
        if head_sha:
            _, checks_data = self._make_request(
                "GET",
                f"/repos/{self.repo}/commits/{head_sha}/check-runs"
            )
            check_runs = checks_data.get("check_runs", [])
            for check in check_runs:
                conclusion = check.get("conclusion")
                if conclusion not in (None, "success", "skipped", "neutral"):
                    checks_passed = False
                    break
        
        return PRStatus(
            number=pr_number,
            state=pr_data.get("state", "unknown"),
            mergeable=pr_data.get("mergeable"),
            mergeable_state=pr_data.get("mergeable_state", "unknown"),
            reviews_approved=approved,
            reviews_pending=pending,
            checks_passed=checks_passed,
            url=pr_data.get("html_url", "")
        )
    
    def merge_pr(
        self,
        pr_number: int,
        method: str = "squash",
        commit_title: Optional[str] = None
    ) -> bool:
        """
        Merge a pull request.
        
        Args:
            pr_number: Pull request number.
            method: Merge method (merge, squash, rebase).
            commit_title: Custom commit title for squash/merge.
            
        Returns:
            True if merge successful.
            
        Raises:
            GitHubConflictError: If PR cannot be merged.
            GitHubError: For other errors.
        """
        data = {"merge_method": method}
        if commit_title:
            data["commit_title"] = commit_title
        
        status, response = self._make_request(
            "PUT",
            f"/repos/{self.repo}/pulls/{pr_number}/merge",
            data
        )
        
        if status == 200:
            logger.info(f"Merged PR #{pr_number} via {method}")
            return True
        elif status == 405:
            raise GitHubConflictError(
                f"PR #{pr_number} cannot be merged: {response.get('message', 'Unknown')}"
            )
        elif status == 409:
            raise GitHubConflictError(f"Merge conflict on PR #{pr_number}")
        else:
            raise GitHubError(f"Failed to merge PR: {response.get('message', 'Unknown')}")
    
    def close_pr(self, pr_number: int) -> bool:
        """
        Close a pull request without merging.
        
        Args:
            pr_number: Pull request number.
            
        Returns:
            True if closed successfully.
        """
        status, _ = self._make_request(
            "PATCH",
            f"/repos/{self.repo}/pulls/{pr_number}",
            {"state": "closed"}
        )
        
        return status == 200
    
    def delete_branch(self, branch: str) -> bool:
        """
        Delete a branch.
        
        Args:
            branch: Branch name to delete.
            
        Returns:
            True if deleted or doesn't exist.
        """
        status, _ = self._make_request(
            "DELETE",
            f"/repos/{self.repo}/git/refs/heads/{branch}"
        )
        
        return status in (204, 404)


def get_client() -> GitHubClient:
    """Get a configured GitHub client."""
    return GitHubClient()


def create_feature_branch(name: str) -> bool:
    """Create a feature branch from main."""
    return get_client().create_branch(name)


def commit_and_pr(
    branch: str,
    files: Dict[str, str],
    pr_title: str,
    pr_body: str,
    commit_prefix: str = "feat"
) -> int:
    """
    Commit multiple files and create a PR in one operation.
    
    Args:
        branch: Branch name to create/use.
        files: Dict of {path: content} for files to commit.
        pr_title: PR title.
        pr_body: PR description.
        commit_prefix: Conventional commit prefix.
        
    Returns:
        PR number.
    """
    client = get_client()
    client.create_branch(branch)
    
    for path, content in files.items():
        filename = path.split("/")[-1]
        client.commit_file(
            branch=branch,
            path=path,
            content=content,
            message=f"{commit_prefix}: add {filename}"
        )
    
    return client.create_pr(branch, pr_title, pr_body)


__all__ = [
    "GitHubClient",
    "GitHubError",
    "GitHubAuthError",
    "GitHubRateLimitError",
    "GitHubConflictError",
    "PRStatus",
    "get_client",
    "create_feature_branch",
    "commit_and_pr",
]
