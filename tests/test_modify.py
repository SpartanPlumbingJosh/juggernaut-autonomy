import json
import sqlite3
import sys
import types
import uuid
from datetime import datetime

import httpx
import pytest

import modify as mut


@pytest.fixture
def openrouter_config():
    return mut.OpenRouterConfig(
        api_key="test-key",
        base_url="https://example.com/chat",
        timeout_seconds=12.5,
        app_name=None,
        site_url=None,
    )


@pytest.fixture
def fake_httpx_client(monkeypatch):
    client = types.SimpleNamespace()
    client.post = None
    client.close = lambda: None
    monkeypatch.setattr(mut.httpx, "Client", lambda timeout: client)
    return client


def test_openrouter_chat_client_close_closes_underlying_http_client(openrouter_config, fake_httpx_client):
    closed = {"value": False}

    def _close():
        closed["value"] = True

    fake_httpx_client.close = _close

    client = mut.OpenRouterChatClient(openrouter_config)
    client.close()

    assert closed["value"] is True


def test_openrouter_chat_client_create_chat_completion_success_minimal_headers(
    openrouter_config, fake_httpx_client
):
    captured = {}

    class Resp:
        text = '{"choices":[{"message":{"role":"assistant","content":"hi"}}]}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"role": "assistant", "content": "hi"}}]}

    def post(url, headers=None, json=None):
        captured["url"] = url
        captured["headers"] = dict(headers or {})
        captured["json"] = json
        return Resp()

    fake_httpx_client.post = post

    client = mut.OpenRouterChatClient(openrouter_config)
    out = client.create_chat_completion({"model": "x", "messages": []})

    assert out["choices"][0]["message"]["content"] == "hi"
    assert captured["url"] == openrouter_config.base_url
    assert captured["headers"]["Authorization"] == f"Bearer {openrouter_config.api_key}"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert "HTTP-Referer" not in captured["headers"]
    assert "X-Title" not in captured["headers"]
    assert captured["json"] == {"model": "x", "messages": []}


def test_openrouter_chat_client_create_chat_completion_includes_optional_headers(monkeypatch, fake_httpx_client):
    cfg = mut.OpenRouterConfig(
        api_key="k",
        base_url="https://example.com/x",
        timeout_seconds=1.0,
        app_name="my-app",
        site_url="https://mysite.example",
    )
    captured = {}

    class Resp:
        text = '{"choices":[{"message":{"role":"assistant","content":"ok"}}]}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    def post(url, headers=None, json=None):
        captured["headers"] = dict(headers or {})
        return Resp()

    fake_httpx_client.post = post

    client = mut.OpenRouterChatClient(cfg)
    client.create_chat_completion({"model": "x"})

    assert captured["headers"]["HTTP-Referer"] == "https://mysite.example"
    assert captured["headers"]["X-Title"] == "my-app"


def test_openrouter_chat_client_create_chat_completion_raises_openrouter_api_error_on_http_status_error(
    openrouter_config, fake_httpx_client
):
    url = openrouter_config.base_url

    def post(_url, headers=None, json=None):
        resp = httpx.Response(
            400,
            request=httpx.Request("POST", url),
            text="bad request",
        )
        return resp

    fake_httpx_client.post = post

    client = mut.OpenRouterChatClient(openrouter_config)

    with pytest.raises(mut.OpenRouterAPIError) as ei:
        client.create_chat_completion({"model": "x"})

    msg = str(ei.value)
    assert "OpenRouter HTTP error" in msg
    assert "body=bad request" in msg


def test_openrouter_chat_client_create_chat_completion_raises_openrouter_api_error_on_request_error(
    openrouter_config, fake_httpx_client
):
    def post(url, headers=None, json=None):
        raise httpx.RequestError("network down", request=httpx.Request("POST", url))

    fake_httpx_client.post = post

    client = mut.OpenRouterChatClient(openrouter_config)

    with pytest.raises(mut.OpenRouterAPIError) as ei:
        client.create_chat_completion({"model": "x"})

    assert "OpenRouter request error" in str(ei.value)


