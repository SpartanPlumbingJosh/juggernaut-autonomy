#!/usr/bin/env python3
"""
Start the autonomy loop via API
"""

import os
import sys
import urllib.request
import json

# Get API URL from env or use default
API_URL = os.getenv("JUGGERNAUT_API_URL", "https://juggernaut-autonomy-production.up.railway.app")

def start_loop():
    """Start the autonomy loop."""
    
    print(f"Starting autonomy loop at {API_URL}...")
    
    url = f"{API_URL}/api/engine/start"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Content-Type", "application/json")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get("success"):
                print("✅ Autonomy loop started successfully!")
                print(f"   Message: {data.get('message')}")
            else:
                print(f"❌ Failed to start: {data.get('error')}")
                
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"❌ HTTP {e.code}: {error_body}")
    except Exception as e:
        print(f"❌ Error: {e}")

def check_status():
    """Check current autonomy loop status."""
    
    print(f"\nChecking status at {API_URL}...")
    
    url = f"{API_URL}/api/engine/status"
    req = urllib.request.Request(url)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get("success"):
                status = data.get("status", {})
                print("\n📊 Current Status:")
                print(f"   Running: {status.get('is_running')}")
                print(f"   Tasks Processed: {status.get('tasks_processed', 0)}")
                print(f"   Tasks Assigned: {status.get('tasks_assigned', 0)}")
                print(f"   Tasks Completed: {status.get('tasks_completed', 0)}")
                print(f"   Tasks Failed: {status.get('tasks_failed', 0)}")
                print(f"   Last Loop: {status.get('last_loop_at', 'Never')}")
            else:
                print(f"❌ Failed to get status: {data.get('error')}")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_status()
    print("\n" + "="*50)
    start_loop()
    print("="*50)
    
    import time
    print("\nWaiting 5 seconds for loop to start...")
    time.sleep(5)
    
    check_status()
