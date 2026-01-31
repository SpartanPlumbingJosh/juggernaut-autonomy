import json
import logging
import re
import sqlite3
import time
import unittest
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


LOGGER = logging.getLogger(__name__)

MAX_TOOL_CALLS: int = 5
SIMPLE_QUERY_MAX_LATENCY_S: float = 10.0
SQLITE_BUSY_TIMEOUT_MS: int = 1_000
RECENT_ACTIVITY_LIMIT: int = 5


class ToolError(Exception):
    """Base class for tool-related failures."""


class ToolRateLimitError(ToolError):
    """Raised when tool call rate limits are exceeded."""


class MCPServerDownError(ToolError):
    """Raised when the MCP server is unavailable."""


class SQLExecutionError(ToolError):
    """Raised when an SQL query fails to execute."""


@dataclass(frozen=True)
class ToolCall:
    """Represents a tool call request.

    Attributes:
        name: Tool name.
        arguments: Tool arguments.
    """

    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """Represents a tool call result.

    Attributes:
        name: Tool name.
        ok: Whether the tool succeeded.
        data: Output payload if succeeded.
        error: Error message if failed.
        trace: Trace info to support provenance.
    """

    name: str
    ok: bool
    data: Optional[Any]
    error: Optional[str]
    trace: Mapping[str, Any]


@dataclass(frozen=True)
class ChatResponse:
    """Represents a chat response.

    Attributes:
        text: User-visible response text.
        tool_calls: Tool calls executed during the turn.
        tool_results: Tool results produced during the turn.
    """

    text: str
    tool_calls: Sequence[ToolCall]
    tool_results: Sequence[ToolResult]


class ToolCallLimiter:
    """Tracks and enforces a maximum tool call count per conversation."""

    def __init__(self, max_calls: int) -> None:
        """Initializes the limiter.

        Args:
            max_calls: Maximum allowed tool calls.
        """
        self._max_calls = max_calls
        self._used_calls = 0

    @property
    def used_calls(self) -> int:
        """Returns the number of used tool calls."""
        return self._used_calls

    @property
    def remaining_calls(self) -> int:
        """Returns the number of remaining tool calls."""
        return max(self._max_calls - self._used_calls, 0)

    def consume(self, count: int = 1) -> None:
        """Consumes tool call capacity.

        Args:
            count: Number of tool calls to consume.

        Raises:
            ToolRateLimitError: If the consumption would exceed the limit.
        """
        if count < 0:
            raise ValueError("count must be non-negative")

        if self._used_calls + count > self._max_calls:
            raise ToolRateLimitError(
                f"Tool call limit exceeded (limit={self._max_calls}, used={self._used_calls}, requested={count})."
            )
        self._used_calls += count


class FallbackTaskStore:
    """Stores tasks locally when MCP is unavailable."""

    def __init__(self) -> None:
        """Initializes the fallback store."""
        self._tasks: Dict[str, Dict[str, Any]] = {}

    def create_task(self, title: str, description: str) -> str:
        """Creates a local fallback task.

        Args:
            title: Task title.
            description: Task description.

        Returns:
            Task ID as a UUID string.
        """
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {
            "id": task_id,
            "title": title,
            "description": description,
            "status": "pending",
            "created_at": time.time(),
        }
        return task_id

    def get_task(self, task_id: str) -> Optional[Mapping[str, Any]]:
        """Gets a local fallback task.

        Args:
            task_id: Task ID.

        Returns:
            The task if present, else None.
        """
        return self._tasks.get(task_id)


