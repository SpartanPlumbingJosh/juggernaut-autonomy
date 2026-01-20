"""
Tests for the auto_scaling module.

Comprehensive test coverage for:
- Dataclass unit tests (ScalingConfig, QueueMetrics, WorkerMetrics, ScalingDecision)
- evaluate_scaling() logic (scale-up, scale-down, no-action scenarios)
- Cooldown period enforcement
- Database call mocking for isolation
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.auto_scaling import (
    AutoScaler,
    QueueMetrics,
    ScalingAction,
    ScalingConfig,
    ScalingDecision,
    WorkerMetrics,
    create_auto_scaler,
    DEFAULT_MAX_WORKERS,
    DEFAULT_MIN_WORKERS,
    SCALE_DOWN_COOLDOWN_SECONDS,
    SCALE_DOWN_THRESHOLD,
    SCALE_UP_COOLDOWN_SECONDS,
    SCALE_UP_THRESHOLD,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS FOR TESTS
# =============================================================================

TEST_DB_ENDPOINT = "https://test-endpoint.example.com/sql"
TEST_CONNECTION_STRING = "postgresql://test:test@localhost/testdb"


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_http_client() -> MagicMock:
    """Create a mock HTTP client for testing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"rows": [], "rowCount": 0}
    mock_client.post.return_value = mock_response
    return mock_client


@pytest.fixture
def auto_scaler(mock_http_client: MagicMock) -> AutoScaler:
    """Create an AutoScaler with mocked HTTP client."""
    scaler = AutoScaler(
        db_endpoint=TEST_DB_ENDPOINT,
        connection_string=TEST_CONNECTION_STRING,
    )
    scaler._http_client = mock_http_client
    return scaler


@pytest.fixture
def custom_config() -> ScalingConfig:
    """Create a custom scaling configuration for tests."""
    return ScalingConfig(
        min_workers=2,
        max_workers=8,
        scale_up_threshold=10,
        scale_down_threshold=1,
        scale_up_cooldown_seconds=120,
        scale_down_cooldown_seconds=240,
        enabled=True,
    )


@pytest.fixture
def auto_scaler_custom_config(
    mock_http_client: MagicMock, custom_config: ScalingConfig
) -> AutoScaler:
    """Create an AutoScaler with custom config and mocked HTTP client."""
    scaler = AutoScaler(
        db_endpoint=TEST_DB_ENDPOINT,
        connection_string=TEST_CONNECTION_STRING,
        config=custom_config,
    )
    scaler._http_client = mock_http_client
    return scaler


# =============================================================================
# DATACLASS UNIT TESTS
# =============================================================================


class TestScalingConfig:
    """Unit tests for ScalingConfig dataclass."""

    def test_default_values(self) -> None:
        """Test that ScalingConfig has correct default values."""
        config = ScalingConfig()

        assert config.min_workers == DEFAULT_MIN_WORKERS
        assert config.max_workers == DEFAULT_MAX_WORKERS
        assert config.scale_up_threshold == SCALE_UP_THRESHOLD
        assert config.scale_down_threshold == SCALE_DOWN_THRESHOLD
        assert config.scale_up_cooldown_seconds == SCALE_UP_COOLDOWN_SECONDS
        assert config.scale_down_cooldown_seconds == SCALE_DOWN_COOLDOWN_SECONDS
        assert config.enabled is True

    def test_custom_values(self) -> None:
        """Test ScalingConfig with custom values."""
        config = ScalingConfig(
            min_workers=3,
            max_workers=15,
            scale_up_threshold=10,
            scale_down_threshold=2,
            scale_up_cooldown_seconds=180,
            scale_down_cooldown_seconds=360,
            enabled=False,
        )

        assert config.min_workers == 3
        assert config.max_workers == 15
        assert config.scale_up_threshold == 10
        assert config.scale_down_threshold == 2
        assert config.scale_up_cooldown_seconds == 180
        assert config.scale_down_cooldown_seconds == 360
        assert config.enabled is False

    def test_partial_custom_values(self) -> None:
        """Test ScalingConfig with some custom, some default values."""
        config = ScalingConfig(min_workers=5, max_workers=20)

        assert config.min_workers == 5
        assert config.max_workers == 20
        assert config.scale_up_threshold == SCALE_UP_THRESHOLD
        assert config.enabled is True


