from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple, Union

import httpx

logger = logging.getLogger(__name__)

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 1024
MAX_TOOL_CALLS_PER_TURN = 5
TOOL_EXECUTION_STATUS_SUCCESS = "success"
TOOL_EXECUTION_STATUS_ERROR = "error"


class ToolExecutionLimitError(RuntimeError):
    """Raised when tool execution exceeds the configured safety limit."""


class OpenRouterAPIError(RuntimeError):
    """Raised when OpenRouter returns an error or an unexpected response."""


class ToolSchemaProvider(Protocol):
    """Protocol for providing tool schemas compatible with OpenRouter."""

    def get_openrouter_tools(self) -> List[Dict[str, Any]]:
        """Returns OpenRouter-compatible tool schemas.

        Returns:
            List[Dict[str, Any]]: Tool schema list for OpenRouter.
        """


class MCPClientProtocol(Protocol):
    """Protocol for executing tools via an MCP client."""

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> Any:
        """Executes an MCP tool call.

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            Any: Tool result.
        """


@dataclass(frozen=True)
class OpenRouterConfig:
    """Configuration for OpenRouter calls."""

    api_key: str
    base_url: str = DEFAULT_OPENROUTER_BASE_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    app_name: Optional[str] = None
    site_url: Optional[str] = None


