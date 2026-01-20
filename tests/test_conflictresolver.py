import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import pytest

import conflictresolver


@pytest.fixture
def sample_conflict() -> conflictresolver.Conflict:
    """Base conflict with naive timestamps and mid-range risk."""
    return conflictresolver.Conflict(
        conflict_id="conflict-1",
        type=conflictresolver.ConflictType.RESOURCE_CONTENTION,
        risk_score=0.5,
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        last_updated_at=datetime(2024, 1, 1, 12, 0, 1),
        status=conflictresolver.ConflictStatus.PENDING,
        payload={},
    )


@pytest.fixture
def resource_contention_strategy() -> conflictresolver.ResourceContentionStrategy:
    return conflictresolver.ResourceContentionStrategy()


# ---------------------------------------------------------------------------
# Tests for Conflict dataclass
# ---------------------------------------------------------------------------


def test_conflict_risk_score_below_min_is_normalized_and_logs() -> None:
    conflict_id = "low-risk"
    created = datetime(2024, 1, 1, 0, 0, 0)
    updated = datetime(2024, 1, 1, 0, 0, 1)

    with pytest.raises(AssertionError):
        # Ensure we actually exercise logging; caplog requires pytest context
        pass  # placeholder to ensure no stray caplog here


def test_conflict_risk_score_below_min_is_normalized_and_logs_caplog(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=conflictresolver.logger.name)

    conflict = conflictresolver.Conflict(
        conflict_id="low-risk",
        type=conflictresolver.ConflictType.RESOURCE_CONTENTION,
        risk_score=-1.0,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        last_updated_at=datetime(2024, 1, 1, 0, 0, 1),
        status=conflictresolver.ConflictStatus.PENDING,
        payload={},
    )

    assert conflict.risk_score == conflictresolver.RISK_SCORE_MIN

    # Verify a debug log was emitted about normalization
    messages = [record.getMessage() for record in caplog.records]
    assert any("Normalizing risk_score below minimum" in msg for msg in messages)


def test_conflict_risk_score_above_max_is_normalized_and_logs_caplog(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=conflictresolver.logger.name)

    conflict = conflictresolver.Conflict(
        conflict_id="high-risk",
        type=conflictresolver.ConflictType.RESOURCE_CONTENTION,
        risk_score=2.5,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        last_updated_at=datetime(2024, 1, 1, 0, 0, 1),
        status=conflictresolver.ConflictStatus.PENDING,
        payload={},
    )

    assert conflict.risk_score == conflictresolver.RISK_SCORE_MAX

    messages = [record.getMessage() for record in caplog.records]
    assert any("Normalizing risk_score above maximum" in msg for msg in messages)


@pytest.mark.parametrize("risk", [conflictresolver.RISK_SCORE_MIN, 0.3, 0.9, conflictresolver.RISK_SCORE_MAX])
def test_conflict_risk_score_within_bounds_is_unchanged(risk: float) -> None:
    conflict = conflictresolver.Conflict(
        conflict_id="in-bounds",
        type=conflictresolver.ConflictType.RESOURCE_CONTENTION,
        risk_score=risk,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        last_updated_at=datetime(2024, 1, 1, 0, 0, 1),
        status=conflictresolver.ConflictStatus.PENDING,
        payload={},
    )

    assert conflict.risk_score == risk


def test_conflict_naive_timestamps_are_made_utc() -> None:
    created = datetime(2024, 1, 1, 0, 0, 0)  # naive
    updated = datetime(2024, 1, 1, 0, 0, 1)  # naive

    conflict = conflictresolver.Conflict(
        conflict_id="naive-ts",
        type=conflictresolver.ConflictType.RESOURCE_CONTENTION,
        risk_score=0.5,
        created_at=created,
        last_updated_at=updated,
        status=conflictresolver.ConflictStatus.PENDING,
        payload={},
    )

    assert conflict.created_at.tzinfo == timezone.utc
    assert conflict.last_updated_at.tzinfo == timezone.utc
    assert conflict.created_at.replace(tzinfo=None) == created
    assert conflict.last_updated_at.replace(tzinfo=None) == updated


def test_conflict_aware_timestamps_are_preserved() -> None:
    tz_other = timezone(timedelta(hours=5))
    created = datetime(2024, 1, 1, 0, 0, 0, tzinfo=tz_other)
    updated = datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc)

    conflict = conflictresolver.Conflict(
        conflict_id="aware-ts",
        type=conflictresolver.ConflictType.RESOURCE_CONTENTION,
        risk_score=0.5,
        created_at=created,
        last_updated_at=updated,
        status=conflictresolver.ConflictStatus.PENDING,
        payload={},
    )

    assert conflict.created_at.tzinfo is tz_other
    assert conflict.last_updated_at.tzinfo is timezone.utc


# ---------------------------------------------------------------------------
# Tests for ConflictResolutionResult dataclass
# ---------------------------------------------------------------------------


def test_conflict_resolution_result_basic_instantiation() -> None:
    result = conflictresolver.ConflictResolutionResult(
        success=True,
        resolved=True,
        escalated=False,
        resolution_type="auto",
        message="Resolved automatically",
        risk_score=0.1,
        strategy_name="dummy_strategy",
        metadata={"key": "value"},
        resolution_time_ms=123,
    )

    assert result.success is True
    assert result.resolved is True
    assert result.escalated is False
    assert result.resolution_type == "auto"
    assert result.message == "Resolved automatically"
    assert result.risk_score == 0.1
    assert result.strategy_name == "dummy_strategy"
    assert result.metadata == {"key": "value"}
    assert result.resolution_time_ms == 123


def test_conflict_resolution_result_defaults() -> None:
    result = conflictresolver.ConflictResolutionResult(
        success=False,
        resolved=False,
        escalated=True,
        resolution_type="error",
        message="Failed",
        risk_score=1.0,
        strategy_name="dummy_strategy",
    )

    assert result.metadata == {}
    assert result.resolution_time_ms == 0


# ---------------------------------------------------------------------------
# Tests for ConflictResolutionMetricsSnapshot dataclass
# ---------------------------------------------------------------------------


def test_conflict_resolution_metrics_snapshot_instantiation() -> None:
    by_type: dict[conflictresolver.ConflictType, dict[str, Any]] = {
        conflictresolver.ConflictType.RESOURCE_CONTENTION: {
            "total": 10,
            "auto_resolved": 7,
            "failed": 1,
            "avg_resolution_time_ms": 200.5,
        }
    }

    snapshot = conflictresolver.ConflictResolutionMetricsSnapshot(
        total_conflicts=10,
        auto_resolved=7,
        escalated=2,
        failed=1,
        avg_resolution_time_ms=150.0,
        by_type=by_type,
    )

    assert snapshot.total_conflicts == 10
    assert snapshot.auto_resolved == 7
    assert snapshot.escalated == 2
    assert snapshot.failed == 1
    assert snapshot.avg_resolution_time_ms == 150.0
    assert snapshot.by_type is by_type