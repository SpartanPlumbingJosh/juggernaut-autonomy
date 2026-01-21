"""
Tests for Endpoint Verifier Module (VERCHAIN-08)
"""

import unittest
from unittest.mock import patch, MagicMock
import json

from core.endpoint_verifier import (
    EndpointVerifier,
    EndpointResult,
    EndpointType,
    verify_http,
    verify_file_exists,
    verify_url_accessible,
    verify_service_health,
    verify_task_endpoint
)


class TestEndpointResult(unittest.TestCase):
    """Tests for EndpointResult dataclass."""
    
    def test_result_creation(self):
        """Test basic result creation."""
        result = EndpointResult(
            passed=True,
            endpoint_type="http",
            details={"url": "https://example.com"}
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.endpoint_type, "http")
        self.assertIn("url", result.details)
    
    def test_result_with_error(self):
        """Test result with error."""
        result = EndpointResult(
            passed=False,
            endpoint_type="http",
            error="Connection failed"
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.error, "Connection failed")
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = EndpointResult(
            passed=True,
            endpoint_type="http",
            details={"status": 200}
        )
        data = result.to_dict()
        self.assertIn("passed", data)
        self.assertIn("endpoint_type", data)
        self.assertIn("details", data)
        self.assertIn("checked_at", data)


class TestEndpointVerifier(unittest.TestCase):
    """Tests for EndpointVerifier class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.verifier = EndpointVerifier(
            github_token="test-github-token",
            railway_token="test-railway-token"
        )
    
    def test_verify_endpoint_no_definition(self):
        """Test verify_endpoint with no endpoint definition."""
        task = {"id": "test-task"}
        result = self.verifier.verify_endpoint(task)
        self.assertFalse(result.passed)
        self.assertIn("No endpoint definition", result.error)
    
    def test_verify_endpoint_invalid_json(self):
        """Test verify_endpoint with invalid JSON definition."""
        task = {"endpoint_definition": "not valid json{"}
        result = self.verifier.verify_endpoint(task)
        self.assertFalse(result.passed)
        self.assertIn("Invalid endpoint definition", result.error)
    
    def test_verify_endpoint_unknown_type(self):
        """Test verify_endpoint with unknown type."""
        task = {"endpoint_definition": {"type": "unknown_type"}}
        result = self.verifier.verify_endpoint(task)
        self.assertFalse(result.passed)
        self.assertIn("Unknown endpoint type", result.error)


class TestHTTPVerification(unittest.TestCase):
    """Tests for HTTP endpoint verification."""
    
    def setUp(self):
        self.verifier = EndpointVerifier()
    
    def test_http_no_url(self):
        """Test HTTP verification without URL."""
        definition = {"type": "http"}
        result = self.verifier._verify_http(definition)
        self.assertFalse(result.passed)
        self.assertIn("No URL", result.error)
    
    @patch('urllib.request.urlopen')
    def test_http_success(self, mock_urlopen):
        """Test successful HTTP verification."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        definition = {
            "type": "http",
            "url": "https://api.example.com/health",
            "expected_status": 200
        }
        result = self.verifier._verify_http(definition)
        self.assertTrue(result.passed)
    
    @patch('urllib.request.urlopen')
    def test_http_wrong_status(self, mock_urlopen):
        """Test HTTP verification with wrong status code."""
        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.read.return_value = b'Not Found'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        definition = {
            "type": "http",
            "url": "https://api.example.com/health",
            "expected_status": 200
        }
        result = self.verifier._verify_http(definition)
        self.assertFalse(result.passed)
        self.assertIn("expected 200", result.error)
    
    @patch('urllib.request.urlopen')
    def test_http_body_contains_success(self, mock_urlopen):
        """Test HTTP verification with body contains check."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'The service is healthy and running'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        definition = {
            "type": "http",
            "url": "https://api.example.com/health",
            "expected_body_contains": "healthy"
        }
        result = self.verifier._verify_http(definition)
        self.assertTrue(result.passed)
    
    @patch('urllib.request.urlopen')
    def test_http_body_contains_failure(self, mock_urlopen):
        """Test HTTP verification with body contains check failure."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'The service is down'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        definition = {
            "type": "http",
            "url": "https://api.example.com/health",
            "expected_body_contains": "healthy"
        }
        result = self.verifier._verify_http(definition)
        self.assertFalse(result.passed)
        self.assertIn("does not contain", result.error)


