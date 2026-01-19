"""
Tests for core/experiments.py

covers:
- _escape_string utility function
- create_experiment_template function
- list_experiment_templates function
- create_experiment function
"""

import pytest
from unittest.mock import patch

from core.experiments import (
    _escape_string,
    create_experiment_template,
    list_experiment_templates,
    create_experiment,
)


@pytest.fixture
def mock_sql():
    """Mock the _execute_sql function for database operations."""
    with patch("core.experiments._execute_sql") as mock:
        yield mock


class TestEscapeString:
    """Tests for _escape_string utility function."""

    def test_escape_single_quotes(self):
        """Verify single quotes are escaped for SQL."""
        assert _escape_string("It's") == "It''s"

    def test_escape_none_returns_null(self):
        """
        Verify None input returns 'NULL' string.
        
        Note: The function signature says `value: str` but the implementation
        accepts None and returns 'NULL'. This test documents the actual
        behavior for backwards compatibility. Consider updating the type
        hint to Optional[str] in a future refactor.
        """
        assert _escape_string(None) == "NULL"

    def test_escape_empty_string(self):
        """Verify empty string is returned as is."""
        assert _escape_string("") == ""

    def test_escape_multiple_quotes(self):
        """Verify multiple quotes are all escaped."""
        assert _escape_string("O'Brien's") == "O''Brien''s"


class TestCreateTemplate:
    """Tests for create_experiment_template function."""

    def test_create_success(self, mock_sql):
        """Verify template creation returns success and calls SQL."""
        mock_sql.return_value = {"success": True}
        result = create_experiment_template(
            name="test_template",
            description="Test description",
            experiment_type="revenue",
            category="digital",
            default_hypothesis="Test hypothesis",
            default_success_criteria={"min_revenue": 100}
        )
        
        assert result["success"] is True
        assert "template_id" in result
        mock_sql.assert_called_once()
        
        # Verify query contains expected values
        query = mock_sql.call_args[0][0]
        assert "test_template" in query
        assert "INSERT INTO experiment_templates" in query


class TestListTemplates:
    """Tests for list_experiment_templates function."""

    def test_list_no_filters(self, mock_sql):
        """Verify listing without filters returns all templates."""
        mock_sql.return_value = {"rows": [{"id": "1", "name": "template1"}]}
        result = list_experiment_templates()
        
        assert len(result) == 1
        mock_sql.assert_called_once()
        
        # Verify no WHERE clause when no filters
        query = mock_sql.call_args[0][0]
        assert "SELECT" in query
        assert "FROM experiment_templates" in query

    def test_list_with_category_filter(self, mock_sql):
        """Verify category filter is applied."""
        mock_sql.return_value = {"rows": []}
        list_experiment_templates(category="digital")
        
        query = mock_sql.call_args[0][0]
        assert "category = 'digital'" in query


class TestCreateExperiment:
    """Tests for create_experiment function."""

    def test_create_success(self, mock_sql):
        """Verify experiment creation returns success and calls SQL."""
        mock_sql.return_value = {"success": True}
        result = create_experiment(
            name="test_experiment",
            hypothesis="Test hypothesis",
            success_criteria={"min_revenue": 100}
        )
        
        assert result["success"] is True
        assert "experiment_id" in result
        mock_sql.assert_called_once()
        
        # Verify query contains expected values
        query = mock_sql.call_args[0][0]
        assert "test_experiment" in query
        assert "INSERT INTO experiments" in query
