import urllib.request
import json
import sys

NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
DATABASE_URL = "postgresql://neondb_owner:npg_OYkCRU4aze2l@ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"

def test_connection():
    try:
        headers = {
            "Content-Type": "application/json",
            "Neon-Connection-String": DATABASE_URL
        }
        data = json.dumps({"query": "SELECT 1 as test, NOW() as current_time"}).encode('utf-8')
        req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
        
        print("Testing Neon database connection...")
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            print("✓ Connection successful!")
            print(f"  Current time: {result['rows'][0]['current_time']}")
            return True
            
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

def test_tables():
    try:
        headers = {
            "Content-Type": "application/json",
            "Neon-Connection-String": DATABASE_URL
        }
        
        # Test governance_tasks
        print("\nChecking governance_tasks...")
        data = json.dumps({"query": "SELECT status, COUNT(*) as count FROM governance_tasks GROUP BY status"}).encode('utf-8')
        req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            print("  Status counts:")
            for row in result.get("rows", []):
                print(f"    {row['status']}: {row['count']}")
        
        # Test worker_registry
        print("\nChecking worker_registry...")
        data = json.dumps({"query": "SELECT status, COUNT(*) as count FROM worker_registry GROUP BY status"}).encode('utf-8')
        req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            print("  Status counts:")
            for row in result.get("rows", []):
                print(f"    {row['status']}: {row['count']}")
        
        # Test execution_logs
        print("\nChecking execution_logs (last 24h)...")
        data = json.dumps({"query": "SELECT event_type, COUNT(*) as count FROM execution_logs WHERE created_at >= NOW() - INTERVAL '24 hours' GROUP BY event_type LIMIT 5"}).encode('utf-8')
        req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            print("  Event types:")
            for row in result.get("rows", []):
                print(f"    {row['event_type']}: {row['count']}")
        
        return True
        
    except Exception as e:
        print(f"✗ Table query failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Spartan HQ Dashboard - Database Verification ===")
    
    if test_connection():
        if test_tables():
            print("\n✓ Database connection is working! Dashboard can show live data.")
            print("\nNext steps:")
            print("1. Set DASHBOARD_API_SECRET environment variable")
            print("2. Run: python dashboard_api_main.py")
            print("3. Access endpoints at http://localhost:8000/v1/overview")
        else:
            print("\n⚠ Connection works but tables may be missing.")
    else:
        print("\n✗ Database connection failed. Check credentials and network.")
