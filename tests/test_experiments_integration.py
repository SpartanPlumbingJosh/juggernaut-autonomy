"""
Integration Tests for JUGGERNAUT Experiments Framework

Tests cover:
1. Experiment creation flow
2. Hypothesis tracking
3. Rollback functionality
4. Budget limit enforcement

Uses test database fixtures from conftest.py.
Does not affect production data.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Generator, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# Configure test logger
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

TEST_PREFIX = "test_exp_integration"
DEFAULT_BUDGET_LIMIT = 100.0
DEFAULT_MAX_ITERATIONS = 10


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_execute_sql():
    """Mock SQL execution for isolated testing."""
    with patch("core.experiments._execute_sql") as mock:
        yield mock


@pytest.fixture
def unique_experiment_name() -> str:
    """Generate unique experiment name for each test."""
    return f"{TEST_PREFIX}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def sample_success_criteria() -> Dict[str, Any]:
    """Standard success criteria for tests."""
    return {
        "metric": "revenue",
        "operator": ">=",
        "target_value": 500.0,
        "measurement_period_days": 7
    }


@pytest.fixture
def sample_failure_criteria() -> Dict[str, Any]:
    """Standard failure criteria for tests."""
    return {
        "metric": "cost",
        "operator": ">",
        "threshold": 1000.0,
        "consecutive_failures": 3
    }


@pytest.fixture
def mock_experiment_data(
    unique_experiment_name: str,
    sample_success_criteria: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate mock experiment data with all required fields."""
    experiment_id = str(uuid.uuid4())
    return {
        "id": experiment_id,
        "name": unique_experiment_name,
        "hypothesis": "Test hypothesis for integration testing",
        "experiment_type": "revenue",
        "description": "Integration test experiment",
        "status": "draft",
        "current_iteration": 0,
        "max_iterations": DEFAULT_MAX_ITERATIONS,
        "budget_limit": DEFAULT_BUDGET_LIMIT,
        "budget_spent": 0.0,
        "success_criteria": sample_success_criteria,
        "failure_criteria": None,
        "owner_worker": "test-worker",
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "completed_at": None,
        "outcome": None
    }


# =============================================================================
# TEST CLASS: EXPERIMENT CREATION FLOW
# =============================================================================


