import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import wire
from wire import (
    DEFAULT_HEALTH_SNAPSHOT_INTERVAL_SECONDS,
    DEFAULT_LOOP_SLEEP_SECONDS,
    DEFAULT_SNAPSHOT_FILE_NAME,
    HealthSnapshot,
    Worker,
    _configure_logging,
    _get_load_average_1m,
    store_health_snapshot,
    track_metrics,
)


@pytest.fixture
def snapshot_path(tmp_path: Path) -> Path:
    return tmp_path / "snapshots" / "health.jsonl"


@pytest.fixture
def worker(snapshot_path: Path) -> Worker:
    return Worker(
        worker_id="worker-1",
        loop_sleep_seconds=0.01,
        health_snapshot_interval_seconds=1.0,
        snapshot_output_path=snapshot_path,
    )


def test_healthsnapshot_creation_and_serialization() -> None:
    snapshot = HealthSnapshot(
        worker_id="worker-123",
        timestamp=1700000000.0,
        loop_iteration=42,
        uptime_seconds=12.34,
        process_id=1234,
        thread_count=7,
        load_average_1m=None,
    )

    assert snapshot.worker_id == "worker-123"
    assert snapshot.loop_iteration == 42
    assert snapshot.load_average_1m is None

    data = json.loads(json.dumps(snapshot.__dict__))
    assert data["worker_id"] == "worker-123"
    assert data["loop_iteration"] == 42
    assert "load_average_1m" in data


def test__get_load_average_1m_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getloadavg():
        return (1.5, 2.0, 3.0)

    monkeypatch.setattr(wire.os, "getloadavg", fake_getloadavg)

    result = _get_load_average_1m()
    assert result == 1.5
    assert isinstance(result, float)


@pytest.mark.parametrize("exc_type", [OSError, AttributeError])
def test__get_load_average_1m_unsupported(monkeypatch: pytest.MonkeyPatch, exc_type) -> None:
    def fake_getloadavg():
        raise exc_type("no loadavg")

    monkeypatch.setattr(wire.os, "getloadavg", fake_getloadavg)

    assert _get_load_average_1m() is None


def test_track_metrics_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=wire.__name__)

    track_metrics("worker-x", 5)

    assert any(
        "Tracking metrics for worker_id=worker-x iteration=5" in message
        for message in caplog.messages
    )


def test_store_health_snapshot_writes_json_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_time = 1700000000.0
    start_monotonic = 100.0
    current_monotonic = 110.0

    monkeypatch.setattr(wire.time, "time", lambda: fixed_time)
    monkeypatch.setattr(wire.time, "monotonic", lambda: current_monotonic)
    monkeypatch.setattr(wire.os, "getpid", lambda: 4321)
    monkeypatch.setattr(wire.threading, "active_count", lambda: 3)
    monkeypatch.setattr(wire, "_get_load_average_1m", lambda: 0.75)

    output_path = tmp_path / "nested" / "health.jsonl"

    snapshot = store_health_snapshot(
        worker_id="worker-abc",
        loop_iteration=2,
        started_at_monotonic=start_monotonic