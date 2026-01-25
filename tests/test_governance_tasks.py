import json
import logging
import os
import sqlite3
import sys
from datetime import datetime

import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import governance_tasks
from governance_tasks import (
    GovernanceTask,
    GovernanceTaskManager,
    STATUS_PENDING,
    STATUS_COMPLETED,
    STATUS_DRY_RUN_COMPLETED,
    ISO_FORMAT,
    SQLITE_BOOLEAN_TRUE,
    SQLITE_BOOLEAN_FALSE,
)


@pytest.fixture
def in_memory_manager():
    manager = GovernanceTaskManager(db_path=":memory:")
    try:
        yield manager
    finally:
        # Close the connection if it has a close method
        connection = getattr(manager, "_connection", None)
        if connection is not None and hasattr(connection, "close"):
            connection.close()


def test_sqlite_boolean_constants_values():
    assert SQLITE_BOOLEAN_TRUE == 1
    assert SQLITE_BOOLEAN_FALSE == 0


def test_governance_task_dataclass_initialization():
    now = datetime.utcnow()
    task = GovernanceTask(
        id=1,
        name="test_task",
        parameters={"key": "value"},
        dry_run=True,
        dry_run_result={"result": "ok"},
        status=STATUS_PENDING,
        created_at=now,
        updated_at=now,
    )
    assert task.id == 1
    assert task.name == "test_task"
    assert task.parameters == {"key": "value"}
    assert task.dry_run is True
    assert task.dry_run_result == {"result": "ok"}
    assert task.status == STATUS_PENDING
    assert isinstance(task.created_at, datetime)
    assert isinstance(task.updated_at, datetime)


def test_init_uses_given_db_path_and_creates_file(tmp_path):
    db_path = tmp_path / "governance_tasks_test.db"
    manager = GovernanceTaskManager(db_path=str(db_path))
    try:
        assert db_path.exists()
        assert isinstance(manager._connection, sqlite3.Connection)
        assert manager._connection.row_factory is sqlite3.Row
    finally:
        manager._connection.close()


def test_init_logs_and_raises_on_connection_error(monkeypatch, caplog):
    def fake_connect(_path):
        raise sqlite3.Error("connection failed")

    monkeypatch.setattr(governance_tasks.sqlite3, "connect", fake_connect)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(sqlite3.Error):
            GovernanceTaskManager(db_path=":memory:")

    assert "Failed to connect to SQLite database at" in caplog.text


def test_ensure_schema_creates_required_tables(in_memory_manager):
    cursor = in_memory_manager._connection.cursor()

    # Check governance_tasks table exists with expected columns
    cursor.execute("PRAGMA table_info(governance_tasks)")
    columns = {row["name"] for row in cursor.fetchall()}
    expected_task_columns = {
        "id",
        "name",
        "parameters",
        "dry_run",
        "dry_run_result",
        "status",
        "created_at",
        "updated_at",
    }
    assert columns == expected_task_columns


def test_create_task_persists_row(in_memory_manager):
    task_id = in_memory_manager.create_task(name="demo", parameters={"k": "v"}, dry_run=False)
    assert isinstance(task_id, int)
    assert task_id > 0

    row = in_memory_manager._connection.execute("SELECT name, parameters, dry_run, status FROM governance_tasks WHERE id=?", (task_id,)).fetchone()
    assert row is not None
    assert row["name"] == "demo"
    assert json.loads(row["parameters"]) == {"k": "v"}
    assert int(row["dry_run"]) == SQLITE_BOOLEAN_FALSE
    assert row["status"] == STATUS_PENDING


def test_execute_task_dry_run_sets_result_and_status(in_memory_manager):
    task_id = in_memory_manager.create_task(name="demo", parameters={"x": 1}, dry_run=True)
    updated = in_memory_manager.execute_task(task_id)

    assert updated is not None
    assert updated.id == task_id
    assert updated.dry_run is True
    assert updated.status == STATUS_DRY_RUN_COMPLETED
    assert updated.dry_run_result is not None
    assert updated.dry_run_result.get("dry_run") is True
