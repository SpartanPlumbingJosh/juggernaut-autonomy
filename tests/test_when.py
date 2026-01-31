import json
import sqlite3
import uuid as uuidlib
from dataclasses import FrozenInstanceError
from typing import Dict, Optional
from unittest.mock import Mock

import pytest

import when


@pytest.fixture()
def fixed_now_iso() -> str:
    return "2020-01-01T00:00:00+00:00"


@pytest.fixture()
def fixed_uuid() -> uuidlib.UUID:
    return uuidlib.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture()
def sample_conversation() -> list[when.ChatMessage]:
    return [
        when.ChatMessage(role="system", content="You are a helpful assistant.", timestamp="2019-12-31T23:59:00+00:00"),
        when.ChatMessage(role="user", content="Please do the thing.", timestamp="2019-12-31T23:59:30+00:00"),
        when.ChatMessage(role="assistant", content="Working on it.", timestamp="2019-12-31T23:59:45+00:00"),
    ]


@pytest.fixture()
def sample_action() -> when.ActionRequest:
    return when.ActionRequest(
        raw_text="Deploy to production",
        tool_name="deploy_tool",
        operation="deploy",
        requires_async=False,
        requires_approval=True,
        estimated_duration_s=1,
        metadata={"env": "prod"},
    )


@pytest.fixture()
def sample_task(fixed_now_iso: str, fixed_uuid: uuidlib.UUID) -> when.GovernanceTask:
    return when.GovernanceTask(
        task_id=str(fixed_uuid),
        task_type=when.TASK_TYPE_DEPLOYMENT,
        status=when.STATUS_QUEUED,
        created_at=fixed_now_iso,
        title="Deploy to production",
        description="Some description",
        conversation_context={"messages": [], "window": 20, "generated_at": fixed_now_iso},
        action={"raw_text": "Deploy to production"},
        metadata={"user_id": "u1"},
    )


@pytest.fixture()
def sqlite_repo(tmp_path) -> when.SqliteGovernanceTaskRepository:
    db_path = tmp_path / "test.db"
    return when.SqliteGovernanceTaskRepository(str(db_path))


