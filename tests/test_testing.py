import sqlite3
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

import testing


@pytest.fixture()
def sqlite_connection():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE tasks(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, status TEXT, description TEXT, created_at INTEGER)"
    )
    conn.execute(
        "CREATE TABLE worker_registry(worker_id TEXT PRIMARY KEY, status TEXT, last_heartbeat INTEGER, cpu_load REAL)"
    )
    conn.execute("CREATE TABLE activity_log(timestamp INTEGER, worker_id TEXT, event TEXT)")
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def mcp_client(sqlite_connection):
    return testing.MCPClient(sqlite_connection, server_up=True)


@pytest.fixture()
def limiter():
    return testing.ToolCallLimiter(max_calls=testing.MAX_TOOL_CALLS)


@pytest.fixture()
def fallback_store():
    return testing.FallbackTaskStore()


@pytest.fixture()
def session(mcp_client, limiter, fallback_store):
    return testing.NeuralChatSession(mcp_client, limiter, fallback_store)


def test_dataclasses_are_frozen_and_immutable():
    call = testing.ToolCall(name="sql_query", arguments={"sql": "SELECT 1", "params": []})
    result = testing.ToolResult(name="sql_query", ok=True, data=[], error=None, trace={})
    resp = testing.ChatResponse(text="ok", tool_calls=[call], tool_results=[result])

    with pytest.raises(FrozenInstanceError):
        call.name = "other"

    with pytest.raises(FrozenInstanceError):
        result.ok = False

    with pytest.raises(FrozenInstanceError):
        resp.text = "changed"


def test_tool_error_inheritance_tree():
    assert issubclass(testing.ToolRateLimitError, testing.ToolError)
    assert issubclass(testing.MCPServerDownError, testing.ToolError)
    assert issubclass(testing.SQLExecutionError, testing.ToolError)


def test_tool_call_limiter_consumes_and_tracks_remaining_calls():
    limiter = testing.ToolCallLimiter(max_calls=3)
    assert limiter.used_calls == 0
    assert limiter.remaining_calls == 3

    limiter.consume()
    assert limiter.used_calls == 1
    assert limiter.remaining_calls == 2

    limiter.consume(2)
    assert limiter.used_calls == 3
    assert limiter.remaining_calls == 0

    limiter.consume(0)
    assert limiter.used_calls == 3
    assert limiter.remaining_calls == 0


def test_tool_call_limiter_rejects_negative_count():
    limiter = testing.ToolCallLimiter(max_calls=3)
    with pytest.raises(ValueError, match="count must be non-negative"):
        limiter.consume(-1)


def test_tool_call_limiter_raises_rate_limit_error_when_exceeding_limit():
    limiter = testing.ToolCallLimiter(max_calls=2)
    limiter.consume(2)
    with pytest.raises(testing.ToolRateLimitError, match=r"Tool call limit exceeded"):
        limiter.consume(1)


def test_fallback_task_store_create_and_get_task_returns_expected_payload(monkeypatch):
    monkeypatch.setattr(testing.uuid, "uuid4", lambda: "00000000-0000-0000-0000-000000000000")
    monkeypatch.setattr(testing.time, "time", lambda: 1234.5)

    store = testing.FallbackTaskStore()
    task_id = store.create_task("Title", "Description")
    assert task_id == "00000000-0000-0000-0000-000000000000"

    task = store.get_task(task_id)
    assert task is not None
    assert task["id"] == task_id
    assert task["title"] == "Title"
    assert task["description"] == "Description"
    assert task["status"] == "pending"
    assert task["created_at"] == 1234.5

    assert store.get_task("missing") is None


def test_mcp_client_server_up_property_and_setter(sqlite_connection):
    client = testing.MCPClient(sqlite_connection, server_up=True)
    assert client.server_up is True

    client.set_server_up(False)
    assert client.server_up is False


def test_mcp_client_sql_query_raises_when_server_is_down(sqlite_connection):
    client = testing.MCPClient(sqlite_connection, server_up=False)
    with pytest.raises(testing.MCPServerDownError, match="MCP server is down"):
        client.sql_query("SELECT 1")


def test_mcp_client_sql_query_returns_list_of_dicts_for_sqlite_row(sqlite_connection):
    sqlite_connection.row_factory = sqlite3.Row
    sqlite_connection.execute(
        "INSERT INTO tasks(title, status, description, created_at) VALUES (?, ?, ?, ?)",
        ("t1", "pending", "d1", 1),
    )
    sqlite_connection.commit()

    client = testing.MCPClient(sqlite_connection, server_up=True)
    rows = client.sql_query("SELECT id, title, status FROM tasks ORDER BY id")
    assert rows == [{"id": 1, "title": "t1", "status": "pending"}]


def test_mcp_client_sql_query_returns_list_of_dicts_for_tuple_rows(sqlite_connection):
    sqlite_connection.execute(
        "INSERT INTO tasks(title, status, description, created_at) VALUES (?, ?, ?, ?)",
        ("t1", "pending", "d1", 1),
    )
    sqlite_connection.commit()

    client = testing.MCPClient(sqlite_connection, server_up=True)
    rows = client.sql_query("SELECT id, title FROM tasks ORDER BY id")
    assert rows == [{"id": 1, "title": "t1"}]


def test_mcp_client_sql_query_with_no_description_returns_value_key_via_mock():
    class DummyCursor:
        description = None

        def fetchall(self):
            return [("a", 1), ("b", 2)]

    class DummyConnection:
        def execute(self, sql, params):
            assert sql == "ANY"
            assert params == []
            return DummyCursor()

    client = testing.MCPClient(DummyConnection(), server_up=True)
    rows = client.sql_query("ANY")
    assert rows == [{"value": ("a", 1)}, {"value": ("b", 2)}]


def test_mcp_client_sql_query_wraps_sqlite_error_into_sql_execution_error(sqlite_connection):
    client = testing.MCPClient(sqlite_connection, server_up=True)
    with pytest.raises(testing.SQLExecutionError):
        client.sql_query("SELECT * FROM does_not_exist")


def test_mcp_client_governance_task_create_inserts_row_and_returns_id(sqlite_connection, monkeypatch):
    monkeypatch.setattr(testing.time, "time", lambda: 999.1)

    client = testing.MCPClient(sqlite_connection, server_up=True)
    created_id = client.governance_task_create("Title", "Desc")