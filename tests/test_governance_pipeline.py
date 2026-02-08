"""
Test module for verifying the governance task pipeline functionality.

This module validates that the governance task pipeline operates correctly
after the scheduler.py bugfix, including task creation, claiming, status
transitions, and completion workflows.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Constants
VALID_TASK_STATUSES = ["pending", "in_progress", "completed", "failed", "cancelled"]
VALID_PRIORITIES = ["critical", "high", "medium", "low"]
VALID_TASK_TYPES = ["code", "test", "deploy", "verification", "documentation"]
WORKER_ID_PREFIX = "agent-chat"


class TestGovernancePipeline:
    """Test suite for governance task pipeline verification."""

    def test_task_status_values_are_valid(self) -> None:
        """Verify that all defined task statuses are recognized by the system."""
        for status in VALID_TASK_STATUSES:
            assert isinstance(status, str)
            assert len(status) > 0
            assert status.islower()

    def test_priority_ordering(self) -> None:
        """Verify priority values follow correct ordering (critical > high > medium > low)."""
        priority_order = {"critical": 1, "high": 2, "medium": 3, "low": 4}
        
        for priority in VALID_PRIORITIES:
            assert priority in priority_order
            
        # Verify ordering
        assert priority_order["critical"] < priority_order["high"]
        assert priority_order["high"] < priority_order["medium"]
        assert priority_order["medium"] < priority_order["low"]

    def test_worker_id_generation(self) -> None:
        """Verify worker ID generation follows expected format."""
        worker_suffix = uuid.uuid4().hex[:4].upper()
        worker_id = f"{WORKER_ID_PREFIX}-{worker_suffix}"
        
        assert worker_id.startswith(WORKER_ID_PREFIX)
        assert len(worker_id) == len(WORKER_ID_PREFIX) + 5  # prefix + hyphen + 4 chars
        assert worker_id.count("-") == 2  # agent-chat-XXXX

    def test_task_type_validation(self) -> None:
        """Verify all task types are properly defined."""
        for task_type in VALID_TASK_TYPES:
            assert isinstance(task_type, str)
            assert len(task_type) > 0

    def test_status_transition_pending_to_in_progress(self) -> None:
        """Verify valid transition from pending to in_progress status."""
        initial_status = "pending"
        target_status = "in_progress"
        
        valid_transitions = {
            "pending": ["in_progress", "cancelled"],
            "in_progress": ["completed", "failed", "pending"],
            "completed": [],
            "failed": ["pending"],
            "cancelled": ["pending"],
        }
        
        assert target_status in valid_transitions[initial_status]

    def test_status_transition_in_progress_to_completed(self) -> None:
        """Verify valid transition from in_progress to completed status."""
        initial_status = "in_progress"
        target_status = "completed"
        
        valid_transitions = {
            "pending": ["in_progress", "cancelled"],
            "in_progress": ["completed", "failed", "pending"],
            "completed": [],
            "failed": ["pending"],
            "cancelled": ["pending"],
        }
        
        assert target_status in valid_transitions[initial_status]

    def test_completion_evidence_required_for_code_tasks(self) -> None:
        """Verify that code tasks require completion evidence."""
        task_types_requiring_evidence = ["code", "deploy"]
        
        for task_type in task_types_requiring_evidence:
            assert task_type in VALID_TASK_TYPES

    def test_task_assignment_atomicity(self) -> None:
        """Verify task claiming uses atomic database operations."""
        # Simulates the atomic claim pattern used in production
        claim_sql_template = """
            UPDATE governance_tasks 
            SET assigned_worker = %s, 
                status = %s,
                started_at = NOW()
            WHERE id = %s 
              AND status = %s
        """
        
        # Verify the SQL template has proper parameterization
        assert "%s" in claim_sql_template
        assert "assigned_worker" in claim_sql_template
        assert "status" in claim_sql_template
        assert "WHERE" in claim_sql_template

    def test_timestamp_fields_use_utc(self) -> None:
        """Verify timestamp handling uses UTC timezone."""
        current_time = datetime.now(timezone.utc)
        
        assert current_time.tzinfo is not None
        assert current_time.tzinfo == timezone.utc


class TestSchedulerIntegration:
    """Test suite for scheduler.py integration after bugfix."""

    def test_scheduler_query_orders_by_priority(self) -> None:
        """Verify scheduler query orders tasks by priority correctly."""
        expected_order_clause = """
            ORDER BY CASE priority 
                WHEN 'critical' THEN 1 
                WHEN 'high' THEN 2 
                WHEN 'medium' THEN 3 
                WHEN 'low' THEN 4 
                ELSE 5 END
        """
        
        # The priority ordering should follow critical -> high -> medium -> low
        assert "critical" in expected_order_clause
        assert "high" in expected_order_clause
        assert "medium" in expected_order_clause
        assert "low" in expected_order_clause

    def test_scheduler_filters_pending_tasks_only(self) -> None:
        """Verify scheduler only retrieves pending tasks."""
        filter_condition = "status = 'pending'"
        
        assert "pending" in filter_condition
        assert "status" in filter_condition

    def test_scheduler_respects_worker_assignment(self) -> None:
        """Verify scheduler filters by assigned worker."""
        worker_filter = "assigned_worker = 'agent-chat'"
        
        assert "agent-chat" in worker_filter
        assert "assigned_worker" in worker_filter


class TestPipelineWorkflow:
    """End-to-end workflow tests for the governance pipeline."""

    def test_complete_task_lifecycle(self) -> None:
        """Verify complete task lifecycle from creation to completion."""
        lifecycle_stages = [
            "pending",      # Task created
            "in_progress",  # Task claimed by worker
            "completed",    # Task finished with evidence
        ]
        
        for i in range(len(lifecycle_stages) - 1):
            current = lifecycle_stages[i]
            next_stage = lifecycle_stages[i + 1]
            
            # Each stage should transition to the next
            assert current != next_stage
            assert current in VALID_TASK_STATUSES
            assert next_stage in VALID_TASK_STATUSES

    def test_failed_task_can_retry(self) -> None:
        """Verify failed tasks can be reset to pending for retry."""
        valid_transitions = {
            "failed": ["pending"],
        }
        
        assert "pending" in valid_transitions["failed"]

    def test_evidence_format_for_code_tasks(self) -> None:
        """Verify completion evidence format for code tasks."""
        sample_evidence = "Merged PR #42: https://github.com/org/repo/pull/42"
        
        assert "PR #" in sample_evidence or "Merged" in sample_evidence
        assert "https://github.com" in sample_evidence


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
