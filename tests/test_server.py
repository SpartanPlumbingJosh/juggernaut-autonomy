import asyncio
import importlib
import sys
import types
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pytest


@pytest.fixture
def fake_mcp_packages(monkeypatch):
    """
    Provide minimal 'mcp' and 'mcp.client.streamable_http' modules so core.mcp_client
    can be imported even if the real dependency is not installed.
    """
    mcp_mod = types.ModuleType("mcp")

    class PlaceholderClientSession:
        def __init__(self, read, write, get_session_id):
            self._read = read
            self._write = write
            self._get_session_id = get_session_id

        async def initialize(self):
            return None

        async def close(self):
            return None

        async def call_tool(self, tool_name: str, arguments: Dict[str, Any]):
            raise NotImplementedError

    mcp_mod.ClientSession = PlaceholderClientSession

    mcp_client_mod = types.ModuleType("mcp.client")
    mcp_stream_mod = types.ModuleType("mcp.client.streamable_http")

    async def placeholder_streamablehttp_client(*args, **kwargs):
        raise NotImplementedError

    mcp_stream_mod.streamablehttp_client = placeholder_streamablehttp_client

    monkeypatch.setitem(sys.modules, "mcp", mcp_mod)
    monkeypatch.setitem(sys.modules, "mcp.client", mcp_client_mod)
    monkeypatch.setitem(sys.modules, "mcp.client.streamable_http", mcp_stream_mod)

    return {"mcp": mcp_mod, "mcp.client": mcp_client_mod, "mcp.client.streamable_http": mcp_stream_mod}


def _reload_module(module_name: str):
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


@pytest.fixture
def mcp_token_env(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "test-token")
    return "test-token"


@pytest.fixture
def mcp_client_module(fake_mcp_packages, mcp_token_env):
    return _reload_module("core.mcp_client")


@pytest.fixture
def brain_module(fake_mcp_packages, mcp_token_env):
    # Ensure core.mcp_client can import first (brain imports it)
    _reload_module("core.mcp_client")
    return _reload_module("core.brain")


class _AsyncClientStub:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.closed = False
        self.aclose_call_count = 0

    async def aclose(self):
        self.closed = True
        self.aclose_call_count += 1


class _AsyncCM:
    def __init__(self, enter_value=None, enter_exc: Optional[BaseException] = None):
        self._enter_value = enter_value
        self._enter_exc = enter_exc

    async def __aenter__(self):
        if self._enter_exc is not None:
            raise self._enter_exc
        return self._enter_value

    async def __aexit__(self, exc_type, exc, tb):
        return False


@dataclass
class _ToolResultWithContent:
    content: Any


class _ClientSessionStub:
    def __init__(self, read, write, get_session_id):
        self.read = read
        self.write = write
        self.get_session_id = get_session_id
        self.initialize_call_count = 0
        self.close_call_count = 0
        self.call_tool_call_args = []
        self._call_tool_side_effect = None
        self._call_tool_return = None

    async def initialize(self):
        self.initialize_call_count += 1

    async def close(self):
        self.close_call_count += 1
        if isinstance(self._call_tool_side_effect, Exception) and getattr(self._call_tool_side_effect, "_raise_on_close", False):
            raise self._call_tool_side_effect

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]):
        self.call_tool_call_args.append((tool_name, arguments))
        if self._call_tool_side_effect is not None:
            raise self._call_tool_side_effect
        return self._call_tool_return


def _make_streamable_client_cm(read_stream="read", write_stream="write", session_id="sid"):
    def get_session_id():
        return session_id

    return _AsyncCM(enter_value=(read_stream, write_stream, get_session_id))


def test_import_raises_value_error_when_auth_token_missing(fake_mcp_packages, monkeypatch):
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    if "core.mcp_client" in sys.modules:
        del sys.modules["core.mcp_client"]

    with pytest.raises(ValueError, match="MCP_AUTH_TOKEN environment variable must be set"):
        importlib.import_module("core.mcp_client")


def test_test_connectivity_returns_true_on_success(mcp_client_module, monkeypatch):
    class _Resp:
        status_code = 200

    class _Client:
        def __init__(self, timeout, headers):
            assert timeout == 5.0
            assert "Authorization" in headers
            self._headers = headers

        def head(self, url):
            assert url == mcp_client_module.MCP_SERVER_URL
            return _Resp()

    monkeypatch.setattr(mcp_client_module.httpx, "Client", _Client)

    assert mcp_client_module.test_connectivity() is True


def test_test_connectivity_returns_false_on_exception(mcp_client_module, monkeypatch):
    class _Client:
        def __init__(self, timeout, headers):
            pass

        def head(self, url):
            raise RuntimeError("boom")

    monkeypatch.setattr(mcp_client_module.httpx, "Client", _Client)

    assert mcp_client_module.test_connectivity() is False