def test_openrouter_chat_client_create_chat_completion_raises_openrouter_api_error_on_non_json(
    openrouter_config, fake_httpx_client
):
    class Resp:
        text = "not json at all"

        def raise_for_status(self):
            return None

        def json(self):
            raise json.JSONDecodeError("bad", "not json at all", 0)

    fake_httpx_client.post = lambda url, headers=None, json=None: Resp()

    client = mut.OpenRouterChatClient(openrouter_config)

    with pytest.raises(mut.OpenRouterAPIError) as ei:
        client.create_chat_completion({"model": "x"})

    assert "returned non-JSON response" in str(ei.value)
    assert "not json at all" in str(ei.value)


@pytest.mark.parametrize(
    "bad_data",
    [
        ["choices"],
        {"not_choices": []},
        None,
        123,
    ],
)
def test_openrouter_chat_client_create_chat_completion_raises_openrouter_api_error_on_missing_choices_key(
    openrouter_config, fake_httpx_client, bad_data
):
    class Resp:
        text = "whatever"

        def raise_for_status(self):
            return None

        def json(self):
            return bad_data

    fake_httpx_client.post = lambda url, headers=None, json=None: Resp()
    client = mut.OpenRouterChatClient(openrouter_config)

    with pytest.raises(mut.OpenRouterAPIError) as ei:
        client.create_chat_completion({"model": "x"})

    assert "missing 'choices'" in str(ei.value)


@pytest.fixture
def sqlite_repo(tmp_path):
    db_path = tmp_path / "exec_logs.db"
    return mut.SQLiteExecutionLogRepository(str(db_path))


def _fetch_all_rows(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = list(conn.execute("SELECT * FROM execution_logs ORDER BY created_at ASC"))
        return rows
    finally:
        conn.close()


def test_sqlite_execution_log_repository_creates_schema_on_init(tmp_path):
    db_path = tmp_path / "schema.db"
    mut.SQLiteExecutionLogRepository(str(db_path))

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='execution_logs'"
        ).fetchone()
        assert row is not None
    finally:
        conn.close()


def test_sqlite_execution_log_repository_log_tool_execution_inserts_row(sqlite_repo):
    sqlite_repo.log_tool_execution(
        conversation_id="c1",
        tool_call_id="tc1",
        tool_name="toolA",
        arguments={"x": 1, "y": "a"},
        result={"ok": True},
        status=mut.TOOL_EXECUTION_STATUS_SUCCESS,
        error=None,
    )

    rows = _fetch_all_rows(sqlite_repo._db_path)
    assert len(rows) == 1
    r = rows[0]

    uuid.UUID(r["id"])  # should not raise
    dt = datetime.fromisoformat(r["created_at"])
    assert dt.tzinfo is not None

    assert r["conversation_id"] == "c1"
    assert r["tool_call_id"] == "tc1"
    assert r["tool_name"] == "toolA"
    assert json.loads(r["arguments_json"]) == {"x": 1, "y": "a"}
    assert json.loads(r["result_json"]) == {"ok": True}
    assert r["status"] == mut.TOOL_EXECUTION_STATUS_SUCCESS
    assert r["error"] is None


def test_sqlite_execution_log_repository_log_tool_execution_handles_unserializable_arguments(sqlite_repo):
    class Unserializable:
        pass

    sqlite_repo.log_tool_execution(
        conversation_id="c2",
        tool_call_id=None,
        tool_name="toolB",
        arguments={"x": Unserializable()},
        result={"ok": True},
        status=mut.TOOL_EXECUTION_STATUS_ERROR,
        error="boom",
    )

    rows = _fetch_all_rows(sqlite_repo._db_path)
    assert len(rows) == 1
    args = json.loads(rows[0]["arguments_json"])
    assert args == {"_unserializable_arguments": True}


