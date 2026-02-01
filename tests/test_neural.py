import pytest
import requests
from unittest.mock import patch, MagicMock

from your_module import (  # Assuming your code is in a file named 'your_module.py'
    NeuralChatOrchestrator,
    ToolExecutionError,
    GITHUB_PUT_FILE_TOOL,
    GITHUB_MERGE_PR_TOOL,
    CODE_GENERATE_TOOL,
    BRAIN_API_URL,
)

# --- Fixtures ---

@pytest.fixture
def orchestrator():
    """Provides an instance of NeuralChatOrchestrator."""
    return NeuralChatOrchestrator()

@pytest.fixture
def mock_brain_api():
    """Mocks the requests.post call for the Brain API."""
    with patch('requests.post') as mock_post:
        yield mock_post

# --- Test Cases for ToolExecutionError ---

def test_tool_execution_error_creation():
    """Tests that ToolExecutionError can be instantiated and has correct attributes."""
    error_message = "Simulated execution failure"
    exc = ToolExecutionError(error_message)
    assert str(exc) == error_message
    assert isinstance(exc, Exception)

def test_tool_execution_error_with_cause():
    """Tests that ToolExecutionError can wrap another exception."""
    original_exception = ValueError("Underlying issue")
    error_message = "Failure due to underlying issue"
    try:
        raise ToolExecutionError(error_message, cause=original_exception)
    except ToolExecutionError as e:
        assert str(e) == error_message
        assert e.__cause__ is original_exception

# --- Test Cases for NeuralChatOrchestrator ---

class TestNeuralChatOrchestrator:

    def test_initialization(self, orchestrator):
        """Tests that the orchestrator initializes correctly with default URL."""
        assert orchestrator.brain_api_url == BRAIN_API_URL

    def test_initialization_with_custom_url(self):
        """Tests that the orchestrator can be initialized with a custom Brain API URL."""
        custom_url = "http://test.com/api/brain"
        orchestrator = NeuralChatOrchestrator(brain_api_url=custom_url)
        assert orchestrator.brain_api_url == custom_url

    @patch('requests.post')
    def test_execute_task_sequence_success(self, mock_post):
        """Tests successful execution of a task sequence via Brain API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "result": {"status": "completed", "message": "All tasks done"}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        orchestrator = NeuralChatOrchestrator()
        prompt = "Do something amazing."
        result = orchestrator.execute_task_sequence(prompt)

        mock_post.assert_called_once_with(
            BRAIN_API_URL,
            json={"prompt": prompt},
            timeout=60
        )
        assert result == {"status": "completed", "message": "All tasks done"}

    @patch('requests.post')
    def test_execute_task_sequence_brain_api_failure(self, mock_post):
        """Tests when the Brain API itself reports a failure."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error": "Brain API internal error"
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        orchestrator = NeuralChatOrchestrator()
        prompt = "Try to do something."
        result = orchestrator.execute_task_sequence(prompt)

        mock_post.assert_called_once_with(
            BRAIN_API_URL,
            json={"prompt": prompt},
            timeout=60
        )
        assert result == {"status": "failed", "error": "Brain API internal error"}

    @patch('requests.post')
    def test_execute_task_sequence_request_exception(self, mock_post):
        """Tests handling of network errors during Brain API call."""
        mock_post.side_effect = requests.exceptions.RequestException("Network error")

        orchestrator = NeuralChatOrchestrator()
        prompt = "Network test."

        with pytest.raises(ToolExecutionError) as excinfo:
            orchestrator.execute_task_sequence(prompt)

        assert "Failed to communicate with Brain API" in str(excinfo.value)
        mock_post.assert_called_once_with(
            BRAIN_API_URL,
            json={"prompt": prompt},
            timeout=60
        )

    @patch('requests.post')
    def test_execute_task_sequence_http_error(self, mock_post):
        """Tests handling of HTTP errors (e.g., 404, 500) from Brain API."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_post.return_value = mock_response

        orchestrator = NeuralChatOrchestrator()
        prompt = "HTTP error test."

        with pytest.raises(ToolExecutionError) as excinfo:
            orchestrator.execute_task_sequence(prompt)

        assert "Failed to communicate with Brain API" in str(excinfo.value)
        assert "404 Not Found" in str(excinfo.value.__cause__)
        mock_post.assert_called_once_with(
            BRAIN_API_URL,
            json={"prompt": prompt},
            timeout=60
        )

    @patch('requests.post')
    def test_execute_task_sequence_unexpected_error(self, mock_post):
        """Tests handling of unexpected errors during Brain API call."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        orchestrator = NeuralChatOrchestrator()
        prompt = "JSON error test."

        with pytest.raises(ToolExecutionError) as excinfo:
            orchestrator.execute_task_sequence(prompt)

        assert "An unexpected error occurred" in str(excinfo.value)
        assert "Invalid JSON" in str(excinfo.value.__cause__)
        mock_post.assert_called_once_with(
            BRAIN_API_URL,
            json={"prompt": prompt},
            timeout=60
        )

    # --- Test Cases for _execute_single_tool ---

    def test_execute_single_tool_github_put_file_success(self, orchestrator):
        """Tests successful execution of the simulated github_put_file tool."""
        tool_input = {"repo": "myorg/myrepo", "file_path": "README.md", "content": "# Hello"}
        result = orchestrator._execute_single_tool(GITHUB_PUT_FILE_TOOL, tool_input, {})
        assert result.success is True
        assert result.output == {"file_path": "README.md", "status": "uploaded"}
        assert result.error is None

    def test_execute_single_tool_github_put_file_missing_args(self, orchestrator):
        """Tests github_put_file tool with missing arguments."""
        tool_input = {"repo": "myorg/myrepo", "content": "# Hello"}
        result = orchestrator._execute_single_tool(GITHUB_PUT_FILE_TOOL, tool_input, {})
        assert result.success is False
        assert "missing required arguments" in result.error
        assert result.output == {}

    def test_execute_single_tool_github_merge_pr_success(self, orchestrator):
        """Tests successful execution of the simulated github_merge_pr tool."""
        tool_input = {"repo": "myorg/myrepo", "pr_number": 123}
        result = orchestrator._execute_single_tool(GITHUB_MERGE_PR_TOOL, tool_input, {})
        assert result.success is True
        assert result.output == {"pr_number": 123, "status": "merged"}
        assert result.error is None

    def test_execute_single_tool_github_merge_pr_missing_args(self, orchestrator):
        """Tests github_merge_pr tool with missing arguments."""
        tool_input = {"repo": "myorg/myrepo"}
        result = orchestrator._execute_single_tool(GITHUB_MERGE_PR_TOOL, tool_input, {})
        assert result.success is False
        assert "missing required arguments" in result.error
        assert result.output == {}

    def test_execute_single_tool_code_generate_success(self, orchestrator):
        """Tests successful execution of the simulated code_generate tool."""
        tool_input = {"description": "A simple function"}
        result = orchestrator._execute_single_tool(CODE_GENERATE_TOOL, tool_input, {})
        assert result.success is True
        assert "code" in result.output
        assert "language" in result.output
        assert result.output["language"] == "javascript"
        assert result.error is None

    def test_execute_single_tool_code_generate_missing_args(self, orchestrator):
        """Tests code_generate tool with missing arguments."""
        tool_input = {"details": "Some details"}
        result = orchestrator._execute_single_tool(CODE_GENERATE_TOOL, tool_input, {})
        assert result.success is False
        assert "missing required argument" in result.error
        assert result.output == {}

    def test_execute_single_tool_unknown_tool(self, orchestrator):
        """Tests execution of an unknown tool."""
        tool_input = {"some": "input"}
        result = orchestrator._execute_single_tool("non_existent_tool", tool_input, {})
        assert result.success is False
        assert "Unknown tool" in result.error
        assert result.output == {}

    def test_execute_single_tool_exception_during_execution(self, orchestrator):
        """Tests handling of exceptions within a simulated tool execution."""
        # Temporarily patch _execute_single_tool to raise an exception for a specific tool
        original_method = orchestrator._execute_single_tool

        def faulty_tool_executor(tool_name, tool_input, current_state):
            if tool_name == "faulty_tool":
                raise RuntimeError("Simulated internal tool error")
            return original_method(tool_name, tool_input, current_state)

        orchestrator._execute_single_tool = faulty_tool_executor

        tool_input = {"data": "value"}
        result = orchestrator._execute_single_tool("faulty_tool", tool_input, {})

        assert result.success is False
        assert "An error occurred during execution" in result.error
        assert "Simulated internal tool error" in result.error
        assert result.output == {}

        # Restore the original method
        orchestrator._execute_single_tool = original_method

    def test_execute_single_tool_with_current_state(self, orchestrator):
        """Tests that _execute_single_tool can receive and potentially use current_state."""
        # This test primarily verifies the method signature and that it doesn't error
        # when current_state is provided. Actual use of current_state depends on tool logic.
        tool_input = {"repo": "myorg/myrepo", "file_path": "file.txt", "content": "data"}
        current_state = {"previous_output": "some_value"}
        result = orchestrator._execute_single_tool(GITHUB_PUT_FILE_TOOL, tool_input, current_state)
        assert result.success is True
        # Ensure the tool execution itself didn't fail due to state being present
        assert result.error is None

