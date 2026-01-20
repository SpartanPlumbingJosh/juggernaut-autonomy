import logging
from datetime import datetime
from unittest.mock import MagicMock

import pytest

import wire
from wire import (
    Task,
    TaskAlreadyCompletedError,
    TaskNotFoundError,
    TaskStatus,
    TaskVerificationError,
    InMemoryTaskRepository,
)


@pytest.fixture
def in_memory_repo() -> InMemoryTaskRepository:
    return InMemoryTaskRepository()


class TestTaskStatus:
    def test_task_status_values_and_names(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED_VERIFICATION.value == "failed_verification"

        assert TaskStatus["PENDING"] is TaskStatus.PENDING
        assert TaskStatus["IN_PROGRESS"] is TaskStatus.IN_PROGRESS
        assert TaskStatus["COMPLETED"] is TaskStatus.COMPLETED
        assert TaskStatus["FAILED_VERIFICATION"] is TaskStatus.FAILED_VERIFICATION


class TestTaskDataclass:
    def test_task_defaults_status_pending_and_timestamps(self):
        task = Task(id="t1", description="Test task")

        assert task.id == "t1"
        assert task.description == "Test task"
        assert task.status is TaskStatus.PENDING
        assert isinstance(task.updated_at, datetime)
        assert task.verified_at is None

    def test_task_custom_initial_values(self):
        custom_time = datetime(2020, 1, 1)
        task = Task(
            id="t2",
            description="Custom",
            status=TaskStatus.IN_PROGRESS,
            updated_at=custom_time,
            verified_at=custom_time,
        )

        assert task.status is TaskStatus.IN_PROGRESS
        assert task.updated_at is custom_time
        assert task.verified_at is custom_time


class TestInMemoryTaskRepository:
    def test_get_task_returns_none_when_missing(self, in_memory_repo: InMemoryTaskRepository):
        assert in_memory_repo.get_task("missing") is None

    def test_save_and_get_task_roundtrip(self, in_memory_repo: InMemoryTaskRepository):
        task = Task(id="t1", description="Test")
        in_memory_repo.save_task(task)

        retrieved = in_memory_repo.get_task("t1")
        assert retrieved is task
        assert retrieved.id == "t1"
        assert retrieved.description == "Test"


class TestExceptions:
    def test_task_not_found_error_message_and_attr(self):
        exc = TaskNotFoundError("abc")
        assert exc.task_id == "abc"
        assert str(exc) == "Task not found: abc"

    def test_task_verification_error_default_message_and_attr(self):
        exc = TaskVerificationError("xyz")
        assert exc.task_id == "xyz"
        assert str(exc) == "Task failed verification: xyz"

    def test_task_verification_error_custom_message(self):
        exc = TaskVerificationError("xyz", message="Custom failure")
        assert exc.task_id == "xyz"
        assert str(exc