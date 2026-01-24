#!/usr/bin/env python3
"""Test script to verify dashboard API connectivity to live Neon DB."""

import os
import json
from api.dashboard import DashboardData, get_agent_health, query_db

# Set required environment variable
os.environ['DASHBOARD_API_SECRET'] = 'test-secret'

def test_db_connection():
    """Test basic database connectivity."""
    try:
        result = query_db("SELECT 1 as test")
        print("✓ Database connection successful")
        print(f"  Result: {result}")
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False

def test_governance_tasks():
    """Test governance_tasks table access."""
    try:
        sql = """
            SELECT 
                status,
                COUNT(*) as count
            FROM governance_tasks
            GROUP BY status
            ORDER BY count DESC
        """
        result = query_db(sql)
        print("\n✓ governance_tasks summary:")
        for row in result.get("rows", []):
            print(f"  {row['status']}: {row['count']}")
        return True
    except Exception as e:
        print(f"✗ governance_tasks query failed: {e}")
        return False

def test_worker_registry():
    """Test worker_registry table access."""
    try:
        sql = """
            SELECT 
                status,
                COUNT(*) as count
            FROM worker_registry
            GROUP BY status
            ORDER BY count DESC
        """
        result = query_db(sql)
        print("\n✓ worker_registry summary:")
        for row in result.get("rows", []):
            print(f"  {row['status']}: {row['count']}")
        return True
    except Exception as e:
        print(f"✗ worker_registry query failed: {e}")
        return False

def test_execution_logs():
    """Test execution_logs table access."""
    try:
        sql = """
            SELECT 
                event_type,
                COUNT(*) as count
            FROM execution_logs
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY event_type
            ORDER BY count DESC
            LIMIT 10
        """
        result = query_db(sql)
        print("\n✓ execution_logs (last 24h):")
        for row in result.get("rows", []):
            print(f"  {row['event_type']}: {row['count']}")
        return True
    except Exception as e:
        print(f"✗ execution_logs query failed: {e}")
        return False

def test_dashboard_overview():
    """Test the main dashboard overview endpoint."""
    try:
        overview = DashboardData.get_overview()
        print("\n✓ Dashboard Overview:")
        print(f"  Timestamp: {overview.get('timestamp')}")
        print(f"  Agents: {overview.get('agents', {}).get('total', 0)} total, {overview.get('agents', {}).get('online', 0)} online")
        print(f"  Tasks (7d): {overview.get('tasks', {})}")
        return True
    except Exception as e:
        print(f"✗ Dashboard overview failed: {e}")
        return False

def test_agent_health():
    """Test agent health endpoint."""
    try:
        health = get_agent_health()
        print("\n✓ Agent Health:")
        if health.get("success"):
            summary = health.get("summary", {})
            print(f"  Total agents: {summary.get('total_agents', 0)}")
            print(f"  Online: {summary.get('online', 0)}")
            print(f"  Average success rate: {summary.get('average_success_rate', 0)}%")
            print(f"  Stale heartbeats: {summary.get('stale_heartbeats', 0)}")
        else:
            print(f"  Error: {health.get('error')}")
        return health.get("success", False)
    except Exception as e:
        print(f"✗ Agent health failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Testing Dashboard API Connection to Live Neon DB ===")
    
    tests = [
        test_db_connection,
        test_governance_tasks,
        test_worker_registry,
        test_execution_logs,
        test_dashboard_overview,
        test_agent_health
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n=== Results: {passed}/{len(tests)} tests passed ===")
    
    if passed == len(tests):
        print("✓ Dashboard API is successfully connected to live Neon database!")
        print("You can now start the dashboard API server:")
        print("  python dashboard_api_main.py")
    else:
        print("✗ Some tests failed. Check the errors above.")
