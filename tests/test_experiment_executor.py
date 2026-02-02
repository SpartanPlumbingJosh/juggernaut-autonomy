"""
Tests for the experiment_executor module.

Tests the experiment classification and task priority normalization functions.
"""

import unittest
from core.experiment_executor import _normalize_task_priority, classify_experiment


class TestExperimentExecutor(unittest.TestCase):
    """Test experiment executor functions."""

    def test_normalize_task_priority(self):
        """Test priority normalization with various inputs."""
        # Test valid enum values
        self.assertEqual(_normalize_task_priority("critical"), "critical")
        self.assertEqual(_normalize_task_priority("high"), "high")
        self.assertEqual(_normalize_task_priority("normal"), "normal")
        self.assertEqual(_normalize_task_priority("low"), "low")
        self.assertEqual(_normalize_task_priority("deferred"), "deferred")
        
        # Test legacy values
        self.assertEqual(_normalize_task_priority("medium"), "normal")
        self.assertEqual(_normalize_task_priority(1), "high")
        self.assertEqual(_normalize_task_priority(2), "normal")
        self.assertEqual(_normalize_task_priority(3), "normal")
        self.assertEqual(_normalize_task_priority(4), "low")
        self.assertEqual(_normalize_task_priority(5), "deferred")
        
        # Test edge cases
        self.assertEqual(_normalize_task_priority(None), "normal")
        self.assertEqual(_normalize_task_priority("invalid"), "normal")
        self.assertEqual(_normalize_task_priority(0), "high")
        self.assertEqual(_normalize_task_priority(10), "deferred")

    def test_classify_experiment(self):
        """Test experiment classification with various inputs."""
        # Test with explicit experiment_type
        self.assertEqual(
            classify_experiment({"experiment_type": "revenue"}),
            "revenue"
        )
        self.assertEqual(
            classify_experiment({"experiment_type": "cost_reduction"}),
            "cost_reduction"
        )
        
        # Test with name patterns
        self.assertEqual(
            classify_experiment({"name": "Review Response Service Test"}),
            "review_response_service"
        )
        self.assertEqual(
            classify_experiment({"name": "Domain Flip Test 001"}),
            "domain_flip"
        )
        self.assertEqual(
            classify_experiment({"name": "REVENUE-EXP-01: Domain Flip Pilot"}),
            "domain_flip"
        )
        self.assertEqual(
            classify_experiment({"name": "FIX-08: Rollback Capability Test"}),
            "rollback_test"
        )
        self.assertEqual(
            classify_experiment({"name": "Wire-up Test Experiment"}),
            "test"
        )
        
        # Test with description
        self.assertEqual(
            classify_experiment({"description": "Testing domain flip strategy"}),
            "domain_flip"
        )
        
        # Test default
        self.assertEqual(
            classify_experiment({"name": "Unknown Experiment"}),
            "revenue"
        )


if __name__ == "__main__":
    unittest.main()
