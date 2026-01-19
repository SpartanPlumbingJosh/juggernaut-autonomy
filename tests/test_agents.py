"""
Unit tests for core/agents.py

Tests agent registration, status updates, and worker management.
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
from typing import Any, Dict, List

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.agents import (
    register_worker,
    update_worker_status,
    worker_heartbeat,
    get_worker,
    list_workers,
    find_workers_by_capability,
    _format_value,
)


# ================================================================
# TEST CONSTANTS
# ================================================================

TEST_WORKER_ID = "test-worker-001"
TEST_WORKER_NAME = "Test Worker"
TEST_WORKER_DESC = "A test worker for unit tests"


# ================================================================
# TESTS: _format_value FUNCTION
# ================================================================


class TestFormatValue:
    """Tests for _format_value helper function."""

    def test_format_none_returns_null(self) -> None:
        """None values should return NULL."""
        result = _format_value(None)
        assert result == "NULL"

    def test_format_bool_true(self) -> None:
        """Boolean True should return TRUE."""
        result = _format_value(True)
        assert result == "TRUE"

    def test_format_bool_false(self) -> None:
        """Boolean False should return FALSE."""
        result = _format_value(False)
        assert result == "FALSE"

    def test_format_integer(self) -> None:
        """Integers should be converted to strings."""
        result = _format_value(42)
        assert result == "42"

    def test_format_float(self) -> None:
        """Floats should be converted to strings."""
        result = _format_value(3.14)
        assert result == "3.14"

    def test_format_string(self) -> None:
        """Strings should be single-quoted."""
        result = _format_value("hello")
        assert result == "'hello'"

    def test_format_string_with_quotes(self) -> None:
        """Strings with quotes should escape them."""
        result = _format_value("it's")
        assert result == "'it''s'"

    def test_format_dict(self) -> None:
        """Dictionaries should be JSON-encoded."""
        result = _format_value({"key": "value"})
        assert result.startswith("'")
        assert result.endswith("'")
        assert "key" in result

    def test_format_list(self) -> None:
        """Lists should be JSON-encoded."""
        result = _format_value(["a", "b"])
        assert result.startswith("'")
        assert result.endswith("'")


# ================================================================
# TESTS: register_worker FUNCTION
# ================================================================


class TestRegisterWorker:
    """Tests for register_worker function."""

    @patch("core.agents._query")
    def test_register_worker_success(self, mock_query: Mock) -> None:
        """register_worker should return worker UUID on success."""
        mock_query.return_value = {
            "rows": [{"id": "uuid-123-456"}],
            "rowCount": 1
        }

        result = register_worker(
            worker_id=TEST_WORKER_ID,
            name=TEST_WORKER_NAME,
            description=TEST_WORKER_DESC
        )

        assert result == "uuid-123-456"
        mock_query.assert_called_once()

    @patch("core.agents._query")
    def test_register_worker_with_capabilities(self, mock_query: Mock) -> None:
        """register_worker should accept capabilities list."""
        mock_query.return_value = {
            "rows": [{"id": "uuid-789"}],
            "rowCount": 1
        }

        result = register_worker(
            worker_id=TEST_WORKER_ID,
            name=TEST_WORKER_NAME,
            description=TEST_WORKER_DESC,
            capabilities=["read", "write", "execute"]
        )

        assert result == "uuid-789"
        # Verify SQL contains capabilities
        call_args = mock_query.call_args[0][0]
        assert "capabilities" in call_args.lower()

    @patch("core.agents._query")
    def test_register_worker_returns_none_on_error(self, mock_query: Mock) -> None:
        """register_worker should return None on database error."""
        mock_query.side_effect = Exception("Database error")

        result = register_worker(
            worker_id=TEST_WORKER_ID,
            name=TEST_WORKER_NAME,
            description=TEST_WORKER_DESC
        )

        assert result is None

    @patch("core.agents._query")
    def test_register_worker_returns_none_on_empty_result(self, mock_query: Mock) -> None:
        """register_worker should return None when no rows returned."""
        mock_query.return_value = {"rows": [], "rowCount": 0}

        result = register_worker(
            worker_id=TEST_WORKER_ID,
            name=TEST_WORKER_NAME,
            description=TEST_WORKER_DESC
        )

        assert result is None


# ================================================================
# TESTS: update_worker_status FUNCTION
# ================================================================


class TestUpdateWorkerStatus:
    """Tests for update_worker_status function."""

    @patch("core.agents._query")
    def test_update_status_success(self, mock_query: Mock) -> None:
        """update_worker_status should return True on success."""
        mock_query.return_value = {"rowCount": 1}

        result = update_worker_status(TEST_WORKER_ID, "active")

        assert result is True
        mock_query.assert_called_once()

    @patch("core.agents._query")
    def test_update_status_no_match(self, mock_query: Mock) -> None:
        """update_worker_status should return False when no rows updated."""
        mock_query.return_value = {"rowCount": 0}

        result = update_worker_status("nonexistent-worker", "active")

        assert result is False

    @patch("core.agents._query")
    def test_update_status_error(self, mock_query: Mock) -> None:
        """update_worker_status should return False on error."""
        mock_query.side_effect = Exception("Database error")

        result = update_worker_status(TEST_WORKER_ID, "active")

        assert result is False


# ================================================================
# TESTS: worker_heartbeat FUNCTION
# ================================================================


class TestWorkerHeartbeat:
    """Tests for worker_heartbeat function."""

    @patch("core.agents._query")
    def test_heartbeat_success(self, mock_query: Mock) -> None:
        """worker_heartbeat should return True on success."""
        mock_query.return_value = {"rowCount": 1}

        result = worker_heartbeat(TEST_WORKER_ID)

        assert result is True
        mock_query.assert_called_once()

    @patch("core.agents._query")
    def test_heartbeat_no_match(self, mock_query: Mock) -> None:
        """worker_heartbeat should return False when worker not found."""
        mock_query.return_value = {"rowCount": 0}

        result = worker_heartbeat("nonexistent-worker")

        assert result is False

    @patch("core.agents._query")
    def test_heartbeat_error(self, mock_query: Mock) -> None:
        """worker_heartbeat should return False on error."""
        mock_query.side_effect = Exception("Database error")

        result = worker_heartbeat(TEST_WORKER_ID)

        assert result is False


# ================================================================
# TESTS: get_worker FUNCTION
# ================================================================


class TestGetWorker:
    """Tests for get_worker function."""

    @patch("core.agents._query")
    def test_get_worker_found(self, mock_query: Mock) -> None:
        """get_worker should return worker dict when found."""
        worker_data = {
            "worker_id": TEST_WORKER_ID,
            "name": TEST_WORKER_NAME,
            "status": "active"
        }
        mock_query.return_value = {"rows": [worker_data]}

        result = get_worker(TEST_WORKER_ID)

        assert result == worker_data

    @patch("core.agents._query")
    def test_get_worker_not_found(self, mock_query: Mock) -> None:
        """get_worker should return None when not found."""
        mock_query.return_value = {"rows": []}

        result = get_worker("nonexistent-worker")

        assert result is None

    @patch("core.agents._query")
    def test_get_worker_error(self, mock_query: Mock) -> None:
        """get_worker should return None on error."""
        mock_query.side_effect = Exception("Database error")

        result = get_worker(TEST_WORKER_ID)

        assert result is None


# ================================================================
# TESTS: list_workers FUNCTION
# ================================================================


class TestListWorkers:
    """Tests for list_workers function."""

    @patch("core.agents._query")
    def test_list_workers_all(self, mock_query: Mock) -> None:
        """list_workers should return all workers."""
        workers = [
            {"worker_id": "w1", "name": "Worker 1"},
            {"worker_id": "w2", "name": "Worker 2"}
        ]
        mock_query.return_value = {"rows": workers}

        result = list_workers()

        assert result == workers

    @patch("core.agents._query")
    def test_list_workers_by_status(self, mock_query: Mock) -> None:
        """list_workers should filter by status."""
        workers = [{"worker_id": "w1", "status": "active"}]
        mock_query.return_value = {"rows": workers}

        result = list_workers(status="active")

        assert result == workers
        call_args = mock_query.call_args[0][0]
        assert "active" in call_args

    @patch("core.agents._query")
    def test_list_workers_by_type(self, mock_query: Mock) -> None:
        """list_workers should filter by worker_type."""
        workers = [{"worker_id": "w1", "worker_type": "agent"}]
        mock_query.return_value = {"rows": workers}

        result = list_workers(worker_type="agent")

        assert result == workers
        call_args = mock_query.call_args[0][0]
        assert "agent" in call_args

    @patch("core.agents._query")
    def test_list_workers_empty(self, mock_query: Mock) -> None:
        """list_workers should return empty list when none found."""
        mock_query.return_value = {"rows": []}

        result = list_workers()

        assert result == []

    @patch("core.agents._query")
    def test_list_workers_error(self, mock_query: Mock) -> None:
        """list_workers should return empty list on error."""
        mock_query.side_effect = Exception("Database error")

        result = list_workers()

        assert result == []


# ================================================================
# TESTS: find_workers_by_capability FUNCTION
# ================================================================


class TestFindWorkersByCapability:
    """Tests for find_workers_by_capability function."""

    @patch("core.agents._query")
    def test_find_workers_success(self, mock_query: Mock) -> None:
        """find_workers_by_capability should return matching workers."""
        workers = [
            {"worker_id": "w1", "capabilities": ["read", "write"]},
        ]
        mock_query.return_value = {"rows": workers}

        result = find_workers_by_capability("read")

        assert result == workers

    @patch("core.agents._query")
    def test_find_workers_none_found(self, mock_query: Mock) -> None:
        """find_workers_by_capability should return empty when none match."""
        mock_query.return_value = {"rows": []}

        result = find_workers_by_capability("nonexistent-capability")

        assert result == []

    @patch("core.agents._query")
    def test_find_workers_error(self, mock_query: Mock) -> None:
        """find_workers_by_capability should return empty list on error."""
        mock_query.side_effect = Exception("Database error")

        result = find_workers_by_capability("read")

        assert result == []
