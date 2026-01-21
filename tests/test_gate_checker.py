"""Tests for VERCHAIN Gate Checker Core System"""

import unittest
from unittest.mock import Mock, patch, MagicMock

# Test GateType and GateResult
class TestGateType(unittest.TestCase):
    def test_all_gate_types_exist(self):
        from core.gate_checker import GateType
        expected = ["plan_approval", "pr_created", "review_requested", 
                   "review_passed", "merged", "deployed", "health_check", "custom"]
        for gt in expected:
            self.assertIsNotNone(GateType(gt))

class TestGateResult(unittest.TestCase):
    def test_create_passed_result(self):
        from core.gate_checker import GateResult
        result = GateResult(passed=True, gate_type="pr_created", evidence={"pr": 123})
        self.assertTrue(result.passed)
        self.assertEqual(result.gate_type, "pr_created")
    
    def test_create_failed_result(self):
        from core.gate_checker import GateResult
        result = GateResult(passed=False, gate_type="merged", reason="PR still open")
        self.assertFalse(result.passed)
        self.assertEqual(result.reason, "PR still open")

class TestGateChecker(unittest.TestCase):
    @patch('core.gate_checker.query_db')
    def test_check_plan_approval_not_submitted(self, mock_db):
        from core.gate_checker import GateChecker
        mock_db.return_value = {"rows": [{"implementation_plan": None, "stage": "discovered"}]}
        checker = GateChecker()
        result = checker._check_plan_approval({"id": "test"}, {})
        self.assertFalse(result.passed)
        self.assertIn("No implementation plan", result.reason)
    
    @patch('core.gate_checker.query_db')
    def test_check_plan_approval_approved(self, mock_db):
        from core.gate_checker import GateChecker
        mock_db.return_value = {"rows": [{"implementation_plan": {"steps": []}, 
                                         "stage": "plan_approved",
                                         "plan_approved_at": "2024-01-01"}]}
        checker = GateChecker()
        result = checker._check_plan_approval({"id": "test"}, {})
        self.assertTrue(result.passed)

class TestPRGates(unittest.TestCase):
    def test_get_pr_number_from_evidence(self):
        from core.gate_checker import GateChecker
        checker = GateChecker()
        task = {"gate_evidence": {"pr_number": 123}}
        self.assertEqual(checker._get_pr_number(task), 123)
    
    def test_get_pr_number_from_completion(self):
        from core.gate_checker import GateChecker
        checker = GateChecker()
        task = {"gate_evidence": {}, "completion_evidence": "PR #456"}
        self.assertEqual(checker._get_pr_number(task), 456)

if __name__ == '__main__':
    unittest.main()
