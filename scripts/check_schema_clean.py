#!/usr/bin/env python3
"""
Check schema issues with clean output
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import _db

def check_schema():
    """Check actual database schema."""
    
    print("\n=== CHECKING SCHEMA ISSUES ===\n")
    
    # 1. Check if worker_registry has 'name' column
    print("1. Checking worker_registry for 'name' column...")
    try:
        result = _db.query("""
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'worker_registry'
            AND column_name = 'name'
        """)
        data = json.loads(result) if isinstance(result, str) else result
        rows = data.get('rows', []) if isinstance(data, dict) else []
        
        if rows:
            print("   ✓ 'name' column exists")
            print(f"   Nullable: {rows[0].get('is_nullable', 'unknown')}")
        else:
            print("   ✗ 'name' column NOT FOUND")
    except Exception as e:
        print(f"   ✗ Error: {str(e)[:100]}")
    
    # 2. Check governance_tasks priority column type
    print("\n2. Checking governance_tasks priority column...")
    try:
        result = _db.query("""
            SELECT udt_name
            FROM information_schema.columns
            WHERE table_name = 'governance_tasks'
            AND column_name = 'priority'
        """)
        data = json.loads(result) if isinstance(result, str) else result
        rows = data.get('rows', []) if isinstance(data, dict) else []
        
        if rows:
            udt_name = rows[0].get('udt_name', 'unknown')
            print(f"   ✓ Priority column type: {udt_name}")
        else:
            print("   ✗ Priority column NOT FOUND")
    except Exception as e:
        print(f"   ✗ Error: {str(e)[:100]}")
    
    # 3. Check what priority enum exists
    print("\n3. Checking priority enum types...")
    try:
        result = _db.query("""
            SELECT typname
            FROM pg_type
            WHERE typname IN ('priority_level', 'task_priority')
        """)
        data = json.loads(result) if isinstance(result, str) else result
        rows = data.get('rows', []) if isinstance(data, dict) else []
        
        if rows:
            for row in rows:
                print(f"   ✓ Found enum: {row.get('typname', 'unknown')}")
        else:
            print("   ✗ No priority enum types found")
    except Exception as e:
        print(f"   ✗ Error: {str(e)[:100]}")
    
    # 4. Check revenue_events for amount columns
    print("\n4. Checking revenue_events amount columns...")
    try:
        result = _db.query("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'revenue_events'
            AND column_name LIKE '%amount%'
        """)
        data = json.loads(result) if isinstance(result, str) else result
        rows = data.get('rows', []) if isinstance(data, dict) else []
        
        if rows:
            for row in rows:
                print(f"   ✓ Found: {row.get('column_name', 'unknown')}")
        else:
            print("   ✗ No amount columns found")
    except Exception as e:
        print(f"   ✗ Error: {str(e)[:100]}")
    
    # 5. Check workers table exists (M5)
    print("\n5. Checking workers table (M5)...")
    try:
        result = _db.query("""
            SELECT COUNT(*) as count
            FROM information_schema.tables
            WHERE table_name = 'workers'
        """)
        data = json.loads(result) if isinstance(result, str) else result
        rows = data.get('rows', []) if isinstance(data, dict) else []
        
        if rows and rows[0].get('count', 0) > 0:
            print("   ✓ workers table exists")
        else:
            print("   ✗ workers table NOT FOUND")
    except Exception as e:
        print(f"   ✗ Error: {str(e)[:100]}")
    
    print("\n=== DIAGNOSIS COMPLETE ===\n")

if __name__ == "__main__":
    check_schema()
