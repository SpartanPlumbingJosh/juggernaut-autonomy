import json
import sqlite3
from datetime import datetime

import pytest
from unittest.mock import Mock

import module_under_test as mod


# ------------------------
# Fixtures
# ------------------------


@pytest.fixture
def tmp_db_path(tmp_path):
    return str(tmp_path / "test_system_state.db")


@pytest.fixture
def sql_tool(tmp_db_path):
    return mod.SQLQueryTool(db_path=tmp_db_path)


@pytest.fixture
def openrouter_client():
    return mod.OpenRouterClient(api_key="test_key", model="test-model", timeout_seconds=15)


# ------------------------
# OpenRouterClient tests
# ------------------------


def test_openrouter_client_initialization(openrouter_client):
    assert openrouter_client._api_key == "test_key"
    assert openrouter_client._model == "test-model"
    assert openrouter_client._timeout_seconds == 15


def test_chat_completion_success_basic(monkeypatch, openrouter_client):
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    response_data = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hi there",
                }
            }
        ]
    }
    mock_response.json.return_value = response_data

    recorded_kwargs = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        recorded_kwargs["url"] = url
        recorded_kwargs["headers"] = headers
        recorded_kwargs["json"] = json
        recorded_kwargs["timeout"] = timeout
        return mock_response

    monkeypatch.setattr(mod.requests, "post", fake_post)

    result = openrouter_client.chat_completion(messages=messages)

    # Returned data is correct
    assert result == response_data

    # URL and timeout are passed correctly
    assert recorded_kwargs["url"] == mod.OPENROUTER_API_URL
    assert recorded_kwargs["timeout"] == openrouter_client._timeout_seconds

    # Payload contains model and messages
    assert recorded_kwargs["json"]["model"] == openrouter_client._model
    assert recorded_kwargs["json"]["messages"] == messages

    # Required headers present
    headers = recorded_kwargs["headers"]
    assert headers["Authorization"] == f"Bearer {openrouter_client._api_key}"
    assert headers["Content-Type"] == "application/json"
    assert "HTTP-Referer" in headers
    assert "X-Title" in headers


def test_chat_completion_includes_tools_and_tool_choice(monkeypatch, openrouter_client):
    messages = [{"role": "user", "content": "Hi"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    tool_choice = "auto"

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"choices": [{"message": {"role": "assistant"}}]}

    captured_json = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured_json.update(json)
        return mock_response

    monkeypatch.setattr(mod.requests, "post", fake_post)

    openrouter_client.chat_completion(messages=messages, tools=tools, tool_choice=tool_choice)

    assert captured_json["tools"] == tools
    assert captured_json["tool_choice"] == tool_choice


def test_chat_completion_timeout_raises_openrouter_error(monkeypatch, openrouter_client):
    def fake_post(*args, **kwargs):
        raise mod.requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(mod.requests, "post", fake_post)

    with pytest.raises(mod.OpenRouterError) as excinfo:
        openrouter_client.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    assert "timed out" in str(excinfo.value).lower()
    assert str(excinfo.value) == "OpenRouter request timed out"


def test_chat_completion_http_error_raises_openrouter_error(monkeypatch, openrouter_client):
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = mod.requests.exceptions.HTTPError("bad request")
    mock_response.status_code = 400
    mock_response.text = "Bad Request"

    def fake_post(*args, **kwargs):
        return mock_response

    monkeypatch.setattr(mod.requests, "post", fake_post)

    with pytest.raises(mod.OpenRouterError) as excinfo:
        openrouter_client.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    msg = str(excinfo.value)
    assert "OpenRouter HTTP error 400: Bad Request" == msg


def test_chat_completion_request_exception_raises_openrouter_error(monkeypatch, openrouter_client):
    def fake_post(*args, **kwargs):
        raise mod.requests.exceptions.RequestException("connection failed")

    monkeypatch.setattr(mod.requests, "post", fake_post)

    with pytest.raises(mod.OpenRouterError) as excinfo:
        openrouter_client.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    assert str(excinfo.value) == "OpenRouter request error"


def test_chat_completion_invalid_json_raises_openrouter_error(monkeypatch, openrouter_client):
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.side_effect = ValueError("not json")

    def fake_post(*args, **kwargs):
        return mock_response

    monkeypatch.setattr(mod.requests, "post", fake_post)

    with pytest.raises(mod.OpenRouterError) as excinfo:
        openrouter_client.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    assert str(excinfo.value) == "Failed to parse OpenRouter JSON response"


def test_chat_completion_no_choices_raises_openrouter_error(monkeypatch, openrouter_client):
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"choices": []}

    def fake_post(*args, **kwargs):
        return mock_response

    monkeypatch.setattr(mod.requests, "post", fake_post)

    with pytest.raises(mod.OpenRouterError) as excinfo:
        openrouter_client.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    assert str(excinfo.value) == "OpenRouter returned no choices"


def test_chat_completion_missing_choices_key_raises_openrouter_error(monkeypatch, openrouter_client):
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"unexpected": "field"}

    def fake_post(*args, **kwargs):
        return mock_response

    monkeypatch.setattr(mod.requests, "post", fake_post)

    with pytest.raises(mod.OpenRouterError) as excinfo:
        openrouter_client.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    assert str(excinfo.value) == "OpenRouter returned no choices"


# ------------------------
# SQLQueryTool tests
# ------------------------


def test_sql_query_tool_initializes_schema(tmp_db_path):
    tool = mod.SQLQueryTool(db_path=tmp_db_path)

    # Ensure table exists by querying sqlite_master
    with sqlite3.connect(tmp_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='governance_tasks';"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "governance_tasks"


def test_sql_query_tool_init_schema_failure_raises_sqltoolerror(monkeypatch, tmp_db_path):
    # Force sqlite3.connect to raise an error only during initialization
    def fake_connect_fail(*args, **kwargs):
        raise sqlite3.Error("db init failure")

    monkeypatch.setattr(mod.sqlite3, "connect", fake_connect_fail)

    with pytest.raises(mod.SQLToolError) as excinfo:
        mod.SQLQueryTool(db_path=tmp_db_path)

    assert "Failed to