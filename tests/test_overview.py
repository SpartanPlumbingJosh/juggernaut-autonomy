import importlib
import logging
from types import ModuleType

import pytest


@pytest.fixture(scope="module")
def github_verifier_module() -> ModuleType:
    """
    Import the github_verifier module once for all tests in this module.
    """
    return importlib.import_module("core.verification.github_verifier")


@pytest.fixture(autouse=True)
def prevent_network_calls(monkeypatch):
    """
    Prevent any accidental real network calls in tests by patching common
    requests HTTP methods to raise an AssertionError if used.
    """
    import requests

    def _no_network_calls(*args, **kwargs):
        raise AssertionError("Network calls are not allowed during unit tests")

    for method_name in ("get", "post", "put", "delete", "head", "patch", "options"):
        if hasattr(requests, method_name):
            monkeypatch.setattr(requests, method_name, _no_network_calls)
    yield


def test_github_api_base_url_points_to_github_api(github_verifier_module: ModuleType):
    """
    GITHUB_API_BASE_URL should be the expected GitHub API base URL.
    """
    assert hasattr(github_verifier_module, "GITHUB_API_BASE_URL"), "Constant GITHUB_API_BASE_URL is missing"
    value = github_verifier_module.GITHUB_API_BASE_URL
    assert isinstance(value, str)
    # Basic sanity check that it points to GitHub's API domain
    assert value.startswith("https://api.github.com")


def test_default_timeout_seconds_is_positive_float(github_verifier_module: ModuleType):
    """
    DEFAULT_TIMEOUT_SECONDS should be a positive float indicating a sensible timeout.
    """
    assert hasattr(github_verifier_module, "DEFAULT_TIMEOUT_SECONDS"), "Constant DEFAULT_TIMEOUT_SECONDS is missing"
    value = github_verifier_module.DEFAULT_TIMEOUT_SECONDS
    assert isinstance(value, (float, int)), "DEFAULT_TIMEOUT_SECONDS should be numeric"
    assert value > 0, "DEFAULT_TIMEOUT_SECONDS should be positive"
    # Upper bound sanity check to catch absurd values
    assert value < 120, "DEFAULT_TIMEOUT_SECONDS appears unreasonably large"


def test_max_request_retries_is_non_negative_integer(github_verifier_module: ModuleType):
    """
    MAX_REQUEST_RETRIES should be a non-negative integer.
    """
    assert hasattr(github_verifier_module, "MAX_REQUEST_RETRIES"), "Constant MAX_REQUEST_RETRIES is missing"
    value = github_verifier_module.MAX_REQUEST_RETRIES
    assert isinstance(value, int), "MAX_REQUEST_RETRIES should be an integer"
    assert value >= 0, "MAX_REQUEST_RETRIES should be non-negative"
    # Reasonable upper limit to avoid infinite/very large retry loops
    assert value <= 10, "MAX_REQUEST_RETRIES appears unreasonably high"


def test_rate_limit_status_code_is_valid_http_status(github_verifier_module: ModuleType):
    """
    RATE_LIMIT_STATUS_CODE should be a valid HTTP status code used for rate limiting.
    Common values are 429 or GitHub-specific codes.
    """
    assert hasattr(github_verifier_module, "RATE_LIMIT_STATUS_CODE"), "Constant RATE_LIMIT_STATUS_CODE is missing"
    value = github_verifier_module.RATE_LIMIT_STATUS_CODE
    assert isinstance(value, int), "RATE_LIMIT_STATUS_CODE should be an integer"
    assert 100 <= value <= 599, "RATE_LIMIT_STATUS_CODE should be a valid HTTP status code range"
    # Specifically ensure it matches the standard Too Many Requests status
    assert value == 429, "RATE_LIMIT_STATUS_CODE should be 429 for rate limiting"


def test_logger_is_configured_with_module_name(github_verifier_module: ModuleType):
    """
    Logger should be a logging.Logger instance named after the module.
    """
    assert hasattr(github_verifier_module, "logger"), "Module logger is missing"
    logger = github_verifier_module.logger
    assert isinstance(logger, logging.Logger)
    assert logger.name == github_verifier_module.__name__, "Logger name should match module __name__"


def test_module_is_importable_without_side_effects(monkeypatch):
    """
    Ensure importing the module does not perform any network calls or raise unexpected exceptions.
    This is an edge case test guarding against side effects in module-level code.
    """
    import importlib
    import sys

    # Ensure a clean import by removing the module if already imported
    module_name = "core.verification.github_verifier"
    sys.modules.pop(module_name, None)

    # Use a sentinel to detect any unexpected behavior if needed in the future
    # Currently, just ensure import does not raise.
    module = importlib.import_module(module_name)
    assert module is not None