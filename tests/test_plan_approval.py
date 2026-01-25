#!/usr/bin/env python3
"""Tests for VERCHAIN-05 Plan Submission and Approval Flow"""

import json
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from core.plan_approval import (
    ExecutionPlan, PlanReview, PlanStatus,
    submit_plan, review_plan, get_plan_status, can_start_work,
    get_tasks_awaiting_plan_review, get_tasks_needing_plan,
    executor_should_submit_plan, executor_should_revise_plan,
    orchestrator_auto_review_plan, quick_submit_plan, approve_plan, reject_plan,
)


class TestExecutionPlan(unittest.TestCase):
    def test_create_from_dict(self):
        data = {"approach": "Test approach with enough detail", "steps": ["Step 1", "Step 2"],
                "files_affected": ["main.py"], "risks": ["Risk 1"], "estimated_duration_minutes": 90,
                "verification_approach": "Run tests and verify coverage"}
        plan = ExecutionPlan.from_dict(data)
        self.assertEqual(plan.approach, data["approach"])
        self.assertEqual(plan.steps, data["steps"])

    def test_validate_valid_plan(self):
        plan = ExecutionPlan(approach="This is a detailed approach", steps=["Step 1: Do something properly"],
                            files_affected=["main.py"], risks=["Risk"], estimated_duration_minutes=60,
                            verification_approach="Verify by running the test suite")
        is_valid, errors = plan.validate()
        self.assertTrue(is_valid)

    def test_validate_missing_approach(self):
        plan = ExecutionPlan(approach="Short", steps=["Step 1: Do something"], files_affected=[],
                            risks=[], estimated_duration_minutes=60,
                            verification_approach="Verify the changes work correctly")
        is_valid, errors = plan.validate()
        self.assertFalse(is_valid)
        self.assertTrue(any("approach" in e.lower() for e in errors))


class TestSubmitPlan(unittest.TestCase):
    @patch('core.plan_approval._execute_sql')
    def test_submit_valid_plan(self, mock_sql):
        mock_sql.side_effect = [
            [{"id": "task-123", "title": "Test", "status": "pending", "stage": "discovered", "assigned_worker": "EX"}],
            [], []
        ]
        plan = {"approach": "Implement using TDD approach with thorough testing",
                "steps": ["Write tests first", "Implement feature", "Refactor"],
                "files_affected": ["main.py"], "risks": ["Breaking tests"],
                "estimated_duration_minutes": 90,
                "verification_approach": "Run full test suite and verify coverage"}
        result = submit_plan("task-123", plan, "EXECUTOR")
        self.assertTrue(result["success"])
        self.assertEqual(result["stage"], "plan_submitted")

    @patch('core.plan_approval._execute_sql')
    def test_submit_invalid_plan(self, mock_sql):
        mock_sql.return_value = [{"id": "task-123", "title": "Test", "status": "pending", "stage": "discovered"}]
        plan = {"approach": "Short", "steps": [], "files_affected": [], "risks": [],
                "estimated_duration_minutes": 60, "verification_approach": "Test"}
        result = submit_plan("task-123", plan)
        self.assertFalse(result["success"])
        self.assertIn("validation_errors", result)

    @patch('core.plan_approval._execute_sql')
    def test_submit_plan_task_not_found(self, mock_sql):
        mock_sql.return_value = []
        plan = {"approach": "Valid approach with sufficient detail",
                "steps": ["Step 1 with enough detail"],
                "files_affected": [], "risks": [], "estimated_duration_minutes": 60,
                "verification_approach": "Verify by checking the results"}
        result = submit_plan("nonexistent", plan)
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])


class TestReviewPlan(unittest.TestCase):
    @patch('core.plan_approval._execute_sql')
    def test_approve_plan(self, mock_sql):
        mock_sql.side_effect = [
            [{"id": "task-123", "title": "Test", "status": "pending", "stage": "plan_submitted",
              "implementation_plan": json.dumps({"approach": "test"})}],
            [], []
        ]
        result = review_plan("task-123", approved=True, feedback="Looks good!")
        self.assertTrue(result["success"])
        self.assertTrue(result["approved"])
        self.assertEqual(result["stage"], "plan_approved")

    @patch('core.plan_approval._execute_sql')
    def test_reject_plan(self, mock_sql):
        mock_sql.side_effect = [
            [{"id": "task-123", "title": "Test", "status": "pending", "stage": "plan_submitted",
              "implementation_plan": json.dumps({"approach": "test"})}],
            [], []
        ]
        result = review_plan("task-123", approved=False, feedback="Needs more detail",
                            required_changes=["Add error handling"])
        self.assertTrue(result["success"])
        self.assertFalse(result["approved"])
        self.assertEqual(result["stage"], "plan_submitted")