def _fetch_row_by_id(db_path: str, task_id: str) -> Optional[Dict[str, str]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(f"SELECT * FROM {when.TABLE_NAME} WHERE task_id = ?", (task_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def test_chat_message_default_metadata_is_distinct_instances() -> None:
    m1 = when.ChatMessage(role="user", content="a")
    m2 = when.ChatMessage(role="user", content="b")
    assert m1.metadata == {}
    assert m2.metadata == {}
    assert m1.metadata is not m2.metadata


def test_action_request_default_metadata_is_distinct_instances() -> None:
    a1 = when.ActionRequest(raw_text="a")
    a2 = when.ActionRequest(raw_text="b")
    assert a1.metadata == {}
    assert a2.metadata == {}
    assert a1.metadata is not a2.metadata


def test_governance_task_default_metadata_is_distinct_instances() -> None:
    t1 = when.GovernanceTask(
        task_id="t1",
        task_type=when.TASK_TYPE_UNKNOWN,
        status=when.STATUS_QUEUED,
        created_at="2020-01-01T00:00:00+00:00",
        title="x",
        description="y",
        conversation_context={},
        action={},
    )
    t2 = when.GovernanceTask(
        task_id="t2",
        task_type=when.TASK_TYPE_UNKNOWN,
        status=when.STATUS_QUEUED,
        created_at="2020-01-01T00:00:00+00:00",
        title="x",
        description="y",
        conversation_context={},
        action={},
    )
    assert t1.metadata == {}
    assert t2.metadata == {}
    assert t1.metadata is not t2.metadata


def test_chat_message_is_frozen_and_cannot_be_modified() -> None:
    msg = when.ChatMessage(role="user", content="hello")
    with pytest.raises(FrozenInstanceError):
        msg.content = "changed"  # type: ignore[misc]


def test_sqlite_repository_creates_schema_on_init(tmp_path) -> None:
    db_path = tmp_path / "schema_init.db"
    _ = when.SqliteGovernanceTaskRepository(str(db_path))

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (when.TABLE_NAME,),
        ).fetchone()
        assert row is not None
        assert row[0] == when.TABLE_NAME
    finally:
        conn.close()


def test_sqlite_repository_init_raises_when_schema_creation_fails(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "bad_schema.db"

    def _bad_connect(self):
        raise sqlite3.OperationalError("cannot connect")

    monkeypatch.setattr(when.SqliteGovernanceTaskRepository, "_connect", _bad_connect)
    with pytest.raises(sqlite3.OperationalError):
        when.SqliteGovernanceTaskRepository(str(db_path))


def test_sqlite_repository_create_and_get_roundtrip(sqlite_repo, sample_task) -> None:
    task_id = sqlite_repo.create(sample_task)
    assert task_id == sample_task.task_id

    loaded = sqlite_repo.get(sample_task.task_id)
    assert loaded == sample_task
    assert loaded is not sample_task


def test_sqlite_repository_get_returns_none_when_missing(sqlite_repo) -> None:
    assert sqlite_repo.get("does-not-exist") is None


def test_sqlite_repository_create_raises_integrity_error_on_duplicate_id(sqlite_repo, sample_task) -> None:
    sqlite_repo.create(sample_task)
    with pytest.raises(sqlite3.IntegrityError):
        sqlite_repo.create(sample_task)


def test_sqlite_repository_create_raises_operational_error_when_db_fails(monkeypatch, tmp_path, sample_task) -> None:
    repo = when.SqliteGovernanceTaskRepository(str(tmp_path / "ops_fail.db"))

    def _bad_connect():
        raise sqlite3.OperationalError("db down")

    monkeypatch.setattr(repo, "_connect", _bad_connect)
    with pytest.raises(sqlite3.OperationalError):
        repo.create(sample_task)


def test_sqlite_repository_get_raises_operational_error_when_db_fails(monkeypatch, tmp_path) -> None:
    repo = when.SqliteGovernanceTaskRepository(str(tmp_path / "ops_fail_get.db"))

    def _bad_connect():
        raise sqlite3.OperationalError("db down")

    monkeypatch.setattr(repo, "_connect", _bad_connect)
    with pytest.raises(sqlite3.OperationalError):
        repo.get("any-id")


def test_sqlite_repository_get_raises_json_decode_error_for_corrupt_json(tmp_path, fixed_uuid) -> None:
    db_path = tmp_path / "corrupt_json.db"
    repo = when.SqliteGovernanceTaskRepository(str(db_path))

    task_id = str(fixed_uuid)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            f"""
            INSERT INTO {when.TABLE_NAME}
            (task_id, task_type, status, created_at, title, description, conversation_context, action, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                when.TASK_TYPE_CODE,
                when.STATUS_QUEUED,
                "2020-01-01T00:00:00+00:00",
                "t",
                "d",
                "{not-json",  # conversation_context invalid
                "{}",  # action ok
                "{}",  # metadata ok
            ),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(json.JSONDecodeError):
        repo.get(task_id)


def test_sqlite_repository_persists_json_fields_as_text(tmp_path, sample_task) -> None:
    db_path = tmp_path / "json_persist.db"
    repo = when.SqliteGovernanceTaskRepository(str(db_path))
    repo.create(sample_task)

    row = _fetch_row_by_id(str(db_path), sample_task.task_id)
    assert row is not None
    assert isinstance(row["conversation_context"], str)
    assert isinstance(row["action"], str)
    assert isinstance(row["metadata"], str)

    assert json.loads(row["conversation_context"]) == sample_task.conversation_context
    assert json.loads(row["action"]) == sample_task.action
    assert json.loads(row["metadata"]) == sample_task.metadata


def test_brain_uses_passed_repository_and_tool_scope() -> None:
    repo = Mock()
    brain = when.Brain(task_repo=repo, tool_scope=["search"], context_window=3)
    assert brain._task_repo is repo
    assert brain._tool_scope == ["search"]
    assert brain._context_window == 3


def test_brain_handle_queues_task_when_fallback_required(monkeypatch, sample_conversation, sample_action, fixed_now_iso, fixed_uuid) -> None:
    repo = Mock()
    repo.create = Mock(return_value=str(fixed_uuid))

    monkeypatch.setattr(when, "_utc_now_iso", lambda: fixed_now_iso)
    monkeypatch.setattr(when.uuid, "uuid4", lambda: fixed_uuid)
    monkeypatch.setattr(when, "_infer_task_type", lambda _text: when.TASK_TYPE_DEPLOYMENT)
    monkeypatch.setattr(
        when,
        "_normalize_context",
        lambda messages, window: {"messages": [{"role": "user", "content": "x"}], "window": window, "generated_at": fixed_now_iso},
    )
    monkeypatch.setattr(when, "_build_task_title", lambda _task_type, _action: "TITLE")
    monkeypatch.setattr(when, "_build_task_description", lambda _task_type, _action, _reason: "DESC")
    monkeypatch.setattr(when, "_requires_governance_fallback", lambda action, tool_scope: (True, "requires_approval"))

    brain = when.Brain(task_repo=repo, tool_scope=["search"], context_window=2)

    result = brain.handle(
        user_text=sample_action.raw_text,
        conversation=sample_conversation,
        action=sample_action,
        user_id="user-123",
        conversation_id="conv-456",
    )

    assert result == str(fixed_uuid)
    assert repo.create.call_count == 1

    created_task = repo.create.call_args.args[0]
    assert isinstance(created_task, when.GovernanceTask)
    assert created_task.task_id == str(fixed_uuid)
    assert created_task.task_type == when.TASK_TYPE_DEPLOYMENT
    assert created_task.status == when.STATUS_QUEUED
    assert created_task.created_at == fixed_now_iso
    assert created_task.title == "TITLE"
    assert created_task.description == "DESC"
    assert created_task.conversation_context["window"] == 2
    assert isinstance(created_task.action, dict)


def test_brain_handle_does_not_queue_task_when_no_fallback(monkeypatch, sample_conversation, fixed_now_iso) -> None:
    repo = Mock()
    repo.create = Mock(side_effect=AssertionError("create should not be called"))

    monkeypatch.setattr(when, "_utc_now_iso", lambda: fixed_now_iso)
    monkeypatch.setattr(when, "_requires_governance_fallback", lambda action, tool_scope: (False, ""))

    brain = when.Brain(task_repo=repo, tool_scope=["search"], context_window=5)

    result = brain.handle(
        user_text="Just answer normally",
        conversation=sample_conversation,
        action=when.ActionRequest(raw_text="Just answer normally", tool_name="search", requires_async=False, requires_approval=False),
        user_id=None,
        conversation_id=None,