class TestQueueMetrics:
    """Unit tests for QueueMetrics dataclass."""

    def test_creation(self) -> None:
        """Test QueueMetrics creation with values."""
        metrics = QueueMetrics(
            pending_count=10,
            in_progress_count=5,
            waiting_approval_count=2,
            total_actionable=15,
        )

        assert metrics.pending_count == 10
        assert metrics.in_progress_count == 5
        assert metrics.waiting_approval_count == 2
        assert metrics.total_actionable == 15

    def test_zero_values(self) -> None:
        """Test QueueMetrics with zero values."""
        metrics = QueueMetrics(
            pending_count=0,
            in_progress_count=0,
            waiting_approval_count=0,
            total_actionable=0,
        )

        assert metrics.pending_count == 0
        assert metrics.in_progress_count == 0
        assert metrics.total_actionable == 0

    def test_large_values(self) -> None:
        """Test QueueMetrics with large values."""
        metrics = QueueMetrics(
            pending_count=10000,
            in_progress_count=5000,
            waiting_approval_count=1000,
            total_actionable=15000,
        )

        assert metrics.pending_count == 10000
        assert metrics.total_actionable == 15000


class TestWorkerMetrics:
    """Unit tests for WorkerMetrics dataclass."""

    def test_creation(self) -> None:
        """Test WorkerMetrics creation with values."""
        metrics = WorkerMetrics(
            active_count=5,
            idle_count=2,
            stale_count=1,
            total_capacity=25,
        )

        assert metrics.active_count == 5
        assert metrics.idle_count == 2
        assert metrics.stale_count == 1
        assert metrics.total_capacity == 25

    def test_zero_values(self) -> None:
        """Test WorkerMetrics with zero values."""
        metrics = WorkerMetrics(
            active_count=0,
            idle_count=0,
            stale_count=0,
            total_capacity=0,
        )

        assert metrics.active_count == 0
        assert metrics.idle_count == 0

    def test_all_idle(self) -> None:
        """Test WorkerMetrics when all workers are idle."""
        metrics = WorkerMetrics(
            active_count=10,
            idle_count=10,
            stale_count=0,
            total_capacity=50,
        )

        assert metrics.active_count == metrics.idle_count


class TestScalingDecision:
    """Unit tests for ScalingDecision dataclass."""

    def test_scale_up_decision(self) -> None:
        """Test ScalingDecision for scale up."""
        decision = ScalingDecision(
            action=ScalingAction.SCALE_UP,
            reason="High queue depth",
            current_workers=3,
            current_queue_depth=20,
            target_workers=5,
            workers_to_add=2,
            workers_to_remove=0,
        )

        assert decision.action == ScalingAction.SCALE_UP
        assert decision.workers_to_add == 2
        assert decision.workers_to_remove == 0
        assert decision.target_workers == 5

    def test_scale_down_decision(self) -> None:
        """Test ScalingDecision for scale down."""
        decision = ScalingDecision(
            action=ScalingAction.SCALE_DOWN,
            reason="Empty queue with idle workers",
            current_workers=5,
            current_queue_depth=0,
            target_workers=3,
            workers_to_add=0,
            workers_to_remove=2,
        )

        assert decision.action == ScalingAction.SCALE_DOWN
        assert decision.workers_to_add == 0
        assert decision.workers_to_remove == 2

    def test_no_action_decision(self) -> None:
        """Test ScalingDecision for no action."""
        decision = ScalingDecision(
            action=ScalingAction.NO_ACTION,
            reason="Queue depth within normal range",
            current_workers=3,
            current_queue_depth=3,
        )

        assert decision.action == ScalingAction.NO_ACTION
        assert decision.workers_to_add == 0
        assert decision.workers_to_remove == 0
        assert decision.target_workers is None

    def test_default_values(self) -> None:
        """Test ScalingDecision default values."""
        decision = ScalingDecision(
            action=ScalingAction.NO_ACTION,
            reason="Test",
            current_workers=1,
            current_queue_depth=1,
        )

        assert decision.target_workers is None
        assert decision.workers_to_add == 0
        assert decision.workers_to_remove == 0


