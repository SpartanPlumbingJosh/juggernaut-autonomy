import builtins
import importlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

import failover
from failover import (
    API_UNAVAILABLE,
    CPU_USAGE_THRESHOLD_PERCENT,
    DB_UNAVAILABLE,
    DEFAULT_HEALTH_CHECK_INTERVAL_SECONDS,
    HEARTBEAT_FAILOVER_THRESHOLD_MINUTES,
    HEARTBEAT_STALE,
    HEARTBEAT_WARNING_THRESHOLD_MINUTES,
    MAX_WORKER_RECOVERY_MINUTES,
    MEMORY_USAGE_THRESHOLD_PERCENT,
    RESOURCE_EXHAUSTION,
    Worker,
    WorkerHealthStatus,
    FailureType,
    Task,
    FailoverEvent,
    WorkerRepository,
    LOGGER,
)


@pytest.fixture
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def sample_worker(utc_now: datetime) -> Worker:
    return Worker(
        worker_id="worker-1",
        role="worker",
        last_heartbeat=utc_now,
        metadata={"region": "us-east-1"},
    )


@pytest.fixture
def sample_task(sample_worker: Worker) -> Task:
    return Task(
        task_id="task-1",
        worker_id=sample_worker.worker_id,
        payload={"job": "process-data"},
    )


@pytest.fixture
def sample_failover_event(sample_worker: Worker, utc_now: datetime) -> FailoverEvent:
    return FailoverEvent(
        worker_id=sample_worker.worker_id,
        failure_type=FailureType.HEARTBEAT_STALE,
        detected_at=utc_now,
        details="Heartbeat stale for worker-1",
    )


def test_constants_have_expected_values():
    assert HEARTBEAT_WARNING_THRESHOLD_MINUTES == 5
    assert HEARTBEAT_FAILOVER_THRESHOLD_MINUTES == 15
    assert MAX_WORKER_RECOVERY_MINUTES == 5
    assert CPU_USAGE_THRESHOLD_PERCENT == 95.0
    assert MEMORY_USAGE_THRESHOLD_PERCENT == 95.0
    assert DEFAULT_HEALTH_CHECK_INTERVAL_SECONDS == 30


def test_failure_type_enum_members_are_unique():
    values = {member.value for member in FailureType}
    assert len(values) == len(FailureType)


def test_worker_health_status_enum_members_are_unique():
    values = {member.value for member in WorkerHealthStatus}
    assert len(values) == len(WorkerHealthStatus)


def test_failure_type_specific_members_exist():
    assert FailureType.HEARTBEAT_STALE is HEARTBEAT_STALE
    assert FailureType.DB_UNAVAILABLE is DB_UNAVAILABLE
    assert FailureType.API_UNAVAILABLE is API_UNAVAILABLE
    assert FailureType.RESOURCE_EXHAUSTION is RESOURCE_EXHAUSTION


def test_worker_dataclass_defaults(utc_now: datetime):
    worker = Worker(worker_id="w-1", role="worker", last_heartbeat=utc_now)
    assert worker.worker_id == "w-1"
    assert worker.role == "worker"
    assert worker.last_heartbeat is utc_now
    assert worker.active is True
    assert isinstance(worker.metadata, dict)
    assert worker.metadata == {}


def test_worker_allows_custom_metadata(utc_now: datetime):
    worker = Worker(
        worker_id="w-2",
        role="orchestrator",
        last_heartbeat=utc_now,
        active=False,
        metadata={"key": "value"},
    )
    assert worker.active is False
    assert worker.metadata == {"key": "value"}


def test_worker_equality_based_on_fields(utc_now: datetime):
    w1 = Worker(worker_id="same", role="role", last_heartbeat=utc_now)
    w2 = Worker(worker_id="same", role="role", last_heartbeat=utc_now)
    assert w1 == w2


def test_task_dataclass_defaults(sample_worker: Worker):
    task = Task(task_id="t-1", worker_id=sample_worker.worker_id)
    assert task.task_id == "t-1"
    assert task.worker_id == sample_worker.worker_id
    assert isinstance(task.payload, dict)
    assert task.payload == {}


def test_task_allows_none_worker_id():
    task = Task(task_id="t-2", worker_id=None)
    assert task.worker_id is None


