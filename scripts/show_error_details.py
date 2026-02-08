#!/usr/bin/env python3
"""Show detailed error information from the log crawler."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import fetch_all

def show_error_details():
    """Show detailed error information with full messages and stack traces."""
    print("\n" + "="*80)
    print("ERROR FINGERPRINTS - DETAILED VIEW")
    print("="*80)
    
    query = """
        SELECT 
            fingerprint,
            error_type,
            normalized_message,
            stack_trace,
            occurrence_count,
            first_seen,
            last_seen,
            task_created,
            task_id,
            status
        FROM error_fingerprints
        ORDER BY occurrence_count DESC, last_seen DESC
        LIMIT 20
    """
    
    result = fetch_all(query)
    
    if not result:
        print("\nNo errors found in database.\n")
        return
    
    for i, error in enumerate(result, 1):
        print(f"\n{'='*80}")
        print(f"ERROR #{i}")
        print(f"{'='*80}")
        print(f"Type: {error.get('error_type')}")
        print(f"Fingerprint: {error.get('fingerprint')}")
        print(f"Occurrences: {error.get('occurrence_count')}")
        print(f"Status: {error.get('status')}")
        print(f"Task Created: {error.get('task_created')}")
        if error.get('task_id'):
            print(f"Task ID: {error.get('task_id')}")
        print(f"First Seen: {error.get('first_seen')}")
        print(f"Last Seen: {error.get('last_seen')}")
        
        print(f"\nMessage:")
        print("-" * 80)
        print(error.get('normalized_message', 'No message'))
        
        if error.get('stack_trace'):
            print(f"\nStack Trace:")
            print("-" * 80)
            print(error.get('stack_trace'))
        
        print()

def show_recent_logs():
    """Show recent Railway logs that were processed."""
    print("\n" + "="*80)
    print("RECENT RAILWAY LOGS (Last 10)")
    print("="*80)
    
    query = """
        SELECT 
            log_level,
            message,
            timestamp,
            fingerprint
        FROM railway_logs
        ORDER BY timestamp DESC
        LIMIT 10
    """
    
    result = fetch_all(query)
    
    if not result:
        print("\nNo logs found in database.\n")
        return
    
    for i, log in enumerate(result, 1):
        print(f"\n{i}. [{log.get('log_level')}] {log.get('timestamp')}")
        print(f"   Fingerprint: {log.get('fingerprint', 'None')}")
        print(f"   Message: {log.get('message', '')[:200]}...")

def show_summary():
    """Show summary statistics."""
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    
    # Total errors
    query = "SELECT COUNT(*) as count FROM error_fingerprints"
    result = fetch_all(query)
    total_errors = result[0].get('count', 0) if result else 0
    
    # Total occurrences
    query = "SELECT SUM(occurrence_count) as total FROM error_fingerprints"
    result = fetch_all(query)
    total_occurrences = result[0].get('total', 0) if result else 0
    
    # Tasks created
    query = "SELECT COUNT(*) as count FROM error_fingerprints WHERE task_created = TRUE"
    result = fetch_all(query)
    tasks_created = result[0].get('count', 0) if result else 0
    
    # By error type
    query = """
        SELECT error_type, COUNT(*) as count, SUM(occurrence_count) as occurrences
        FROM error_fingerprints
        GROUP BY error_type
        ORDER BY occurrences DESC
    """
    result = fetch_all(query)
    
    print(f"\nTotal Error Fingerprints: {total_errors}")
    print(f"Total Error Occurrences: {total_occurrences}")
    print(f"Tasks Created: {tasks_created}")
    
    print(f"\nBy Error Type:")
    for row in result:
        print(f"  {row.get('error_type')}: {row.get('count')} fingerprints, {row.get('occurrences')} occurrences")

if __name__ == "__main__":
    try:
        show_summary()
        show_error_details()
        show_recent_logs()
        print("\n" + "="*80)
        print("✅ Report complete")
        print("="*80 + "\n")
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