class TestScalingAction:
    """Unit tests for ScalingAction enum."""

    def test_enum_values(self) -> None:
        """Test ScalingAction enum has correct values."""
        assert ScalingAction.SCALE_UP.value == "scale_up"
        assert ScalingAction.SCALE_DOWN.value == "scale_down"
        assert ScalingAction.NO_ACTION.value == "no_action"

    def test_enum_members(self) -> None:
        """Test all enum members exist."""
        members = list(ScalingAction)
        assert len(members) == 3
        assert ScalingAction.SCALE_UP in members
        assert ScalingAction.SCALE_DOWN in members
        assert ScalingAction.NO_ACTION in members


# =============================================================================
# AUTOSCALER INITIALIZATION TESTS
# =============================================================================


class TestAutoScalerInit:
    """Tests for AutoScaler initialization."""

    def test_init_with_defaults(self) -> None:
        """Test AutoScaler initialization with default config."""
        scaler = AutoScaler(
            db_endpoint=TEST_DB_ENDPOINT,
            connection_string=TEST_CONNECTION_STRING,
        )

        assert scaler.db_endpoint == TEST_DB_ENDPOINT
        assert scaler.connection_string == TEST_CONNECTION_STRING
        assert scaler.config.min_workers == DEFAULT_MIN_WORKERS
        assert scaler.config.max_workers == DEFAULT_MAX_WORKERS
        assert scaler._last_scale_up is None
        assert scaler._last_scale_down is None

    def test_init_with_custom_config(self, custom_config: ScalingConfig) -> None:
        """Test AutoScaler initialization with custom config."""
        scaler = AutoScaler(
            db_endpoint=TEST_DB_ENDPOINT,
            connection_string=TEST_CONNECTION_STRING,
            config=custom_config,
        )

        assert scaler.config.min_workers == 2
        assert scaler.config.max_workers == 8
        assert scaler.config.scale_up_threshold == 10

    def test_http_client_lazy_initialization(self) -> None:
        """Test that HTTP client is lazily initialized."""
        scaler = AutoScaler(
            db_endpoint=TEST_DB_ENDPOINT,
            connection_string=TEST_CONNECTION_STRING,
        )

        assert scaler._http_client is None
        # Accessing the property should initialize it
        with patch("core.auto_scaling.httpx.Client") as mock_client:
            _ = scaler.http_client
            mock_client.assert_called_once_with(timeout=30.0)


# =============================================================================
# EVALUATE_SCALING TESTS - SCALE UP SCENARIOS
# =============================================================================


