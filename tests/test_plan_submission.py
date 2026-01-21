"""
Tests for Plan Submission and Approval Flow
============================================

Tests the plan submission, validation, review, and enforcement logic.
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from core.plan_submission import (
    validate_plan,
    submit_plan,
    review_plan,
    get_plan,
    can_start_work,
    get_tasks_pending_plan_review,
    get_tasks_needing_plan,
    start_work_on_task,
    generate_plan_template,
    PlanValidationResult,
    PlanSubmissionResult,
    PlanReviewResult,
    REQUIRED_PLAN_FIELDS,
    RECOMMENDED_PLAN_FIELDS,
)


class TestValidatePlan(unittest.TestCase):
    """Tests for plan validation logic."""
    
    def test_valid_plan_minimal(self):
        """Test validation passes with minimal required fields."""
        plan = {
            "approach": "I will implement the feature using TDD",
            "steps": ["Write tests", "Implement code", "Refactor"]
        }
        result = validate_plan(plan)
        
        self.assertTrue(result.valid)
        self.assertEqual(len(result.errors), 0)
        # Should have warnings for missing recommended fields
        self.assertGreater(len(result.warnings), 0)
    
    def test_valid_plan_complete(self):
        """Test validation passes with all fields."""
        plan = {
            "approach": "I will implement the feature using TDD",
            "steps": ["Write tests", "Implement code", "Refactor"],
            "files_affected": ["core/feature.py", "tests/test_feature.py"],
            "risks": ["May break existing API"],
            "estimated_duration_minutes": 120,
            "verification_approach": "Run test suite and manual verification"
        }
        result = validate_plan(plan)
        
        self.assertTrue(result.valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)
    
    def test_invalid_plan_not_dict(self):
        """Test validation fails for non-dict input."""
        result = validate_plan("not a dict")
        
        self.assertFalse(result.valid)
        self.assertIn("Plan must be a dictionary", result.errors)
    
    def test_invalid_plan_missing_approach(self):
        """Test validation fails without approach."""
        plan = {
            "steps": ["Step 1", "Step 2"]
        }
        result = validate_plan(plan)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("approach" in e for e in result.errors))
    
    def test_invalid_plan_missing_steps(self):
        """Test validation fails without steps."""
        plan = {
            "approach": "I will do something"
        }
        result = validate_plan(plan)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("steps" in e for e in result.errors))
    
    def test_invalid_plan_empty_approach(self):
        """Test validation fails with empty approach."""
        plan = {
            "approach": "",
            "steps": ["Step 1"]
        }
        result = validate_plan(plan)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("Approach cannot be empty" in e for e in result.errors))
    
    def test_invalid_plan_empty_steps(self):
        """Test validation fails with empty steps list."""
        plan = {
            "approach": "My approach",
            "steps": []
        }
        result = validate_plan(plan)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("Steps cannot be empty" in e for e in result.errors))
    
    def test_invalid_plan_steps_not_list(self):
        """Test validation fails when steps is not a list."""
        plan = {
            "approach": "My approach",
            "steps": "Step 1, Step 2"
        }
        result = validate_plan(plan)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("Steps must be a list" in e for e in result.errors))
    
    def test_invalid_plan_negative_duration(self):
        """Test validation fails with negative duration."""
        plan = {
            "approach": "My approach",
            "steps": ["Step 1"],
            "estimated_duration_minutes": -30
        }
        result = validate_plan(plan)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("positive number" in e for e in result.errors))
    
    def test_warnings_for_missing_recommended(self):
        """Test warnings are generated for missing recommended fields."""
        plan = {
            "approach": "My approach",
            "steps": ["Step 1"]
        }
        result = validate_plan(plan)
        
        self.assertTrue(result.valid)
        self.assertGreater(len(result.warnings), 0)
        
        # Check each recommended field generates a warning
        for field in RECOMMENDED_PLAN_FIELDS:
            self.assertTrue(
                any(field in w for w in result.warnings),
                f"Expected warning for missing {field}"
            )


class TestSubmitPlan(unittest.TestCase):
    """Tests for plan submission."""
    
    @patch('core.plan_submission.query_db')
    def test_submit_plan_success(self, mock_query):
        """Test successful plan submission."""
        # Mock task lookup - in decomposed stage
        mock_query.side_effect = [
            {"rows": [{"id": "test-id", "stage": "decomposed", "plan": None, "metadata": {}}]},
            {"rowCount": 1},  # Update result
            {"rowCount": 1}   # Transition log
        ]
        
        plan = {
            "approach": "My approach",
            "steps": ["Step 1", "Step 2"]
        }
        
        result = submit_plan("test-id", plan)
        
        self.assertTrue(result.success)
        self.assertEqual(result.task_id, "test-id")
        self.assertEqual(result.stage, "plan_submitted")
        self.assertEqual(result.plan_version, 1)
    
    @patch('core.plan_submission.query_db')
    def test_submit_plan_resubmission(self, mock_query):
        """Test plan resubmission increments version."""
        existing_plan = {"approach": "Old", "steps": ["Old step"], "_version": 1}
        
        mock_query.side_effect = [
            {"rows": [{"id": "test-id", "stage": "plan_submitted", "plan": existing_plan, "metadata": {"plan_feedback": "Please revise"}}]},
            {"rowCount": 1},
            {"rowCount": 1}
        ]
        
        plan = {
            "approach": "New approach",
            "steps": ["Step 1", "Step 2"]
        }
        
        result = submit_plan("test-id", plan)
        
        self.assertTrue(result.success)
        self.assertEqual(result.plan_version, 2)
    
    @patch('core.plan_submission.query_db')
    def test_submit_plan_task_not_found(self, mock_query):
        """Test submission fails for non-existent task."""
        mock_query.return_value = {"rows": []}
        
        plan = {"approach": "My approach", "steps": ["Step 1"]}
        result = submit_plan("nonexistent", plan)
        
        self.assertFalse(result.success)
        self.assertIn("not found", result.error)
    
    def test_submit_plan_invalid_plan(self):
        """Test submission fails with invalid plan."""
        plan = {"steps": ["Step 1"]}  # Missing approach
        
        result = submit_plan("test-id", plan)
        
        self.assertFalse(result.success)
        self.assertIn("Invalid plan", result.error)
    
    @patch('core.plan_submission.query_db')
    def test_submit_plan_wrong_stage(self, mock_query):
        """Test submission fails from wrong stage."""
        mock_query.return_value = {
            "rows": [{"id": "test-id", "stage": "in_progress", "plan": None, "metadata": {}}]
        }
        
        plan = {"approach": "My approach", "steps": ["Step 1"]}
        result = submit_plan("test-id", plan)
        
        self.assertFalse(result.success)
        self.assertIn("Cannot submit plan", result.error)


class TestReviewPlan(unittest.TestCase):
    """Tests for plan review."""
    
    @patch('core.plan_submission.query_db')
    def test_review_plan_approve(self, mock_query):
        """Test plan approval."""
        mock_query.side_effect = [
            {"rows": [{"id": "test-id", "stage": "plan_submitted", "plan": {"approach": "x", "steps": ["y"]}, "metadata": {}}]},
            {"rowCount": 1},
            {"rowCount": 1}
        ]
        
        result = review_plan("test-id", approved=True, feedback="Good plan!")
        
        self.assertTrue(result.success)
        self.assertTrue(result.approved)
        self.assertEqual(result.stage, "plan_approved")
    
    @patch('core.plan_submission.query_db')
    def test_review_plan_reject(self, mock_query):
        """Test plan rejection."""
        mock_query.side_effect = [
            {"rows": [{"id": "test-id", "stage": "plan_submitted", "plan": {"approach": "x", "steps": ["y"]}, "metadata": {}}]},
            {"rowCount": 1},
            {"rowCount": 1}
        ]
        
        result = review_plan("test-id", approved=False, feedback="Please add more detail")
        
        self.assertTrue(result.success)
        self.assertFalse(result.approved)
        self.assertEqual(result.stage, "plan_submitted")  # Stays in same stage
        self.assertEqual(result.feedback, "Please add more detail")
    
    @patch('core.plan_submission.query_db')
    def test_review_plan_reject_requires_feedback(self, mock_query):
        """Test rejection requires feedback."""
        mock_query.return_value = {
            "rows": [{"id": "test-id", "stage": "plan_submitted", "plan": {"approach": "x", "steps": ["y"]}, "metadata": {}}]
        }
        
        result = review_plan("test-id", approved=False)
        
        self.assertFalse(result.success)
        self.assertIn("Feedback is required", result.error)
    
    @patch('core.plan_submission.query_db')
    def test_review_plan_wrong_stage(self, mock_query):
        """Test review fails from wrong stage."""
        mock_query.return_value = {
            "rows": [{"id": "test-id", "stage": "in_progress", "plan": {"approach": "x", "steps": ["y"]}, "metadata": {}}]
        }
        
        result = review_plan("test-id", approved=True)
        
        self.assertFalse(result.success)
        self.assertIn("must be in 'plan_submitted' stage", result.error)
    
    @patch('core.plan_submission.query_db')
    def test_review_plan_no_plan(self, mock_query):
        """Test review fails when no plan submitted."""
        mock_query.return_value = {
            "rows": [{"id": "test-id", "stage": "plan_submitted", "plan": None, "metadata": {}}]
        }
        
        result = review_plan("test-id", approved=True)
        
        self.assertFalse(result.success)
        self.assertIn("No plan submitted", result.error)


class TestCanStartWork(unittest.TestCase):
    """Tests for work start authorization."""
    
    @patch('core.plan_submission.query_db')
    def test_can_start_with_approved_plan(self, mock_query):
        """Test work can start with approved plan."""
        mock_query.return_value = {
            "rows": [{
                "stage": "plan_approved",
                "plan": {"approach": "x", "steps": ["y"]},
                "metadata": {"plan_approved": True}
            }]
        }
        
        can_start, reason = can_start_work("test-id")
        
        self.assertTrue(can_start)
        self.assertIn("approved", reason.lower())
    
    @patch('core.plan_submission.query_db')
    def test_cannot_start_without_plan(self, mock_query):
        """Test work cannot start without plan."""
        mock_query.return_value = {
            "rows": [{"stage": "decomposed", "plan": None, "metadata": {}}]
        }
        
        can_start, reason = can_start_work("test-id")
        
        self.assertFalse(can_start)
        self.assertIn("No plan submitted", reason)
    
    @patch('core.plan_submission.query_db')
    def test_cannot_start_unapproved_plan(self, mock_query):
        """Test work cannot start with unapproved plan."""
        mock_query.return_value = {
            "rows": [{
                "stage": "plan_submitted",
                "plan": {"approach": "x", "steps": ["y"]},
                "metadata": {"plan_approved": False}
            }]
        }
        
        can_start, reason = can_start_work("test-id")
        
        self.assertFalse(can_start)
        self.assertIn("not approved", reason.lower())
    
    @patch('core.plan_submission.query_db')
    def test_task_not_found(self, mock_query):
        """Test check fails for non-existent task."""
        mock_query.return_value = {"rows": []}
        
        can_start, reason = can_start_work("nonexistent")
        
        self.assertFalse(can_start)
        self.assertIn("not found", reason)


class TestStartWork(unittest.TestCase):
    """Tests for starting work on a task."""
    
    @patch('core.plan_submission.query_db')
    @patch('core.plan_submission.can_start_work')
    @patch('core.plan_submission.get_task_stage')
    def test_start_work_success(self, mock_stage, mock_can_start, mock_query):
        """Test successfully starting work."""
        mock_can_start.return_value = (True, "Plan approved")
        mock_stage.return_value = "plan_approved"
        mock_query.side_effect = [
            {"rowCount": 1},
            {"rowCount": 1}
        ]
        
        success, message = start_work_on_task("test-id", "EXECUTOR-1")
        
        self.assertTrue(success)
        self.assertIn("successfully", message.lower())
    
    @patch('core.plan_submission.can_start_work')
    def test_start_work_no_plan(self, mock_can_start):
        """Test cannot start without approved plan."""
        mock_can_start.return_value = (False, "No plan submitted")
        
        success, message = start_work_on_task("test-id", "EXECUTOR-1")
        
        self.assertFalse(success)
        self.assertIn("No plan submitted", message)
    
    @patch('core.plan_submission.can_start_work')
    @patch('core.plan_submission.get_task_stage')
    def test_start_work_already_in_progress(self, mock_stage, mock_can_start):
        """Test starting work on already in-progress task."""
        mock_can_start.return_value = (True, "Plan approved")
        mock_stage.return_value = "in_progress"
        
        success, message = start_work_on_task("test-id", "EXECUTOR-1")
        
        self.assertTrue(success)
        self.assertIn("already in progress", message.lower())


class TestGetPlan(unittest.TestCase):
    """Tests for plan retrieval."""
    
    @patch('core.plan_submission.query_db')
    def test_get_plan_exists(self, mock_query):
        """Test getting existing plan."""
        plan = {"approach": "My approach", "steps": ["Step 1"]}
        mock_query.return_value = {"rows": [{"plan": plan}]}
        
        result = get_plan("test-id")
        
        self.assertEqual(result, plan)
    
    @patch('core.plan_submission.query_db')
    def test_get_plan_not_found(self, mock_query):
        """Test getting plan for non-existent task."""
        mock_query.return_value = {"rows": []}
        
        result = get_plan("nonexistent")
        
        self.assertIsNone(result)
    
    @patch('core.plan_submission.query_db')
    def test_get_plan_json_string(self, mock_query):
        """Test getting plan stored as JSON string."""
        plan_str = '{"approach": "My approach", "steps": ["Step 1"]}'
        mock_query.return_value = {"rows": [{"plan": plan_str}]}
        
        result = get_plan("test-id")
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result["approach"], "My approach")


class TestGeneratePlanTemplate(unittest.TestCase):
    """Tests for plan template generation."""
    
    def test_template_has_required_fields(self):
        """Test template includes all required fields."""
        template = generate_plan_template("Test Task", "A test task")
        
        for field in REQUIRED_PLAN_FIELDS:
            self.assertIn(field, template)
    
    def test_template_has_recommended_fields(self):
        """Test template includes all recommended fields."""
        template = generate_plan_template("Test Task", "A test task")
        
        for field in RECOMMENDED_PLAN_FIELDS:
            self.assertIn(field, template)
    
    def test_template_is_valid_structure(self):
        """Test template passes validation."""
        template = generate_plan_template("Test Task", "A test task")
        
        # Template is valid structure but has placeholder content
        self.assertIsInstance(template["approach"], str)
        self.assertIsInstance(template["steps"], list)
        self.assertGreater(len(template["steps"]), 0)


class TestGetTasksForReview(unittest.TestCase):
    """Tests for getting tasks pending review."""
    
    @patch('core.plan_submission.query_db')
    def test_get_tasks_pending_review(self, mock_query):
        """Test getting tasks in plan_submitted stage."""
        mock_query.return_value = {
            "rows": [
                {"id": "task-1", "title": "Task 1", "plan": '{"approach": "x"}'},
                {"id": "task-2", "title": "Task 2", "plan": '{"approach": "y"}'}
            ]
        }
        
        tasks = get_tasks_pending_plan_review()
        
        self.assertEqual(len(tasks), 2)
        # Should parse JSON strings
        self.assertIsInstance(tasks[0]["plan"], dict)


class TestGetTasksNeedingPlan(unittest.TestCase):
    """Tests for getting tasks that need plans."""
    
    @patch('core.plan_submission.query_db')
    def test_get_tasks_needing_plan(self, mock_query):
        """Test getting tasks in decomposed stage without plans."""
        mock_query.return_value = {
            "rows": [
                {"id": "task-1", "title": "Task 1", "assigned_to": "EXECUTOR-1"},
                {"id": "task-2", "title": "Task 2", "assigned_to": "EXECUTOR-2"}
            ]
        }
        
        tasks = get_tasks_needing_plan()
        
        self.assertEqual(len(tasks), 2)


if __name__ == "__main__":
    unittest.main()
