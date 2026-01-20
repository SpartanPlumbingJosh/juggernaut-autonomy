"""
GitHub Automation Module Tests

Tests for the github_automation module, covering:
- Happy path scenarios
- Error handling and retries
- Edge cases
"""

import base64
import os
from unittest import TestCase
from unittest.mock import Mock, patch

import pytest

from src.github_automation import (
    GitHubAutomation,
    GitHubAuthError,
    GitHubAutomationError,
    GitHubRateLimitError,
)


class TestGitHubAutomationInit(TestCase):
    """Tests for GitHubAutomation initialization."""

    def test_init_with_token(self) -> None:
        """Test initialization with explicit token."""
        gh = GitHubAutomation(owner="test", repo="repo", token="test-token")
        assert gh.owner == "test"
        assert gh.repo == "repo"
        assert gh.token == "test-token"

    def test_init_missing_token_raises_error(self) -> None:
        """Test that missing token raises GitHubAuthError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(GitHubAuthError) as excinfo:
                GitHubAutomation(owner="test", repo="repo")
            assert "token not provided" in str(excinfo.value)

    def test_init_from_env_vars(self) -> None:
        """Test initialization from environment variables."""
        env_vars = {
            "GITHUB_OWNER": "env-owner",
            "GITHUB_REPO": "env-repo",
            "GITHUB_TOKEN": "env-token",
        }
        with patch.dict(os.environ, env_vars):
            gh = GitHubAutomation()
            assert gh.owner == "env-owner"
            assert gh.repo == "env-repo"
            assert gh.token == "env-token"


class TestGetMainSha(TestCase):
    """Tests for get_main_sha method."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.gh = GitHubAutomation(owner="test", repo="repo", token="token")

    @patch("requests.request")
    def test_get_main_sha_success(self, mock_request: Mock) -> None:
        """Test successful SHA retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": {"sha": "abc123def456"}
        }
        mock_request.return_value = mock_response

        sha = self.gh.get_main_sha()

        assert sha == "abc123def456"
        mock_request.assert_called_once()

    @patch("requests.request")
    def test_get_main_sha_custom_branch(self, mock_request: Mock) -> None:
        """Test SHA retrieval for custom branch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": {"sha": "develop-sha-789"}
        }
        mock_request.return_value = mock_response

        sha = self.gh.get_main_sha(branch="develop")

        assert sha == "develop-sha-789"
        call_args = mock_request.call_args
        assert "develop" in call_args.kwargs["url"]


class TestCreateBranch(TestCase):
    """Tests for create_branch method."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.gh = GitHubAutomation(owner="test", repo="repo", token="token")

    @patch("requests.request")
    def test_create_branch_success(self, mock_request: Mock) -> None:
        """Test successful branch creation."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "ref": "refs/heads/feature/new-branch"
        }
        mock_request.return_value = mock_response

        result = self.gh.create_branch(
            name="feature/new-branch",
            from_sha="abc123",
        )

        assert result is True


class TestCommitFile(TestCase):
    """Tests for commit_file method."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.gh = GitHubAutomation(owner="test", repo="repo", token="token")

    @patch("requests.request")
    def test_commit_file_new_file(self, mock_request: Mock) -> None:
        """Test committing a new file."""
        mock_file_not_found = Mock()
        mock_file_not_found.status_code = 404
        mock_file_not_found.raise_for_status.side_effect = Exception("Not found")

        mock_create_success = Mock()
        mock_create_success.status_code = 201
        mock_create_success.json.return_value = {"content": {"sha": "newsha"}}

        mock_request.side_effect = [mock_file_not_found, mock_create_success]

        result = self.gh.commit_file(
            branch="feature/test",
            path="test.py",
            content="print('hello')",
            message="Add test file",
        )

        assert result is True

    @patch("requests.request")
    def test_commit_file_update_existing(self, mock_request: Mock) -> None:
        """Test updating an existing file."""
        mock_file_exists = Mock()
        mock_file_exists.status_code = 200
        mock_file_exists.json.return_value = {"sha": "existingsha123"}

        mock_update_success = Mock()
        mock_update_success.status_code = 200
        mock_update_success.json.return_value = {"content": {"sha": "updatedsha"}}

        mock_request.side_effect = [mock_file_exists, mock_update_success]

        result = self.gh.commit_file(
            branch="feature/test",
            path="existing.py",
            content="updated content",
            message="Update file",
        )

        assert result is True


class TestCreatePR(TestCase):
    """Tests for create_pr method."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.gh = GitHubAutomation(owner="test", repo="repo", token="token")

    @patch("requests.request")
    def test_create_pr_success(self, mock_request: Mock) -> None:
        """Test successful PR creation."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "number": 42,
            "html_url": "https://github.com/test/repo/pull/42",
        }
        mock_request.return_value = mock_response

        pr_number = self.gh.create_pr(
            branch="feature/test",
            title="Test PR",
            body="This is a test",
        )

        assert pr_number == 42


class TestCheckPRStatus(TestCase):
    """Tests for check_pr_status method."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.gh = GitHubAutomation(owner="test", repo="repo", token="token")

    @patch("requests.request")
    def test_check_pr_status_open(self, mock_request: Mock) -> None:
        """Test checking status of an open PR."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "state": "open",
            "merged": False,
            "mergeable": True,
            "mergeable_state": "clean",
            "html_url": "https://github.com/test/repo/pull/1",
        }
        mock_request.return_value = mock_response

        status = self.gh.check_pr_status(1)

        assert status["state"] == "open"
        assert status["merged"] is False
        assert status["mergeable"] is True

    @patch("requests.request")
    def test_check_pr_status_merged(self, mock_request: Mock) -> None:
        """Test checking status of a merged PR."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "state": "closed",
            "merged": True,
            "mergeable": None,
            "mergeable_state": "unknown",
            "html_url": "https://github.com/test/repo/pull/1",
        }
        mock_request.return_value = mock_response

        status = self.gh.check_pr_status(1)

        assert status["state"] == "closed"
        assert status["merged"] is True


