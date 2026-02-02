"""
Tests for Puppeteer wiring improvements.

Tests URL normalization, authentication handling, and error reporting.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

# Import the classes we want to test
from core.handlers.research_handler import ResearchHandler
from core.unified_brain import BrainService


class TestPuppeteerWiring(unittest.TestCase):
    """Test Puppeteer wiring improvements."""

    @patch("core.handlers.research_handler.PUPPETEER_URL", "https://puppeteer-test.railway.app")
    @patch("core.handlers.research_handler.PUPPETEER_AUTH_TOKEN", "test-token")
    @patch("urllib.request.urlopen")
    def test_puppeteer_action_url_formatting(self, mock_urlopen):
        """Test that puppeteer_action correctly formats URLs."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"success": true}'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Create a ResearchHandler instance
        handler = ResearchHandler()
        
        # Call the method
        result = handler._puppeteer_action("navigate", {"url": "https://example.com"})
        
        # Check the URL was correctly formatted
        args, kwargs = mock_urlopen.call_args
        self.assertEqual(kwargs["timeout"], 30)  # Check timeout is set
        
        # Check request URL and headers
        request = args[0]
        self.assertEqual(request.full_url, "https://puppeteer-test.railway.app/action")
        self.assertEqual(request.headers["Authorization"], "Bearer test-token")
        self.assertEqual(request.headers["Content-Type"], "application/json")

    @patch("os.getenv")
    def test_puppeteer_healthcheck_url_normalization(self, mock_getenv):
        """Test that puppeteer_healthcheck normalizes URLs correctly."""
        # Setup environment variables
        mock_getenv.side_effect = lambda key, default="": {
            "PUPPETEER_URL": "puppeteer-service.railway.app",  # No scheme
            "PUPPETEER_AUTH_TOKEN": "test-token",
            "RAILWAY_PROJECT_ID": "project-123"
        }.get(key, default)
        
        # Create a BrainService instance
        brain = BrainService()
        
        # Mock urllib.request.Request and urlopen
        with patch("urllib.request.Request") as mock_request, \
             patch("urllib.request.urlopen") as mock_urlopen:
            
            # Setup mock response
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"status": "healthy", "version": "1.0"}'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # Call the function
            result = brain._execute_tool("puppeteer_healthcheck", {})
            
            # Check URL normalization
            args, _ = mock_request.call_args
            self.assertEqual(args[0], "https://puppeteer-service.railway.app/health")
            
            # Check result contains expected fields
            self.assertTrue(result["configured"])
            self.assertEqual(result["status"], "healthy")
            self.assertEqual(result["version"], "1.0")
            self.assertEqual(result["url"], "https://puppeteer-service.railway.app")
            self.assertTrue(result["auth_configured"])

    @patch("os.getenv")
    def test_puppeteer_healthcheck_missing_url(self, mock_getenv):
        """Test that puppeteer_healthcheck handles missing URL correctly."""
        # Setup environment variables with missing PUPPETEER_URL
        mock_getenv.side_effect = lambda key, default="": {
            "PUPPETEER_URL": "",
            "RAILWAY_PROJECT_ID": "project-123"
        }.get(key, default)
        
        # Create a BrainService instance
        brain = BrainService()
        
        # Call the function
        result = brain._execute_tool("puppeteer_healthcheck", {})
        
        # Check result indicates not configured but Railway is available
        self.assertFalse(result["configured"])
        self.assertEqual(result["error"], "PUPPETEER_URL not set")
        self.assertTrue(result["railway_configured"])


if __name__ == "__main__":
    unittest.main()
