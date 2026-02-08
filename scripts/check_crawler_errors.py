#!/usr/bin/env python3
"""Check log crawler errors and state."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import fetch_all

def check_crawler_state():
    """Check current crawler state."""
    print("\n=== LOG CRAWLER STATE ===")
    query = """
        SELECT 
            status,
            logs_processed,
            errors_found,
            tasks_created,
            run_duration_ms,
            error_message,
            last_run,
            updated_at
        FROM log_crawler_state
        ORDER BY updated_at DESC
        LIMIT 1
    """
    result = fetch_all(query)
    if result:
        state = result[0]
        print(f"Status: {state.get('status')}")
        print(f"Logs Processed: {state.get('logs_processed')}")
        print(f"Errors Found: {state.get('errors_found')}")
        print(f"Tasks Created: {state.get('tasks_created')}")
        print(f"Duration: {state.get('run_duration_ms')}ms")
        print(f"Last Run: {state.get('last_run')}")
        print(f"Last Updated: {state.get('updated_at')}")
        if state.get('error_message'):
            print(f"\n⚠️ Last Error:\n{state.get('error_message')}")
    else:
        print("No crawler state found")

def check_error_fingerprints():
    """Check error fingerprints found by crawler."""
    print("\n\n=== ERROR FINGERPRINTS (Last 10) ===")
    query = """
        SELECT 
            fingerprint,
            error_type,
            normalized_message,
            occurrence_count,
            first_seen,
            last_seen,
            task_created,
            status
        FROM error_fingerprints
        ORDER BY last_seen DESC
        LIMIT 10
    """
    result = fetch_all(query)
    if result:
        for i, fp in enumerate(result, 1):
            print(f"\n{i}. {fp.get('error_type')} ({fp.get('occurrence_count')} occurrences)")
            print(f"   Fingerprint: {fp.get('fingerprint')[:16]}...")
            print(f"   Message: {fp.get('normalized_message')[:80]}...")
            print(f"   Task Created: {fp.get('task_created')}")
            print(f"   Status: {fp.get('status')}")
            print(f"   Last Seen: {fp.get('last_seen')}")
    else:
        print("No error fingerprints found")

def check_recent_tasks():
    """Check recently created investigation tasks."""
    print("\n\n=== INVESTIGATION TASKS (Last 5) ===")
    query = """
        SELECT 
            id,
            task_type,
            status,
            metadata->>'fingerprint_id' as fingerprint_id,
            metadata->>'error_type' as error_type,
            created_at
        FROM governance_tasks
        WHERE task_type = 'investigate_error'
        ORDER BY created_at DESC
        LIMIT 5
    """
    result = fetch_all(query)
    if result:
        for i, task in enumerate(result, 1):
            print(f"\n{i}. Task {task.get('id')[:8]}...")
            print(f"   Type: {task.get('error_type')}")
            print(f"   Status: {task.get('status')}")
            print(f"   Created: {task.get('created_at')}")
    else:
        print("No investigation tasks found")

if __name__ == "__main__":
    try:
        check_crawler_state()
        check_error_fingerprints()
        check_recent_tasks()
        print("\n✅ Check complete\n")
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
