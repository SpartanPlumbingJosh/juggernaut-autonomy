import logging
from typing import Any, Dict

import pytest

import core


@pytest.fixture
def sample_task() -> core.Task:
    return core.Task(
        task_id="task-1",
        task_type="type-a",
        payload={"key": "value"},
        metadata={"meta": "data"},
    )


@pytest.fixture
def sample_workers() -> Dict[str, core.Worker]:
    return {
        "w1": core.Worker(
            worker_id="w1",
            capabilities=["type-a", "type-b"],
            reliability_score=1.0,
            current_load=0.1,
        ),
        "w2": core.Worker(
            worker_id="w2",
            capabilities=["type-a"],
            reliability_score=2.0,
            current_load=0.5,
        ),
        "w3": core.Worker(
            worker_id="w3",
            capabilities=["type-c"],
            reliability_score=0.5,
            current_load=0.0,
        ),
    }


def test_task_to_dict_includes_all_fields(sample_task: core.Task) -> None:
    result = sample_task.to_dict()
    assert result["task_id"] == sample_task.task_id
    assert result["task_type"] == sample_task.task_type
    assert result["payload"] == sample_task.payload
    assert result["metadata"] == sample_task.metadata


def test_task_metadata_default_is_isolated_between_instances() -> None:
    t1 = core.Task(task_id="1", task_type="type", payload={})
    t2 = core.Task(task_id="2", task_type="type", payload={})

    t1.metadata["foo"] = "bar"

    assert "foo" not in t2.metadata
    assert t1.metadata != t2.metadata


def test_worker_to_dict_includes_all_fields() -> None:
    worker = core.Worker(
        worker_id="worker-1",
        capabilities=["type-a"],
        reliability_score=0.9,
        current_load=0.2,
    )

    result = worker.to_dict()
    assert result["worker_id"] == worker.worker_id
    assert result["capabilities"] == worker.capabilities
    assert result["reliability_score"] == worker.reliability_score
    assert result["current_load"] == worker.current_load


def test_worker_default_values() -> None:
    worker = core.Worker(worker_id="worker-1", capabilities=["type-a"])
    assert worker.reliability_score == 1.0
    assert worker.current_load == 0.0


def test_task_execution_result_dataclass_fields(sample_task: core.Task, sample_workers) -> None:
    worker = sample_workers["w1"]
    error = RuntimeError("test error")

    result = core.TaskExecutionResult(
        task=sample_task,
        worker=worker,
        success=False,
        result=None,
        error=error,
        attempts=3,
    )

    assert result.task is sample_task
    assert result.worker is worker
    assert result.success is False
    assert result.result is None
    assert result.error is error
    assert result.attempts == 3


def test_transient_worker_error_is_exception() -> None:
    with pytest.raises(core.TransientWorkerError):
        raise core.TransientWorkerError("transient failure")


def test_permanent_worker_error_is_exception() -> None:
    with pytest.raises(core.PermanentWorkerError):
        raise core.PermanentWorkerError("permanent failure")


def test_task_router_filters_by_capabilities_and_sorts_by_bias_and_load(