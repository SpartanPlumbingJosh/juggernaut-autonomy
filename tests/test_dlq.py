"""
Unit tests for the Dead Letter Queue (DLQ) module.

Tests the DLQ functionality for moving failed tasks, retrying, and resolving.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
import uuid

from core.dlq import move_to_dlq, retry_dlq_item, resolve_dlq_item, get_dlq_items


@pytest.fixture
def mock_query_db():
    """Mock for the query_db function."""
    return AsyncMock()


@pytest.fixture
def mock_task_id():
    """Generate a mock task ID."""
    return str(uuid.uuid4())


@pytest.fixture
def mock_dlq_id():
    """Generate a mock DLQ ID."""
    return str(uuid.uuid4())


class TestDLQ:
    """Test suite for the Dead Letter Queue module."""

    async def test_move_to_dlq(self, mock_query_db, mock_task_id):
        """Test moving a task to the DLQ."""
        # Setup mock to return a successful result with a DLQ ID
        dlq_id = str(uuid.uuid4())
        mock_query_db.return_value = {
            "rows": [{"id": dlq_id}]
        }
        
        # Call the function
        with patch('core.dlq.query_db', mock_query_db):
            result = await move_to_dlq(
                task_id=mock_task_id,
                failure_reason="Test failure reason"
            )
        
        # Verify the result
        assert result == dlq_id
        
        # Verify the query was called correctly
        mock_query_db.assert_called_once()
        args = mock_query_db.call_args[0]
        query = args[0]
        params = args[1]
        
        # Check that the query is for inserting into dead_letter_queue
        assert "INSERT INTO dead_letter_queue" in query
        assert params[0] == mock_task_id
        assert params[1] == "Test failure reason"

    async def test_move_to_dlq_with_snapshot(self, mock_query_db, mock_task_id):
        """Test moving a task to the DLQ with task snapshot."""
        # Setup mock to return task data and then DLQ ID
        task_data = {
            "rows": [{
                "id": mock_task_id,
                "task_type": "test",
                "title": "Test Task",
                "description": "Test Description",
                "status": "failed",
                "payload": {"key": "value"}
            }]
        }
        dlq_id = str(uuid.uuid4())
        mock_query_db.side_effect = [
            task_data,  # First call gets task data
            {"rows": [{"id": dlq_id}]}  # Second call returns DLQ ID
        ]
        
        # Call the function
        with patch('core.dlq.query_db', mock_query_db):
            result = await move_to_dlq(
                task_id=mock_task_id,
                failure_reason="Test failure reason",
                include_snapshot=True
            )
        
        # Verify the result
        assert result == dlq_id
        
        # Verify the queries were called correctly
        assert mock_query_db.call_count == 2
        
        # First call should fetch task data
        first_call_args = mock_query_db.call_args_list[0][0]
        assert "SELECT * FROM governance_tasks" in first_call_args[0]
        assert first_call_args[1][0] == mock_task_id
        
        # Second call should insert into DLQ with snapshot
        second_call_args = mock_query_db.call_args_list[1][0]
        assert "INSERT INTO dead_letter_queue" in second_call_args[0]
        assert second_call_args[1][0] == mock_task_id
        assert second_call_args[1][1] == "Test failure reason"
        assert "task_snapshot" in second_call_args[0]

    async def test_retry_dlq_item(self, mock_query_db, mock_dlq_id, mock_task_id):
        """Test retrying a DLQ item."""
        # Setup mock to return DLQ data and then update result
        dlq_data = {
            "rows": [{
                "id": mock_dlq_id,
                "task_id": mock_task_id,
                "status": "pending",
                "failure_reason": "Test failure",
                "task_snapshot": {"id": mock_task_id, "task_type": "test"}
            }]
        }
        update_result = {
            "rowCount": 1
        }
        mock_query_db.side_effect = [
            dlq_data,  # First call gets DLQ data
            update_result,  # Second call updates DLQ status
            {"rowCount": 1}  # Third call updates task status
        ]
        
        # Call the function
        with patch('core.dlq.query_db', mock_query_db):
            result = await retry_dlq_item(
                dlq_id=mock_dlq_id
            )
        
        # Verify the result
        assert result is True
        
        # Verify the queries were called correctly
        assert mock_query_db.call_count == 3
        
        # First call should fetch DLQ data
        first_call_args = mock_query_db.call_args_list[0][0]
        assert "SELECT * FROM dead_letter_queue" in first_call_args[0]
        assert first_call_args[1][0] == mock_dlq_id
        
        # Second call should update DLQ status
        second_call_args = mock_query_db.call_args_list[1][0]
        assert "UPDATE dead_letter_queue" in second_call_args[0]
        assert "retrying" in second_call_args[0]
        assert second_call_args[1][0] == mock_dlq_id
        
        # Third call should update task status
        third_call_args = mock_query_db.call_args_list[2][0]
        assert "UPDATE governance_tasks" in third_call_args[0]
        assert "pending" in third_call_args[0]
        assert third_call_args[1][0] == mock_task_id

    async def test_resolve_dlq_item(self, mock_query_db, mock_dlq_id, mock_task_id):
        """Test resolving a DLQ item."""
        # Setup mock to return DLQ data and then update result
        dlq_data = {
            "rows": [{
                "id": mock_dlq_id,
                "task_id": mock_task_id,
                "status": "pending",
                "failure_reason": "Test failure"
            }]
        }
        update_result = {
            "rowCount": 1
        }
        mock_query_db.side_effect = [
            dlq_data,  # First call gets DLQ data
            update_result,  # Second call updates DLQ status
            {"rowCount": 1}  # Third call updates task status
        ]
        
        # Call the function
        with patch('core.dlq.query_db', mock_query_db):
            result = await resolve_dlq_item(
                dlq_id=mock_dlq_id,
                resolution_notes="Fixed manually"
            )
        
        # Verify the result
        assert result is True
        
        # Verify the queries were called correctly
        assert mock_query_db.call_count == 3
        
        # First call should fetch DLQ data
        first_call_args = mock_query_db.call_args_list[0][0]
        assert "SELECT * FROM dead_letter_queue" in first_call_args[0]
        assert first_call_args[1][0] == mock_dlq_id
        
        # Second call should update DLQ status
        second_call_args = mock_query_db.call_args_list[1][0]
        assert "UPDATE dead_letter_queue" in second_call_args[0]
        assert "resolved" in second_call_args[0]
        assert second_call_args[1][0] == mock_dlq_id
        assert second_call_args[1][1] == "Fixed manually"
        
        # Third call should update task status
        third_call_args = mock_query_db.call_args_list[2][0]
        assert "UPDATE governance_tasks" in third_call_args[0]
        assert "failed" in third_call_args[0]
        assert third_call_args[1][0] == mock_task_id

    async def test_get_dlq_items(self, mock_query_db):
        """Test getting DLQ items."""
        # Setup mock to return DLQ items
        dlq_items = {
            "rows": [
                {
                    "id": str(uuid.uuid4()),
                    "task_id": str(uuid.uuid4()),
                    "status": "pending",
                    "failure_reason": "Test failure 1",
                    "created_at": "2023-01-01T00:00:00Z"
                },
                {
                    "id": str(uuid.uuid4()),
                    "task_id": str(uuid.uuid4()),
                    "status": "pending",
                    "failure_reason": "Test failure 2",
                    "created_at": "2023-01-02T00:00:00Z"
                }
            ]
        }
        mock_query_db.return_value = dlq_items
        
        # Call the function
        with patch('core.dlq.query_db', mock_query_db):
            result = await get_dlq_items(
                status="pending",
                limit=10
            )
        
        # Verify the result
        assert len(result) == 2
        assert result[0]["failure_reason"] == "Test failure 1"
        assert result[1]["failure_reason"] == "Test failure 2"
        
        # Verify the query was called correctly
        mock_query_db.assert_called_once()
        args = mock_query_db.call_args[0]
        query = args[0]
        params = args[1]
        
        # Check that the query filters by status and has a limit
        assert "FROM dead_letter_queue" in query
        assert "WHERE status = $1" in query
        assert "LIMIT $2" in query
        assert params[0] == "pending"
        assert params[1] == 10

    async def test_get_dlq_items_with_task_data(self, mock_query_db):
        """Test getting DLQ items with task data."""
        # Setup mock to return DLQ items with task data
        dlq_items = {
            "rows": [
                {
                    "id": str(uuid.uuid4()),
                    "task_id": str(uuid.uuid4()),
                    "status": "pending",
                    "failure_reason": "Test failure",
                    "created_at": "2023-01-01T00:00:00Z",
                    "task_title": "Test Task",
                    "task_status": "failed",
                    "task_type": "test"
                }
            ]
        }
        mock_query_db.return_value = dlq_items
        
        # Call the function
        with patch('core.dlq.query_db', mock_query_db):
            result = await get_dlq_items(
                include_task_data=True
            )
        
        # Verify the result
        assert len(result) == 1
        assert result[0]["failure_reason"] == "Test failure"
        assert result[0]["task_title"] == "Test Task"
        
        # Verify the query was called correctly
        mock_query_db.assert_called_once()
        args = mock_query_db.call_args[0]
        query = args[0]
        
        # Check that the query joins with governance_tasks
        assert "FROM dead_letter_queue" in query
        assert "JOIN governance_tasks" in query
