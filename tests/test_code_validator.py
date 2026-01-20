"""Tests for the code validation module."""

import pytest

from src.code_validator import (
    CodeValidator,
    ValidationResult,
    ValidationSeverity,
    validate_code,
)


class TestCodeValidator:
    """Test cases for the CodeValidator class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.validator = CodeValidator()

    def test_valid_code_passes(self) -> None:
        """Test that valid code passes all checks."""
        valid_code = '''
import logging

logger = logging.getLogger(__name__)


def add_numbers(a: int, b: int) -> int:
    """Add two numbers together.

    Args:
        a: First number.
        b: Second number.

    Returns:
        The sum of a and b.
    """
    logger.info("Adding %d + %d", a, b)
    return a + b
'''
        result = self.validator.validate(valid_code)
        assert result.is_valid is True
        assert result.get_error_count() == 0

    def test_syntax_error_detected(self) -> None:
        """Test that syntax errors are detected."""
        invalid_code = "def bad_function("
        result = self.validator.validate(invalid_code)
        assert result.is_valid is False
        assert any("Syntax error" in issue.message for issue in result.issues)

    def test_missing_return_type_detected(self) -> None:
        """Test that missing return type hints are detected."""
        code_missing_return = '''
def no_return_type(a: int):
    """Missing return type."""
    return a
'''
        result = self.validator.validate(code_missing_return)
        assert result.is_valid is False
        assert any("missing return type hint" in issue.message for issue in result.issues)

    def test_missing_parameter_type_detected(self) -> None:
        """Test that missing parameter type hints are detected."""
        code_missing_param = '''
def no_param_type(a) -> int:
    """Missing param type."""
    return a
'''
        result = self.validator.validate(code_missing_param)
        assert result.is_valid is False
        assert any("missing type hint" in issue.message for issue in result.issues)

    def test_self_parameter_skipped(self) -> None:
        """Test that 'self' parameter does not require type hint."""
        class_code = '''
class MyClass:
    """A test class."""

    def my_method(self, value: int) -> int:
        """A test method."""
        return value
'''
        result = self.validator.validate(class_code)
        assert result.is_valid is True

    def test_missing_docstring_detected(self) -> None:
        """Test that missing docstrings are detected."""
        code_no_docstring = '''
def no_docstring(a: int) -> int:
    return a
'''
        result = self.validator.validate(code_no_docstring)
        assert result.is_valid is False
        assert any("missing docstring" in issue.message for issue in result.issues)

    def test_print_statement_detected(self) -> None:
        """Test that print() statements are detected."""
        code_with_print = '''
def with_print(a: int) -> None:
    """Uses print."""
    print(a)
'''
        result = self.validator.validate(code_with_print)
        assert result.is_valid is False
        assert any("logging instead of print" in issue.message for issue in result.issues)

    def test_bare_except_detected(self) -> None:
        """Test that bare except clauses are detected."""
        code_bare_except = '''
def with_bare_except() -> None:
    """Uses bare except."""
    try:
        pass
    except:
        pass
'''
        result = self.validator.validate(code_bare_except)
        assert result.is_valid is False
        assert any("Bare except clause" in issue.message for issue in result.issues)

    def test_specific_except_allowed(self) -> None:
        """Test that specific exception types are allowed."""
        code_specific_except = '''
def with_specific_except() -> None:
    """Uses specific except."""
    try:
        pass
    except ValueError:
        pass
'''
        result = self.validator.validate(code_specific_except)
        assert not any("Bare except" in issue.message for issue in result.issues)

    def test_import_not_at_top_warning(self) -> None:
        """Test that imports not at top generate warning."""
        code_late_import = '''
x = 1

import os
'''
        result = self.validator.validate(code_late_import)
        warnings = [i for i in result.issues if i.severity == ValidationSeverity.WARNING]
        assert any("Import statement should be at top" in w.message for w in warnings)


class TestValidationResult:
    """Test cases for the ValidationResult class."""

    def test_error_count(self) -> None:
        """Test error counting."""
        result = ValidationResult(is_valid=True)
        assert result.get_error_count() == 0

    def test_warning_count(self) -> None:
        """Test warning counting."""
        result = ValidationResult(is_valid=True)
        assert result.get_warning_count() == 0


class TestValidateCodeFunction:
    """Test cases for the validate_code convenience function."""

    def test_validate_code_function(self) -> None:
        """Test that the convenience function works."""
        code = '''
def hello() -> str:
    """Say hello."""
    return "hello"
'''
        result = validate_code(code)
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
