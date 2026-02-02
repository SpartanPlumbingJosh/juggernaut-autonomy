"""
Tests for the opportunity scan handler.

Tests the config coercion, error logging, and no-sources behavior.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from core.opportunity_scan_handler import (
    _coerce_config,
    _safe_bool,
    _safe_float,
    _safe_int,
    handle_opportunity_scan
)


class TestOpportunityScanHandler(unittest.TestCase):
    """Test opportunity scan handler functions."""

    def test_coerce_config_with_dict(self):
        """Test config coercion with dictionary input."""
        log_action = MagicMock()
        config = {"min_confidence_score": 0.8, "create_tasks": True}
        
        result = _coerce_config(config, log_action)
        
        self.assertEqual(result, config)
        log_action.assert_not_called()
    
    def test_coerce_config_with_json_string(self):
        """Test config coercion with JSON string input."""
        log_action = MagicMock()
        config_dict = {"min_confidence_score": 0.8, "create_tasks": True}
        config_str = json.dumps(config_dict)
        
        result = _coerce_config(config_str, log_action)
        
        self.assertEqual(result, config_dict)
        log_action.assert_not_called()
    
    def test_coerce_config_with_invalid_json(self):
        """Test config coercion with invalid JSON string."""
        log_action = MagicMock()
        invalid_json = "{invalid:json}"
        
        result = _coerce_config(invalid_json, log_action)
        
        self.assertEqual(result, {})
        log_action.assert_called_once()
        self.assertEqual(log_action.call_args[0][0], "opportunity_scan.config_parse_error")
    
    def test_coerce_config_with_non_dict(self):
        """Test config coercion with non-dictionary input."""
        log_action = MagicMock()
        non_dict = ["list", "not", "dict"]
        
        result = _coerce_config(non_dict, log_action)
        
        self.assertEqual(result, {})
        log_action.assert_called_once()
        self.assertEqual(log_action.call_args[0][0], "opportunity_scan.invalid_config")
    
    def test_safe_float_conversion(self):
        """Test safe float conversion."""
        self.assertEqual(_safe_float("3.14"), 3.14)
        self.assertEqual(_safe_float(3.14), 3.14)
        self.assertEqual(_safe_float(None), 0.0)
        self.assertEqual(_safe_float(None, 1.0), 1.0)
        self.assertEqual(_safe_float("invalid"), 0.0)
        self.assertEqual(_safe_float("invalid", 1.0), 1.0)
    
    def test_safe_int_conversion(self):
        """Test safe int conversion."""
        self.assertEqual(_safe_int("42"), 42)
        self.assertEqual(_safe_int(42), 42)
        self.assertEqual(_safe_int(None), 0)
        self.assertEqual(_safe_int(None, 1), 1)
        self.assertEqual(_safe_int("invalid"), 0)
        self.assertEqual(_safe_int("invalid", 1), 1)
    
    def test_safe_bool_conversion(self):
        """Test safe boolean conversion."""
        self.assertTrue(_safe_bool(True))
        self.assertTrue(_safe_bool("true"))
        self.assertTrue(_safe_bool("True"))
        self.assertTrue(_safe_bool("yes"))
        self.assertTrue(_safe_bool("1"))
        self.assertTrue(_safe_bool(1))
        
        self.assertFalse(_safe_bool(False))
        self.assertFalse(_safe_bool("false"))
        self.assertFalse(_safe_bool("no"))
        self.assertFalse(_safe_bool("0"))
        self.assertFalse(_safe_bool(0))
        self.assertFalse(_safe_bool(None))
        
        self.assertTrue(_safe_bool(None, True))
    
    @patch("core.opportunity_scan_handler._create_diverse_tasks")
    def test_handle_no_sources(self, mock_create_diverse):
        """Test handling when no sources are available."""
        # Setup
        mock_execute_sql = MagicMock()
        mock_log_action = MagicMock()
        mock_execute_sql.return_value = {"rows": []}
        mock_create_diverse.return_value = {
            "tasks_created": 2,
            "tasks_skipped_duplicate": 1,
            "tasks_skipped_quality": 0
        }
        
        task = {"config": {"fallback_to_diverse_tasks": True}}
        
        # Execute
        result = handle_opportunity_scan(task, mock_execute_sql, mock_log_action)
        
        # Verify
        self.assertTrue(result["success"])
        self.assertTrue(result["no_sources"])
        self.assertEqual(result["tasks_created"], 2)
        self.assertEqual(result["tasks_skipped_duplicate"], 1)
        
        # Verify logging
        self.assertEqual(mock_log_action.call_count, 2)
        mock_log_action.assert_any_call(
            "opportunity_scan.no_sources",
            "No active opportunity sources found. Falling back to diversified task generation.",
            "warning"
        )
    
    @patch("core.opportunity_scan_handler._create_diverse_tasks")
    def test_handle_no_sources_fallback_disabled(self, mock_create_diverse):
        """Test handling when no sources are available and fallback is disabled."""
        # Setup
        mock_execute_sql = MagicMock()
        mock_log_action = MagicMock()
        mock_execute_sql.return_value = {"rows": []}
        
        task = {"config": {"fallback_to_diverse_tasks": False}}
        
        # Execute
        result = handle_opportunity_scan(task, mock_execute_sql, mock_log_action)
        
        # Verify
        self.assertTrue(result["success"])
        self.assertTrue(result["no_sources"])
        self.assertEqual(result["tasks_created"], 0)
        
        # Verify logging
        self.assertEqual(mock_log_action.call_count, 2)
        mock_log_action.assert_any_call(
            "opportunity_scan.fallback_disabled",
            "Fallback to diverse tasks is disabled in config",
            "info"
        )
        
        # Verify diverse tasks not called
        mock_create_diverse.assert_not_called()


if __name__ == "__main__":
    unittest.main()
