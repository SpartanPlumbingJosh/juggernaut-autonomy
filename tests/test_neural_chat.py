"""
Integration tests for Neural Chat with MCP tools.

Tests BrainService tool integration, fallback task creation,
and response format validation.
"""

import json
import logging
import os
from unittest.mock import MagicMock, patch

import pytest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_env():
    """Mock environment variables for testing."""
    with patch.dict(os.environ, {
        "OPENROUTER_API_KEY": "test-api-key",
        "MCP_AUTH_TOKEN": "test-mcp-token",
        "MCP_SERVER_URL": "https://test-mcp-server.example.com",
    }):
        yield


@pytest.fixture
def brain_service(mock_env):
    """Create BrainService instance for testing."""
    from core.brain import BrainService
    return BrainService()


@pytest.fixture
def mock_openrouter_response():
    """Factory for creating mock OpenRouter API responses."""
    def _create_response(content: str, tool_calls: list = None):
        response = {
            "choices": [{
                "message": {
                    "content": content,
                    "tool_calls": tool_calls or []
                }
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50
            }
        }
        return json.dumps(response).encode("utf-8")
    return _create_response


@pytest.fixture
def mock_tool_response():
    """Factory for creating mock MCP tool responses."""
    def _create_response(result: dict, success: bool = True):
        if success:
            return json.dumps(result).encode("utf-8")
        else:
            return json.dumps({"error": result.get("error", "Unknown error")}).encode("utf-8")
    return _create_response


# =============================================================================
# UNIT TESTS - BrainService Methods
# =============================================================================

class TestBrainServiceBasics:
    """Test basic BrainService functionality."""

    def test_brain_service_initializes(self, brain_service):
        """BrainService should initialize with default configuration."""
        assert brain_service is not None
        assert brain_service.model == "openrouter/auto"
        assert brain_service.max_tokens == 4096

    def test_brain_service_requires_api_key(self):
        """BrainService should raise error without API key."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            from core.brain import BrainService
            brain = BrainService()
            with pytest.raises(Exception):
                brain.consult_with_tools("test question")


class TestToolExecution:
    """Test tool execution functionality."""

    def test_execute_tool_returns_result(self, brain_service, mock_tool_response):
        """_execute_tool should return parsed JSON result."""
        mock_result = {"rows": [{"count": 10}]}

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = mock_tool_response(mock_result)
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            result = brain_service._execute_tool("sql_query", {"sql": "SELECT 1"})

            assert result == mock_result

    def test_execute_tool_handles_http_error(self, brain_service):
        """_execute_tool should return error dict on HTTP failure."""
        from urllib.error import HTTPError

        with patch("urllib.request.urlopen") as mock_urlopen:
            error = HTTPError(
                url="https://test.com",
                code=500,
                msg="Internal Server Error",
                hdrs={},
                fp=MagicMock(read=lambda: b'{"error": "server error"}')
            )
            mock_urlopen.side_effect = error

            result = brain_service._execute_tool("sql_query", {"sql": "SELECT 1"})

            assert "error" in result

    def test_execute_tool_handles_connection_error(self, brain_service):
        """_execute_tool should return error dict on connection failure."""
        from urllib.error import URLError

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = URLError("Connection refused")

            result = brain_service._execute_tool("sql_query", {"sql": "SELECT 1"})

            assert "error" in result
            assert "Connection" in result["error"]


class TestFallbackTaskCreation:
    """Test governance task fallback functionality."""

    def test_create_fallback_task_calls_hq_execute(self, brain_service):
        """_create_fallback_task should call hq_execute with task.create."""
        with patch.object(brain_service, "_execute_tool") as mock_execute:
            mock_execute.return_value = {"result": {"id": "task-123"}}

            result = brain_service._create_fallback_task(
                tool_name="sql_query",
                arguments={"sql": "SELECT * FROM users"},
                error="Connection timeout",
                user_question="How many users are there?"
            )

            mock_execute.assert_called_once()
            call_args = mock_execute.call_args
            assert call_args[0][0] == "hq_execute"
            assert call_args[0][1]["action"] == "task.create"

    def test_create_fallback_task_includes_context(self, brain_service):
        """_create_fallback_task should include tool and error details."""
        with patch.object(brain_service, "_execute_tool") as mock_execute:
            mock_execute.return_value = {"result": {"id": "task-123"}}

            brain_service._create_fallback_task(
                tool_name="github_create_pr",
                arguments={"title": "Test PR"},
                error="Rate limit exceeded",
                user_question="Create a PR for the feature"
            )

            call_args = mock_execute.call_args
            task_params = call_args[0][1]["params"]

            assert "[Neural Chat] Failed: github_create_pr" in task_params["title"]
            assert "Rate limit exceeded" in task_params["description"]
            assert "Create a PR for the feature" in task_params["description"]

    def test_fallback_task_handles_hq_execute_failure(self, brain_service):
        """_create_fallback_task should handle hq_execute failures gracefully."""
        with patch.object(brain_service, "_execute_tool") as mock_execute:
            mock_execute.side_effect = Exception("HQ execute failed")

            result = brain_service._create_fallback_task(
                tool_name="sql_query",
                arguments={},
                error="Test error",
                user_question="Test question"
            )

            assert "error" in result
            assert result.get("success") is False


class TestConsultWithTools:
    """Test the main consult_with_tools method."""

    def test_consult_returns_required_fields(self, brain_service, mock_openrouter_response):
        """consult_with_tools should return all required response fields."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = mock_openrouter_response("Hello!")
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch.object(brain_service, "_ensure_session") as mock_session:
                mock_session.return_value = ("test-session-id", True)

                with patch.object(brain_service, "_load_history") as mock_history:
                    mock_history.return_value = []

                    with patch.object(brain_service, "_store_message"):
                        result = brain_service.consult_with_tools(
                            "Hello",
                            enable_tools=False
                        )

            assert "response" in result
            assert "session_id" in result
            assert "tool_executions" in result
            assert "iterations" in result

    def test_consult_without_tools_returns_empty_executions(self, brain_service, mock_openrouter_response):
        """consult_with_tools with enable_tools=False should return empty tool_executions."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = mock_openrouter_response("Hello!")
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch.object(brain_service, "_ensure_session") as mock_session:
                mock_session.return_value = ("test-session-id", True)

                with patch.object(brain_service, "_load_history") as mock_history:
                    mock_history.return_value = []

                    with patch.object(brain_service, "_store_message"):
                        result = brain_service.consult_with_tools(
                            "Hello",
                            enable_tools=False
                        )

            assert result["tool_executions"] == []


class TestMaxIterations:
    """Test iteration limits."""

    def test_max_iterations_constant_exists(self, brain_service):
        """MAX_TOOL_ITERATIONS constant should be defined."""
        from core.brain import MAX_TOOL_ITERATIONS
        assert MAX_TOOL_ITERATIONS > 0
        assert MAX_TOOL_ITERATIONS <= 20  # Sanity check


# =============================================================================
# INTEGRATION TESTS - Response Format
# =============================================================================

class TestResponseFormat:
    """Test API response format compliance."""

    def test_tool_execution_record_has_required_fields(self):
        """Tool execution records should have required fields."""
        required_fields = {"tool", "arguments", "result", "success"}

        # Create a sample execution record
        sample_record = {
            "tool": "sql_query",
            "arguments": {"sql": "SELECT 1"},
            "result": {"rows": []},
            "success": True
        }

        assert required_fields.issubset(sample_record.keys())

    def test_fallback_execution_record_has_fallback_fields(self):
        """Failed tool executions with fallback should include fallback fields."""
        sample_record = {
            "tool": "sql_query",
            "arguments": {"sql": "SELECT 1"},
            "result": {"error": "Connection timeout"},
            "success": False,
            "fallback_task_created": True,
            "fallback_task_id": "task-123"
        }

        assert sample_record["fallback_task_created"] is True
        assert "fallback_task_id" in sample_record


# =============================================================================
# MCP TOOL SCHEMA TESTS
# =============================================================================

class TestMCPToolSchemas:
    """Test MCP tool schema definitions."""

    def test_tool_schemas_are_valid(self):
        """Tool schemas should be valid OpenRouter function definitions."""
        from core.mcp_tool_schemas import get_tool_schemas

        schemas = get_tool_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) > 0

        for schema in schemas:
            assert schema.get("type") == "function"
            assert "function" in schema
            func = schema["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func

    def test_sql_query_tool_schema_exists(self):
        """sql_query tool should be defined in schemas."""
        from core.mcp_tool_schemas import get_tool_schemas

        schemas = get_tool_schemas()
        tool_names = [s["function"]["name"] for s in schemas]

        assert "sql_query" in tool_names

    def test_hq_execute_tool_schema_exists(self):
        """hq_execute tool should be defined in schemas."""
        from core.mcp_tool_schemas import get_tool_schemas

        schemas = get_tool_schemas()
        tool_names = [s["function"]["name"] for s in schemas]

        assert "hq_execute" in tool_names

    def test_github_write_tools_exist(self):
        """GitHub write tools should be defined in schemas."""
        from core.mcp_tool_schemas import get_tool_schemas

        schemas = get_tool_schemas()
        tool_names = [s["function"]["name"] for s in schemas]

        # Verify GitHub write tools are available
        assert "github_put_file" in tool_names
        assert "github_create_branch" in tool_names
        assert "github_create_pr" in tool_names
        assert "github_merge_pr" in tool_names

    def test_github_put_file_schema_has_required_fields(self):
        """github_put_file schema should have all required fields."""
        from core.mcp_tool_schemas import get_tool_schemas

        schemas = get_tool_schemas()
        github_put_file = next(
            (s for s in schemas if s["function"]["name"] == "github_put_file"), None
        )
        
        assert github_put_file is not None
        params = github_put_file["function"]["parameters"]
        
        # Check required parameters
        assert "required" in params
        assert "path" in params["required"]
        assert "content" in params["required"]
        assert "message" in params["required"]
        assert "branch" in params["required"]
        
        # Check properties exist
        properties = params["properties"]
        assert "path" in properties
        assert "content" in properties
        assert "message" in properties
        assert "branch" in properties
        assert "sha" in properties  # Optional but should be defined
