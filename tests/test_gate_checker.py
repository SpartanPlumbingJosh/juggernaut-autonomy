"""
Tests for Gate Checker Core System
==================================

Tests each gate type and the overall gate checking flow.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Import the module under test
from core.gate_checker import (
    GateType,
    GateResult,
    GateDefinition,
    GateChecker,
    check_task_gates,
    advance_task_gate,
    get_blocking_gate
)


class TestGateType:
    """Tests for GateType enum."""
    
    def test_all_gate_types_exist(self):
        """Verify all expected gate types are defined."""
        expected = [
            "plan_approval", "pr_created", "review_requested",
            "review_passed", "merged", "deployed", "health_check", "custom"
        ]
        for gate_type in expected:
            assert GateType(gate_type) is not None
    
    def test_invalid_gate_type_raises(self):
        """Invalid gate types should raise ValueError."""
        with pytest.raises(ValueError):
            GateType("invalid_gate")


class TestGateResult:
    """Tests for GateResult dataclass."""
    
    def test_gate_result_creation(self):
        """GateResult should initialize with defaults."""
        result = GateResult(passed=True, gate_type="test")
        assert result.passed is True
        assert result.gate_type == "test"
        assert result.checked_at is not None
    
    def test_gate_result_to_dict(self):
        """GateResult should convert to dictionary."""
        result = GateResult(
            passed=True,
            gate_type="test",
            evidence={"key": "value"},
            reason="Test passed"
        )
        d = result.to_dict()
        assert d["passed"] is True
        assert d["gate_type"] == "test"
        assert d["evidence"]["key"] == "value"


class TestGateDefinition:
    """Tests for GateDefinition dataclass."""
    
    def test_from_dict(self):
        """GateDefinition should parse from dictionary."""
        data = {
            "gate_type": "pr_created",
            "gate_name": "PR Created",
            "criteria": "PR must exist",
            "evidence_required": "PR number",
            "verifier": "ORCHESTRATOR",
            "timeout_minutes": 30
        }
        gate = GateDefinition.from_dict(data)
        assert gate.gate_type == "pr_created"
        assert gate.gate_name == "PR Created"
        assert gate.timeout_minutes == 30
    
    def test_from_dict_defaults(self):
        """GateDefinition should use defaults for missing fields."""
        gate = GateDefinition.from_dict({})
        assert gate.gate_type == "custom"
        assert gate.verifier == "ORCHESTRATOR"
        assert gate.timeout_minutes == 60


class TestGateCheckerPlanApproval:
    """Tests for plan_approval gate checking."""
    
    @patch('core.gate_checker.query_db')
    def test_plan_approved_via_metadata(self, mock_query):
        """Should pass if metadata has plan_approved=True."""
        mock_query.return_value = {
            "rows": [{
                "plan": "Do something",
                "metadata": json.dumps({"plan_approved": True}),
                "status": "in_progress",
                "stage": "in_progress"
            }]
        }
        
        checker = GateChecker()
        result = checker._check_plan_approval("task-123", GateDefinition.from_dict({}))
        
        assert result.passed is True
        assert "plan_approved" in result.evidence
    
    @patch('core.gate_checker.query_db')
    def test_plan_not_approved(self, mock_query):
        """Should fail if plan exists but not approved."""
        mock_query.return_value = {
            "rows": [{
                "plan": "Do something",
                "metadata": json.dumps({}),
                "status": "pending",
                "stage": "plan_submitted"
            }]
        }
        
        checker = GateChecker()
        result = checker._check_plan_approval("task-123", GateDefinition.from_dict({}))
        
        assert result.passed is False
        assert "not yet approved" in result.reason
    
    @patch('core.gate_checker.query_db')
    def test_no_plan_submitted(self, mock_query):
        """Should fail if no plan exists."""
        mock_query.return_value = {
            "rows": [{
                "plan": None,
                "metadata": json.dumps({}),
                "status": "pending",
                "stage": "discovered"
            }]
        }
        
        checker = GateChecker()
        result = checker._check_plan_approval("task-123", GateDefinition.from_dict({}))
        
        assert result.passed is False
        assert "No plan submitted" in result.reason


class TestGateCheckerPRCreated:
    """Tests for pr_created gate checking."""
    
    @patch('core.gate_checker.GateChecker._get_github_pr')
    @patch('core.gate_checker.query_db')
    def test_pr_found_in_metadata(self, mock_query, mock_get_pr):
        """Should pass if PR exists in metadata and GitHub."""
        mock_query.return_value = {
            "rows": [{
                "metadata": json.dumps({"pr_number": 42}),
                "completion_evidence": ""
            }]
        }
        mock_get_pr.return_value = {
            "html_url": "https://github.com/test/repo/pull/42",
            "title": "Test PR",
            "state": "open",
            "created_at": "2024-01-01T00:00:00Z"
        }
        
        checker = GateChecker()
        result = checker._check_pr_created("task-123", GateDefinition.from_dict({}))
        
        assert result.passed is True
        assert result.evidence["pr_number"] == 42
    
    @patch('core.gate_checker.GateChecker._get_github_pr')
    @patch('core.gate_checker.query_db')
    def test_pr_extracted_from_evidence(self, mock_query, mock_get_pr):
        """Should extract PR number from completion evidence."""
        mock_query.return_value = {
            "rows": [{
                "metadata": json.dumps({}),
                "completion_evidence": "Created PR #99 for this task"
            }]
        }
        mock_get_pr.return_value = {
            "html_url": "https://github.com/test/repo/pull/99",
            "title": "Test PR",
            "state": "open"
        }
        
        checker = GateChecker()
        result = checker._check_pr_created("task-123", GateDefinition.from_dict({}))
        
        assert result.passed is True
        assert result.evidence["pr_number"] == 99
    
    @patch('core.gate_checker.query_db')
    def test_no_pr_found(self, mock_query):
        """Should fail if no PR info found."""
        mock_query.return_value = {
            "rows": [{
                "metadata": json.dumps({}),
                "completion_evidence": "Working on it"
            }]
        }
        
        checker = GateChecker()
        result = checker._check_pr_created("task-123", GateDefinition.from_dict({}))
        
        assert result.passed is False
        assert "No PR found" in result.reason


class TestGateCheckerReviewPassed:
    """Tests for review_passed gate checking."""
    
    @patch('core.gate_checker.GateChecker._get_pr_reviews')
    @patch('core.gate_checker.GateChecker._get_task_pr_number')
    def test_approved_by_reviewer(self, mock_get_pr, mock_get_reviews):
        """Should pass if approved by reviewer."""
        mock_get_pr.return_value = 42
        mock_get_reviews.return_value = [{
            "state": "APPROVED",
            "user": {"login": "reviewer1"},
            "submitted_at": "2024-01-01T00:00:00Z"
        }]
        
        checker = GateChecker()
        result = checker._check_review_passed("task-123", GateDefinition.from_dict({}))
        
        assert result.passed is True
        assert len(result.evidence["approvals"]) == 1
    
    @patch('core.gate_checker.GateChecker._get_pr_reviews')
    @patch('core.gate_checker.GateChecker._get_task_pr_number')
    def test_changes_requested(self, mock_get_pr, mock_get_reviews):
        """Should fail if changes are requested."""
        mock_get_pr.return_value = 42
        mock_get_reviews.return_value = [{
            "state": "CHANGES_REQUESTED",
            "user": {"login": "reviewer1"},
            "submitted_at": "2024-01-01T00:00:00Z"
        }]
        
        checker = GateChecker()
        result = checker._check_review_passed("task-123", GateDefinition.from_dict({}))
        
        assert result.passed is False
        assert "Changes requested" in result.reason
    
    @patch('core.gate_checker.GateChecker._get_pr_reviews')
    @patch('core.gate_checker.GateChecker._get_task_pr_number')
    def test_coderabbit_approval_detected(self, mock_get_pr, mock_get_reviews):
        """Should detect CodeRabbit approval."""
        mock_get_pr.return_value = 42
        mock_get_reviews.return_value = [{
            "state": "APPROVED",
            "user": {"login": "coderabbitai"},
            "submitted_at": "2024-01-01T00:00:00Z"
        }]
        
        checker = GateChecker()
        result = checker._check_review_passed("task-123", GateDefinition.from_dict({}))
        
        assert result.passed is True
        assert result.evidence["coderabbit_approved"] is True


class TestGateCheckerPRMerged:
    """Tests for pr_merged gate checking."""
    
    @patch('core.gate_checker.GateChecker._get_github_pr')
    @patch('core.gate_checker.GateChecker._get_task_pr_number')
    def test_pr_merged(self, mock_get_pr_num, mock_get_pr):
        """Should pass if PR is merged."""
        mock_get_pr_num.return_value = 42
        mock_get_pr.return_value = {
            "merged": True,
            "merged_at": "2024-01-01T12:00:00Z",
            "merge_commit_sha": "abc123",
            "merged_by": {"login": "merger"}
        }
        
        checker = GateChecker()
        result = checker._check_pr_merged("task-123", GateDefinition.from_dict({}))
        
        assert result.passed is True
        assert result.evidence["merged"] is True
        assert result.evidence["merge_commit_sha"] == "abc123"
    
    @patch('core.gate_checker.GateChecker._get_github_pr')
    @patch('core.gate_checker.GateChecker._get_task_pr_number')
    def test_pr_not_merged(self, mock_get_pr_num, mock_get_pr):
        """Should fail if PR not merged."""
        mock_get_pr_num.return_value = 42
        mock_get_pr.return_value = {
            "merged": False,
            "state": "open"
        }
        
        checker = GateChecker()
        result = checker._check_pr_merged("task-123", GateDefinition.from_dict({}))
        
        assert result.passed is False
        assert "not merged" in result.reason


class TestGateCheckerHealthCheck:
    """Tests for health_check gate checking."""
    
    @patch('urllib.request.urlopen')
    @patch('core.gate_checker.query_db')
    def test_health_check_passes(self, mock_query, mock_urlopen):
        """Should pass if endpoint returns expected status."""
        mock_query.return_value = {"rows": []}
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        gate_config = {
            "gate_type": "health_check",
            "config": {
                "url": "https://example.com/health",
                "expected_status": 200
            }
        }
        
        checker = GateChecker()
        result = checker._check_health_check("task-123", GateDefinition.from_dict(gate_config))
        
        assert result.passed is True
        assert result.evidence["status_code"] == 200
    
    @patch('urllib.request.urlopen')
    @patch('core.gate_checker.query_db')
    def test_health_check_wrong_status(self, mock_query, mock_urlopen):
        """Should fail if endpoint returns wrong status."""
        mock_query.return_value = {"rows": []}
        
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.read.return_value = b'Internal Server Error'
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        gate_config = {
            "gate_type": "health_check",
            "config": {
                "url": "https://example.com/health",
                "expected_status": 200
            }
        }
        
        checker = GateChecker()
        result = checker._check_health_check("task-123", GateDefinition.from_dict(gate_config))
        
        assert result.passed is False
        assert "500" in result.reason


class TestGateCheckerFlow:
    """Tests for overall gate checking flow."""
    
    @patch('core.gate_checker.query_db')
    def test_check_all_gates(self, mock_query):
        """Should check all gates in verification chain."""
        mock_query.return_value = {
            "rows": [{
                "verification_chain": json.dumps([
                    {"gate_type": "plan_approval", "gate_name": "Plan"},
                    {"gate_type": "pr_created", "gate_name": "PR"}
                ]),
                "gate_evidence": json.dumps({}),
                "plan": "Test plan",
                "metadata": json.dumps({"plan_approved": True}),
                "status": "in_progress",
                "stage": "in_progress",
                "completion_evidence": ""
            }]
        }
        
        checker = GateChecker()
        results = checker.check_all_gates("task-123")
        
        assert len(results) == 2
    
    @patch('core.gate_checker.query_db')
    def test_get_current_gate(self, mock_query):
        """Should return current gate definition."""
        mock_query.return_value = {
            "rows": [{
                "verification_chain": json.dumps([
                    {"gate_type": "plan_approval", "gate_name": "Plan"},
                    {"gate_type": "pr_created", "gate_name": "PR"}
                ]),
                "current_gate": "pr_created",
                "gate_evidence": json.dumps({})
            }]
        }
        
        checker = GateChecker()
        gate = checker.get_current_gate("task-123")
        
        assert gate is not None
        assert gate["gate_type"] == "pr_created"


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""
    
    @patch('core.gate_checker.GateChecker.check_all_gates')
    def test_check_task_gates(self, mock_check):
        """check_task_gates should delegate to GateChecker."""
        mock_check.return_value = [GateResult(passed=True, gate_type="test")]
        
        results = check_task_gates("task-123")
        
        assert len(results) == 1
        mock_check.assert_called_once_with("task-123")
    
    @patch('core.gate_checker.GateChecker.advance_gate')
    def test_advance_task_gate(self, mock_advance):
        """advance_task_gate should delegate to GateChecker."""
        mock_advance.return_value = (True, "next_gate", GateResult(passed=True, gate_type="test"))
        
        advanced, next_gate, result = advance_task_gate("task-123")
        
        assert advanced is True
        assert next_gate == "next_gate"
        mock_advance.assert_called_once_with("task-123")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