class MCPClient:
    """Simulates an MCP client that provides tool methods."""

    def __init__(self, connection: sqlite3.Connection, *, server_up: bool = True) -> None:
        """Initializes the client.

        Args:
            connection: SQLite connection.
            server_up: Whether the MCP server is available.
        """
        self._connection = connection
        self._server_up = server_up

    @property
    def server_up(self) -> bool:
        """Returns whether the MCP server is available."""
        return self._server_up

    def set_server_up(self, up: bool) -> None:
        """Sets the server availability.

        Args:
            up: True if MCP should be available, False otherwise.
        """
        self._server_up = up

    def sql_query(self, sql: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
        """Executes an SQL query against the MCP database.

        Args:
            sql: SQL string.
            params: Optional parameters.

        Returns:
            List of rows as dictionaries.

        Raises:
            MCPServerDownError: If MCP is unavailable.
            SQLExecutionError: If the SQL fails.
        """
        if not self._server_up:
            raise MCPServerDownError("MCP server is down")

        try:
            cur = self._connection.execute(sql, params or [])
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()
            out: List[Dict[str, Any]] = []
            for row in rows:
                if isinstance(row, sqlite3.Row):
                    out.append(dict(row))
                elif columns:
                    out.append({columns[i]: row[i] for i in range(len(columns))})
                else:
                    out.append({"value": row})
            return out
        except sqlite3.Error as exc:
            raise SQLExecutionError(str(exc)) from exc

    def governance_task_create(self, title: str, description: str) -> int:
        """Creates a governance task in the MCP system.

        Args:
            title: Task title.
            description: Task description.

        Returns:
            Created task ID.

        Raises:
            MCPServerDownError: If MCP is unavailable.
            SQLExecutionError: If the operation fails.
        """
        if not self._server_up:
            raise MCPServerDownError("MCP server is down")

        try:
            cur = self._connection.execute(
                "INSERT INTO tasks(title, status, description, created_at) VALUES (?, ?, ?, ?)",
                (title, "pending", description, int(time.time())),
            )
            self._connection.commit()
            return int(cur.lastrowid)
        except sqlite3.Error as exc:
            raise SQLExecutionError(str(exc)) from exc


class NeuralChatSession:
    """A minimal end-to-end session that plans tool calls and produces grounded responses."""

    def __init__(
        self,
        mcp_client: MCPClient,
        limiter: ToolCallLimiter,
        fallback_store: FallbackTaskStore,
    ) -> None:
        """Initializes the session.

        Args:
            mcp_client: MCP client for tool calls.
            limiter: Tool call limiter.
            fallback_store: Fallback task store for MCP outages.
        """
        self._mcp = mcp_client
        self._limiter = limiter
        self._fallback = fallback_store

    def handle_message(self, user_message: str) -> ChatResponse:
        """Handles a user message and returns a grounded response.

        Args:
            user_message: The user's message.

        Returns:
            A chat response containing executed tool calls and results.
        """
        tool_calls: List[ToolCall] = []
        tool_results: List[ToolResult] = []

        plan = self._plan(user_message)
        gathered: Dict[str, Any] = {}
        for call in plan:
            if self._limiter.remaining_calls <= 0:
                break
            try:
                self._limiter.consume(1)
            except ToolRateLimitError as exc:
                LOGGER.warning("Rate limit exceeded: %s", exc)
                break

            tool_calls.append(call)
            result = self._execute_tool(call)
            tool_results.append(result)
            if result.ok:
                gathered_key = f"{call.name}:{len([c for c in tool_calls if c.name == call.name])}"
                gathered[gathered_key] = result.data

        if any(isinstance(self._tool_error_kind(r), MCPServerDownError) for r in tool_results if not r.ok):
            fallback_text, fallback_calls, fallback_results = self._fallback_on_mcp_down(user_message)
            tool_calls.extend(fallback_calls)
            tool_results.extend(fallback_results)
            return ChatResponse(text=fallback_text, tool_calls=tool_calls, tool_results=tool_results)

        response_text = self._render_response(user_message, tool_calls, tool_results, gathered)
        if self._limiter.used_calls >= MAX_TOOL_CALLS and self._limiter.remaining_calls == 0:
            response_text = self._append_rate_limit_summary(response_text, tool_calls, tool_results, gathered)
        return ChatResponse(text=response_text, tool_calls=tool_calls, tool_results=tool_results)

    def _plan(self, user_message: str) -> List[ToolCall]:
        """Creates a tool-call plan based on user message.

        Args:
            user_message: User message.

        Returns:
            List of tool calls to execute.
        """
        msg = user_message.strip()
        lower = msg.lower()

        if lower.startswith("run sql:"):
            sql = msg.split(":", 1)[1].strip()
            return [ToolCall(name="sql_query", arguments={"sql": sql, "params": []})]

        # Multi-tool requests
        wants_health = "worker health" in lower or ("health" in lower and "worker" in lower)
        wants_activity = "recent activity" in lower or ("summarize" in lower and "activity" in lower)

        if wants_health and wants_activity:
            return [
                ToolCall(
                    name="sql_query",
                    arguments={
                        "sql": "SELECT worker_id, status, last_heartbeat, cpu_load FROM worker_registry ORDER BY worker_id",
                        "params": [],
                    },
                ),
                ToolCall(
                    name="sql_query",
                    arguments={
                        "sql": "SELECT timestamp, worker_id, event FROM activity_log ORDER BY timestamp DESC LIMIT ?",
                        "params": [RECENT_ACTIVITY_LIMIT],
                    },
                ),
            ]

        # Query mode tasks
        if "tasks" in lower and ("pending" in lower or "open" in lower):
            return [
                ToolCall(
                    name="sql_query",
                    arguments={
                        "sql": "SELECT id, title, status FROM tasks WHERE status = ? ORDER BY id",
                        "params": ["pending"],
                    },
                )
            ]

        # Query mode worker health
        if wants_health:
            return [
                ToolCall(
                    name="sql_query",
                    arguments={
                        "sql": "SELECT worker_id, status, last_heartbeat, cpu_load FROM worker_registry ORDER BY worker_id",
                        "params": [],
                    },
                )
            ]

        # Command mode task creation
        if ("create a task" in lower) or lower.startswith("create task") or ("make a task" in lower):
            title = self._extract_task_title(msg)
            desc = f"Created from user request: {msg}"
            return [ToolCall(name="governance_task_create", arguments={"title": title, "description": desc})]

        # A "tool-heavy" request to exercise rate limiting
        if ("list" in lower or "show" in lower) and ("pending tasks" in lower and "completed tasks" in lower):
            return [
                ToolCall(
                    name="sql_query",
                    arguments={"sql": "SELECT id, title, status FROM tasks WHERE status = ? ORDER BY id", "params": ["pending"]},
                ),
                ToolCall(
                    name="sql_query",
                    arguments={"sql": "SELECT id, title, status FROM tasks WHERE status = ? ORDER BY id", "params": ["completed"]},
                ),
                ToolCall(
                    name="sql_query",
                    arguments={"sql": "SELECT id, title, status FROM tasks WHERE status = ? ORDER BY id", "params": ["failed"]},
                ),
                ToolCall(
                    name="sql_query",
                    arguments={
                        "sql": "SELECT worker_id, status, last_heartbeat, cpu_load FROM worker_registry ORDER BY worker_id",
                        "params": [],
                    },
                ),
                ToolCall(
                    name="sql_query",
                    arguments={
                        "sql": "SELECT timestamp, worker_id, event FROM activity_log ORDER BY timestamp DESC LIMIT ?",
                        "params": [RECENT_ACTIVITY_LIMIT],
                    },
                ),
                ToolCall(
                    name="sql_query",
                    arguments={"sql": "SELECT COUNT(*) AS task_count FROM tasks", "params": []},
                ),
            ]

        # Default: try a safe minimal