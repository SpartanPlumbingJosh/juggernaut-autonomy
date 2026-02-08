"""
Tests for PR Lifecycle Tracker (VERCHAIN-06)
=============================================

Unit tests for the PRTracker class and related functionality.
"""

import json
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Import the module under test
from core.pr_tracker import (
    PRTracker, PRStatus, PRState, ReviewStatus,
    track_pr_for_task, get_pr_status, sync_tracked_prs,
    is_pr_mergeable, merge_pr
)


class TestPRUrlParsing(unittest.TestCase):
    """Test PR URL parsing functionality."""
    
    def setUp(self):
        self.tracker = PRTracker()
    
    def test_parse_full_url(self):
        """Test parsing a full GitHub PR URL."""
        repo = "example-owner/example-repo"
        result = self.tracker._parse_pr_url(
            f"https://github.com/{repo}/pull/123"
        )
        self.assertEqual(result["repo"], repo)
        self.assertEqual(result["pr_number"], 123)
    
    def test_parse_number_only(self):
        """Test parsing just a PR number."""
        with patch.dict("os.environ", {"GITHUB_REPO": "example-owner/example-repo"}):
            result = self.tracker._parse_pr_url("456")
        self.assertEqual(result["pr_number"], 456)
        self.assertEqual(result["repo"], "example-owner/example-repo")
    
    def test_parse_with_hash(self):
        """Test parsing PR number with hash."""
        result = self.tracker._parse_pr_url("#789")
        self.assertEqual(result["pr_number"], 789)
    
    def test_parse_invalid(self):
        """Test parsing invalid input."""
        result = self.tracker._parse_pr_url("")
        self.assertIsNone(result)
        
        result = self.tracker._parse_pr_url(None)
        self.assertIsNone(result)


class TestReviewAnalysis(unittest.TestCase):
    """Test review analysis functionality."""
    
    def setUp(self):
        self.tracker = PRTracker()
    
    def test_no_reviews(self):
        """Test analysis with no reviews."""
        result = self.tracker._analyze_reviews([])
        self.assertEqual(result["status"], ReviewStatus.PENDING)
        self.assertEqual(result["approvals"], [])
        self.assertEqual(result["changes_requested_by"], [])
        self.assertFalse(result["coderabbit_approved"])
    
    def test_single_approval(self):
        """Test analysis with single approval."""
        reviews = [{
            "user": {"login": "reviewer1"},
            "state": "APPROVED",
            "submitted_at": "2026-01-21T10:00:00Z"
        }]
        result = self.tracker._analyze_reviews(reviews)
        self.assertEqual(result["status"], ReviewStatus.APPROVED)
        self.assertEqual(len(result["approvals"]), 1)
        self.assertEqual(result["approvals"][0]["reviewer"], "reviewer1")
    
    def test_coderabbit_approval(self):
        """Test CodeRabbit approval detection."""
        reviews = [{
            "user": {"login": "coderabbitai"},
            "state": "APPROVED",
            "submitted_at": "2026-01-21T10:00:00Z"
        }]
        result = self.tracker._analyze_reviews(reviews)
        self.assertTrue(result["coderabbit_approved"])
    
    def test_changes_requested(self):
        """Test changes requested detection."""
        reviews = [{
            "user": {"login": "reviewer1"},
            "state": "CHANGES_REQUESTED",
            "submitted_at": "2026-01-21T10:00:00Z"
        }]
        result = self.tracker._analyze_reviews(reviews)
        self.assertEqual(result["status"], ReviewStatus.CHANGES_REQUESTED)
        self.assertIn("reviewer1", result["changes_requested_by"])
    
    def test_approval_after_changes(self):
        """Test approval after changes requested."""
        reviews = [
            {
                "user": {"login": "reviewer1"},
                "state": "CHANGES_REQUESTED",
                "submitted_at": "2026-01-21T09:00:00Z"
            },
            {
                "user": {"login": "reviewer1"},
                "state": "APPROVED",
                "submitted_at": "2026-01-21T11:00:00Z"
            }
        ]
        result = self.tracker._analyze_reviews(reviews)
        self.assertEqual(result["status"], ReviewStatus.APPROVED)
        self.assertEqual(len(result["changes_requested_by"]), 0)


