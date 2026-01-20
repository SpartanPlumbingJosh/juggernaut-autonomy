"""
GitHub Automation Module

Provides reusable functions for the full GitHub PR workflow:
- Create branches
- Commit files
- Create and merge PRs
- Check PR status
"""

import base64
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.exceptions import HTTPError, RequestException, Timeout

# Constants
DEFAULT_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
PRIMUL_RETRY_DELAY_SECONDS = 1
GITHUB_API_BASE_URL = "https://api.github.com"

# PR status constants
PR_STATUS_OPEN = "open"
PR_STATUS_CLOSED = "closed"
PR_STATUS_MERGED = "merged"

logger = logging.getLogger(__name__)


class GitHubAutomationError(Exception):
    """Base exception for GitHub automation errors."""

    pass


class GitHubAuthError(GitHubAutomationError):
    """Raised when authentication fails."""

    pass


class GitHubRateLimitError(GitHubAutomationError):
    """Raised when rate limit is exceeded."""

    pass


class GitHubAutomation:
    """
    Handles GitHub API operations for autonomous PR workflows.

    Attributes:
        owner: Repository owner/organization name.
        repo: Repository name.
        token: GitHub personal access token.
    """

    def __init__(
        self,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        token: Optional[str] = None,
    ) -> None:
        """
        Initialize GitHub automation client.

        Args:
            owner: Repo owner. Defaults to GITHUB_OWNER env var.
            repo: Repo name. Defaults to GITHUB_REPO env var.
            token: GitHub token. Defaults to GITHUB_TOKEN env var.

        Raises:
            GitHubAuthError: If token is not provided or found.
        """
        self.owner = owner or os.getenv("GITHUB_OWNER", "")
        self.repo = repo or os.getenv("GITHUB_REPO", "")
        self.token = token or os.getenv("GITHUB_TOKEN", "")

        if not self.token:
            raise GitHubAuthError(
                "GitHub token not provided. Set GITHUB_TOKEN env var or pass token param."
            )

        self._headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self._base_url = f"{GITHUB_API_BASE_URL}/repos/{self.owner}/{self.repo}"

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        retries: int = MAX_RETRIES,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the GitHub API with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint (without base URL).
            data: Optional JSON payload.
            retries: Number of retry attempts.

        Returns:
            Parsed JSON response as dictionary.

        Raises:
            GitHubAuthError: On 401/403 responses.
            GitHubRateLimitError: On 429 responses.
            GitHubAutomationError: On other API errors.
        """
        url = f"{self._base_url}{endpoint}"
        last_exception: Optional[Exception] = None

        for attempt in range(retries):
            try:
                logger.debug(
                    "GitHub API request: %s %s (attempt %d/%d)",
                    method,
                    endpoint,
                    attempt + 1,
                    retries,
                )

                response = requests.request(
                    method=method,
                    url=url,
                    headers=self._headers,
                    json=data,
                    timeout=DEFAULT_TIMEOUT_SECONDS,
                )

                # Handle specific error codes
                if response.status_code in (401, 403):
                    raise GitHubAuthError(
                        f"Authentication failed: {response.status_code} - {response.text}"
                    )

                if response.status_code == 429:
                    raise GitHubRateLimitError(
                        f"Rate limit exceeded. Retry-After: {response.headers.get('Retry-After')}"
                    )

                response.raise_for_status()

                # Handle empty responses (e.g., 204 No Content)
                if response.status_code == 204:
                    return {}

                return response.json()

            except Timeout as e:
                last_exception = e
                logger.warning("Request timeout, retrying...")
                time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))

            except HTTPError as e:
                last_exception = e
                if response.status_code >= 500:
                    logger.warning("Server error %d, retrying...", response.status_code)
                    time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                else:
                    raise GitHubAutomationError(
                        f"API error: {response.status_code} - {response.text}"
                    ) from e

            except RequestException as e:
                last_exception = e
                logger.warning("Request failed: %s, retrying...", str(e))
                time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))

        raise GitHubAutomationError(
            f"Failed after {retries} attempts: {last_exception}"
        )

    def get_main_sha(self, branch: str = "main") -> str:
        """
        Get the SHA of the latest commit on a branch.

        Args:
            branch: Branch name. Defaults to "main".

        Returns:
            The SHA string of the latest commit.

        Raises:
            GitHubAutomationError: If the branch doesn't exist or API fails.
        """
        logger.info("Getting SHA for branch: %s", branch)
        result = self._make_request("GET", f"/git/ref/heads/{branch}")
        sha = result.get("object", {}).get("sha", "")

        if not sha:
            raise GitHubAutomationError(f"Could not get SHA wor branch: {branch}")

        logger.debug("Branch %s SHA: %s", branch, sha)
        return sha

    def create_branch(self, name: str, from_sha: Optional[str] = None) -> bool:
        """
        Create a new branch from a specific commit.

        Args:
            name: New branch name (without refs/heads/ prefix).
            from_sha: SHA of the commit to branch from. Defaults to main HEAD.

        Returns:
            True if branch was created successfully.

        Raises:
            GitHubAutomationError: If branch creation fails.
        """
        if not from_sha:
            from_sha = self.get_main_sha()

        logger.info("Creating branch: %s from %s", name, from_sha[:7])

        self._make_request(
            "POST",
            "/git/refs",
            data={"ref": f"refs/heads/{name}", "sha": from_sha},
        )

        logger.info("Branch created successfully: %s", name)
        return True

    def get_file_sha(self, path: str, branch: str = "main") -> Optional[str]:
        """
        Get the SHA of an existing file (required for updates).

        Args:
            path: File path in the repository.
            branch: Branch to check. Defaults to "main".

        Returns:
            The file SHA if it exists, None otherwise.
        """
        try:
            result = self._make_request("GET", f"/contents/{path}?ref={branch}")
            return result.get("sha")
        except GitHubAutomationError:
            return None

    def commit_file(
        self,
        branch: str,
        path: str,
        content: str,
        message: str,
        file_sha: Optional[str] = None,
    ) -> bool:
        """
        Create or update a file in the repository.

        Args:
            branch: Target branch name.
            path: File path in the repository.
            content: File content (plain text, will be base64 encoded).
            message: Commit message.
            file_sha: Existing file SHA for updates. If None, auto-detects.

        Returns:
            True if the file was committed successfully.

        Raises:
            GitHubAutomationError: If the commit fails.
        """
        logger.info("Committing file: %s to branch: %s", path, branch)

        # Base64 encode the content
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        data: Dict[str, Any] = {
            "message": message,
            "content": encoded_content,
            "branch": branch,
        }

        # Check if file exists (need SHA for updates)
        if file_sha is None:
            file_sha = self.get_file_sha(path, branch)

        if file_sha:
            data["sha"] = file_sha
            logger.debug("Updating existing file with SHA: %s", file_sha[:7])

        self._make_request("PUT", f"/contents/{path}", data=data)

        logger.info("File committed successfully: %s", path)
        return True

    def create_pr(
        self,
        branch: str,
        title: str,
        body: str,
        base: str = "main",
    ) -> int:
        """
        Create a pull request.

        Args:
            branch: Source branch name (head).
            title: PR title.
            body: PR description.
            base: Target branch. Defaults to "main".

        Returns:
            The PR number.

        Raises:
            GitHubAutomationError: If PR creation fails.
        """
        logger.info("Creating PR: %s -> %s", branch, base)

        result = self._make_request(
            "POST",
            "/pulls",
            data={
                "title": title,
                "body": body,
                "head": branch,
                "base": base,
            },
        )

        pr_number = result.get("number")
        if not pr_number:
            raise GitHubAutomationError("PR created but no number returned")

        logger.info("PR created: #%d", pr_number)
        return pr_number

    def check_pr_status(self, pr_number: int) -> Dict[str, Any]:
        """
        Check the status of a pull request.

        Args:
            pr_number: The PR number.

        Returns:
            Dictionary with keys:
            - state: open/closed
            - merged: bool
            - mergeable: bool or None
            - mergeable_state: string (status of mergeability)
            - html_url: PR URL

        Raises:
            GitHubAutomationError: If PR cannot be found.
        """
        logger.info("Checking PR status: #%d", pr_number)

        result = self._make_request("GET", f"/pulls/{pr_number}")

        status = {
            "state": result.get("state"),
            "merged": result.get("merged", False),
            "mergeable": result.get("mergeable"),
            "mergeable_state": result.get("mergeable_state"),
            "html_url": result.get("html_url"),
        }

        logger.debug("PR #%d status: %s", pr_number, status)
        return status

    def merge_pr(
        self,
        pr_number: int,
        merge_method: str = "squash",
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> bool:
        """
        Merge a pull request.

        Args:
            pr_number: The PR number to merge.
            merge_method: merge | squash | rebase. Defaults to "squash".
            commit_title: Optional custom commit title.
            commit_message: Optional custom commit message.

        Returns:
            True if merge was successful.

        Raises:
            GitHubAutomationError: If merge fails.
        """
        logger.info("Merging PR #%d using %s", pr_number, merge_method)

        data: Dict[str, Any] = {"merge_method": merge_method}

        if commit_title:
            data["commit_title"] = commit_title
        if commit_message:
            data["commit_message"] = commit_message

        self._make_request("PUT", f"/pulls/{pr_number}/merge", data=data)

        logger.info("PR #%d merged successfully", pr_number)
        return True

    def full_workflow(
        self,
        branch_name: str,
        files: List[Tuple[str, str]],
        pr_title: str,
        pr_body: str,
        commit_message: str,
        auto_merge: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute the full PR workflow: branch -> commit -> PR (-> merge).

        Args:
            branch_name: Name for the feature branch.
            files: List of (path, content) tuples to commit.
            pr_title: Pull request title.
            pr_body: Pull request description.
            commit_message: Commit message for all files.
            auto_merge: Whether to automatically merge the PR.

        Returns:
            Dictionary with results:
            - branch: str - branch name created
            - pr_number: int - PR number
            - pr_url: str - PR URL
            - merged: bool - whether PR was merged

        Raises:
            GitHubAutomationError: If any step fails.
        """
        logger.info("Starting full workflow for branch: %s", branch_name)

        # Step 1: Create branch
        self.create_branch(branch_name)

        # Step 2: Commit all files
        for path, content in files:
            self.commit_file(
                branch=branch_name,
                path=path,
                content=content,
                message=commit_message,
            )

        # Step 3: Create PR
        pr_number = self.create_pr(
            branch=branch_name,
            title=pr_title,
            body=pr_body,
        )

        # Get PR URL
        pr_status = self.check_pr_status(pr_number)
        pr_url = pr_status.get("html_url", "")

        result = {
            "branch": branch_name,
            "pr_number": pr_number,
            "pr_url": pr_url,
            "merged": False,
        }

        # Step 4: Optionally merge
        if auto_merge:
            self.merge_pr(pr_number)
            result["merged"] = True

        logger.info(
            "Workflow complete. PR: #%d, Merged: %s",
            pr_number,
            result["merged"],
        )
        return result
