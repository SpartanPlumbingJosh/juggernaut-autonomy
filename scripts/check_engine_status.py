#!/usr/bin/env python3
"""
Check Engine Status and Task Assignment

Diagnoses why workers aren't picking up tasks.
"""

import os
from core.database import fetch_all

def check_engine_status():
    """Check engine and worker status."""
    print("=" * 80)
    print("ENGINE STATUS CHECK")
    print("=" * 80)
    
    # Check engine status
    print("\n1. ENGINE STATUS")
    print("-" * 80)
    engine_query = """
        SELECT status, started_at, last_heartbeat
        FROM engine_status
        ORDER BY last_heartbeat DESC
        LIMIT 1
    """
    engine = fetch_all(engine_query)
    if engine:
        e = engine[0]
        print(f"Status: {e['status']}")
        print(f"Started: {e['started_at']}")
        print(f"Last Heartbeat: {e['last_heartbeat']}")
    else:
        print("❌ No engine status found")
    
    # Check workers
    print("\n2. WORKER STATUS")
    print("-" * 80)
    worker_query = """
        SELECT 
            worker_type,
            status,
            last_heartbeat,
            current_task_id,
            tasks_completed
        FROM workers
        ORDER BY worker_type
    """
    workers = fetch_all(worker_query)
    if workers:
        for w in workers:
            print(f"\n{w['worker_type']}:")
            print(f"  Status: {w['status']}")
            print(f"  Last Heartbeat: {w['last_heartbeat']}")
            print(f"  Current Task: {w['current_task_id'] or 'None'}")
            print(f"  Tasks Completed: {w['tasks_completed']}")
    else:
        print("❌ No workers found")
    
    # Check pending tasks
    print("\n3. PENDING TASKS")
    print("-" * 80)
    pending_query = """
        SELECT 
            task_type,
            priority,
            COUNT(*) as count
        FROM governance_tasks
        WHERE status = 'pending'
        GROUP BY task_type, priority
        ORDER BY priority DESC, task_type
    """
    pending = fetch_all(pending_query)
    if pending:
        total = 0
        for p in pending:
            count = int(p['count'])
            total += count
            print(f"  {p['task_type']} (priority {p['priority']}): {count}")
        print(f"\nTotal pending: {total}")
    else:
        print("✅ No pending tasks")
    
    # Check assigned tasks
    print("\n4. ASSIGNED TASKS")
    print("-" * 80)
    assigned_query = """
        SELECT 
            id,
            task_type,
            assigned_to,
            assigned_at,
            status
        FROM governance_tasks
        WHERE status = 'assigned'
        ORDER BY assigned_at DESC
        LIMIT 10
    """
    assigned = fetch_all(assigned_query)
    if assigned:
        print(f"Found {len(assigned)} assigned tasks:")
        for a in assigned:
            print(f"  {a['id'][:8]}... {a['task_type']} -> {a['assigned_to']} ({a['assigned_at']})")
    else:
        print("No assigned tasks")
    
    # Check in_progress tasks
    print("\n5. IN-PROGRESS TASKS")
    print("-" * 80)
    progress_query = """
        SELECT 
            id,
            task_type,
            assigned_to,
            started_at
        FROM governance_tasks
        WHERE status = 'in_progress'
        ORDER BY started_at DESC
        LIMIT 10
    """
    progress = fetch_all(progress_query)
    if progress:
        print(f"Found {len(progress)} in-progress tasks:")
        for p in progress:
            print(f"  {p['id'][:8]}... {p['task_type']} -> {p['assigned_to']} ({p['started_at']})")
    else:
        print("No in-progress tasks")
    
    # Check recent completions
    print("\n6. RECENT COMPLETIONS")
    print("-" * 80)
    completed_query = """
        SELECT 
            task_type,
            completed_at,
            result
        FROM governance_tasks
        WHERE status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 5
    """
    completed = fetch_all(completed_query)
    if completed:
        for c in completed:
            result = c.get('result', {})
            if isinstance(result, str):
                import json
                try:
                    result = json.loads(result)
                except:
                    pass
            success = result.get('success', False) if isinstance(result, dict) else False
            print(f"  {c['task_type']}: {c['completed_at']} - {'✅' if success else '❌'}")
    else:
        print("No completed tasks")
    
    # Check task assignments table
    print("\n7. TASK ASSIGNMENTS")
    print("-" * 80)
    assignments_query = """
        SELECT 
            worker_type,
            COUNT(*) as assigned_count
        FROM task_assignments
        GROUP BY worker_type
    """
    assignments = fetch_all(assignments_query)
    if assignments:
        for a in assignments:
            print(f"  {a['worker_type']}: {a['assigned_count']} assignments")
    else:
        print("No task assignments found")
    
    # Check orchestrator state
    print("\n8. ORCHESTRATOR STATE")
    print("-" * 80)
    orch_query = """
        SELECT 
            last_assignment_check,
            tasks_assigned_today,
            last_error
        FROM orchestrator_state
        ORDER BY last_assignment_check DESC
        LIMIT 1
    """
    orch = fetch_all(orch_query)
    if orch:
        o = orch[0]
        print(f"Last Assignment Check: {o['last_assignment_check']}")
        print(f"Tasks Assigned Today: {o['tasks_assigned_today']}")
        if o['last_error']:
            print(f"Last Error: {o['last_error']}")
    else:
        print("❌ No orchestrator state found")
    
    print("\n" + "=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)
    
    # Diagnose issues
    if not engine:
        print("❌ Engine not running - start the engine first")
    elif engine[0]['status'] != 'running':
        print(f"❌ Engine status is '{engine[0]['status']}' - should be 'running'")
    
    if not workers:
        print("❌ No workers registered - workers not started")
    else:
        idle_workers = [w for w in workers if w['status'] == 'idle' and not w['current_task_id']]
        if idle_workers and pending:
            print(f"⚠️  {len(idle_workers)} idle workers but {sum(int(p['count']) for p in pending)} pending tasks")
            print("   → Task assignment may not be working")
    
    if assigned and not progress:
        print("⚠️  Tasks are assigned but none in progress")
        print("   → Workers may not be picking up assigned tasks")
    
    if not orch:
        print("❌ No orchestrator state - ORCHESTRATOR worker may not be running")

if __name__ == "__main__":
    check_engine_status()
