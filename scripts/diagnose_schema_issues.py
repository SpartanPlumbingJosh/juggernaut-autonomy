#!/usr/bin/env python3
"""
Diagnose schema issues - check what actually exists in the database
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import _db

def check_schema():
    """Check actual database schema."""
    
    print("=" * 60)
    print("SCHEMA DIAGNOSIS")
    print("=" * 60)
    
    # Check worker_registry columns
    print("\n1. worker_registry table columns:")
    try:
        result = _db.query("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'worker_registry'
            ORDER BY ordinal_position
        """)
        if result:
            for row in result:
                nullable = "NULL" if row[2] == 'YES' else "NOT NULL"
                print(f"   - {row[0]}: {row[1]} ({nullable})")
        else:
            print("   ✗ Table not found or no columns")
    except Exception as e:
        print(f"   ✗ Error: {str(e)[:200]}")
    
    # Check governance_tasks priority column
    print("\n2. governance_tasks priority column:")
    try:
        result = _db.query("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'governance_tasks'
            AND column_name = 'priority'
        """)
        if result and len(result) > 0:
            print(f"   Column: {result[0][0]}")
            print(f"   Type: {result[0][1]}")
            print(f"   UDT: {result[0][2]}")
        else:
            print("   ✗ Priority column not found")
    except Exception as e:
        print(f"   ✗ Error: {str(e)[:200]}")
    
    # Check what enum types exist
    print("\n3. Enum types in database:")
    try:
        result = _db.query("""
            SELECT t.typname, e.enumlabel
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname IN ('priority_level', 'task_priority', 'worker_status')
            ORDER BY t.typname, e.enumsortorder
        """)
        if result:
            current_type = None
            for row in result:
                if row[0] != current_type:
                    current_type = row[0]
                    print(f"\n   {current_type}:")
                print(f"      - {row[1]}")
        else:
            print("   ✗ No enum types found")
    except Exception as e:
        print(f"   ✗ Error: {str(e)[:200]}")
    
    # Check revenue_events columns
    print("\n4. revenue_events table columns:")
    try:
        result = _db.query("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'revenue_events'
            AND column_name LIKE '%amount%'
            ORDER BY ordinal_position
        """)
        if result:
            for row in result:
                print(f"   - {row[0]}: {row[1]}")
        else:
            print("   ✗ No amount columns found")
    except Exception as e:
        print(f"   ✗ Error: {str(e)[:200]}")
    
    # Check workers table (M5)
    print("\n5. workers table (M5) columns:")
    try:
        result = _db.query("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'workers'
            ORDER BY ordinal_position
        """)
        if result:
            for row in result:
                nullable = "NULL" if row[2] == 'YES' else "NOT NULL"
                print(f"   - {row[0]}: {row[1]} ({nullable})")
        else:
            print("   ✗ Table not found")
    except Exception as e:
        print(f"   ✗ Error: {str(e)[:200]}")
    
    print("\n" + "=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    check_schema()