def test_mcpclient_init_runs_connectivity_test_and_constructs_async_client(mcp_client_module, monkeypatch):
    called = {"connectivity": 0}

    def _test_connectivity():
        called["connectivity"] += 1
        return True

    monkeypatch.setattr(mcp_client_module, "test_connectivity", _test_connectivity)
    monkeypatch.setattr(mcp_client_module.httpx, "AsyncClient", _AsyncClientStub)

    client = mcp_client_module.MCPClient()
    assert called["connectivity"] == 1
    assert client._connected is False
    assert isinstance(client._client, _AsyncClientStub)
    assert client._session is None


@pytest.mark.asyncio
async def test_connect_sets_up_session_and_marks_connected(mcp_client_module, monkeypatch):
    monkeypatch.setattr(mcp_client_module.httpx, "AsyncClient", _AsyncClientStub)
    monkeypatch.setattr(mcp_client_module, "test_connectivity", lambda: True)

    created_sessions = []

    def _client_session_factory(read, write, get_session_id):
        s = _ClientSessionStub(read=read, write=write, get_session_id=get_session_id)
        created_sessions.append(s)
        return s

    monkeypatch.setattr(mcp_client_module, "ClientSession", _client_session_factory)
    monkeypatch.setattr(
        mcp_client_module,
        "streamablehttp_client",
        lambda url, client: _make_streamable_client_cm(read_stream="r", write_stream="w", session_id="abc"),
    )

    c = mcp_client_module.MCPClient()
    await c.connect()

    assert c._connected is True
    assert c._session is created_sessions[0]
    assert created_sessions[0].initialize_call_count == 1
    assert created_sessions[0].read == "r"
    assert created_sessions[0].write == "w"
    assert created_sessions[0].get_session_id() == "abc"


@pytest.mark.asyncio
async def test_connect_is_noop_when_already_connected(mcp_client_module, monkeypatch):
    monkeypatch.setattr(mcp_client_module.httpx, "AsyncClient", _AsyncClientStub)
    monkeypatch.setattr(mcp_client_module, "test_connectivity", lambda: True)

    stream_calls = {"count": 0}

    def _streamable(url, client):
        stream_calls["count"] += 1
        return _make_streamable_client_cm()

    monkeypatch.setattr(mcp_client_module, "streamablehttp_client", _streamable)

    c = mcp_client_module.MCPClient()
    c._connected = True

    await c.connect()
    assert stream_calls["count"] == 0


@pytest.mark.asyncio
async def test_connect_raises_connection_error_on_failure(mcp_client_module, monkeypatch):
    monkeypatch.setattr(mcp_client_module.httpx, "AsyncClient", _AsyncClientStub)
    monkeypatch.setattr(mcp_client_module, "test_connectivity", lambda: True)

    async def _failing_enter():
        raise RuntimeError("handshake failed")

    class _FailCM:
        async def __aenter__(self):
            await _failing_enter()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(mcp_client_module, "streamablehttp_client", lambda url, client: _FailCM())

    c = mcp_client_module.MCPClient()
    with pytest.raises(ConnectionError, match=r"MCP server connection failed: .*handshake failed"):
        await c.connect()
    assert c._connected is False


@pytest.mark.asyncio
async def test_disconnect_closes_session_and_async_client_and_resets_connected(mcp_client_module, monkeypatch):
    monkeypatch.setattr(mcp_client_module.httpx, "AsyncClient", _AsyncClientStub)
    monkeypatch.setattr(mcp_client_module, "test_connectivity", lambda: True)

    c = mcp_client_module.MCPClient()
    sess = _ClientSessionStub(read=None, write=None, get_session_id=lambda: "x")
    c._session = sess
    c._connected = True

    await c.disconnect()

    assert sess.close_call_count == 1
    assert c._client.closed is True
    assert c._client.aclose_call_count == 1
    assert c._connected is False


@pytest.mark.asyncio
async def test_disconnect_handles_session_close_error_and_still_closes_http_client(mcp_client_module, monkeypatch):
    monkeypatch.setattr(mcp_client_module.httpx, "AsyncClient", _AsyncClientStub)
    monkeypatch.setattr(mcp_client_module, "test_connectivity", lambda: True)

    c = mcp_client_module.MCPClient()

    class _CloseErr(Exception):
        pass

    err = _CloseErr("close failed")
    setattr(err, "_raise_on_close", True)

    sess = _ClientSessionStub(read=None, write=None, get_session_id=lambda: "x")
    sess._call_tool_side_effect = err  # used by close() in this stub

    c._session = sess
    c._connected = True

    await c.disconnect()

    assert sess.close_call_count == 1
    assert c._client.closed is True
    assert c._connected is False


@pytest.mark.asyncio
async def test_context_manager_connects_and_disconnects(mcp_client_module, monkeypatch):
    monkeypatch.setattr(mcp_client_module.httpx, "AsyncClient", _AsyncClientStub)
    monkeypatch.setattr(mcp_client_module, "test_connectivity", lambda: True)

    session = _ClientSessionStub(read="r", write="w", get_session_id=lambda: "sid")

    monkeypatch.setattr(mcp_client_module, "ClientSession", lambda read, write, get_session_id: session)
    monkeypatch.setattr(mcp_client_module, "streamablehttp_client", lambda url, client: