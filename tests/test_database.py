"""
Unit tests for core/database.py

Tests database operations including SQL escaping,
query execution, and logging functions.
"""

import json
import pytest
from unittest.mock import patch, Mock, MagicMock
from typing import Any, Dict

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.database import (
    Database,
    escape_sql_value,
    query_db,
    log_execution,
)


# ================================================================
# TEST CONSTANTS
# ================================================================

TEST_CONNECTION_STRING = "postgresql://test:test@localhost/testdb"


# ================================================================
# TESTS: escape_sql_value FUNCTION
# ================================================================


class TestEscapeSqlValue:
    """Tests for escape_sql_value function."""

    def test_escape_none_returns_null(self) -> None:
        """None values should return NULL."""
        result = escape_sql_value(None)
        assert result == "NULL"

    def test_escape_bool_true_returns_true(self) -> None:
        """Boolean True should return TRUE."""
        result = escape_sql_value(True)
        assert result == "TRUE"

    def test_escape_bool_false_returns_false(self) -> None:
        """Boolean False should return FALSE."""
        result = escape_sql_value(False)
        assert result == "FALSE"

    def test_escape_integer_returns_string(self) -> None:
        """Integers should return their string representation."""
        result = escape_sql_value(42)
        assert result == "42"

    def test_escape_float_returns_string(self) -> None:
        """Floats should return their string representation."""
        result = escape_sql_value(3.14)
        assert result == "3.14"

    def test_escape_string_quotes_properly(self) -> None:
        """Strings should be single-quoted."""
        result = escape_sql_value("hello")
        assert result == "'hello'"

    def test_escape_string_with_quotes_escapes(self) -> None:
        """Strings with single quotes should have them escaped."""
        result = escape_sql_value("O'Brien")
        assert result == "'O''Brien'"

    def test_escape_dict_returns_json(self) -> None:
        """Dictionaries should be converted to JSON strings."""
        test_dict = {"key": "value", "num": 42}
        result = escape_sql_value(test_dict)
        assert result.startswith("'")
        assert result.endswith("'")
        inner_json = result[1:-1]
        parsed = json.loads(inner_json)
        assert parsed == test_dict

    def test_escape_list_returns_json(self) -> None:
        """Lists should be converted to JSON arrays."""
        test_list = ["a", "b", "c"]
        result = escape_sql_value(test_list)
        assert result.startswith("'")
        assert result.endswith("'")
        inner_json = result[1:-1]
        parsed = json.loads(inner_json)
        assert parsed == test_list

    def test_escape_sql_injection_prevented(self) -> None:
        """SQL injection attempts should be escaped."""
        malicious = "'; DROP TABLE users; --"
        result = escape_sql_value(malicious)
        assert "''" in result


# ================================================================
# TESTS: Database CLASS
# ================================================================


class TestDatabaseClass:
    """Tests for the Database class."""

    def test_database_init_with_custom_connection(self) -> None:
        """Database should accept custom connection string."""
        db = Database(connection_string=TEST_CONNECTION_STRING)
        assert db.connection_string == TEST_CONNECTION_STRING

    def test_database_init_with_default_connection(self) -> None:
        """Database should use default connection when not provided."""
        db = Database()
        assert db.connection_string is not None
        assert len(db.connection_string) > 0

    def test_database_format_value_none(self) -> None:
        """_format_value should handle None."""
        db = Database()
        result = db._format_value(None)
        assert result == "NULL"

    def test_database_format_value_bool(self) -> None:
        """_format_value should handle booleans."""
        db = Database()
        assert db._format_value(True) == "TRUE"
        assert db._format_value(False) == "FALSE"

    def test_database_format_value_numbers(self) -> None:
        """_format_value should handle numbers."""
        db = Database()
        assert db._format_value(123) == "123"
        assert db._format_value(3.14159) == "3.14159"

    def test_database_format_value_strings(self) -> None:
        """_format_value should quote strings."""
        db = Database()
        assert db._format_value("test") == "'test'"


# ================================================================
# TESTS: log_execution FUNCTION
# ================================================================


class TestLogExecution:
    """Tests for log_execution function."""

    @patch("core.database._db")
    def test_log_execution_basic(self, mock_db: Mock) -> None:
        """log_execution should insert log entry."""
        mock_db.insert.return_value = "test-uuid-123"
        
        result = log_execution(
            worker_id="test-worker",
            action="test.action",
            message="Test message"
        )
        
        assert result == "test-uuid-123"
        mock_db.insert.assert_called_once()

    @patch("core.database._db")
    def test_log_execution_handles_error(self, mock_db: Mock) -> None:
        """log_execution should return None on error."""
        mock_db.insert.side_effect = Exception("Database error")
        
        result = log_execution(
            worker_id="test-worker",
            action="test.action",
            message="Test message"
        )
        
        assert result is None


# ================================================================
# EDGE CASES AND SECURITY TESTS
# ================================================================


class TestEdgeCases:
    """Tests for edge cases and security."""

    def test_escape_empty_string(self) -> None:
        """Empty strings should be escaped properly."""
        result = escape_sql_value("")
        assert result == "''"

    def test_escape_negative_numbers(self) -> None:
        """Negative numbers should be handled."""
        assert escape_sql_value(-42) == "-42"
        assert escape_sql_value(-3.14) == "-3.14"

    def test_escape_large_numbers(self) -> None:
        """Large numbers should be handled."""
        big_int = 999999999999999999
        result = escape_sql_value(big_int)
        assert result == str(big_int)