class TestMergePR(TestCase):
    """Tests for merge_pr method."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.gh = GitHubAutomation(owner="test", repo="repo", token="token")

    @patch("requests.request")
    def test_merge_pr_success(self, mock_request: Mock) -> None:
        """Test successful PR merge."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "sha": "mergedsha123",
            "merged": True,
        }
        mock_request.return_value = mock_response

        result = self.gh.merge_pr(1)

        assert result is True

    @patch("requests.request")
    def test_merge_pr_with_custom_message(self, mock_request: Mock) -> None:
        """Test PR merge with custom commit message."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"merged": True}
        mock_request.return_value = mock_response

        result = self.gh.merge_pr(
            pr_number=1,
            merge_method="squash",
            commit_title="Custom merge title",
            commit_message="Custom merge description",
        )

        assert result is True


class TestErrorHandling(TestCase):
    """Tests for error handling and retries."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.gh = GitHubAutomation(owner="test", repo="repo", token="token")

    @patch("requests.request")
    def test_auth_error_401(self, mock_request: Mock) -> None:
        """Test 401 error raises GitHubAuthError."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Bad credentials"
        mock_request.return_value = mock_response

        with pytest.raises(GitHubAuthError):
            self.gh.get_main_sha()

    @patch("requests.request")
    def test_rate_limit_error_429(self, mock_request: Mock) -> None:
        """Test 429 error raises GitHubRateLimitError."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_request.return_value = mock_response

        with pytest.raises(GitHubRateLimitError):
            self.gh.get_main_sha()


class TestFullWorkflow(TestCase):
    """Tests for the full_workflow method."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.gh = GitHubAutomation(owner="test", repo="repo", token="token")

    @patch.object(GitHubAutomation, "create_branch")
    @patch.object(GitHubAutomation, "commit_file")
    @patch.object(GitHubAutomation, "create_pr")
    @patch.object(GitHubAutomation, "check_pr_status")
    @patch.object(GitHubAutomation, "merge_pr")
    def test_full_workflow_with_auto_merge(
        self,
        mock_merge: Mock,
        mock_check_status: Mock,
        mock_create_pr: Mock,
        mock_commit: Mock,
        mock_create_branch: Mock,
    ) -> None:
        """Test full workflow with auto-merge enabled."""
        mock_create_branch.return_value = True
        mock_commit.return_value = True
        mock_create_pr.return_value = 42
        mock_check_status.return_value = {
            "html_url": "https://github.com/test/repo/pull/42"
        }
        mock_merge.return_value = True

        result = self.gh.full_workflow(
            branch_name="feature/test",
            files=[("test.py", "content")],
            pr_title="Test PR",
            pr_body="Description",
            commit_message="Add test",
            auto_merge=True,
        )

        assert result["branch"] == "feature/test"
        assert result["pr_number"] == 42
        assert result["merged"] is True
        mock_merge.assert_called_once_with(42)

    @patch.object(GitHubAutomation, "create_branch")
    @patch.object(GitHubAutomation, "commit_file")
    @patch.object(GitHubAutomation, "create_pr")
    @patch.object(GitHubAutomation, "check_pr_status")
    def test_full_workflow_without_auto_merge(
        self,
        mock_check_status: Mock,
        mock_create_pr: Mock,
        mock_commit: Mock,
        mock_create_branch: Mock,
    ) -> None:
        """Test full workflow without auto-merge."""
        mock_create_branch.return_value = True
        mock_commit.return_value = True
        mock_create_pr.return_value = 10
        mock_check_status.return_value = {
            "html_url": "https://github.com/test/repo/pull/10"
        }

        result = self.gh.full_workflow(
            branch_name="feature/no-merge",
            files=[("a.py", "a"), ("b.py", "b")],
            pr_title="No merge PR",
            pr_body="Description",
            commit_message="Add files",
            auto_merge=False,
        )

        assert result["merged"] is False
        assert mock_commit.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