class TestJSONPathExtraction(unittest.TestCase):
    """Tests for JSON path extraction."""
    
    def setUp(self):
        self.verifier = EndpointVerifier()
    
    def test_simple_key(self):
        """Test extracting simple key."""
        data = {"status": "ok"}
        result = self.verifier._extract_json_path(data, "$.status")
        self.assertEqual(result, "ok")
    
    def test_nested_key(self):
        """Test extracting nested key."""
        data = {"data": {"user": {"name": "John"}}}
        result = self.verifier._extract_json_path(data, "$.data.user.name")
        self.assertEqual(result, "John")
    
    def test_array_index(self):
        """Test extracting array index."""
        data = {"items": ["a", "b", "c"]}
        result = self.verifier._extract_json_path(data, "$.items[1]")
        self.assertEqual(result, "b")
    
    def test_nonexistent_key(self):
        """Test extracting nonexistent key."""
        data = {"status": "ok"}
        result = self.verifier._extract_json_path(data, "$.missing")
        self.assertIsNone(result)


class TestFileExistsVerification(unittest.TestCase):
    """Tests for file exists verification."""
    
    def setUp(self):
        self.verifier = EndpointVerifier(github_token="test-token")
    
    def test_file_exists_missing_params(self):
        """Test file exists with missing parameters."""
        definition = {"type": "file_exists", "repo": "owner/repo"}
        result = self.verifier._verify_file_exists(definition)
        self.assertFalse(result.passed)
        self.assertIn("required", result.error)
    
    def test_file_exists_no_token(self):
        """Test file exists without GitHub token."""
        verifier = EndpointVerifier(github_token="")
        definition = {"type": "file_exists", "repo": "owner/repo", "path": "test.py"}
        result = verifier._verify_file_exists(definition)
        self.assertFalse(result.passed)
        self.assertIn("No GitHub token", result.error)
    
    @patch('urllib.request.urlopen')
    def test_file_exists_success(self, mock_urlopen):
        """Test successful file exists check."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "sha": "abc123",
            "size": 100,
            "content": ""
        }).encode('utf-8')
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        definition = {
            "type": "file_exists",
            "repo": "owner/repo",
            "path": "src/test.py"
        }
        result = self.verifier._verify_file_exists(definition)
        self.assertTrue(result.passed)


class TestServiceHealthVerification(unittest.TestCase):
    """Tests for service health verification."""
    
    def setUp(self):
        self.verifier = EndpointVerifier(railway_token="test-token")
    
    def test_service_health_no_id(self):
        """Test service health without service ID."""
        definition = {"type": "service_health"}
        result = self.verifier._verify_service_health(definition)
        self.assertFalse(result.passed)
        self.assertIn("No service_id", result.error)
    
    def test_service_health_unknown_platform(self):
        """Test service health with unknown platform."""
        definition = {
            "type": "service_health",
            "service_id": "test-123",
            "platform": "unknown_platform"
        }
        result = self.verifier._verify_service_health(definition)
        self.assertFalse(result.passed)
        self.assertIn("Unknown platform", result.error)


class TestURLAccessibleVerification(unittest.TestCase):
    """Tests for URL accessible verification."""
    
    def setUp(self):
        self.verifier = EndpointVerifier()
    
    def test_url_accessible_no_url(self):
        """Test URL accessible without URL."""
        definition = {"type": "url_accessible"}
        result = self.verifier._verify_url_accessible(definition)
        self.assertFalse(result.passed)
        self.assertIn("No URL", result.error)
    
    @patch('urllib.request.urlopen')
    def test_url_accessible_success(self, mock_urlopen):
        """Test successful URL accessible check."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        definition = {"type": "url_accessible", "url": "https://example.com"}
        result = self.verifier._verify_url_accessible(definition)
        self.assertTrue(result.passed)