class TestPRStateDetection(unittest.TestCase):
    """Test PR state detection."""
    
    def setUp(self):
        self.tracker = PRTracker()
    
    def test_merged_state(self):
        """Test merged PR detection."""
        pr_data = {"merged": True, "state": "closed"}
        review_analysis = {"status": ReviewStatus.APPROVED, "changes_requested_by": [], "approvals": []}
        
        result = self.tracker._determine_pr_state(pr_data, review_analysis)
        self.assertEqual(result, PRState.MERGED)
    
    def test_closed_without_merge(self):
        """Test closed PR without merge."""
        pr_data = {"merged": False, "state": "closed"}
        review_analysis = {"status": ReviewStatus.PENDING, "changes_requested_by": [], "approvals": []}
        
        result = self.tracker._determine_pr_state(pr_data, review_analysis)
        self.assertEqual(result, PRState.CLOSED)
    
    def test_approved_state(self):
        """Test approved PR detection."""
        pr_data = {"merged": False, "state": "open"}
        review_analysis = {
            "status": ReviewStatus.APPROVED, 
            "changes_requested_by": [],
            "approvals": [{"reviewer": "user1"}]
        }
        
        result = self.tracker._determine_pr_state(pr_data, review_analysis)
        self.assertEqual(result, PRState.APPROVED)
    
    def test_changes_requested_state(self):
        """Test changes requested state."""
        pr_data = {"merged": False, "state": "open"}
        review_analysis = {
            "status": ReviewStatus.CHANGES_REQUESTED,
            "changes_requested_by": ["reviewer1"],
            "approvals": []
        }
        
        result = self.tracker._determine_pr_state(pr_data, review_analysis)
        self.assertEqual(result, PRState.CHANGES_REQUESTED)
    
    def test_review_requested_state(self):
        """Test review requested state."""
        pr_data = {
            "merged": False, 
            "state": "open",
            "requested_reviewers": [{"login": "reviewer1"}],
            "requested_teams": []
        }
        review_analysis = {
            "status": ReviewStatus.PENDING,
            "changes_requested_by": [],
            "approvals": []
        }
        
        result = self.tracker._determine_pr_state(pr_data, review_analysis)
        self.assertEqual(result, PRState.REVIEW_REQUESTED)
    
    def test_created_state(self):
        """Test newly created PR state."""
        pr_data = {
            "merged": False,
            "state": "open",
            "requested_reviewers": [],
            "requested_teams": []
        }
        review_analysis = {
            "status": ReviewStatus.PENDING,
            "changes_requested_by": [],
            "approvals": []
        }
        
        result = self.tracker._determine_pr_state(pr_data, review_analysis)
        self.assertEqual(result, PRState.CREATED)


class TestGateAdvancement(unittest.TestCase):
    """Test gate advancement logic."""
    
    def setUp(self):
        self.tracker = PRTracker()
    
    def test_should_advance_on_progress(self):
        """Test advancement when PR progresses."""
        self.assertTrue(self.tracker._should_advance_gate("created", "review_requested"))
        self.assertTrue(self.tracker._should_advance_gate("review_requested", "approved"))
        self.assertTrue(self.tracker._should_advance_gate("approved", "merged"))
    
    def test_should_not_advance_on_close(self):
        """Test no advancement when PR closes."""
        self.assertFalse(self.tracker._should_advance_gate("review_requested", "closed"))
    
    def test_should_not_advance_backwards(self):
        """Test no advancement when PR goes backwards."""
        self.assertFalse(self.tracker._should_advance_gate("approved", "changes_requested"))
        self.assertFalse(self.tracker._should_advance_gate("merged", "approved"))


class TestPRStatus(unittest.TestCase):
    """Test PRStatus dataclass."""
    
    def test_to_dict(self):
        """Test PRStatus serialization."""
        status = PRStatus(
            pr_number=123,
            repo="test/repo",
            state=PRState.APPROVED,
            review_status=ReviewStatus.APPROVED,
            mergeable=True,
            title="Test PR",
            url="https://github.com/test/repo/pull/123",
            created_at="2026-01-21T10:00:00Z",
            updated_at="2026-01-21T11:00:00Z",
            coderabbit_approved=True
        )
        
        result = status.to_dict()
        
        self.assertEqual(result["pr_number"], 123)
        self.assertEqual(result["state"], "approved")
        self.assertEqual(result["review_status"], "approved")
        self.assertTrue(result["mergeable"])
        self.assertTrue(result["coderabbit_approved"])


class TestMockGitHubIntegration(unittest.TestCase):
    """Test GitHub integration with mocked responses."""
    
    def setUp(self):
        self.tracker = PRTracker()
        self.tracker.github_token = "test_token"
    
    @patch.object(PRTracker, '_github_request')
    def test_get_pr_status(self, mock_request):
        """Test getting PR status with mocked GitHub API."""
        # Mock PR data
        mock_request.side_effect = [
            # First call - PR data
            {
                "number": 123,
                "html_url": "https://github.com/test/repo/pull/123",
                "title": "Test PR",
                "state": "open",
                "merged": False,
                "mergeable": True,
                "created_at": "2026-01-21T10:00:00Z",
                "updated_at": "2026-01-21T11:00:00Z",
                "requested_reviewers": [],
                "requested_teams": [],
                "head": {"sha": "abc123"}
            },
            # Second call - Reviews
            [{
                "user": {"login": "coderabbitai"},
                "state": "APPROVED",
                "submitted_at": "2026-01-21T10:30:00Z"
            }]
        ]
        
        status = self.tracker.get_pr_status("https://github.com/test/repo/pull/123")
        
        self.assertIsNotNone(status)
        self.assertEqual(status.pr_number, 123)
        self.assertEqual(status.state, PRState.APPROVED)
        self.assertTrue(status.coderabbit_approved)


if __name__ == "__main__":
    unittest.main()
