"""
Tests for Deployment Verifier Module
====================================

Unit tests for core/deploy_verifier.py
"""

import unittest
from unittest.mock import patch, MagicMock
import json

from core.deploy_verifier import (
    DeployStatus,
    DeployResult,
    DeployVerifier,
    check_railway_deployment,
    check_vercel_deployment,
    run_health_check,
)


class TestDeployStatus(unittest.TestCase):
    """Test DeployStatus enum."""
    
    def test_from_railway_success(self):
        """Test Railway status mapping for success states."""
        self.assertEqual(DeployStatus.from_railway("SUCCESS"), DeployStatus.SUCCESS)
        self.assertEqual(DeployStatus.from_railway("RUNNING"), DeployStatus.SUCCESS)
        self.assertEqual(DeployStatus.from_railway("success"), DeployStatus.SUCCESS)
    
    def test_from_railway_pending(self):
        """Test Railway status mapping for pending states."""
        self.assertEqual(DeployStatus.from_railway("QUEUED"), DeployStatus.PENDING)
        self.assertEqual(DeployStatus.from_railway("INITIALIZING"), DeployStatus.PENDING)
    
    def test_from_railway_building(self):
        """Test Railway status mapping for building state."""
        self.assertEqual(DeployStatus.from_railway("BUILDING"), DeployStatus.BUILDING)
    
    def test_from_railway_failed(self):
        """Test Railway status mapping for failed states."""
        self.assertEqual(DeployStatus.from_railway("FAILED"), DeployStatus.FAILED)
        self.assertEqual(DeployStatus.from_railway("CRASHED"), DeployStatus.CRASHED)
    
    def test_from_railway_unknown(self):
        """Test Railway status mapping for unknown states."""
        self.assertEqual(DeployStatus.from_railway("UNKNOWN_STATE"), DeployStatus.UNKNOWN)
    
    def test_from_vercel_success(self):
        """Test Vercel status mapping for success."""
        self.assertEqual(DeployStatus.from_vercel("READY", "READY"), DeployStatus.SUCCESS)
    
    def test_from_vercel_building(self):
        """Test Vercel status mapping for building."""
        self.assertEqual(DeployStatus.from_vercel("QUEUED", "BUILDING"), DeployStatus.BUILDING)
    
    def test_from_vercel_failed(self):
        """Test Vercel status mapping for error."""
        self.assertEqual(DeployStatus.from_vercel("ERROR", None), DeployStatus.FAILED)


class TestDeployResult(unittest.TestCase):
    """Test DeployResult dataclass."""
    
    def test_is_success(self):
        """Test is_success property."""
        result = DeployResult(status=DeployStatus.SUCCESS)
        self.assertTrue(result.is_success)
        
        result = DeployResult(status=DeployStatus.FAILED)
        self.assertFalse(result.is_success)
    
    def test_is_pending(self):
        """Test is_pending property."""
        for status in [DeployStatus.PENDING, DeployStatus.BUILDING, DeployStatus.DEPLOYING]:
            result = DeployResult(status=status)
            self.assertTrue(result.is_pending, f"Expected {status} to be pending")
        
        result = DeployResult(status=DeployStatus.SUCCESS)
        self.assertFalse(result.is_pending)
    
    def test_is_failed(self):
        """Test is_failed property."""
        for status in [DeployStatus.FAILED, DeployStatus.CRASHED, DeployStatus.CANCELLED]:
            result = DeployResult(status=status)
            self.assertTrue(result.is_failed, f"Expected {status} to be failed")
        
        result = DeployResult(status=DeployStatus.SUCCESS)
        self.assertFalse(result.is_failed)
    
    def test_to_dict(self):
        """Test to_dict method."""
        result = DeployResult(
            status=DeployStatus.SUCCESS,
            service_id="svc-123",
            deployment_id="dep-456",
            url="https://example.com",
            platform="railway"
        )
        
        d = result.to_dict()
        self.assertEqual(d["status"], "success")
        self.assertEqual(d["service_id"], "svc-123")
        self.assertEqual(d["deployment_id"], "dep-456")
        self.assertEqual(d["url"], "https://example.com")
        self.assertEqual(d["platform"], "railway")