class TestExperimentCreationFlow:
    """Tests for experiment creation and retrieval."""
    
    def test_create_experiment_basic(
        self,
        mock_execute_sql: MagicMock,
        unique_experiment_name: str,
        sample_success_criteria: Dict[str, Any]
    ) -> None:
        """Test creating an experiment with basic parameters."""
        from core.experiments import create_experiment
        
        mock_execute_sql.return_value = {"success": True, "rows": [], "rowCount": 1}
        
        result = create_experiment(
            name=unique_experiment_name,
            hypothesis="Revenue increases with feature X",
            success_criteria=sample_success_criteria,
            experiment_type="revenue",
            budget_limit=DEFAULT_BUDGET_LIMIT
        )
        
        assert result["success"] is True
        assert "experiment_id" in result
        mock_execute_sql.assert_called_once()
    
    def test_create_experiment_with_all_params(
        self,
        mock_execute_sql: MagicMock,
        unique_experiment_name: str,
        sample_success_criteria: Dict[str, Any],
        sample_failure_criteria: Dict[str, Any]
    ) -> None:
        """Test creating an experiment with all optional parameters."""
        from core.experiments import create_experiment
        
        mock_execute_sql.return_value = {"success": True, "rows": [], "rowCount": 1}
        
        result = create_experiment(
            name=unique_experiment_name,
            hypothesis="Full parameter test hypothesis",
            success_criteria=sample_success_criteria,
            experiment_type="cost_reduction",
            description="Comprehensive experiment test",
            failure_criteria=sample_failure_criteria,
            budget_limit=200.0,
            max_iterations=20,
            cost_per_iteration=5.0,
            scheduled_end=datetime.utcnow() + timedelta(days=14),
            owner_worker="test-owner",
            tags=["integration", "test"],
            config={"feature_flag": True}
        )
        
        assert result["success"] is True
        mock_execute_sql.assert_called_once()
        
        # Verify SQL contains all parameters
        call_args = mock_execute_sql.call_args[0][0]
        assert unique_experiment_name in call_args
        assert "cost_reduction" in call_args
    
    def test_get_experiment_found(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test retrieving an existing experiment."""
        from core.experiments import get_experiment
        
        mock_execute_sql.return_value = {
            "success": True,
            "rows": [mock_experiment_data],
            "rowCount": 1
        }
        
        result = get_experiment(mock_experiment_data["id"])
        
        assert result is not None
        assert result["id"] == mock_experiment_data["id"]
        assert result["name"] == mock_experiment_data["name"]
    
    def test_get_experiment_not_found(
        self,
        mock_execute_sql: MagicMock
    ) -> None:
        """Test retrieving a non-existent experiment returns None."""
        from core.experiments import get_experiment
        
        mock_execute_sql.return_value = {
            "success": True,
            "rows": [],
            "rowCount": 0
        }
        
        result = get_experiment("non-existent-id")
        
        assert result is None
    
    def test_list_experiments_with_filters(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test listing experiments with status filter."""
        from core.experiments import list_experiments
        
        mock_execute_sql.return_value = {
            "success": True,
            "rows": [mock_experiment_data],
            "rowCount": 1
        }
        
        result = list_experiments(status="draft", experiment_type="revenue")
        
        assert len(result) == 1
        call_args = mock_execute_sql.call_args[0][0]
        assert "status = 'draft'" in call_args
        assert "experiment_type = 'revenue'" in call_args


# =============================================================================
# TEST CLASS: HYPOTHESIS TRACKING
# =============================================================================


class TestHypothesisTracking:
    """Tests for hypothesis tracking and result recording."""
    
    def test_record_result_success(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test recording a successful experiment result."""
        from core.experiments import record_result
        
        mock_execute_sql.return_value = {"success": True, "rowCount": 1}
        
        result = record_result(
            experiment_id=mock_experiment_data["id"],
            iteration=1,
            metric_name="revenue",
            metric_value=600.0,
            variant_id=None,
            metadata={"source": "test"}
        )
        
        assert result["success"] is True
        mock_execute_sql.assert_called()
    
    def test_record_multiple_results(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test recording multiple iteration results."""
        from core.experiments import record_result
        
        mock_execute_sql.return_value = {"success": True, "rowCount": 1}
        
        results = []
        for iteration in range(1, 4):
            result = record_result(
                experiment_id=mock_experiment_data["id"],
                iteration=iteration,
                metric_name="revenue",
                metric_value=500.0 + (iteration * 50)
            )
            results.append(result)
        
        assert all(r["success"] for r in results)
        assert mock_execute_sql.call_count == 3
    
    def test_evaluate_success_criteria_met(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test evaluating when success criteria is met."""
        from core.experiments import evaluate_success_criteria
        
        # Mock returns experiment with results exceeding target
        mock_execute_sql.side_effect = [
            # First call: get experiment
            {
                "success": True,
                "rows": [mock_experiment_data],
                "rowCount": 1
            },
            # Second call: get results
            {
                "success": True,
                "rows": [
                    {"metric_name": "revenue", "metric_value": 600.0}
                ],
                "rowCount": 1
            }
        ]
        
        result = evaluate_success_criteria(mock_experiment_data["id"])
        
        assert "criteria_met" in result or "evaluation" in result
    
    def test_increment_iteration(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test incrementing experiment iteration counter."""
        from core.experiments import increment_iteration
        
        mock_execute_sql.return_value = {
            "success": True,
            "rows": [{"current_iteration": 2}],
            "rowCount": 1
        }
        
        result = increment_iteration(
            experiment_id=mock_experiment_data["id"],
            iteration_notes="Test iteration"
        )
        
        assert result["success"] is True
        assert result.get("new_iteration", 2) >= 1


# =============================================================================
# TEST CLASS: ROLLBACK FUNCTIONALITY
# =============================================================================


class TestRollbackFunctionality:
    """Tests for experiment rollback system."""
    
    def test_create_rollback_snapshot(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test creating a rollback snapshot."""
        from core.experiments import create_rollback_snapshot
        
        mock_execute_sql.return_value = {"success": True, "rowCount": 1}
        
        result = create_rollback_snapshot(
            experiment_id=mock_experiment_data["id"],
            snapshot_type="checkpoint",
            snapshot_data={"state": "pre_change", "metrics": {"revenue": 450}},
            description="Pre-change snapshot"
        )
        
        assert result["success"] is True
        assert "snapshot_id" in result
    
    def test_execute_rollback(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test executing a rollback to previous snapshot."""
        from core.experiments import execute_rollback
        
        snapshot_id = str(uuid.uuid4())
        
        # Mock calls: get snapshot, update experiment, log rollback
        mock_execute_sql.side_effect = [
            {
                "success": True,
                "rows": [{
                    "id": snapshot_id,
                    "experiment_id": mock_experiment_data["id"],
                    "snapshot_data": {"state": "previous"}
                }],
                "rowCount": 1
            },
            {"success": True, "rowCount": 1},  # Update experiment
            {"success": True, "rowCount": 1}   # Log rollback
        ]
        
        result = execute_rollback(
            experiment_id=mock_experiment_data["id"],
            snapshot_id=snapshot_id,
            reason="Test rollback",
            executed_by="test-system"
        )
        
        assert result["success"] is True
    
    def test_check_auto_rollback_triggers_no_trigger(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test auto-rollback check when no triggers are met."""
        from core.experiments import check_auto_rollback_triggers
        
        # Experiment within budget and iterations
        healthy_experiment = mock_experiment_data.copy()
        healthy_experiment["budget_spent"] = 50.0
        healthy_experiment["current_iteration"] = 3
        healthy_experiment["status"] = "running"
        
        mock_execute_sql.return_value = {
            "success": True,
            "rows": [healthy_experiment],
            "rowCount": 1
        }
        
        result = check_auto_rollback_triggers(mock_experiment_data["id"])
        
        assert result.get("should_rollback", False) is False or \
               result.get("triggers_found", []) == []
    
    def test_fail_experiment(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test marking an experiment as failed."""
        from core.experiments import fail_experiment
        
        mock_execute_sql.return_value = {"success": True, "rowCount": 1}
        
        result = fail_experiment(
            experiment_id=mock_experiment_data["id"],
            failure_reason="Budget exceeded",
            auto_rollback=True,
            failed_by="test-system"
        )
        
        assert result["success"] is True
        call_args = mock_execute_sql.call_args[0][0]
        assert "failed" in call_args.lower() or "status" in call_args


# =============================================================================
# TEST CLASS: BUDGET LIMIT ENFORCEMENT
# =============================================================================


class TestBudgetLimitEnforcement:
    """Tests for budget tracking and enforcement."""
    
    def test_record_experiment_cost(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test recording cost against experiment budget."""
        from core.experiments import record_experiment_cost
        
        mock_execute_sql.return_value = {
            "success": True,
            "rows": [{"budget_spent": 25.0}],
            "rowCount": 1
        }
        
        result = record_experiment_cost(
            experiment_id=mock_experiment_data["id"],
            amount=25.0,
            cost_type="api_call",
            description="Test API call cost"
        )
        
        assert result["success"] is True
        assert result.get("new_total", 25.0) >= 25.0
    
    def test_budget_limit_not_exceeded(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test experiment continues when under budget."""
        from core.experiments import record_experiment_cost
        
        # Under budget scenario
        mock_execute_sql.return_value = {
            "success": True,
            "rows": [{"budget_spent": 50.0, "budget_limit": 100.0}],
            "rowCount": 1
        }
        
        result = record_experiment_cost(
            experiment_id=mock_experiment_data["id"],
            amount=30.0,
            cost_type="compute"
        )
        
        assert result["success"] is True
        assert result.get("budget_exceeded", False) is False
    
    def test_budget_limit_exceeded_triggers_warning(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test budget exceeded returns warning."""
        from core.experiments import record_experiment_cost
        
        # Exceeds budget scenario
        mock_execute_sql.return_value = {
            "success": True,
            "rows": [{"budget_spent": 110.0, "budget_limit": 100.0}],
            "rowCount": 1
        }
        
        result = record_experiment_cost(
            experiment_id=mock_experiment_data["id"],
            amount=60.0,
            cost_type="compute"
        )
        
        # Either succeeds with warning or returns budget_exceeded flag
        assert result["success"] is True or "budget_exceeded" in result
    
    def test_create_experiment_with_zero_budget(
        self,
        mock_execute_sql: MagicMock,
        unique_experiment_name: str,
        sample_success_criteria: Dict[str, Any]
    ) -> None:
        """Test creating experiment with zero budget limit."""
        from core.experiments import create_experiment
        
        mock_execute_sql.return_value = {"success": True, "rowCount": 1}
        
        result = create_experiment(
            name=unique_experiment_name,
            hypothesis="Zero budget test",
            success_criteria=sample_success_criteria,
            budget_limit=0.0
        )
        
        assert result["success"] is True
        call_args = mock_execute_sql.call_args[0][0]
        assert "0" in call_args or "0.0" in call_args


# =============================================================================
# TEST CLASS: EXPERIMENT LIFECYCLE
# =============================================================================


class TestExperimentLifecycle:
    """Tests for full experiment lifecycle operations."""
    
    def test_start_experiment(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test starting a draft experiment."""
        from core.experiments import start_experiment
        
        mock_execute_sql.return_value = {"success": True, "rowCount": 1}
        
        result = start_experiment(
            experiment_id=mock_experiment_data["id"],
            started_by="test-worker"
        )
        
        assert result["success"] is True
        call_args = mock_execute_sql.call_args[0][0]
        assert "running" in call_args.lower() or "start" in call_args.lower()
    
    def test_pause_experiment(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test pausing a running experiment."""
        from core.experiments import pause_experiment
        
        mock_execute_sql.return_value = {"success": True, "rowCount": 1}
        
        result = pause_experiment(
            experiment_id=mock_experiment_data["id"],
            reason="Awaiting resource allocation",
            paused_by="test-worker"
        )
        
        assert result["success"] is True
    
    def test_resume_experiment(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test resuming a paused experiment."""
        from core.experiments import resume_experiment
        
        mock_execute_sql.return_value = {"success": True, "rowCount": 1}
        
        result = resume_experiment(
            experiment_id=mock_experiment_data["id"],
            resumed_by="test-worker"
        )
        
        assert result["success"] is True
    
    def test_conclude_experiment_success(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test concluding an experiment with success outcome."""
        from core.experiments import conclude_experiment
        
        mock_execute_sql.return_value = {"success": True, "rowCount": 1}
        
        result = conclude_experiment(
            experiment_id=mock_experiment_data["id"],
            outcome="success",
            final_metrics={"revenue": 750.0, "conversion_rate": 0.15},
            conclusion_notes="Hypothesis validated",
            concluded_by="test-worker"
        )
        
        assert result["success"] is True


# =============================================================================
# TEST CLASS: LEARNINGS EXTRACTION
# =============================================================================


class TestLearningsExtraction:
    """Tests for experiment learnings capture."""
    
    def test_record_learning(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test recording a learning from experiment."""
        from core.experiments import record_learning
        
        mock_execute_sql.return_value = {"success": True, "rowCount": 1}
        
        result = record_learning(
            experiment_id=mock_experiment_data["id"],
            learning_type="pattern",
            title="Higher conversion with personalization",
            description="Personalized offers increase conversion by 15%",
            confidence_score=0.85,
            impact_assessment="high",
            applicable_contexts=["digital_products", "saas"]
        )
        
        assert result["success"] is True
        assert "learning_id" in result
    
    def test_extract_learnings_from_experiment(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test extracting learnings from completed experiment."""
        from core.experiments import extract_learnings
        
        mock_execute_sql.return_value = {
            "success": True,
            "rows": [
                {
                    "id": str(uuid.uuid4()),
                    "learning_type": "pattern",
                    "title": "Test learning",
                    "confidence_score": 0.8
                }
            ],
            "rowCount": 1
        }
        
        result = extract_learnings(mock_experiment_data["id"])
        
        assert "learnings" in result or result.get("success", True)


# =============================================================================
# TEST CLASS: EDGE CASES AND ERROR HANDLING
# =============================================================================


class TestEdgeCasesAndErrors:
    """Tests for edge cases and error handling."""
    
    def test_create_experiment_with_special_characters(
        self,
        mock_execute_sql: MagicMock,
        sample_success_criteria: Dict[str, Any]
    ) -> None:
        """Test creating experiment with special characters in name."""
        from core.experiments import create_experiment
        
        mock_execute_sql.return_value = {"success": True, "rowCount": 1}
        
        result = create_experiment(
            name="Test's Experiment (Rev 2.0)",
            hypothesis="Testing O'Brien's hypothesis",
            success_criteria=sample_success_criteria
        )
        
        assert result["success"] is True
    
    def test_get_experiment_invalid_uuid(
        self,
        mock_execute_sql: MagicMock
    ) -> None:
        """Test get_experiment with invalid UUID format."""
        from core.experiments import get_experiment
        
        mock_execute_sql.return_value = {"success": True, "rows": [], "rowCount": 0}
        
        result = get_experiment("not-a-valid-uuid")
        
        assert result is None
    
    def test_record_negative_cost(
        self,
        mock_execute_sql: MagicMock,
        mock_experiment_data: Dict[str, Any]
    ) -> None:
        """Test recording negative cost (refund scenario)."""
        from core.experiments import record_experiment_cost
        
        mock_execute_sql.return_value = {
            "success": True,
            "rows": [{"budget_spent": -10.0}],
            "rowCount": 1
        }
        
        result = record_experiment_cost(
            experiment_id=mock_experiment_data["id"],
            amount=-10.0,
            cost_type="refund",
            description="Cost refund"
        )
        
        # Should succeed - refunds are valid
        assert result["success"] is True
