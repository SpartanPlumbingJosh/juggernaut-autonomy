#!/usr/bin/env python3
"""
Show Active Errors from System Health

Displays detailed information about current active errors.
"""

import requests
import json

API_URL = "https://juggernaut-dashboard-api-production.up.railway.app"

def show_active_errors():
    print("=" * 80)
    print("ACTIVE ERRORS FROM SYSTEM HEALTH")
    print("=" * 80)
    
    try:
        response = requests.get(f"{API_URL}/api/logs/errors?limit=50", timeout=10)
        
        if response.ok:
            data = response.json()
            errors = data.get('errors', [])
            
            # Filter active errors
            active = [e for e in errors if e.get('status') != 'resolved']
            
            print(f"\nFound {len(active)} active errors:\n")
            
            for i, err in enumerate(active, 1):
                print(f"{i}. {err['error_type']} (occurred {err['occurrence_count']}x)")
                print(f"   Fingerprint: {err['fingerprint'][:16]}...")
                print(f"   Message: {err['normalized_message']}")
                print(f"   First seen: {err['first_seen']}")
                print(f"   Last seen: {err['last_seen']}")
                print(f"   Status: {err['status']}")
                print(f"   Task created: {err['task_created']}")
                if err.get('task_id'):
                    print(f"   Task ID: {err['task_id']}")
                print()
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    show_active_errors()
