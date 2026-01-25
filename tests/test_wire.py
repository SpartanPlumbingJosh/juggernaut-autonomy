
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


def test_allocate_resources_clamps_to_min_and_max_defaults():
    tasks = [
        TaskSpec(task_id='a', priority=Priority.CRITICAL, estimated_complexity=1000.0),
        TaskSpec(task_id='b', priority=Priority.LOW, estimated_complexity=0.0),
    ]
    allocations = allocate_resources(tasks, 1000.0)

    assert allocations['a'] <= MAX_TASK_TIME
    assert allocations['b'] >= MIN_TASK_TIME

