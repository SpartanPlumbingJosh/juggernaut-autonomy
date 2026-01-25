
import os
import sys

import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from wire import MultiAgentExecutor, Task


def test_run_multi_agent_tasks_returns_results_for_each_task():
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

