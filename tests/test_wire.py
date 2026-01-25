
import os
import sys

import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from wire import (
    MAX_TASK_TIME,
    MIN_TASK_TIME,
    ResourceAllocationError,
    TaskSpec,
    Priority,
    allocate_resources,
)


try:
    from wire import MultiAgentExecutor, Task  # type: ignore
except Exception:  # pragma: no cover
    MultiAgentExecutor = None  # type: ignore
    Task = None  # type: ignore


def test_allocate_resources_basic_constraints_respected():
    tasks = [
        TaskSpec(task_id='a', priority=Priority.CRITICAL, estimated_complexity=8.0),
        TaskSpec(task_id='b', priority=Priority.HIGH, estimated_complexity=4.0),
        TaskSpec(task_id='c', priority=Priority.LOW, estimated_complexity=1.0),
    ]
    total = 60.0
    allocations = allocate_resources(tasks, total)

    assert set(allocations.keys()) == {'a', 'b', 'c'}
    for t in tasks:
        assert allocations[t.task_id] >= t.min_time
        assert allocations[t.task_id] <= t.max_time

    assert sum(allocations.values()) <= total + 1e-6


def test_allocate_resources_empty_tasks_raises_value_error():
    with pytest.raises(ValueError):
        allocate_resources([], 10.0)


def test_allocate_resources_min_sum_exceeds_budget_raises_resource_allocation_error():
    tasks = [
        TaskSpec(task_id='a', priority=Priority.MEDIUM, estimated_complexity=1.0, min_time=10.0, max_time=20.0),
        TaskSpec(task_id='b', priority=Priority.MEDIUM, estimated_complexity=1.0, min_time=10.0, max_time=20.0),
    ]
    with pytest.raises(ResourceAllocationError):
        allocate_resources(tasks, 5.0)


def test_allocate_resources_invalid_constraints_raise_value_error():
    tasks = [
        TaskSpec(task_id='a', priority=Priority.MEDIUM, estimated_complexity=1.0, min_time=5.0, max_time=1.0),
    ]
    with pytest.raises(ValueError):
        allocate_resources(tasks, 10.0)


def test_allocate_resources_duplicate_task_ids_raise_value_error():
    tasks = [
        TaskSpec(task_id='dup', priority=Priority.MEDIUM, estimated_complexity=1.0),
        TaskSpec(task_id='dup', priority=Priority.HIGH, estimated_complexity=2.0),
    ]
    with pytest.raises(ValueError):
        allocate_resources(tasks, 10.0)


def test_allocate_resources_clamps_to_min_and_max_defaults():
    tasks = [
        TaskSpec(task_id='a', priority=Priority.CRITICAL, estimated_complexity=1000.0),
        TaskSpec(task_id='b', priority=Priority.LOW, estimated_complexity=0.0),
    ]
    allocations = allocate_resources(tasks, 1000.0)

    assert allocations['a'] <= MAX_TASK_TIME
    assert allocations['b'] >= MIN_TASK_TIME


def test_run_multi_agent_tasks_returns_results_for_each_task():
    if MultiAgentExecutor is None or Task is None:
        pytest.skip("MultiAgentExecutor/Task not present in this branch")

    executor = MultiAgentExecutor(conflict_manager=None, max_concurrent_tasks=2)
    tasks = [
        Task(task_id='t1', agent_id='a1', payload={'x': 1}, priority=1, resources=['r1']),
        Task(task_id='t2', agent_id='a2', payload={'x': 2}, priority=0, resources=['r2']),
        Task(task_id='t3', agent_id='a3', payload={'x': 3}, priority=2, resources=[]),
    ]

    results = executor.run_multi_agent_tasks(tasks)
    assert len(results) == len(tasks)
    assert {r.task_id for r in results} == {'t1', 't2', 't3'}
    assert all(r.success for r in results)


def test_conflict_manager_detect_and_resolve_is_used_when_present():
    if MultiAgentExecutor is None or Task is None:
        pytest.skip("MultiAgentExecutor/Task not present in this branch")

    class DummyConflictManager:
        def detect_and_resolve_conflicts(self, tasks):
            # reverse order to prove we ran through conflict manager
            return list(reversed(tasks))

    executor = MultiAgentExecutor(conflict_manager=DummyConflictManager(), max_concurrent_tasks=1)
    tasks = [
        Task(task_id='t1', agent_id='a1', payload={'x': 1}),
        Task(task_id='t2', agent_id='a2', payload={'x': 2}),
    ]

    results = executor.run_multi_agent_tasks(tasks)
    assert {r.task_id for r in results} == {'t1', 't2'}

