import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

LOGGER = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.environ.get("JUGGERNAUT_DB_PATH", os.path.join(os.getcwd(), "juggernaut.db"))
DEFAULT_CONTEXT_WINDOW = int(os.environ.get("JUGGERNAUT_CONTEXT_WINDOW", "20"))
DEFAULT_MAX_SYNC_SECONDS = int(os.environ.get("JUGGERNAUT_MAX_SYNC_SECONDS", "15"))

DEFAULT_TOOL_SCOPE = tuple(
    t.strip()
    for t in os.environ.get("JUGGERNAUT_TOOL_SCOPE", "search,files,knowledge,calculator").split(",")
    if t.strip()
)

TABLE_NAME = "governance_tasks"

# Task type defaults
TASK_TYPE_CODE = "code"
TASK_TYPE_ANALYSIS = "analysis"
TASK_TYPE_RESEARCH = "research"
TASK_TYPE_DEPLOYMENT = "deployment"
TASK_TYPE_OPERATIONS = "operations"
TASK_TYPE_SECURITY = "security"
TASK_TYPE_UNKNOWN = "unknown"

# Status defaults
STATUS_QUEUED = "queued"

# Regex / keyword heuristics
_DEPLOY_KEYWORDS = (
    "deploy",
    "deployment",
    "release",
    "ship",
    "publish",
    "rollout",
    "railway",
    "vercel",
    "render",
    "fly.io",
    "kubernetes",
    "k8s",
    "docker push",
    "helm",
)
_SECURITY_KEYWORDS = (
    "rotate key",
    "rotate keys",
    "secret",
    "api key",
    "token",
    "credentials",
    "permission",
    "iam",
    "admin",
    "ssh",
    "private key",
)
_RESEARCH_KEYWORDS = ("research", "find sources", "compare", "literature", "survey")
_ANALYSIS_KEYWORDS = ("analyze", "analysis", "root cause", "postmortem", "investigate")
_CODE_KEYWORDS = ("implement", "refactor", "fix", "bug", "feature", "write code", "add tests", "update module")
_OPS_KEYWORDS = ("restart", "scale", "backup", "restore", "migrate", "database", "db", "cron", "monitor")