class TestEvaluateScalingScaleUp:
    """Tests for evaluate_scaling() scale-up scenarios."""

    def test_scale_up_when_queue_exceeds_threshold(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test scale up when queue depth exceeds threshold."""
        # Mock queue metrics - high pending count
        queue_response = MagicMock()
        queue_response.json.return_value = {
            "rows": [{"pending": 10, "in_progress": 2, "waiting": 0}]
        }
        queue_response.raise_for_status = MagicMock()

        # Mock worker metrics - low active count
        worker_response = MagicMock()
        worker_response.json.return_value = {
            "rows": [{"active": 2, "stale": 0, "capacity": 10}]
        }
        worker_response.raise_for_status = MagicMock()

        # Mock busy workers query
        busy_response = MagicMock()
        busy_response.json.return_value = {"rows": [{"busy_workers": 2}]}
        busy_response.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [
            queue_response,
            worker_response,
            busy_response,
        ]

        decision = auto_scaler.evaluate_scaling()

        assert decision.action == ScalingAction.SCALE_UP
        assert decision.workers_to_add > 0
        assert "exceeds threshold" in decision.reason.lower()

    def test_no_scale_up_when_at_max_workers(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test no scale up when already at max workers."""
        # Set max_workers to current active
        auto_scaler.config.max_workers = 5

        queue_response = MagicMock()
        queue_response.json.return_value = {
            "rows": [{"pending": 20, "in_progress": 5, "waiting": 0}]
        }
        queue_response.raise_for_status = MagicMock()

        worker_response = MagicMock()
        worker_response.json.return_value = {
            "rows": [{"active": 5, "stale": 0, "capacity": 25}]
        }
        worker_response.raise_for_status = MagicMock()

        busy_response = MagicMock()
        busy_response.json.return_value = {"rows": [{"busy_workers": 5}]}
        busy_response.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [
            queue_response,
            worker_response,
            busy_response,
        ]

        decision = auto_scaler.evaluate_scaling()

        assert decision.action == ScalingAction.NO_ACTION
        assert "max workers" in decision.reason.lower()

    def test_scale_up_limited_by_max_workers(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test scale up is limited by max_workers configuration."""
        auto_scaler.config.max_workers = 5

        queue_response = MagicMock()
        queue_response.json.return_value = {
            "rows": [{"pending": 50, "in_progress": 3, "waiting": 0}]
        }
        queue_response.raise_for_status = MagicMock()

        worker_response = MagicMock()
        worker_response.json.return_value = {
            "rows": [{"active": 3, "stale": 0, "capacity": 15}]
        }
        worker_response.raise_for_status = MagicMock()

        busy_response = MagicMock()
        busy_response.json.return_value = {"rows": [{"busy_workers": 3}]}
        busy_response.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [
            queue_response,
            worker_response,
            busy_response,
        ]

        decision = auto_scaler.evaluate_scaling()

        assert decision.action == ScalingAction.SCALE_UP
        # Should only add up to max_workers (5) - current (3) = 2
        assert decision.workers_to_add <= 2
        assert decision.target_workers <= 5


# =============================================================================
# EVALUATE_SCALING TESTS - SCALE DOWN SCENARIOS
# =============================================================================


class TestEvaluateScalingScaleDown:
    """Tests for evaluate_scaling() scale-down scenarios."""

    def test_scale_down_when_queue_empty_with_idle_workers(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test scale down when queue is empty and workers are idle."""
        queue_response = MagicMock()
        queue_response.json.return_value = {
            "rows": [{"pending": 0, "in_progress": 0, "waiting": 0}]
        }
        queue_response.raise_for_status = MagicMock()

        worker_response = MagicMock()
        worker_response.json.return_value = {
            "rows": [{"active": 5, "stale": 0, "capacity": 25}]
        }
        worker_response.raise_for_status = MagicMock()

        busy_response = MagicMock()
        busy_response.json.return_value = {"rows": [{"busy_workers": 0}]}
        busy_response.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [
            queue_response,
            worker_response,
            busy_response,
        ]

        decision = auto_scaler.evaluate_scaling()

        assert decision.action == ScalingAction.SCALE_DOWN
        assert decision.workers_to_remove > 0
        assert "idle" in decision.reason.lower()

    def test_no_scale_down_when_at_min_workers(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test no scale down when already at min workers."""
        auto_scaler.config.min_workers = 1

        queue_response = MagicMock()
        queue_response.json.return_value = {
            "rows": [{"pending": 0, "in_progress": 0, "waiting": 0}]
        }
        queue_response.raise_for_status = MagicMock()

        worker_response = MagicMock()
        worker_response.json.return_value = {
            "rows": [{"active": 1, "stale": 0, "capacity": 5}]
        }
        worker_response.raise_for_status = MagicMock()

        busy_response = MagicMock()
        busy_response.json.return_value = {"rows": [{"busy_workers": 0}]}
        busy_response.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [
            queue_response,
            worker_response,
            busy_response,
        ]

        decision = auto_scaler.evaluate_scaling()

        assert decision.action == ScalingAction.NO_ACTION
        assert "min workers" in decision.reason.lower()

    def test_scale_down_limited_by_min_workers(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test scale down is limited by min_workers configuration."""
        auto_scaler.config.min_workers = 3

        queue_response = MagicMock()
        queue_response.json.return_value = {
            "rows": [{"pending": 0, "in_progress": 0, "waiting": 0}]
        }
        queue_response.raise_for_status = MagicMock()

        worker_response = MagicMock()
        worker_response.json.return_value = {
            "rows": [{"active": 5, "stale": 0, "capacity": 25}]
        }
        worker_response.raise_for_status = MagicMock()

        busy_response = MagicMock()
        busy_response.json.return_value = {"rows": [{"busy_workers": 0}]}
        busy_response.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [
            queue_response,
            worker_response,
            busy_response,
        ]

        decision = auto_scaler.evaluate_scaling()

        assert decision.action == ScalingAction.SCALE_DOWN
        # Should only remove down to min_workers (3), so remove 5-3=2
        assert decision.workers_to_remove <= 2
        assert decision.target_workers >= 3


# =============================================================================
# EVALUATE_SCALING TESTS - NO ACTION SCENARIOS
# =============================================================================


class TestEvaluateScalingNoAction:
    """Tests for evaluate_scaling() no-action scenarios."""

    def test_no_action_when_disabled(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test no action when auto-scaling is disabled."""
        auto_scaler.config.enabled = False

        decision = auto_scaler.evaluate_scaling()

        assert decision.action == ScalingAction.NO_ACTION
        assert "disabled" in decision.reason.lower()
        # No database calls should be made
        mock_http_client.post.assert_not_called()

    def test_no_action_when_queue_within_normal_range(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test no action when queue depth is within normal range."""
        queue_response = MagicMock()
        queue_response.json.return_value = {
            "rows": [{"pending": 3, "in_progress": 2, "waiting": 0}]
        }
        queue_response.raise_for_status = MagicMock()

        worker_response = MagicMock()
        worker_response.json.return_value = {
            "rows": [{"active": 3, "stale": 0, "capacity": 15}]
        }
        worker_response.raise_for_status = MagicMock()

        busy_response = MagicMock()
        busy_response.json.return_value = {"rows": [{"busy_workers": 2}]}
        busy_response.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [
            queue_response,
            worker_response,
            busy_response,
        ]

        decision = auto_scaler.evaluate_scaling()

        assert decision.action == ScalingAction.NO_ACTION
        assert "normal range" in decision.reason.lower()

    def test_no_action_when_queue_above_threshold_but_no_idle_workers(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test behavior when queue is low but all workers are busy."""
        auto_scaler.config.scale_down_threshold = 0

        queue_response = MagicMock()
        queue_response.json.return_value = {
            "rows": [{"pending": 0, "in_progress": 3, "waiting": 0}]
        }
        queue_response.raise_for_status = MagicMock()

        worker_response = MagicMock()
        worker_response.json.return_value = {
            "rows": [{"active": 3, "stale": 0, "capacity": 15}]
        }
        worker_response.raise_for_status = MagicMock()

        busy_response = MagicMock()
        busy_response.json.return_value = {"rows": [{"busy_workers": 3}]}
        busy_response.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [
            queue_response,
            worker_response,
            busy_response,
        ]

        decision = auto_scaler.evaluate_scaling()

        # Should be NO_ACTION since idle_count would be 0
        assert decision.action == ScalingAction.NO_ACTION


# =============================================================================
# COOLDOWN PERIOD TESTS
# =============================================================================


class TestCooldownPeriods:
    """Tests for cooldown period enforcement."""

    def test_scale_up_cooldown_blocks_scaling(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test that scale-up cooldown prevents rapid scaling."""
        # Set last scale up to recent time
        auto_scaler._last_scale_up = datetime.now(timezone.utc) - timedelta(seconds=60)

        queue_response = MagicMock()
        queue_response.json.return_value = {
            "rows": [{"pending": 20, "in_progress": 2, "waiting": 0}]
        }
        queue_response.raise_for_status = MagicMock()

        worker_response = MagicMock()
        worker_response.json.return_value = {
            "rows": [{"active": 2, "stale": 0, "capacity": 10}]
        }
        worker_response.raise_for_status = MagicMock()

        busy_response = MagicMock()
        busy_response.json.return_value = {"rows": [{"busy_workers": 2}]}
        busy_response.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [
            queue_response,
            worker_response,
            busy_response,
        ]

        decision = auto_scaler.evaluate_scaling()

        assert decision.action == ScalingAction.NO_ACTION
        assert "cooldown" in decision.reason.lower()

    def test_scale_down_cooldown_blocks_scaling(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test that scale-down cooldown prevents rapid scaling."""
        # Set last scale down to recent time
        auto_scaler._last_scale_down = datetime.now(timezone.utc) - timedelta(
            seconds=60
        )

        queue_response = MagicMock()
        queue_response.json.return_value = {
            "rows": [{"pending": 0, "in_progress": 0, "waiting": 0}]
        }
        queue_response.raise_for_status = MagicMock()

        worker_response = MagicMock()
        worker_response.json.return_value = {
            "rows": [{"active": 5, "stale": 0, "capacity": 25}]
        }
        worker_response.raise_for_status = MagicMock()

        busy_response = MagicMock()
        busy_response.json.return_value = {"rows": [{"busy_workers": 0}]}
        busy_response.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [
            queue_response,
            worker_response,
            busy_response,
        ]

        decision = auto_scaler.evaluate_scaling()

        assert decision.action == ScalingAction.NO_ACTION
        assert "cooldown" in decision.reason.lower()

    def test_scale_up_allowed_after_cooldown_expires(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test that scaling is allowed after cooldown period expires."""
        # Set last scale up to well past cooldown period
        auto_scaler._last_scale_up = datetime.now(timezone.utc) - timedelta(seconds=600)

        queue_response = MagicMock()
        queue_response.json.return_value = {
            "rows": [{"pending": 20, "in_progress": 2, "waiting": 0}]
        }
        queue_response.raise_for_status = MagicMock()

        worker_response = MagicMock()
        worker_response.json.return_value = {
            "rows": [{"active": 2, "stale": 0, "capacity": 10}]
        }
        worker_response.raise_for_status = MagicMock()

        busy_response = MagicMock()
        busy_response.json.return_value = {"rows": [{"busy_workers": 2}]}
        busy_response.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [
            queue_response,
            worker_response,
            busy_response,
        ]

        decision = auto_scaler.evaluate_scaling()

        assert decision.action == ScalingAction.SCALE_UP

    def test_scale_down_allowed_after_cooldown_expires(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test that scale down is allowed after cooldown period expires."""
        # Set last scale down to well past cooldown period
        auto_scaler._last_scale_down = datetime.now(timezone.utc) - timedelta(
            seconds=1200
        )

        queue_response = MagicMock()
        queue_response.json.return_value = {
            "rows": [{"pending": 0, "in_progress": 0, "waiting": 0}]
        }
        queue_response.raise_for_status = MagicMock()

        worker_response = MagicMock()
        worker_response.json.return_value = {
            "rows": [{"active": 5, "stale": 0, "capacity": 25}]
        }
        worker_response.raise_for_status = MagicMock()

        busy_response = MagicMock()
        busy_response.json.return_value = {"rows": [{"busy_workers": 0}]}
        busy_response.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [
            queue_response,
            worker_response,
            busy_response,
        ]

        decision = auto_scaler.evaluate_scaling()

        assert decision.action == ScalingAction.SCALE_DOWN

    def test_no_cooldown_when_never_scaled(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test that cooldown is not active when never scaled before."""
        assert auto_scaler._last_scale_up is None
        assert auto_scaler._last_scale_down is None

        assert auto_scaler._is_cooldown_active(ScalingAction.SCALE_UP) is False
        assert auto_scaler._is_cooldown_active(ScalingAction.SCALE_DOWN) is False

    def test_cooldown_custom_config(
        self, auto_scaler_custom_config: AutoScaler
    ) -> None:
        """Test cooldown with custom configuration values."""
        scaler = auto_scaler_custom_config

        # Set last scale up to 60 seconds ago (under custom cooldown of 120s)
        scaler._last_scale_up = datetime.now(timezone.utc) - timedelta(seconds=60)

        assert scaler._is_cooldown_active(ScalingAction.SCALE_UP) is True

        # Set last scale up to 180 seconds ago (over custom cooldown of 120s)
        scaler._last_scale_up = datetime.now(timezone.utc) - timedelta(seconds=180)

        assert scaler._is_cooldown_active(ScalingAction.SCALE_UP) is False


# =============================================================================
# DATABASE INTERACTION TESTS
# =============================================================================


class TestDatabaseInteractions:
    """Tests for database interaction methods with mocking."""

    def test_get_queue_metrics_empty_result(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test get_queue_metrics with empty database result."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"rows": []}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        metrics = auto_scaler.get_queue_metrics()

        assert metrics.pending_count == 0
        assert metrics.in_progress_count == 0
        assert metrics.total_actionable == 0

    def test_get_queue_metrics_with_data(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test get_queue_metrics with actual data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "rows": [{"pending": 10, "in_progress": 5, "waiting": 2}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        metrics = auto_scaler.get_queue_metrics()

        assert metrics.pending_count == 10
        assert metrics.in_progress_count == 5
        assert metrics.waiting_approval_count == 2
        assert metrics.total_actionable == 15

    def test_get_queue_metrics_null_values(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test get_queue_metrics handles null values gracefully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "rows": [{"pending": None, "in_progress": None, "waiting": None}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        metrics = auto_scaler.get_queue_metrics()

        assert metrics.pending_count == 0
        assert metrics.in_progress_count == 0

    def test_get_worker_metrics_empty_result(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test get_worker_metrics with empty database result."""
        mock_response1 = MagicMock()
        mock_response1.json.return_value = {"rows": []}
        mock_response1.raise_for_status = MagicMock()

        mock_response2 = MagicMock()
        mock_response2.json.return_value = {"rows": []}
        mock_response2.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [mock_response1, mock_response2]

        metrics = auto_scaler.get_worker_metrics()

        assert metrics.active_count == 0
        assert metrics.idle_count == 0

    def test_execute_query_error_handling(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test _execute_query raises RuntimeError on HTTP error."""
        import httpx

        mock_http_client.post.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock()
        )

        with pytest.raises(RuntimeError, match="Database query failed"):
            auto_scaler._execute_query("SELECT 1")


# =============================================================================
# SPAWN AND TERMINATE WORKER TESTS
# =============================================================================


class TestSpawnWorker:
    """Tests for spawn_worker method."""

    def test_spawn_worker_success(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test successful worker spawn."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"rows": [{"worker_id": "test-worker-abc123"}]}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        result = auto_scaler.spawn_worker()

        assert result is not None
        assert result.worker_id is not None
        assert result.worker_id.startswith("claude-worker-")
        assert auto_scaler._last_scale_up is not None

    def test_spawn_worker_failure(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test worker spawn failure."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"rows": []}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        result = auto_scaler.spawn_worker()

        assert result is not None
        assert result.success is False

    def test_spawn_worker_with_custom_type(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test worker spawn with custom worker type."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"rows": [{"worker_id": "custom-worker-xyz"}]}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        result = auto_scaler.spawn_worker(worker_type="custom-worker")

        assert result is not None
        assert result.worker_id is not None
        assert result.worker_id.startswith("custom-worker-")


class TestTerminateWorker:
    """Tests for terminate_worker method."""

    def test_terminate_worker_success(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test successful worker termination."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"rowCount": 1}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        result = auto_scaler.terminate_worker("test-worker-123")

        assert result is True
        assert auto_scaler._last_scale_down is not None

    def test_terminate_worker_not_found(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test worker termination when worker not found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"rowCount": 0}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        result = auto_scaler.terminate_worker("nonexistent-worker")

        assert result is False


# =============================================================================
# GET IDLE WORKERS TESTS
# =============================================================================


class TestGetIdleWorkers:
    """Tests for get_idle_workers method."""

    def test_get_idle_workers_returns_list(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test get_idle_workers returns list of worker IDs."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "rows": [
                {"worker_id": "worker-1"},
                {"worker_id": "worker-2"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        idle_workers = auto_scaler.get_idle_workers()

        assert len(idle_workers) == 2
        assert "worker-1" in idle_workers
        assert "worker-2" in idle_workers

    def test_get_idle_workers_empty(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test get_idle_workers returns empty list when no idle workers."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"rows": []}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        idle_workers = auto_scaler.get_idle_workers()

        assert len(idle_workers) == 0


# =============================================================================
# EXECUTE SCALING TESTS
# =============================================================================


class TestExecuteScaling:
    """Tests for execute_scaling method."""

    def test_execute_scaling_scale_up(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test execute_scaling performs scale up."""
        # Mock for evaluate_scaling
        queue_response = MagicMock()
        queue_response.json.return_value = {
            "rows": [{"pending": 20, "in_progress": 2, "waiting": 0}]
        }
        queue_response.raise_for_status = MagicMock()

        worker_response = MagicMock()
        worker_response.json.return_value = {
            "rows": [{"active": 2, "stale": 0, "capacity": 10}]
        }
        worker_response.raise_for_status = MagicMock()

        busy_response = MagicMock()
        busy_response.json.return_value = {"rows": [{"busy_workers": 2}]}
        busy_response.raise_for_status = MagicMock()

        # Mock for spawn_worker
        spawn_response = MagicMock()
        spawn_response.json.return_value = {"rows": [{"worker_id": "new-worker"}]}
        spawn_response.raise_for_status = MagicMock()

        mock_http_client.post.side_effect = [
            queue_response,
            worker_response,
            busy_response,
            spawn_response,
            spawn_response,
            spawn_response,
            spawn_response,
        ]

        result = auto_scaler.execute_scaling()

        assert result["action"] == "scale_up"
        assert len(result["workers_added"]) > 0

    def test_execute_scaling_no_action(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test execute_scaling with no action needed."""
        auto_scaler.config.enabled = False

        result = auto_scaler.execute_scaling()

        assert result["action"] == "no_action"
        assert len(result["workers_added"]) == 0
        assert len(result["workers_removed"]) == 0


# =============================================================================
# FACTORY FUNCTION TESTS
# =============================================================================


class TestCreateAutoScaler:
    """Tests for create_auto_scaler factory function."""

    def test_create_auto_scaler_default_config(self) -> None:
        """Test create_auto_scaler with default config."""
        scaler = create_auto_scaler(
            db_endpoint=TEST_DB_ENDPOINT,
            connection_string=TEST_CONNECTION_STRING,
        )

        assert isinstance(scaler, AutoScaler)
        assert scaler.config.min_workers == DEFAULT_MIN_WORKERS

    def test_create_auto_scaler_custom_config(
        self, custom_config: ScalingConfig
    ) -> None:
        """Test create_auto_scaler with custom config."""
        scaler = create_auto_scaler(
            db_endpoint=TEST_DB_ENDPOINT,
            connection_string=TEST_CONNECTION_STRING,
            config=custom_config,
        )

        assert isinstance(scaler, AutoScaler)
        assert scaler.config.min_workers == 2
        assert scaler.config.max_workers == 8


# =============================================================================
# LOG SCALING EVENT TESTS
# =============================================================================


class TestLogScalingEvent:
    """Tests for log_scaling_event method."""

    def test_log_scaling_event_success(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test successful scaling event logging."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"rowCount": 1}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        decision = ScalingDecision(
            action=ScalingAction.SCALE_UP,
            reason="Test scaling",
            current_workers=2,
            current_queue_depth=10,
            target_workers=4,
        )

        # Should not raise
        auto_scaler.log_scaling_event(decision)
        mock_http_client.post.assert_called_once()

    def test_log_scaling_event_table_not_exists(
        self, auto_scaler: AutoScaler, mock_http_client: MagicMock
    ) -> None:
        """Test log_scaling_event handles missing table gracefully."""
        mock_http_client.post.side_effect = RuntimeError("Table does not exist")

        decision = ScalingDecision(
            action=ScalingAction.NO_ACTION,
            reason="Test",
            current_workers=1,
            current_queue_depth=1,
        )

        # Should not raise, just log warning
        auto_scaler.log_scaling_event(decision)
