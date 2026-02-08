#!/usr/bin/env python3
"""
Check Railway Workers via API

Checks worker status through the deployed API.
"""

import requests
import json

API_URL = "https://juggernaut-dashboard-api-production.up.railway.app"

def check_railway_workers():
    print("=" * 80)
    print("CHECKING RAILWAY WORKERS")
    print("=" * 80)
    
    # Check engine status
    print("\n1. ENGINE STATUS")
    print("-" * 80)
    try:
        response = requests.get(f"{API_URL}/api/engine/status", timeout=10)
        if response.ok:
            data = response.json()
            print(json.dumps(data, indent=2))
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Check workers
    print("\n2. WORKERS")
    print("-" * 80)
    try:
        response = requests.get(f"{API_URL}/api/engine/workers", timeout=10)
        if response.ok:
            data = response.json()
            workers = data.get('workers', [])
            if workers:
                for w in workers:
                    print(f"\n{w['worker_type']}:")
                    print(f"  Status: {w['status']}")
                    print(f"  Heartbeat: {w['last_heartbeat']}")
                    print(f"  Active Tasks: {w.get('active_tasks', 0)}")
                    print(f"  Capabilities: {w.get('capability_count', 0)}")
            else:
                print("❌ No workers found")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Check assignments
    print("\n3. TASK ASSIGNMENTS")
    print("-" * 80)
    try:
        response = requests.get(f"{API_URL}/api/engine/assignments?limit=10", timeout=10)
        if response.ok:
            data = response.json()
            assignments = data.get('assignments', [])
            if assignments:
                for a in assignments:
                    print(f"  {a['task_type']:20} -> {a.get('worker_name', 'Unknown')} ({a['status']})")
            else:
                print("No assignments found")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print("\nIf no workers are found:")
    print("  1. Check Railway logs for worker processes")
    print("  2. Verify EXECUTOR, STRATEGIST, ANALYST workers are deployed")
    print("  3. Check if workers are registering themselves on startup")
    print("\nIf workers exist but aren't picking up tasks:")
    print("  1. Check autonomy loop is running")
    print("  2. Verify task assignment logic")
    print("  3. Check worker execution loops")

if __name__ == "__main__":
    check_railway_workers()