_OUTSIDE_SCOPE_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\bdeploy\b", re.IGNORECASE),
    re.compile(r"\bproduction\b", re.IGNORECASE),
    re.compile(r"\brotate\b.*\bkey\b", re.IGNORECASE),
    re.compile(r"\bmake payment\b|\bpurchase\b|\bbuy\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class ChatMessage:
    """Represents a chat message within a conversation.

    Attributes:
        role: The role of the message sender (e.g., "user", "assistant", "system").
        content: The message content.
        timestamp: Optional ISO timestamp; if not provided, it will be generated when context is built.
        metadata: Optional metadata for the message.
    """

    role: str
    content: str
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionRequest:
    """Represents an action request inferred from user input.

    Attributes:
        raw_text: The raw user input.
        tool_name: Optional tool that would be used to execute the action (if known).
        operation: Optional operation name (if known).
        requires_async: Whether the action requires asynchronous execution.
        requires_approval: Whether the action requires governance approval.
        estimated_duration_s: Estimated duration in seconds for direct execution (if known).
        metadata: Additional action metadata.
    """

    raw_text: str
    tool_name: Optional[str] = None
    operation: Optional[str] = None
    requires_async: bool = False
    requires_approval: bool = False
    estimated_duration_s: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GovernanceTask:
    """Represents a governance task to be queued for engine handling.

    Attributes:
        task_id: Unique task ID.
        task_type: Task type classification (e.g., code, analysis, research, deployment).
        status: Task status (e.g., queued).
        created_at: ISO timestamp.
        title: Human-friendly title.
        description: Task description including actionable details.
        conversation_context: Serialized conversation context for continuity.
        action: Serialized action request.
        metadata: Additional metadata for routing/approval.
    """

    task_id: str
    task_type: str
    status: str
    created_at: str
    title: str
    description: str
    conversation_context: Dict[str, Any]
    action: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


class GovernanceTaskRepository(Protocol):
    """Repository interface for governance tasks."""

    def create(self, task: GovernanceTask) -> str:
        """Creates a governance task.

        Args:
            task: The task to create.

        Returns:
            The created task ID.
        """
        raise NotImplementedError

    def get(self, task_id: str) -> Optional[GovernanceTask]:
        """Fetches a governance task by ID.

        Args:
            task_id: The task ID.

        Returns:
            The task if found; otherwise None.
        """
        raise NotImplementedError


class SqliteGovernanceTaskRepository:
    """SQLite-backed repository for governance tasks."""

    def __init__(self, db_path: str) -> None:
        """Initializes the repository and ensures schema exists.

        Args:
            db_path: Path to SQLite database file.
        """
        self._db_path = db_path
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        """Creates a SQLite connection.

        Returns:
            A SQLite connection.
        """
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Ensures the governance task table exists."""
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            task_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            conversation_context TEXT NOT NULL,
            action TEXT NOT NULL,
            metadata TEXT NOT NULL
        );
        """
        try:
            with self._lock:
                with self._connect() as conn:
                    conn.execute(ddl)
                    conn.commit()
        except sqlite3.OperationalError as exc:
            LOGGER.exception("Failed to ensure schema: %s", exc)
            raise

    def create(self, task: GovernanceTask) -> str:
        """Creates a governance task.

        Args:
            task: The task to create.

        Returns:
            The created task ID.

        Raises:
            sqlite3.IntegrityError: If task_id already exists.
            sqlite3.OperationalError: If database operation fails.
        """
        sql = f"""
        INSERT INTO {TABLE_NAME}
        (task_id, task_type, status, created_at, title, description, conversation_context, action, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        try:
            with self._lock:
                with self._connect() as conn:
                    conn.execute(
                        sql,
                        (
                            task.task_id,
                            task.task_type,
                            task.status,
                            task.created_at,
                            task.title,
                            task.description,
                            json.dumps(task.conversation_context, ensure_ascii=False),
                            json.dumps(task.action, ensure_ascii=False),
                            json.dumps(task.metadata, ensure_ascii=False),
                        ),
                    )
                    conn.commit()
            return task.task_id
        except sqlite3.IntegrityError:
            LOGGER.exception("Task ID collision for task_id=%s", task.task_id)
            raise
        except sqlite3.OperationalError as exc:
            LOGGER.exception("Failed to create governance task: %s", exc)
            raise

    def get(self, task_id: str) -> Optional[GovernanceTask]:
        """Fetches a governance task by ID.

        Args:
            task_id: The task ID.

        Returns:
            The task if found; otherwise None.

        Raises:
            sqlite3.OperationalError: If database operation fails.
        """
        sql = f"SELECT * FROM {TABLE_NAME} WHERE task_id = ?;"
        try:
            with self._lock:
                with self._connect() as conn:
                    row = conn.execute(sql, (task_id,)).fetchone()
            if row is None:
                return None
            return GovernanceTask(
                task_id=str(row["task_id"]),
                task_type=str(row["task_type"]),
                status=str(row["status"]),
                created_at=str(row["created_at"]),
                title=str(row["title"]),
                description=str(row["description"]),
                conversation_context=json.loads(str(row["conversation_context"])),
                action=json.loads(str(row["action"])),
                metadata=json.loads(str(row["metadata"])),
            )
        except sqlite3.OperationalError as exc:
            LOGGER.exception("Failed to fetch governance task: %s", exc)
            raise
        except json.JSONDecodeError as exc:
            LOGGER.exception("Failed to decode governance task JSON for task_id=%s: %s", task_id, exc)
            raise


def _utc_now_iso() -> str:
    """Returns current UTC time as an ISO-8601 string.

    Returns:
        ISO string timestamp.
    """
    return datetime.now(timezone.utc).isoformat()


def _truncate_messages(messages: Sequence[ChatMessage], window: int) -> List[ChatMessage]:
    """Truncates messages to the last N items.

    Args:
        messages: Full message list.
        window: Max number of messages to keep.

    Returns:
        Truncated list of messages.
    """
    if window <= 0:
        return []
    return list(messages[-window:])


def _normalize_context(messages: Sequence[ChatMessage], window: int) -> Dict[str, Any]:
    """Builds a normalized conversation context object.

    Args:
        messages: Conversation messages.
        window: Number of messages to include.

    Returns:
        Normalized context dict suitable for persistence.
    """
    selected = _truncate_messages(messages, window)
    normalized: List[Dict[str, Any]] = []
    now = _utc_now_iso()
    for m in selected:
        normalized.append(
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp or now,
                "metadata": m.metadata or {},
            }
        )
    return {
        "messages": normalized,
        "window": window,
        "generated_at": now,
    }


def _infer_task_type(text: str) -> str:
    """Infers a governance task type from raw user text.

    Args:
        text: User request text.

    Returns:
        Inferred task type string.
    """
    lowered = text.lower()

    if any(k in lowered for k in _DEPLOY_KEYWORDS):
        return TASK_TYPE_DEPLOYMENT
    if any(k in lowered for k in _SECURITY_KEYWORDS):
        return TASK_TYPE_SECURITY
    if any(k in lowered for k in _RESEARCH_KEYWORDS):
        return TASK_TYPE_RESEARCH
    if any(k in lowered for k in _ANALYSIS_KEYWORDS):
        return TASK_TYPE_ANALYSIS
    if any(k in lowered for k in _OPS_KEYWORDS):
        return TASK_TYPE_OPERATIONS
    if any(k in lowered for k in _CODE_KEYWORDS):
        return TASK_TYPE_CODE
    return TASK_TYPE_UNKNOWN


def _requires_governance_fallback(action: ActionRequest, tool_scope: Sequence[str]) -> Tuple[bool, str]:
    """Determines whether an action must be delegated to governance task fallback.

    Args:
        action: The action request.
        tool_scope: List of tool names that Brain can directly execute.

    Returns:
        Tuple of (requires_fallback, reason).
    """
    if action.requires_approval:
        return True, "requires_approval"

    if action.requires_async:
        return True, "requires_async"

    if action.estimated_duration_s is not None and action.estimated_duration_s > DEFAULT_MAX_SYNC_SECONDS:
        return True, "too_long_for_sync"

    if action.tool_name is not None and action.tool_name.strip() != "":
        if action.tool_name not in tool_scope:
            return True, "outside_tool_scope"

    raw = action.raw_text or ""
    for pattern in _OUTSIDE_SCOPE_PATTERNS:
        if pattern.search(raw) is not None:
            return True, "outside_tool_scope_heuristic"

    return False, ""


def _build_task_title(task_type: str, action: ActionRequest) -> str:
    """Builds a task title.

    Args:
        task_type: Inferred task type.
        action: The action request.

    Returns:
        Task title.
    """
    base = action.raw_text.strip()
    if len(base) <= 90:
        return base if base else f"{task_type} task"
    return f"{base[:87]}..."


def _build_task_description(task_type: str, action: ActionRequest, reason: str) -> str:
    """Builds a detailed task description.

    Args:
        task_type: Inferred task type.
        action: The action request.
        reason: Reason the task was created.

    Returns:
        Task description.
    """
    parts = [
        f"Task type: {task_type}",
        f"Reason queued: {reason}",
        f"User request: {action.raw_text.strip()}",
    ]
    if action.tool_name:
        parts.append(f"Suggested tool: {action.tool_name}")
    if action.operation:
        parts.append(f"Suggested operation: {action.operation}")
    if action.estimated_duration_s is not None:
        parts.append(f"Estimated duration: {action.estimated_duration_s}s")
    if action.metadata:
        parts.append(f"Action metadata: {json.dumps(action.metadata, ensure_ascii=False)}")
    return "\n".join(parts)


class Brain:
    """Brain orchestrator that falls back to governance tasks when direct execution isn't possible.

    This module focuses on detecting when an action requires asynchronous execution or is outside
    current tool scope, and creates a queued governance task that includes conversation context.
    """

    def __init__(
        self,
        task_repo: Optional[GovernanceTaskRepository] = None,
        tool_scope: Optional[Sequence[str]] = None,
        context_window: int = DEFAULT_CONTEXT_WINDOW,
    ) -> None:
        """Initializes Brain.

        Args:
            task_repo: Repository to store governance tasks. Defaults to SQLite repo.
            tool_scope: Tool scope for direct execution. Defaults to env-derived scope.
            context_window: Number of recent messages to attach as context.
        """
        self._task_repo = task_repo or SqliteGovernanceTaskRepository(DEFAULT_DB_PATH)
        self._tool_scope = list(tool_scope) if tool_scope is not None else list(DEFAULT_TOOL_SCOPE)
        self._context_window = context_window

    def handle(
        self,
        user_text: str,
        conversation: Sequence[ChatMessage],
        action: Optional[ActionRequest] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> str:
        """Handles a user request, creating a governance task when needed.

        Args:
            user_text: Raw user message text.
            conversation: Conversation history including current message.
            action: Optional pre-parsed action request. If not provided, Brain will infer minimal action.
            user_id: Optional user identifier