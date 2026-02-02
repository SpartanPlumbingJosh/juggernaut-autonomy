"""
Tests for multi-step reasoning capabilities in the Brain.

Tests the ReasoningState class and related functionality for enabling
complex multi-step reasoning chains in the Brain.
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import re

from core.unified_brain import ReasoningState, BrainService


class TestReasoningState(unittest.TestCase):
    """Test the ReasoningState class for tracking multi-step reasoning."""

    def test_initialization(self):
        """Test basic initialization of ReasoningState."""
        state = ReasoningState(original_question="Why is my app crashing?")
        self.assertEqual(state.stage, "initial")
        self.assertEqual(state.original_question, "Why is my app crashing?")
        self.assertFalse(state.is_multi_step)
        self.assertEqual(state.current_step, 0)
        self.assertEqual(len(state.findings), 0)
        self.assertEqual(len(state.completed_steps), 0)

    def test_step_progression(self):
        """Test step progression in reasoning state."""
        state = ReasoningState()
        state.plan = ["step1", "step2", "step3"]
        
        # Test get_next_step
        self.assertEqual(state.get_next_step(), "step1")
        
        # Test complete_current_step
        state.complete_current_step()
        self.assertEqual(state.current_step, 1)
        self.assertIn(0, state.completed_steps)
        self.assertEqual(state.get_next_step(), "step2")
        
        # Test is_complete
        self.assertFalse(state.is_complete())
        state.complete_current_step()
        state.complete_current_step()
        self.assertTrue(state.is_complete())

    def test_to_dict(self):
        """Test serialization of reasoning state."""
        state = ReasoningState(
            stage="diagnosing",
            original_question="What's wrong with the database?",
            is_multi_step=True
        )
        state.plan = ["identify_problem", "gather_data", "analyze"]
        state.findings = {"sql_0": {"result": "connection error"}}
        state.complete_current_step()
        
        result = state.to_dict()
        self.assertEqual(result["stage"], "diagnosing")
        self.assertEqual(result["current_step"], 1)
        self.assertEqual(len(result["completed_steps"]), 1)
        self.assertTrue(result["is_multi_step"])
        self.assertEqual(result["findings"]["sql_0"]["result"], "connection error")


class TestMultiStepReasoning(unittest.TestCase):
    """Test multi-step reasoning capabilities in BrainService."""

    def setUp(self):
        """Set up test environment."""
        self.brain = BrainService(api_key="test_key", model="test_model")

    def test_determine_max_iterations(self):
        """Test dynamic iteration limit determination."""
        # Simple question
        simple = self.brain._determine_max_iterations("What time is it?")
        self.assertEqual(simple, 10)  # Base iterations
        
        # Complex diagnostic question
        diagnostic = self.brain._determine_max_iterations(
            "Diagnose why my database connection is failing"
        )
        self.assertEqual(diagnostic, 30)  # 3x base for complex reasoning
        
        # Tool chain question
        tool_chain = self.brain._determine_max_iterations(
            "Find all failed tasks and then analyze the error patterns"
        )
        self.assertEqual(tool_chain, 30)  # 3x base for complex reasoning (matches both multi-step and tool chain patterns)
        
        # Context-based complexity
        context = self.brain._determine_max_iterations(
            "Check the system", {"complex_task": True}
        )
        self.assertEqual(context, 20)  # 2x base for complex context

    @patch("core.unified_brain.BrainService._update_reasoning_state")
    def test_reasoning_state_updates(self, mock_update):
        """Test reasoning state updates during tool execution."""
        # Create a mock reasoning state
        state = ReasoningState(is_multi_step=True, stage="diagnosing")
        state.plan = ["identify_problem", "gather_data", "analyze"]
        
        # Mock tool execution
        tool_name = "sql_query"
        arguments = {"sql": "SELECT * FROM errors"}
        result = {"rows": [{"error": "connection timeout"}]}
        success = True
        
        # Call the update method
        self.brain._update_reasoning_state(state, tool_name, arguments, result, success)
        
        # Verify the mock was called with correct arguments
        mock_update.assert_called_once_with(state, tool_name, arguments, result, success)


if __name__ == "__main__":
    unittest.main()
