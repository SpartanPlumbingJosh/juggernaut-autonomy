#!/usr/bin/env python3
"""
Diagnose Autonomy Engine Issues

Checks why workers aren't picking up tasks.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import fetch_all

def main():
    print("=" * 80)
    print("AUTONOMY ENGINE DIAGNOSTICS")
    print("=" * 80)
    
    # 1. Check workers
    print("\n1. WORKERS STATUS")
    print("-" * 80)
    workers = fetch_all("""
        SELECT worker_id, worker_type, status, last_heartbeat, current_task_id
        FROM workers
        ORDER BY worker_type
    """)
    
    if workers:
        for w in workers:
            print(f"{w['worker_type']:15} | {w['status']:10} | Heartbeat: {w['last_heartbeat']} | Task: {w['current_task_id'] or 'None'}")
    else:
        print("❌ No workers found")
    
    # 2. Check pending tasks
    print("\n2. PENDING TASKS")
    print("-" * 80)
    pending = fetch_all("""
        SELECT task_type, priority, COUNT(*) as count
        FROM governance_tasks
        WHERE status = 'pending'
        GROUP BY task_type, priority
        ORDER BY priority DESC
    """)
    
    if pending:
        total = sum(int(p['count']) for p in pending)
        for p in pending:
            print(f"  {p['task_type']:20} Priority {p['priority']}: {p['count']}")
        print(f"\n  Total: {total} pending tasks")
    else:
        print("✅ No pending tasks")
    
    # 3. Check assigned tasks
    print("\n3. ASSIGNED TASKS")
    print("-" * 80)
    assigned = fetch_all("""
        SELECT t.id, t.task_type, t.status, t.assigned_to, t.assigned_at
        FROM governance_tasks t
        WHERE status = 'assigned'
        ORDER BY assigned_at DESC
        LIMIT 10
    """)
    
    if assigned:
        print(f"Found {len(assigned)} assigned tasks:")
        for a in assigned:
            print(f"  {a['id'][:8]}... {a['task_type']:20} -> {a['assigned_to']} ({a['assigned_at']})")
    else:
        print("No assigned tasks")
    
    # 4. Check in-progress tasks
    print("\n4. IN-PROGRESS TASKS")
    print("-" * 80)
    in_progress = fetch_all("""
        SELECT t.id, t.task_type, t.assigned_to, t.started_at
        FROM governance_tasks t
        WHERE status = 'in_progress'
        ORDER BY started_at DESC
        LIMIT 10
    """)
    
    if in_progress:
        print(f"Found {len(in_progress)} in-progress tasks:")
        for p in in_progress:
            print(f"  {p['id'][:8]}... {p['task_type']:20} -> {p['assigned_to']} ({p['started_at']})")
    else:
        print("No in-progress tasks")
    
    # 5. Check task assignments table
    print("\n5. TASK ASSIGNMENTS")
    print("-" * 80)
    assignments = fetch_all("""
        SELECT 
            ta.status,
            COUNT(*) as count
        FROM task_assignments ta
        GROUP BY ta.status
    """)
    
    if assignments:
        for a in assignments:
            print(f"  {a['status']:15}: {a['count']}")
    else:
        print("No task assignments found")
    
    # 6. Check recent activity
    print("\n6. RECENT COMPLETIONS (last 5)")
    print("-" * 80)
    completed = fetch_all("""
        SELECT task_type, completed_at
        FROM governance_tasks
        WHERE status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 5
    """)
    
    if completed:
        for c in completed:
            print(f"  {c['task_type']:20} at {c['completed_at']}")
    else:
        print("No completed tasks")
    
    # 7. Diagnosis
    print("\n" + "=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)
    
    if not workers:
        print("❌ CRITICAL: No workers registered")
        print("   → Workers need to be started")
    else:
        idle_workers = [w for w in workers if w['status'] == 'idle']
        busy_workers = [w for w in workers if w['status'] == 'busy']
        
        print(f"✅ {len(workers)} workers registered")
        print(f"   - {len(idle_workers)} idle")
        print(f"   - {len(busy_workers)} busy")
        
        if idle_workers and pending:
            print(f"\n⚠️  ISSUE: {len(idle_workers)} idle workers but {sum(int(p['count']) for p in pending)} pending tasks")
            print("   → Task assignment/routing may not be working")
            print("   → Check if autonomy loop is running")
        
        if assigned and not in_progress:
            print(f"\n⚠️  ISSUE: {len(assigned)} tasks assigned but none in progress")
            print("   → Workers may not be picking up assigned tasks")
            print("   → Check worker execution logic")
    
    # 8. Check autonomy loop status
    print("\n8. AUTONOMY LOOP CHECK")
    print("-" * 80)
    print("To check if autonomy loop is running:")
    print("  curl http://localhost:8000/api/engine/status")
    print("\nTo start autonomy loop:")
    print("  curl -X POST http://localhost:8000/api/engine/start")

if __name__ == "__main__":
    main()