class TestCanStartWork(unittest.TestCase):
    @patch('core.plan_approval._execute_sql')
    def test_can_start_approved(self, mock_sql):
        mock_sql.return_value = [{"id": "task-123", "stage": "plan_approved",
                                  "implementation_plan": "{}", "metadata": "{}"}]
        can_start, reason = can_start_work("task-123")
        self.assertTrue(can_start)

    @patch('core.plan_approval._execute_sql')
    def test_cannot_start_no_plan(self, mock_sql):
        mock_sql.return_value = [{"id": "task-123", "stage": "discovered",
                                  "implementation_plan": None, "metadata": "{}"}]
        can_start, reason = can_start_work("task-123")
        self.assertFalse(can_start)


class TestIntegrationHelpers(unittest.TestCase):
    def test_executor_should_submit_plan_true(self):
        task = {"stage": "discovered", "implementation_plan": None}
        self.assertTrue(executor_should_submit_plan(task))

    def test_executor_should_submit_plan_false(self):
        task = {"stage": "plan_submitted", "implementation_plan": "{}"}
        self.assertFalse(executor_should_submit_plan(task))

    def test_executor_should_revise_after_rejection(self):
        task = {"stage": "plan_submitted", "metadata": {
            "plan_rejected_at": "2024-01-02T00:00:00Z",
            "plan_submitted_at": "2024-01-01T00:00:00Z",
            "plan_rejection_feedback": "Needs more detail"
        }}
        should_revise, feedback = executor_should_revise_plan(task)
        self.assertTrue(should_revise)
        self.assertEqual(feedback, "Needs more detail")


class TestOrchestratorAutoReview(unittest.TestCase):
    @patch('core.plan_approval.review_plan')
    def test_auto_approve_good_plan(self, mock_review):
        mock_review.return_value = {"success": True, "approved": True}
        good_plan = {"steps": ["Step 1", "Step 2", "Step 3"], "estimated_duration_minutes": 120,
                     "verification_approach": "Run tests", "risks": ["Potential issues"]}
        result = orchestrator_auto_review_plan("task-123", good_plan)
        mock_review.assert_called_once()
        self.assertTrue(mock_review.call_args[1]["approved"])

    @patch('core.plan_approval.review_plan')
    def test_auto_reject_incomplete_plan(self, mock_review):
        mock_review.return_value = {"success": True, "approved": False}
        bad_plan = {"steps": ["One step"], "estimated_duration_minutes": 60,
                    "verification_approach": "Check", "risks": []}
        result = orchestrator_auto_review_plan("task-123", bad_plan)
        self.assertFalse(mock_review.call_args[1]["approved"])


class TestConvenienceFunctions(unittest.TestCase):
    @patch('core.plan_approval.submit_plan')
    def test_quick_submit_plan(self, mock_submit):
        mock_submit.return_value = {"success": True}
        result = quick_submit_plan("task-123", approach="Quick approach", steps=["Step 1", "Step 2"])
        mock_submit.assert_called_once()

    @patch('core.plan_approval.review_plan')
    def test_approve_plan_wrapper(self, mock_review):
        mock_review.return_value = {"success": True}
        result = approve_plan("task-123", "Looks good")
        mock_review.assert_called_once_with("task-123", approved=True, feedback="Looks good")

    @patch('core.plan_approval.review_plan')
    def test_reject_plan_wrapper(self, mock_review):
        mock_review.return_value = {"success": True}
        result = reject_plan("task-123", "Needs work", ["Add tests"])
        mock_review.assert_called_once_with("task-123", approved=False, feedback="Needs work", required_changes=["Add tests"])


if __name__ == "__main__":
    unittest.main()
