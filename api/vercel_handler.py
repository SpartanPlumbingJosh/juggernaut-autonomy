"""
JUGGERNAUT Dashboard API - Vercel Serverless Handler
Main entry point for all dashboard API requests.

Deploy to: /api/dashboard/[...path].py
"""

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.dashboard import (
    handle_request,
    DashboardData,
    get_revenue_summary,
    get_revenue_by_source,
    get_experiment_status,
    get_experiment_details,
    get_agent_health,
    get_goal_progress,
    get_profit_loss,
    get_pending_approvals,
    get_system_alerts,
    generate_api_key,
    API_VERSION
)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler."""
    
    def do_GET(self):
        self._handle_request("GET")
    
    def do_POST(self):
        self._handle_request("POST")
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()
    
    def _send_cors_headers(self):
        """Add CORS headers for browser access."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    
    def _handle_request(self, method: str):
        """Process the incoming request."""
        # Parse URL
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        
        # Get headers
        headers = {k.lower(): v for k, v in dict(self.headers).items()}
        
        # Get body for POST
        body = None
        if method == "POST":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                raw_body = self.rfile.read(content_length)
                try:
                    body = json.loads(raw_body.decode("utf-8"))
                except:
                    body = {}
        
        # Handle the request
        result = handle_request(
            method=method,
            path=path,
            headers=headers,
            query_params=query_params,
            body=body
        )
        
        # Send response
        self.send_response(result.get("status", 200))
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        
        response_body = json.dumps(result.get("body", {}), default=str)
        self.wfile.write(response_body.encode("utf-8"))


# For local testing
if __name__ == "__main__":
    from http.server import HTTPServer
    
    print("Starting JUGGERNAUT Dashboard API server...")
    print(f"API Version: {API_VERSION}")
    print(f"Test endpoint: http://localhost:8000/{API_VERSION}/overview")
    
    # Generate a test API key
    test_key = generate_api_key("local_test")
    print(f"Test API Key: {test_key}")
    
    server = HTTPServer(("0.0.0.0", 8000), handler)
    server.serve_forever()
