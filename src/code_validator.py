"""
Code Validation Module for Juggernaut Autonomy System.

This module validates generated Python code against CODESTANDRDD.md standards
before committing to the repository.
"""

import ast
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Represents a single validation issue found in code."""

    message: str
    severity: ValidationSeverity
    line_number: Optional[int] = None
    column: Optional[int] = None
    rule: str = ""


@dataclass
class ValidationResult:
    """Result of code validation containing all issues found."""

    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    code_snippet: str = ""

    def add_issue(self, issue: ValidationIssue) -> None:
        """Add a validation issue to the result.

        Args:
            issue: The validation issue to add.
        """
        self.issues.append(issue)
        if issue.severity == ValidationSeverity.ERROR:
            self.is_valid = False

    def get_error_count(self) -> int:
        """Get the number of errors in the result.

        Returns:
            The count of error-severity issues.
        """
        return sum(
            1 for issue in self.issues if issue.severity == ValidationSeverity.ERROR
        )

    def get_warning_count(self) -> int:
        """Get the number of warnings in the result.

        Returns:
            The count of warning-severity issues.
        """
        return sum(
            1 for issue in self.issues if issue.severity == ValidationSeverity.WARNING
        )


class CodeValidator:
    """Validates Python code against CODE_STANDARDS.md requirements."""

    def validate(self, code: str) -> ValidationResult:
        """Validate Python code against all standards.

        Args:
            code: The Python source code to validate.

        Returns:
            A ValidationResult containing all issues found.
        """
        result = ValidationResult(is_valid=True, code_snippet=code[:200])

        # Check syntax first - if it fails, skip other checks
        tree = self._check_syntax(code, result)
        if tree is None:
            return result

        # Run all AST-based checks
        self._check_type_hints(tree, result)
        self._check_docstrings(tree, result)
        self._check_no_print_statements(tree, result)
        self._check_no_bare_excepts(tree, result)
        self._check_imports(tree, result)

        logger.info(
            "Validation complete: valid=%s, errors=%d, warnings=%d",
            result.is_valid,
            result.get_error_count(),
            result.get_warning_count(),
        )

        return result

    def _check_syntax(self, code: str, result: ValidationResult) -> Optional[ast.Module]:
        """Check if code has valid Python syntax.

        Args:
            code: The Python source code.
            result: The validation result to add issues to.

        Returns:
            The parsed AST if syntax is valid, None otherwise.
        """
        try:
            return ast.parse(code)
        except SyntaxError as e:
            result.add_issue(
                ValidationIssue(
                    message=f"Syntax error: {e.msg}",
                    severity=ValidationSeverity.ERROR,
                    line_number=e.lineno,
                    column=e.offset,
                    rule="syntax",
                )
            )
            return None

    def _check_type_hints(self, tree: ast.Module, result: ValidationResult) -> None:
        """Check that all functions have type hints.

        Args:
            tree: The parsed AST.
            result: The validation result to add issues to.
        """
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check return type annotation
                if node.returns is None:
                    result.add_issue(
                        ValidationIssue(
                            message=f"Function '{node.name}' missing return type hint",
                            severity=ValidationSeverity.ERROR,
                            line_number=node.lineno,
                            rule="type-hints",
                        )
                    )

                # Check parameter type annotations (skip 'self' and 'cls')
                for arg in node.args.args:
                    if arg.arg not in ("self", "cls") and arg.annotation is None:
                        result.add_issue(
                            ValidationIssue(
                                message=f"Parameter '{arg.arg}' in '{node.name}' missing type hint",
                                severity=ValidationSeverity.ERROR,
                                line_number=node.lineno,
                                rule="type-hints",
                            )
                        )

    def _check_docstrings(self, tree: ast.Module, result: ValidationResult) -> None:
        """Check that all functions and classes have docstrings.

        Args:
            tree: The parsed AST.
            result: The validation result to add issues to.
        """
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                docstring = ast.get_docstring(node)
                if not docstring:
                    node_type = "class" if isinstance(node, ast.ClassDef) else "function"
                    result.add_issue(
                        ValidationIssue(
                            message=f"{node_type.capitalize()} '{node.name}' missing docstring",
                            severity=ValidationSeverity.ERROR,
                            line_number=node.lineno,
                            rule="docstrings",
                        )
                    )

    def _check_no_print_statements(self, tree: ast.Module, result: ValidationResult) -> None:
        """Check that code uses logging instead of print().

        Args:
            tree: The parsed AST.
            result: The validation result to add issues to.
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "print":
                    result.add_issue(
                        ValidationIssue(
                            message="Use logging instead of print()",
                            severity=ValidationSeverity.ERROR,
                            line_number=node.lineno,
                            rule="no-print",
                        )
                    )

    def _check_no_bare_excepts(self, tree: ast.Module, result: ValidationResult) -> None:
        """Check that code does not use bare except clauses.

        Args:
            tree: The parsed AST.
            result: The validation result to add issues to.
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    result.add_issue(
                        ValidationIssue(
                            message="Bare except clause - specify exception type",
                            severity=ValidationSeverity.ERROR,
                            line_number=node.lineno,
                            rule="no-bare-except",
                        )
                    )

    def _check_imports(self, tree: ast.Module, result: ValidationResult) -> None:
        """Check that imports are at the top of the file.

        Args:
            tree: The parsed AST.
            result: The validation result to add issues to.
        """
        found_non_import = False
        for node in ast.iter_child_nodes(tree):
            # Skip docstrings and __future__ imports
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue

            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if found_non_import:
                    result.add_issue(
                        ValidationIssue(
                            message="Import statement should be at top of file",
                            severity=ValidationSeverity.WARNING,
                            line_number=node.lineno,
                            rule="import-order",
                        )
                    )
            else:
                found_non_import = True


def validate_code(code: str) -> ValidationResult:
    """Convenience function to validate Python code.

    Args:
        code: The Python source code to validate.

    Returns:
        A ValidationResult containing all issues found.
    """
    validator = CodeValidator()
    return validator.validate(code)
