import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict, Literal

import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL_NAME = "openai/gpt-4.1-mini"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_DB_PATH = "system_state.db"
DEFAULT_MCP_BASE_URL = "http://localhost:8000"

GOVERNANCE_TASK_STATUS_PENDING = "pending"


class ToolFunction(TypedDict):
    """TypedDict representing a tool function for OpenAI-compatible APIs."""

    name: str
    description: str
    parameters: Dict[str, Any]


class ToolSpec(TypedDict):
    """TypedDict for OpenAI-compatible tool specification."""

    type: Literal["function"]
    function: ToolFunction


class ToolFunctionCall(TypedDict):
    """TypedDict representing a tool function call from the model."""

    name: str
    arguments: str


class ToolCall(TypedDict):
    """TypedDict representing a tool call envelope."""

    id: str
    type: Literal["function"]
    function: ToolFunctionCall


class ChatMessage(TypedDict, total=False):
    """TypedDict representing a chat message."""

    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[str]
    name: Optional[str]
    tool_call_id: Optional[str]
    tool_calls: Optional[List[ToolCall]]


class OpenRouterError(Exception):
    """Exception raised for errors interacting with OpenRouter."""


class SQLToolError(Exception):
    """Exception raised for SQL tool related errors."""


class MCPToolError(Exception):
    """Exception raised for MCP tool related errors."""


class ChatOrchestrationError(Exception):
    """Exception raised for chat orchestration errors."""


class OpenRouterClient:
    """Client for interacting with the OpenRouter chat completions API."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL_NAME,
        timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize the OpenRouter client.

        Args:
            api_key: OpenRouter API key.
            model: Default model name to use.
            timeout_seconds: HTTP request timeout in seconds.
        """
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def chat_completion(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolSpec]] = None,
        tool_choice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call the OpenRouter chat completions endpoint.

        Args:
            messages: Conversation history.
            tools: Optional list of tool definitions.
            tool_choice: Tool choice directive ("auto", "none", or specific).

        Returns:
            Parsed JSON response from OpenRouter.

        Raises:
            OpenRouterError: If the HTTP request fails or response is invalid.
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/juggernaut-system",
            "X-Title": "Juggernaut Dashboard Assistant",
        }

        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }

        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice

        try:
            logger.debug("Sending request to OpenRouter: %s", json.dumps(payload))
            response = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            logger.error("OpenRouter request timed out: %s", exc)
            raise OpenRouterError("OpenRouter request timed out") from exc
        except requests.exceptions.HTTPError as exc:
            logger.error(
                "OpenRouter HTTP error %s: %s", response.status_code, response.text
            )
            raise OpenRouterError(
                f"OpenRouter HTTP error {response.status_code}: {response.text}"
            ) from exc
        except requests.exceptions.RequestException as exc:
            logger.error("OpenRouter request error: %s", exc)
            raise OpenRouterError("OpenRouter request error") from exc

        try:
            data = response.json()
        except ValueError as exc:
            logger.error("Failed to parse OpenRouter JSON response: %s", exc)
            raise OpenRouterError("Failed to parse OpenRouter JSON response") from exc

        if "choices" not in data or not data["choices"]:
            logger.error("OpenRouter returned no choices: %s", data)
            raise OpenRouterError("OpenRouter returned no choices")

        logger.debug("Received response from OpenRouter: %s", json.dumps(data))
        return data


class SQLQueryTool:
    """Tool for executing SQL queries against a SQLite database."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        """Initialize the SQLQueryTool.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = db_path
        self._lock = threading.Lock()
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Initialize the database schema, including governance_tasks table."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS governance_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL
        );
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(create_table_sql)
                conn.commit()
            logger.debug("Database schema initialized successfully.")
        except sqlite3.Error as exc:
            logger.error("Failed to initialize database schema: %s", exc)
            raise SQLToolError("Failed to initialize database schema") from exc

    def execute(
        self,
        statement: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a SQL query in a parameterized fashion.

        Args:
            statement: SQL statement to execute. Use named parameters (e.g., :name).
            parameters: Optional dictionary of parameters.

        Returns:
            List of rows as dictionaries (column_name -> value).

        Raises:
            SQLToolError: If the query fails.
        """
        logger.info("Executing SQL query: %s with params: %s", statement, parameters)
        with self._lock:
            try:
                with sqlite3.connect(self._db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    if parameters is not None:
                        cursor.execute(statement, parameters)
                    else:
                        cursor.execute(statement)
                    rows = cursor.fetchall()
                    result = [dict(row) for row in rows]
                    logger.debug("SQL query returned %d rows.", len(result))
                    return result
            except sqlite3.OperationalError as exc:
                logger.error("SQL operational error: %s", exc)
                raise SQLToolError("SQL operational error") from exc
            except sqlite3.IntegrityError as exc:
                logger.error("SQL integrity error: %s", exc)
                raise SQLToolError("SQL integrity error") from exc
            except sqlite3.Error as exc:
                logger.error("SQL error: %s", exc)
                raise SQLToolError("SQL error") from exc

    def create_governance_task(self, user_id: str, description: str) -> int:
        """Create a new governance task.

        Args:
            user_id: Identifier for the user who requested the task.
            description: Description of the task to be addressed.

        Returns:
            ID of the newly created governance task.

        Raises:
            SQLToolError: If insertion fails.
        """
        insert_sql = """
        INSERT INTO governance_tasks (user_id, description, created_at, status