# --- Test Cases for ToolResult ---

class TestToolResult:

    def test_tool_result_success_with_output(self):
        """Tests creating a successful ToolResult with output."""
        output_data = {"key": "value", "number": 123}
        result = ToolResult(success=True, output=output_data)
        assert result.success is True
        assert result.output == output_data
        assert result.error is None

    def test_tool_result_success_without_output(self):
        """Tests creating a successful ToolResult without explicit output."""
        result = ToolResult(success=True)
        assert result.success is True
        assert result.output == {}
        assert result.error is None

    def test_tool_result_failure_with_error(self):
        """Tests creating a failed ToolResult with an error message."""
        error_message = "Operation failed"
        result = ToolResult(success=False, error=error_message)
        assert result.success is False
        assert result.output == {}
        assert result.error == error_message

    def test_tool_result_failure_without_error(self):
        """Tests creating a failed ToolResult without an explicit error message (should still have error field)."""
        result = ToolResult(success=False)
        assert result.success is False
        assert result.output == {}
        assert result.error is None # It's None by default if not provided

    def test_tool_result_repr(self):
        """Tests the string representation of ToolResult."""
        output_data = {"status": "done"}
        result = ToolResult(success=True, output=output_data, error="Some error")
        expected_repr = "ToolResult(success=True, output={'status': 'done'}, error='Some error')"
        assert repr(result) == expected_repr

        result_minimal = ToolResult(success=False)
        expected_repr_minimal = "ToolResult(success=False, output={}, error=None)"
        assert repr(result_minimal) == expected_repr_minimal