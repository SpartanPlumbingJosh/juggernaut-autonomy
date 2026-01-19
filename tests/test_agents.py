"""
Unit tests for core/agents.py
Tests worker registration, status updates, and heartbeats.
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import Any, Dict, List

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agents import (
    register_worker,
    update_worker_status,
    worker_heartbeat,
    get_worker,
    list_workers,
    find_workers_by_capability,
    _format_value,
)


class TestFormatValue:
    """Tests for _format_value function."""

    def test_format_none(self) -> None:
        """Test None returns NULL."""
        assert _format_value(None) == "NULL"

    def test_format_bool(self) -> None:
        """Test boolean formatting."""
        assert _format_value(True) == "TRUE"
        assert _format_value(False) == "FALSE"

    def test_format_numbers(self) -> None:
        """Test number formatting."""
        assert _format_value(42) == "42"
        assert _format_value(3.14) == "3.14"

    def test_format_string(self) -> None:
        """Test string formatting with escaping."""
        assert _format_value("hello") == "'hello'"
        assert _format_value("it's") == "'it''s'"

    def test_format_list(self) -> None:
        """Test list JSON serialization."""
        result = _format_value(["a", "b"])
        assert result.startswith("'")
        assert "a" in result

    def test_format_dict(self) -> None:
        """Test dict JSON serialization."""
        result = _format_value({"key": "value"})
        assert "key" in result
        assert "value" in result


class TestRegisterWorker:
    """Tests for register_worker function."""

    @patch('core.agents._query')
    def test_register_worker_success(self, mock_query: MagicMock) -> None:
        """Test successful worker registration."""
        mock_query.return_value = {"rows": [{"id": "test-uuid"}]}
        
        result = register_worker(
            worker_id="TEST_WORKER",
            name="Test Worker",
            description="A test worker"
        )
        
        assert result == "test-uuid"
        assert mock_query.called

    @patch('core.agents._query')
    def test_register_worker_with_capabilities(self, mock_query: MagicMock) -> None:
        """Test worker registration with capabilities."""
        mock_query.return_value = {"rows": [{"id": "test-uuid"}]}
        
        result = register_worker(
            worker_id="TEST_WORKER",
            name="Test Worker",
            description="A test worker",
            capabilities=["coding", "analysis"]
        )
        
        assert result == "test-uuid"

    @patch('core.agents._query')
    def test_register_worker_failure(self, mock_query: MagicMock) -> None:
        """Test worker registration failure."""
        mock_query.side_effect = Exception("Database error")
        
        result = register_worker(
            worker_id="TEST_WORKER",
            name="Test Worker",
            description="A test worker"
        )
        
        assert result is None


class TestUpdateWorkerStatus:
    """Tests for update_worker_status function."""

    @patch('core.agents._query')
    def test_update_status_success(self, mock_query: MagicMock) -> None:
        """Test successful status update."""
        mock_query.return_value = {"rowCount": 1}
        
        result = update_worker_status("TEST_WORKER", "active")
        
        assert result is True
        assert mock_query.called

    @patch('core.agents._query')
    def test_update_status_not_found(self, mock_query: MagicMock) -> None:
        """Test status update for non-existent worker."""
        mock_query.return_value = {"rowCount": 0}
        
        result = update_worker_status("NONEXISTENT", "active")
        
        assert result is False


class TestWorkerHeartbeat:
    """Tests for worker_heartbeat function."""

    @patch('core.agents._query')
    def test_heartbeat_success(self, mock_query: MagicMock) -> None:
        """Test successful heartbeat."""
        mock_query.return_value = {"rowCount": 1}
        
        result = worker_heartbeat("TEST_WORKER")
        
        assert result is True

    @patch('core.agents._query')
    def test_heartbeat_failure(self, mock_query: MagicMock) -> None:
        """Test heartbeat failure."""
        mock_query.side_effect = Exception("Database error")
        
        result = worker_heartbeat("TEST_WORKER")
        
        assert result is False


class TestGetWorker:
    """Tests for get_worker function."""

    @patch('core.agents._query')
    def test_get_worker_found(self, mock_query: MagicMock) -> None:
        """Test getting an existing worker."""
        worker_data = {
            "worker_id": "TEST_WORKER",
            "name": "Test Worker",
            "status": "active"
        }
        mock_query.return_value = {"rows": [worker_data]}
        
        result = get_worker("TEST_WORKER")
        
        assert result is not None
        assert result["worker_id"] == "TEST_WORKER"

    @patch('core.agents._query')
    def test_get_worker_not_found(self, mock_query: MagicMock) -> None:
        """Test getting a non-existent worker."""
        mock_query.return_value = {"rows": []}
        
        result = get_worker("NONEXISTENT")
        
        assert result is None


class TestListWorkers:
    """Tests for list_workers function."""

    @patch('core.agents._query')
    def test_list_all_workers(self, mock_query: MagicMock) -> None:
        """Test listing all workers."""
        mock_query.return_value = {
            "rows": [
                {"worker_id": "WORKER1"},
                {"worker_id": "WORKER2"}
            ]
        }
        
        result = list_workers()
        
        assert len(result) == 2

    @patch('core.agents._query')
    def test_list_workers_by_status(self, mock_query: MagicMock) -> None:
        """Test listing workers by status."""
        mock_query.return_value = {"rows": [{"worker_id": "WORKER1"}]}
        
        result = list_workers(status="active")
        
        assert len(result) == 1
        call_args = str(mock_query.call_args)
        assert "status" in call_args.lower()

    @patch('core.agents._query')
    def test_list_workers_exception(self, mock_query: MagicMock) -> None:
        """Test list workers returns empty on exception."""
        mock_query.side_effect = Exception("Database error")
        
        result = list_workers()
        
        assert result == []


class TestFindWorkersByCapability:
    """Tests for find_workers_by_capability function."""

    @patch('core.agents._query')
    def test_find_workers_found(self, mock_query: MagicMock) -> None:
        """Test finding workers with a capability."""
        mock_query.return_value = {
            "rows": [
                {"worker_id": "WORKER1", "capabilities": ["coding"]}
            ]
        }
        
        result = find_workers_by_capability("coding")
        
        assert len(result) == 1

    @patch('core.agents._query')
    def test_find_workers_none_found(self, mock_query: MagicMock) -> None:
        """Test no workers found with capability."""
        mock_query.return_value = {"rows": []}
        
        result = find_workers_by_capability("nonexistent")
        
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