class TestCompositeVerification(unittest.TestCase):
    """Tests for composite verification."""
    
    def setUp(self):
        self.verifier = EndpointVerifier()
    
    def test_composite_no_checks(self):
        """Test composite with no checks."""
        definition = {"type": "composite", "checks": []}
        result = self.verifier._verify_composite(definition)
        self.assertFalse(result.passed)
        self.assertIn("No checks", result.error)
    
    @patch('urllib.request.urlopen')
    def test_composite_all_pass(self, mock_urlopen):
        """Test composite with all checks passing."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'ok'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        definition = {
            "type": "composite",
            "checks": [
                {"type": "url_accessible", "url": "https://example.com"},
                {"type": "url_accessible", "url": "https://test.com"}
            ],
            "require": "all"
        }
        result = self.verifier._verify_composite(definition)
        self.assertTrue(result.passed)
        self.assertEqual(result.details["passed_count"], 2)
    
    def test_composite_any_mode(self):
        """Test composite with 'any' requirement mode."""
        definition = {
            "type": "composite",
            "checks": [
                {"type": "unknown_type"},  # This will fail
                {"type": "unknown_type"}   # This will also fail
            ],
            "require": "any"
        }
        result = self.verifier._verify_composite(definition)
        self.assertFalse(result.passed)
        self.assertIn("All checks failed", result.error)


class TestExpectedChecking(unittest.TestCase):
    """Tests for expected value checking."""
    
    def setUp(self):
        self.verifier = EndpointVerifier()
    
    def test_greater_than(self):
        """Test greater than comparison."""
        passed, error = self.verifier._check_expected(10, "> 5")
        self.assertTrue(passed)
        
        passed, error = self.verifier._check_expected(3, "> 5")
        self.assertFalse(passed)
    
    def test_less_than(self):
        """Test less than comparison."""
        passed, error = self.verifier._check_expected(3, "< 5")
        self.assertTrue(passed)
        
        passed, error = self.verifier._check_expected(10, "< 5")
        self.assertFalse(passed)
    
    def test_equals(self):
        """Test equality comparison."""
        passed, error = self.verifier._check_expected(5, "= 5")
        self.assertTrue(passed)
        
        passed, error = self.verifier._check_expected("ok", "= ok")
        self.assertTrue(passed)
    
    def test_not_equals(self):
        """Test not equals comparison."""
        passed, error = self.verifier._check_expected(5, "!= 10")
        self.assertTrue(passed)
    
    def test_contains(self):
        """Test contains comparison."""
        passed, error = self.verifier._check_expected("hello world", "contains hello")
        self.assertTrue(passed)
    
    def test_not_contains(self):
        """Test not contains comparison."""
        passed, error = self.verifier._check_expected("hello world", "not_contains goodbye")
        self.assertTrue(passed)


class TestConvenienceFunctions(unittest.TestCase):
    """Tests for convenience functions."""
    
    @patch('urllib.request.urlopen')
    def test_verify_http_function(self, mock_urlopen):
        """Test verify_http convenience function."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'ok'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = verify_http("https://example.com")
        self.assertTrue(result.passed)
    
    @patch('urllib.request.urlopen')
    def test_verify_url_accessible_function(self, mock_urlopen):
        """Test verify_url_accessible convenience function."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = verify_url_accessible("https://example.com")
        self.assertTrue(result.passed)


class TestScriptVerification(unittest.TestCase):
    """Tests for script verification."""
    
    def setUp(self):
        self.verifier = EndpointVerifier()
    
    def test_script_disabled_by_default(self):
        """Test that script verification is disabled by default."""
        definition = {"type": "script", "command": "echo hello"}
        result = self.verifier._verify_script(definition)
        self.assertFalse(result.passed)
        self.assertIn("disabled", result.error)
    
    def test_script_no_command(self):
        """Test script verification without command."""
        with patch.dict('os.environ', {'ALLOW_SCRIPT_VERIFICATION': 'true'}):
            definition = {"type": "script"}
            result = self.verifier._verify_script(definition)
            self.assertFalse(result.passed)
            self.assertIn("No command", result.error)


if __name__ == '__main__':
    unittest.main()