class OpenRouterChatClient:
    """HTTP client for OpenRouter chat completions (OpenAI-compatible API)."""

    def __init__(self, config: OpenRouterConfig) -> None:
        """Initializes the client.

        Args:
            config: OpenRouter configuration.
        """
        self._config = config
        self._client = httpx.Client(timeout=httpx.Timeout(config.timeout_seconds))

    def close(self) -> None:
        """Closes the underlying HTTP client."""
        self._client.close()

    def create_chat_completion(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Calls OpenRouter chat completion endpoint.

        Args:
            payload: JSON payload.

        Returns:
            Dict[str, Any]: Parsed JSON response.

        Raises:
            OpenRouterAPIError: On HTTP errors or malformed responses.
        """
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        if self._config.site_url:
            headers["HTTP-Referer"] = self._config.site_url
        if self._config.app_name:
            headers["X-Title"] = self._config.app_name

        try:
            resp = self._client.post(self._config.base_url, headers=headers, json=dict(payload))
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            body = e.response.text if e.response is not None else ""
            raise OpenRouterAPIError(f"OpenRouter HTTP error: {e} body={body}") from e
        except httpx.RequestError as e:
            raise OpenRouterAPIError(f"OpenRouter request error: {e}") from e

        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            raise OpenRouterAPIError(f"OpenRouter returned non-JSON response: {resp.text}") from e

        if not isinstance(data, dict) or "choices" not in data:
            raise OpenRouterAPIError(f"OpenRouter response missing 'choices': {data}")

        return data


class SQLiteExecutionLogRepository:
    """SQLite repository for persisting tool execution logs."""

    def __init__(self, db_path: str) -> None:
        """Initializes repository and ensures schema exists.

        Args:
            db_path: Path to SQLite database file.
        """
        self._db_path = db_path
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        """Creates a SQLite connection.

        Returns:
            sqlite3.Connection: A connection object.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Ensures the execution_logs table exists."""
        ddl = """
        CREATE TABLE IF NOT EXISTS execution_logs (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            tool_call_id TEXT,
            tool_name TEXT NOT NULL,
            arguments_json TEXT NOT NULL,
            result_json TEXT,
            status TEXT NOT NULL,
            error TEXT
        );
        """
        with self._connect() as conn:
            conn.execute(ddl)
            conn.commit()

    def log_tool_execution(
        self,
        conversation_id: str,
        tool_call_id: Optional[str],
        tool_name: str,
        arguments: Mapping[str, Any],
        result: Optional[Any],
        status: str,
        error: Optional[str],
    ) -> None:
        """Inserts a tool execution record.

        Args:
            conversation_id: Conversation identifier.
            tool_call_id: Tool call id from model response.
            tool_name: Executed tool name.
            arguments: Tool arguments.
            result: Tool result.
            status: Execution status.
            error: Error string if any.
        """
        record_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        try:
            arguments_json = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            arguments_json = json.dumps({"_unserializable_arguments": True}, ensure_ascii=False)

        result_json: Optional[str]
        if result is None:
            result_json = None
        else:
            try:
                result_json = json.dumps(result, ensure_ascii=False)
            except (TypeError, ValueError):
                result_json = json.dumps({"_unserializable_result": True}, ensure_ascii=False)

        sql = """
        INSERT INTO execution_logs (
            id, created_at, conversation_id, tool_call_id, tool_name,
            arguments_json, result_json, status, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params: Tuple[Any, ...] = (
            record_id,
            created_at,
            conversation_id,
            tool_call_id,
            tool_name,
            arguments_json,
            result_json,
            status,
            error,
        )
        with self._connect() as conn:
            conn.execute(sql, params)
            conn.commit()


class DefaultToolSchemaProvider:
    """Default tool schema provider that loads tool schemas from Task 1."""

    def __init__(self) -> None:
        """Initializes the provider."""
        self._cached: Optional[List[Dict[str, Any]]] = None

    def get_openrouter_tools(self) -> List[Dict[str, Any]]:
        """Returns tool schemas for OpenRouter, loading from Task 1 module.

        Returns:
            List[Dict[str, Any]]: Tool schema list.

        Raises:
            ImportError: If Task 1 schema module is unavailable.
            ValueError: If loaded schemas are not valid.
        """
        if self._cached is not None:
            return self._cached

        try:
            from core.tools.schemas import get_openrouter_tools  # type: ignore
        except ImportError as e:
            raise ImportError(
                "Tool schemas provider not available. Ensure Task 1 is complete and "
                "core.tools.schemas.get_openrouter_tools exists."
            ) from e

        tools = get_openrouter_tools()
        if not isinstance(tools, list):
            raise ValueError("get_openrouter_tools() must return a list of tool schemas.")
        for t in tools:
            if not isinstance(t, dict):
                raise ValueError("Each tool schema must be a dict.")
        self._cached = tools
        return tools


class BrainService:
    """Service layer for model consultation with tool calling via MCP."""

    def __init__(
        self,
        openrouter_client: OpenRouterChatClient,
        mcp_client: MCPClientProtocol,
        tool_schema_provider: ToolSchemaProvider,
        execution_log_repo: SQLiteExecutionLogRepository,
    ) -> None:
        """Initializes BrainService.

        Args:
            openrouter_client: Client for OpenRouter chat completions.
            mcp_client: MCP client used to execute tool calls.
            tool_schema_provider: Provider for OpenRouter tool schemas (Task 1).
            execution_log_repo: Repository to store tool execution logs.
        """
        self._openrouter = openrouter_client
        self._mcp = mcp_client
        self._tools = tool_schema_provider
        self._execution_logs = execution_log_repo

    def consult(
        self,
        conversation_id: str,
        messages: Sequence[Mapping[str, Any]],
        model: str,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        extra_payload: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        """Consults the model with OpenRouter tool calling enabled and executes tools via MCP.

        This method:
          - Adds tools to OpenRouter payload using schemas from Task 1
          - Detects tool calls in response.choices[0].message.tool_calls
          - Executes tools via MCP (Task 2)
          - Feeds tool results back using role 'tool_result'
          - Supports multi-turn tool execution with a hard cap of 5 tool calls
          - Logs all tool executions to execution_logs table

        Args:
            conversation_id: Unique conversation identifier for logging.
            messages: Conversation messages in OpenAI-compatible format.
            model: OpenRouter model name.
            temperature: Sampling temperature.
            max_tokens: Max output tokens.
            extra_payload: Optional extra payload fields passed to OpenRouter.

        Returns:
            Mapping[str, Any]: Final OpenRouter response message (choices[0].message).

        Raises:
            ToolExecutionLimitError: If tool calls exceed MAX_TOOL_CALLS_PER_TURN.
            OpenRouterAPIError: For OpenRouter errors.
            ValueError: For malformed tool call arguments.
        """
        tools = self._tools.get_openrouter_tools()
        running_messages: List[Dict[str, Any]] = [dict(m) for m in messages]

        tool_calls_executed = 0
        last_model_message: Optional[Dict[str, Any]] = None

        while True:
            payload: Dict[str, Any] = {
                "model": model,
                "messages": running_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "tools": tools,
                "tool_choice": "auto",
            }
            if extra_payload:
                payload.update(dict(extra_payload))

            logger.debug(
                "OpenRouter consult request: conversation_id=%s model=%s messages=%d tools=%d",
                conversation_id,
                model,
                len(running_messages),
                len(tools),
            )

            response = self._openrouter.create_chat_completion(payload)
            message = self._extract_first_message(response)
            last_model_message = message

            running_messages.append(message)

            tool_calls = self._extract_tool_calls(message)
            if not tool_calls:
                return message

            for tool_call in tool_calls:
                if tool_calls_executed >= MAX_TOOL_CALLS_PER_TURN:
                    raise ToolExecutionLimitError(
                        f"Exceeded max tool calls per turn ({MAX_TOOL_CALLS_PER_TURN})."
                    )

                tool_calls_executed += 1
                tool_call_id, tool_name, arguments = self._parse_tool_call(tool_call)