class TestDeployVerifier(unittest.TestCase):
    """Test DeployVerifier class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.verifier = DeployVerifier(
            railway_token="test-railway-token",
            vercel_token="test-vercel-token"
        )
    
    @patch("urllib.request.urlopen")
    def test_check_railway_status_success(self, mock_urlopen):
        """Test successful Railway status check."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "deployments": {
                    "edges": [{
                        "node": {
                            "id": "dep-123",
                            "status": "SUCCESS",
                            "staticUrl": "https://app.railway.app",
                            "createdAt": "2026-01-21T10:00:00Z",
                            "meta": {"commitSha": "abc123"}
                        }
                    }]
                }
            }
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = self.verifier.check_railway_status("svc-123")
        
        self.assertEqual(result.status, DeployStatus.SUCCESS)
        self.assertEqual(result.deployment_id, "dep-123")
        self.assertEqual(result.url, "https://app.railway.app")
        self.assertEqual(result.platform, "railway")
    
    @patch("urllib.request.urlopen")
    def test_check_railway_status_no_deployments(self, mock_urlopen):
        """Test Railway status check with no deployments."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "deployments": {
                    "edges": []
                }
            }
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = self.verifier.check_railway_status("svc-123")
        
        self.assertEqual(result.status, DeployStatus.UNKNOWN)
        self.assertIn("No deployments found", result.error)
    
    def test_check_railway_status_no_token(self):
        """Test Railway status check without token."""
        verifier = DeployVerifier(railway_token="")
        result = verifier.check_railway_status("svc-123")
        
        self.assertEqual(result.status, DeployStatus.UNKNOWN)
        self.assertIn("No Railway API token", result.error)
    
    @patch("urllib.request.urlopen")
    def test_check_vercel_status_success(self, mock_urlopen):
        """Test successful Vercel status check."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "deployments": [{
                "uid": "dep-456",
                "state": "READY",
                "readyState": "READY",
                "url": "app.vercel.app",
                "createdAt": "2026-01-21T10:00:00Z",
                "meta": {"githubCommitSha": "def456"}
            }]
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = self.verifier.check_vercel_status("prj-123")
        
        self.assertEqual(result.status, DeployStatus.SUCCESS)
        self.assertEqual(result.deployment_id, "dep-456")
        self.assertEqual(result.platform, "vercel")
    
    def test_check_vercel_status_no_token(self):
        """Test Vercel status check without token."""
        verifier = DeployVerifier(vercel_token="")
        result = verifier.check_vercel_status("prj-123")
        
        self.assertEqual(result.status, DeployStatus.UNKNOWN)
        self.assertIn("No Vercel API token", result.error)
    
    @patch("urllib.request.urlopen")
    def test_run_health_check_success(self, mock_urlopen):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = self.verifier.run_health_check("https://example.com/health")
        
        self.assertTrue(result)
    
    @patch("urllib.request.urlopen")
    def test_run_health_check_wrong_status(self, mock_urlopen):
        """Test health check with wrong status code."""
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.read.return_value = b'Internal Server Error'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        # With retry_count=1 to speed up test
        result = self.verifier.run_health_check(
            "https://example.com/health",
            expected_status=200,
            retry_count=1
        )
        
        self.assertFalse(result)
    
    @patch("urllib.request.urlopen")
    def test_run_health_check_detailed(self, mock_urlopen):
        """Test detailed health check."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "healthy"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = self.verifier.run_health_check_detailed(
            "https://example.com/health",
            expected_body_contains="healthy"
        )
        
        self.assertTrue(result["passed"])
        self.assertEqual(result["status_code"], 200)
        self.assertIsNotNone(result["response_time_ms"])
    
    @patch("urllib.request.urlopen")
    def test_verify_deployment_full_pipeline(self, mock_urlopen):
        """Test full deployment verification pipeline."""
        # Mock Railway response
        railway_response = MagicMock()
        railway_response.read.return_value = json.dumps({
            "data": {
                "deployments": {
                    "edges": [{
                        "node": {
                            "id": "dep-123",
                            "status": "SUCCESS",
                            "staticUrl": "app.railway.app",
                            "createdAt": "2026-01-21T10:00:00Z"
                        }
                    }]
                }
            }
        }).encode("utf-8")
        railway_response.__enter__ = MagicMock(return_value=railway_response)
        railway_response.__exit__ = MagicMock(return_value=False)
        
        # Mock health check response
        health_response = MagicMock()
        health_response.status = 200
        health_response.read.return_value = b'OK'
        health_response.__enter__ = MagicMock(return_value=health_response)
        health_response.__exit__ = MagicMock(return_value=False)
        
        # Return different responses for different calls
        mock_urlopen.side_effect = [railway_response, health_response]
        
        task = {
            "metadata": {
                "railway_service_id": "svc-123",
                "deploy_platform": "railway"
            },
            "endpoint_definition": {
                "url": "/api/health",
                "expected_status": 200
            }
        }
        
        result = self.verifier.verify_deployment(task, run_health_check=True)
        
        self.assertEqual(result.status, DeployStatus.SUCCESS)
        self.assertTrue(result.health_check_passed)


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""
    
    @patch.object(DeployVerifier, "check_railway_status")
    def test_check_railway_deployment(self, mock_check):
        """Test check_railway_deployment convenience function."""
        mock_check.return_value = DeployResult(status=DeployStatus.SUCCESS)
        
        result = check_railway_deployment("svc-123")
        
        self.assertEqual(result.status, DeployStatus.SUCCESS)
        mock_check.assert_called_once_with("svc-123")
    
    @patch.object(DeployVerifier, "check_vercel_status")
    def test_check_vercel_deployment(self, mock_check):
        """Test check_vercel_deployment convenience function."""
        mock_check.return_value = DeployResult(status=DeployStatus.SUCCESS)
        
        result = check_vercel_deployment("prj-123")
        
        self.assertEqual(result.status, DeployStatus.SUCCESS)
        mock_check.assert_called_once_with("prj-123")
    
    @patch.object(DeployVerifier, "run_health_check")
    def test_run_health_check_function(self, mock_check):
        """Test run_health_check convenience function."""
        mock_check.return_value = True
        
        result = run_health_check("https://example.com", 200, 30)
        
        self.assertTrue(result)
        mock_check.assert_called_once_with("https://example.com", 200, 30)


if __name__ == "__main__":
    unittest.main()
