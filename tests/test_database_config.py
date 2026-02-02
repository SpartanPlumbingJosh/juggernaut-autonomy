"""
Tests for database configuration and environment variable handling.

Tests that database configuration properly uses environment variables
instead of hardcoded credentials.
"""

import os
import unittest
from unittest.mock import patch

# Import the modules we want to test
from core.experiments import NEON_CONNECTION_STRING as exp_conn_string
from core.orchestration import NEON_CONNECTION_STRING as orch_conn_string


class TestDatabaseConfig(unittest.TestCase):
    """Test database configuration from environment variables."""

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@test.example.com/db"})
    def test_database_url_takes_precedence(self):
        """Test that DATABASE_URL takes precedence over NEON_CONNECTION_STRING."""
        # Re-import to get fresh environment variables
        import importlib
        import core.experiments
        import core.orchestration
        
        # Reload modules to pick up new environment variables
        importlib.reload(core.experiments)
        importlib.reload(core.orchestration)
        
        # Check that both modules use DATABASE_URL
        self.assertEqual(
            core.experiments.NEON_CONNECTION_STRING,
            "postgresql://user:pass@test.example.com/db"
        )
        self.assertEqual(
            core.orchestration.NEON_CONNECTION_STRING,
            "postgresql://user:pass@test.example.com/db"
        )

    @patch.dict(os.environ, {
        "DATABASE_URL": "",
        "NEON_CONNECTION_STRING": "postgresql://neon:test@neon.example.com/neondb"
    })
    def test_neon_connection_string_fallback(self):
        """Test that NEON_CONNECTION_STRING is used as fallback."""
        # Re-import to get fresh environment variables
        import importlib
        import core.experiments
        import core.orchestration
        
        # Reload modules to pick up new environment variables
        importlib.reload(core.experiments)
        importlib.reload(core.orchestration)
        
        # Check that both modules use NEON_CONNECTION_STRING
        self.assertEqual(
            core.experiments.NEON_CONNECTION_STRING,
            "postgresql://neon:test@neon.example.com/neondb"
        )
        self.assertEqual(
            core.orchestration.NEON_CONNECTION_STRING,
            "postgresql://neon:test@neon.example.com/neondb"
        )

    @patch.dict(os.environ, {"DATABASE_URL": "", "NEON_CONNECTION_STRING": ""})
    def test_missing_connection_string(self):
        """Test behavior when no connection string is provided."""
        # Re-import to get fresh environment variables
        import importlib
        import core.experiments
        import core.orchestration
        
        # Reload modules to pick up new environment variables
        importlib.reload(core.experiments)
        importlib.reload(core.orchestration)
        
        # Check that both modules have empty connection strings
        self.assertEqual(core.experiments.NEON_CONNECTION_STRING, "")
        self.assertEqual(core.orchestration.NEON_CONNECTION_STRING, "")


if __name__ == "__main__":
    unittest.main()
