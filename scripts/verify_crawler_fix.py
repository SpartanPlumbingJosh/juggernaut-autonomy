#!/usr/bin/env python3
"""Verify the log crawler fix is working after deployment."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import fetch_all
from datetime import datetime, timezone

def check_crawler_state():
    """Check current crawler state."""
    print("\n" + "="*80)
    print("LOG CRAWLER STATE")
    print("="*80)
    
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
        print(f"\nStatus: {state.get('status')}")
        print(f"Last Run: {state.get('last_run')}")
        print(f"Updated: {state.get('updated_at')}")
        print(f"Logs Processed: {state.get('logs_processed')}")
        print(f"Errors Found: {state.get('errors_found')}")
        print(f"Tasks Created: {state.get('tasks_created')}")
        print(f"Duration: {state.get('run_duration_ms')}ms")
        
        if state.get('error_message'):
            print("\n⚠️ Error Message:")
            print(state.get('error_message'))
        else:
            print("\n✅ No errors")
            
        # Check if recently run
        if state.get('last_run'):
            last_run = state.get('last_run')
            if isinstance(last_run, str):
                from dateutil import parser
                last_run = parser.parse(last_run)
            
            now = datetime.now(timezone.utc)
            if last_run.tzinfo is None:
                last_run = last_run.replace(tzinfo=timezone.utc)
                
            minutes_ago = (now - last_run).total_seconds() / 60
            print(f"\nLast run was {minutes_ago:.1f} minutes ago")
            
            if minutes_ago > 15:
                print("⚠️ Crawler hasn't run in over 15 minutes")
            else:
                print("✅ Crawler is running regularly")
    else:
        print("\n❌ No crawler state found")

def check_tasks_created():
    """Check if tasks were created."""
    print("\n" + "="*80)
    print("INVESTIGATION TASKS CREATED")
    print("="*80)
    
    query = """
        SELECT 
            id,
            task_type,
            status,
            priority,
            metadata->>'fingerprint_id' as fingerprint_id,
            metadata->>'error_type' as error_type,
            metadata->>'occurrence_count' as occurrence_count,
            created_at
        FROM governance_tasks
        WHERE task_type = 'investigate_error'
        ORDER BY created_at DESC
        LIMIT 10
    """
    
    result = fetch_all(query)
    
    if result:
        print(f"\n✅ Found {len(result)} investigation tasks")
        for i, task in enumerate(result, 1):
            print(f"\n{i}. Task {task.get('id')[:8]}...")
            print(f"   Type: {task.get('error_type')}")
            print(f"   Priority: {task.get('priority')}")
            print(f"   Status: {task.get('status')}")
            print(f"   Occurrences: {task.get('occurrence_count')}")
            print(f"   Created: {task.get('created_at')}")
    else:
        print("\n❌ No investigation tasks found")
        print("This might mean:")
        print("  - Crawler hasn't run yet after deployment")
        print("  - No new errors detected")
        print("  - Task creation is still failing")

def check_error_fingerprints():
    """Check error fingerprints."""
    print("\n" + "="*80)
    print("ERROR FINGERPRINTS")
    print("="*80)
    
    query = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN task_created = TRUE THEN 1 ELSE 0 END) as with_tasks,
            SUM(CASE WHEN task_created = FALSE THEN 1 ELSE 0 END) as without_tasks
        FROM error_fingerprints
    """
    
    result = fetch_all(query)
    
    if result:
        stats = result[0]
        total = int(stats.get('total', 0) or 0)
        with_tasks = int(stats.get('with_tasks', 0) or 0)
        without_tasks = int(stats.get('without_tasks', 0) or 0)
        
        print(f"\nTotal Fingerprints: {total}")
        print(f"With Tasks: {with_tasks}")
        print(f"Without Tasks: {without_tasks}")
        
        if total > 0:
            percentage = (with_tasks / total) * 100
            print(f"Task Creation Rate: {percentage:.1f}%")
            
            if percentage == 0:
                print("\n❌ No tasks created for any errors")
            elif percentage < 50:
                print("\n⚠️ Less than half of errors have tasks")
            else:
                print("\n✅ Most errors have tasks created")

def check_execution_logs():
    """Check if execution_logs has recent error/warn logs."""
    print("\n" + "="*80)
    print("EXECUTION LOGS (Source Data)")
    print("="*80)
    
    query = """
        SELECT 
            level,
            COUNT(*) as count
        FROM execution_logs
        WHERE created_at > NOW() - INTERVAL '1 hour'
        GROUP BY level
        ORDER BY count DESC
    """
    
    result = fetch_all(query)
    
    if result:
        print("\nLogs in last hour:")
        for row in result:
            print(f"  {row.get('level')}: {row.get('count')}")
            
        # Check for errors
        error_query = """
            SELECT COUNT(*) as count
            FROM execution_logs
            WHERE level IN ('error', 'warn')
            AND created_at > NOW() - INTERVAL '1 hour'
        """
        error_result = fetch_all(error_query)
        error_count = error_result[0].get('count', 0) if error_result else 0
        
        print(f"\nTotal error/warn logs: {error_count}")
        
        if error_count == 0:
            print("✅ No errors in last hour - system is healthy!")
        else:
            print(f"⚠️ {error_count} error/warn logs available for processing")
    else:
        print("\n❌ No logs found in last hour")

def main():
    """Run all checks."""
    print("\n" + "="*80)
    print("LOG CRAWLER FIX VERIFICATION")
    print("="*80)
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    
    try:
        check_execution_logs()
        check_crawler_state()
        check_error_fingerprints()
        check_tasks_created()
        
        print("\n" + "="*80)
        print("VERIFICATION COMPLETE")
        print("="*80)
        print("\nNext steps:")
        print("1. If crawler hasn't run recently, trigger manual crawl")
        print("2. If no tasks created, check Railway logs for errors")
        print("3. If tasks created, verify they contain correct error info")
        print()
        
    except Exception as e:
        print(f"\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
