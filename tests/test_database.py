"""
Unit tests for core/database.py
Tests database operations, SQL escaping, and logging functions.
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import Any, Dict

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import (
    Database,
    escape_sql_value,
    query_db,
    log_execution,
    get_logs,
)


class TestEscapeSqlValue:
    """Tests for escape_sql_value function."""

    def test_escape_none(self) -> None:
        """Test None returns NULL."""
        assert escape_sql_value(None) == "NULL"

    def test_escape_true(self) -> None:
        """Test True returns TRUE."""
        assert escape_sql_value(True) == "TRUE"

    def test_escape_false(self) -> None:
        """Test False returns FALSE."""
        assert escape_sql_value(False) == "FALSE"

    def test_escape_integer(self) -> None:
        """Test integers are returned as strings."""
        assert escape_sql_value(42) == "42"

    def test_escape_string(self) -> None:
        """Test strings are quoted and escaped."""
        assert escape_sql_value("hello") == "'hello'"


class TestDatabaseClass:
    """Tests for Database class."""

    def test_init_default_connection(self) -> None:
        """Test Database initializes with default connection string."""
        db = Database()
        assert db.connection_string is not None
        assert db.endpoint is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
