"""
JUGGERNAUT Health Check Endpoint
Public endpoint for monitoring and load balancers.

No authentication required.
"""

import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
API_VERSION = "v1"
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
DATABASE_URL = os.getenv("DATABASE_URL", "")


def check_database_connection(connection_string: str = None) -> bool:
    """
    Check if the database is reachable.

    Args:
        connection_string: PostgreSQL connection string (uses DATABASE_URL env if not provided)

    Returns:
        True if database is reachable, False otherwise
    """
    conn_str = connection_string or DATABASE_URL
    if not conn_str:
        logger.error("No database connection string available")
        return False

    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": conn_str
    }

    data = json.dumps({"query": "SELECT 1"}).encode('utf-8')
    req = urllib.request.Request(
        NEON_ENDPOINT,
        data=data,
        headers=headers,
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get("rowCount", 0) > 0
    except (urllib.error.URLError, urllib.error.HTTPError, Exception) as e:
        logger.error("Database connection check failed: %s", str(e))
        return False


def get_health_status(connection_string: str = None) -> Dict[str, Any]:
    """
    Get the health status of the API.

    Args:
        connection_string: PostgreSQL connection string (optional)

    Returns:
        Health status dictionary with status, timestamp, db_connected, and version
    """
    db_connected = check_database_connection(connection_string)

    return {
        "status": "healthy" if db_connected else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db_connected": db_connected,
        "version": API_VERSION
    }


def handle_health_request(connection_string: str = None) -> Dict[str, Any]:
    """
    Handle health check request. No authentication required.

    Args:
        connection_string: PostgreSQL connection string (optional)

    Returns:
        Response dict with status code and body
    """
    health = get_health_status(connection_string)

    status_code = 200 if health["db_connected"] else 503

    return {
        "status": status_code,
        "body": health
    }


if __name__ == "__main__":
    # Quick test
    result = handle_health_request()
    print(json.dumps(result, indent=2))