def test_sqlite_execution_log_repository_log_tool_execution_handles_unserializable_result(sqlite_repo):
    class Unserializable:
        pass

    sqlite_repo.log_tool_execution(
        conversation_id="c3",
        tool_call_id="tc3",
        tool_name="toolC",
        arguments={"x": 1},
        result=Unserializable(),
        status=mut.TOOL_EXECUTION_STATUS_ERROR,
        error="bad result",
    )

    rows = _fetch_all_rows(sqlite_repo._db_path)
    assert len(rows) == 1
    res = json.loads(rows[0]["result_json"])
    assert res == {"_unserializable_result": True}


def test_sqlite_execution_log_repository_log_tool_execution_allows_none_result(sqlite_repo):
    sqlite_repo.log_tool_execution(
        conversation_id="c4",
        tool_call_id="tc4",
        tool_name="toolD",
        arguments={},
        result=None,
        status=mut.TOOL_EXECUTION_STATUS_SUCCESS,
        error=None,
    )

    rows = _fetch_all_rows(sqlite_repo._db_path)
    assert len(rows) == 1
    assert rows[0]["result_json"] is None


@pytest.fixture
def clean_core_tools_modules():
    to_remove = [k for k in sys.modules.keys() if k == "core" or k.startswith("core.")]
    for k in to_remove:
        sys.modules.pop(k, None)
    yield
    to_remove = [k for k in sys.modules.keys() if k == "core" or k.startswith("core.")]
    for k in to_remove:
        sys.modules.pop(k, None)


def test_default_tool_schema_provider_raises_import_error_when_task1_module_missing(clean_core_tools_modules):
    p = mut.DefaultToolSchemaProvider()
    with pytest.raises(ImportError) as ei:
        p.get_openrouter_tools()
    assert "Tool schemas provider not available" in str(ei.value)


def test_default_tool_schema_provider_validates_return_type_is_list(clean_core_tools_modules):
    core = types.ModuleType("core")
    tools = types.ModuleType("core.tools")
    schemas = types.ModuleType("core.tools.schemas")
    schemas.get_openrouter_tools = lambda: {"not": "a list"}

    sys.modules["core"] = core
    sys.modules["core.tools"] = tools
    sys.modules["core.tools.schemas"] = schemas

    p = mut.DefaultToolSchemaProvider()
    with pytest.raises(ValueError) as ei:
        p.get_openrouter_tools()
    assert "must return a list" in str(ei.value)


def test_default_tool_schema_provider_validates_each_schema_is_dict(clean_core_tools_modules):
    core = types.ModuleType("core")
    tools = types.ModuleType("core.tools")
    schemas = types.ModuleType("core.tools.schemas")
    schemas.get_openrouter_tools = lambda: [{"ok": True}, "bad"]

    sys.modules["core"] = core
    sys.modules["core.tools"] = tools
    sys.modules["core.tools.schemas"] = schemas

    p = mut.DefaultToolSchemaProvider()
    with pytest.raises(ValueError) as ei:
        p.get_openrouter_tools()
    assert "must be a dict" in str(ei.value)


def test_default_tool_schema_provider_caches_loaded_tools(clean_core_tools_modules):
    core = types.ModuleType("core")
    tools = types.ModuleType("core.tools")
    schemas = types.ModuleType("core.tools.schemas")
    calls = {"n": 0}
    expected = [{"type": "function", "function": {"name": "t", "parameters": {}}}]

    def get_openrouter_tools():
        calls["n"] += 1
        return list(expected)

    schemas.get_openrouter_tools = get_openrouter_tools

    sys.modules["core"] = core
    sys.modules["core.tools"] = tools
    sys.modules["core.tools.schemas"] = schemas

    p = mut.DefaultToolSchemaProvider()
    out1 = p.get_openrouter_tools()
    out2 = p.get_openrouter_tools()

    assert out1 == expected
    assert out2 == expected
    assert calls["n"] == 1


class _DummyOpenRouterClient:
    def __init__(self):
        self.calls = []

    def create_chat_completion(self, payload):
        self.calls.append(payload)
        return {"choices": [{"message": {"role": "assistant", "content": "final"}}]}


class _DummyToolSchemaProvider:
    def __init__(self,