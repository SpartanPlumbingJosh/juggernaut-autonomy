"""
Tests for core/experiments.py
"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_sql():
    with patch("core.experiments._execute_sql") as mock:
        yield mock


class TestEscapeString:
    def test_escape_quotes(self):
        from core.experiments import _escape_string
        assert _escape_string("It's") == "It''s"

    def test_escape_none(self):
        from core.experiments import _escape_string
        assert _escape_string(None) == "NULL"


class TestCreateTemplate:
    def test_create_success(self, mock_sql):
        from core.experiments import create_experiment_template
        mock_sql.return_value = {"success": True}
        result = create_experiment_template(
            name="test",
            description="test",
            experiment_type="revenue",
            category="digital",
            default_hypothesis="test",
            default_success_criteria={"min": 100}
        )
        assert result["success"] is True


class TestListTemplates:
    def test_list_no_filters(self, mock_sql):
        from core.experiments import list_experiment_templates
        mock_sql.return_value = {"rows": [{"id": "1"}]}
        result = list_experiment_templates()
        assert len(result) == 1


class TestCreateExperiment:
    def test_create_success(self, mock_sql):
        from core.experiments import create_experiment
        mock_sql.return_value = {"success": True}
        result = create_experiment(
            name="test",
            hypothesis="test",
            success_criteria={"min": 100}
        )
        assert result["success"] is True
