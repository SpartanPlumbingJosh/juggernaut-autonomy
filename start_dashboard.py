#!/usr/bin/env python3
"""Start the dashboard API server with live database connection."""

import os
import sys
import uvicorn

# Require DASHBOARD_API_SECRET from environment (no hardcoded fallback)
if not os.getenv("DASHBOARD_API_SECRET"):
    print("ERROR: DASHBOARD_API_SECRET environment variable is not set.")
    sys.exit(1)

print("=== Starting Spartan HQ Dashboard API ===")
print("Database: Neon PostgreSQL")
print(f"API Secret: {'Set' if os.getenv('DASHBOARD_API_SECRET') else 'Missing'}")
print(f"Port: {os.getenv('PORT', 8000)}")
print("\nEndpoints:")
print("  GET  /health - Health check")
print("  GET  /v1/overview - Dashboard overview")
print("  GET  /v1/agent_health - Worker health")
print("  GET  /v1/revenue_summary - Revenue metrics")
print("  GET  /v1/experiment_status - Experiment status")
print("  GET  /v1/pending_approvals - Pending approvals")
print("  GET  /v1/system_alerts - System alerts")
print("\nStarting server...")

# Import and run the FastAPI app
from dashboard_api_main import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
