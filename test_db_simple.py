#!/usr/bin/env python3
"""Simple database connectivity test."""

import os
import urllib.request
import json
import base64

# Database connection from user
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
DATABASE_URL = "postgresql://neondb_owner:npg_OYkCRU4aze2l@ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"

def test_connection():
    """Test basic database connectivity."""
    try:
        # Prepare headers with connection string
        headers = {
            "Content-Type": "application/json",
            "Neon-Connection-String": DATABASE_URL
        }
        
        # Simple test query
        data = json.dumps({"query": "SELECT 1 as test, NOW() as current_time"}).encode('utf-8')
        req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
        
        print("Testing Neon database connection...")
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            print("✓ Connection successful!")
            print(f"  Result: {result}")
            return True
            
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

def test_tables():
    """Test key tables exist and have data."""
    try:
        headers = {
            "Content-Type": "application/json",
            "Neon-Connection-String": DATABASE_URL
        }
        
        # Test governance_tasks
        print("\nTesting governance_tasks table...")
        data = json.dumps({"query": "SELECT status, COUNT(*) as count FROM governance_tasks GROUP BY status"}).encode('utf-8')
        req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            print("✓ governance_tasks:")
            for row in result.get("rows", []):
                print(f"  {row['status']}: {row['count']}")
        
        # Test worker_registry
        print("\nTesting worker_registry table...")
        data = json.dumps({"query": "SELECT status, COUNT(*) as count FROM worker_registry GROUP BY status"}).encode('utf-8')
        req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            print("✓ worker_registry:")
            for row in result.get("rows", []):
                print(f"  {row['status']}: {row['count']}")
        
        # Test execution_logs
        print("\nTesting execution_logs table...")
        data = json.dumps({"query": "SELECT event_type, COUNT(*) as count FROM execution_logs WHERE created_at >= NOW() - INTERVAL '24 hours' GROUP BY event_type LIMIT 5"}).encode('utf-8')
        req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            print("✓ execution_logs (last 24h):")
            for row in result.get("rows", []):
                print(f"  {row['event_type']}: {row['count']}")
        
        return True
        
    except Exception as e:
        print(f"✗ Table query failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Spartan HQ Dashboard - Database Test ===")
    
    if test_connection():
        if test_tables():
            print("\n✓ All tests passed! Dashboard API can connect to live data.")
        else:
            print("\n⚠ Connection works but some tables may be missing.")
    else:
        print("\n✗ Database connection failed. Check credentials and network.")