def test_task_equality_based_on_fields():
    t1 = Task(task_id="t-1", worker_id=None, payload={"a": "b"})
    t2 = Task(task_id="t-1", worker_id=None, payload={"a": "b"})
    assert t1 == t2


def test_failover_event_defaults(sample_failover_event: FailoverEvent, utc_now: datetime):
    event = sample_failover_event
    assert event.worker_id == "worker-1"
    assert event.failure_type is FailureType.HEARTBEAT_STALE
    assert isinstance(event.detected_at, datetime)
    assert event.recovered_at is None
    assert event.recovery_duration is None
    assert "Heartbeat stale" in event.details


def test_failover_event_with_recovery_times(utc_now: datetime):
    detected_at = utc_now
    recovered_at = utc_now + timedelta(seconds=30)
    event = FailoverEvent(
        worker_id=None,
        failure_type=FailureType.DB_UNAVAILABLE,
        detected_at=detected_at,
        recovered_at=recovered_at,
        details="Database outage",
        recovery_duration=(recovered_at - detected_at).total_seconds(),
    )
    assert event.worker_id is None
    assert event.failure_type is FailureType.DB_UNAVAILABLE
    assert event.detected_at == detected_at
    assert event.recovered_at == recovered_at
    assert event.recovery_duration == 30.0


def test_failover_event_equality_based_on_fields(utc_now: datetime):
    e1 = FailoverEvent(
        worker_id="w1",
        failure_type=FailureType.API_UNAVAILABLE,
        detected_at=utc_now,
    )
    e2 = FailoverEvent(
        worker_id="w1",
        failure_type=FailureType.API_UNAVAILABLE,
        detected_at=utc_now,
    )
    assert e1 == e2


def test_worker_repository_runtime_checkable_accepts_valid_impl(sample_worker: Worker):
    class InMemoryWorkerRepo:
        def __init__(self):
            self._workers = {}

        def get_all_workers(self):
            return list(self._workers.values())

        def get_worker(self, worker_id: str):
            return self._workers.get(worker_id)

        def save_worker(self, worker: Worker) -> None:
            self._workers[worker.worker_id] = worker

    repo = InMemoryWorkerRepo()
    assert isinstance(repo, WorkerRepository)

    # Behavior test using the protocol methods
    assert repo.get_all_workers() == []
    repo.save_worker(sample_worker)
    assert repo.get_worker(sample_worker.worker_id) is sample_worker
    assert repo.get_all_workers() == [sample_worker]


def test_worker_repository_runtime_checkable_rejects_incomplete_impl():
    class IncompleteRepo:
        # Missing get_worker and save_worker
        def get_all_workers(self):
            return []

    incomplete = IncompleteRepo()
    assert not isinstance(incomplete, WorkerRepository)


def test_worker_repository_allows_subclassing_protocol(sample_worker: Worker):
    class BaseRepo(WorkerRepository):  # type: ignore[misc]
        def get_all_workers(self):
            raise NotImplementedError

        def get_worker(self, worker_id: str):
            raise NotImplementedError

        def save_worker(self, worker: Worker) -> None:
            raise NotImplementedError

    class ConcreteRepo(BaseRepo):
        def __init__(self):
            self._workers = {}

        def get_all_workers(self):
            return list(self._workers.values())

        def get_worker(self, worker_id: str):
            return self._workers.get(worker_id)

        def save_worker(self, worker: Worker) -> None:
            self._workers[worker.worker_id] = worker

    repo = ConcreteRepo()
    assert isinstance(repo, WorkerRepository)
    repo.save_worker(sample_worker)
    assert repo.get_worker(sample_worker.worker_id) is sample_worker


def test_logger_is_configured_logger_instance():
    assert LOGGER is not None
    assert LOGGER.name == "failover"
    assert isinstance(LOGGER, type(failover.logging.getLogger(__name__)))


def test_psutil_import_error_sets_psutil_to_none(monkeypatch):
    # Ensure a clean import of the module with psutil import failing
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "psutil":
            raise ImportError("psutil not available")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # Remove any existing cached module to force re-import
    if "failover" in sys.modules:
        del sys.modules["failover"]

    module = importlib.import_module("failover")
    assert module.psutil is None


def test_psutil_present_attribute_exists():
    # In normal import scenarios, psutil attribute should always exist
    # either as the imported module or None when import fails.
    assert hasattr(failover, "psutil")