#!/usr/bin/env python3
"""Test the dashboard API endpoints."""

import os
import urllib.request
import json
import time
import hmac
import hashlib

# Configuration
API_BASE = "http://localhost:8000"
API_SECRET = "spartan-dashboard-secret-2025"
USER_ID = "test_user"

def generate_api_key():
    """Generate an API key for testing."""
    timestamp = str(int(time.time()))
    message = f"{USER_ID}:{timestamp}"
    signature = hmac.new(
        API_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()[:32]
    return f"jug_{USER_ID}_{timestamp}_{signature}"

def test_endpoint(endpoint, api_key):
    """Test a specific API endpoint."""
    try:
        url = f"{API_BASE}{endpoint}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        req = urllib.request.Request(url, headers=headers, method='GET')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
            
    except Exception as e:
        return {"error": str(e)}

def main():
    print("=== Testing Dashboard API Endpoints ===")
    
    # Generate API key
    api_key = generate_api_key()
    print(f"Generated API key: {api_key}")
    
    # Test endpoints
    endpoints = [
        "/health",
        "/v1/overview",
        "/v1/agent_health",
        "/v1/revenue_summary",
        "/v1/experiment_status",
        "/v1/pending_approvals",
        "/v1/system_alerts"
    ]
    
    for endpoint in endpoints:
        print(f"\nTesting {endpoint}...")
        result = test_endpoint(endpoint, api_key)
        
        if "error" in result:
            print(f"  ✗ Error: {result['error']}")
        else:
            print(f"  ✓ Success")
            if "body" in result:
                body = result["body"]
                if "success" in body and not body["success"]:
                    print(f"    ⚠ API Error: {body.get('error', 'Unknown error')}")
                elif "agents" in body:
                    agents = body.get("agents", {})
                    print(f"    Agents: {agents.get('total', 0)} total, {agents.get('online', 0)} online")
                elif "summary" in body:
                    summary = body.get("summary", {})
                    print(f"    Summary: {summary}")
                elif "revenue" in body:
                    revenue = body.get("revenue", {})
                    print(f"    Revenue (30d): ${revenue.get('net_30d', 0):,.2f}")
                else:
                    print(f"    Keys: {list(body.keys())[:5]}")

if __name__ == "__main__":
    main()
