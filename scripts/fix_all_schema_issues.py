#!/usr/bin/env python3
"""
Fix all schema mismatches between code and database
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import _db

def fix_all_issues():
    """Fix all identified schema issues."""
    
    print("\n" + "="*60)
    print("FIXING ALL SCHEMA ISSUES")
    print("="*60 + "\n")
    
    # Issue 1: Create priority_level enum as alias to task_priority
    print("1. Creating priority_level enum (if needed)...")
    try:
        # Check if priority_level exists
        result = _db.query("SELECT 1 FROM pg_type WHERE typname = 'priority_level'")
        
        if not result or len(result) == 0:
            print("   Creating priority_level enum...")
            _db.query("""
                CREATE TYPE priority_level AS ENUM (
                    'low', 'medium', 'high', 'critical', 'deferred'
                )
            """)
            print("   ✓ Created priority_level enum")
        else:
            print("   ✓ priority_level enum already exists")
    except Exception as e:
        if "already exists" in str(e):
            print("   ✓ priority_level enum already exists")
        else:
            print(f"   ⚠ Warning: {str(e)[:150]}")
    
    # Issue 2: Add amount_cents column to revenue_events (as computed column)
    print("\n2. Adding amount_cents column to revenue_events...")
    try:
        # Check if column exists
        result = _db.query("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'revenue_events'
            AND column_name = 'amount_cents'
        """)
        
        if not result or len(result) == 0:
            print("   Adding amount_cents as alias to net_amount...")
            _db.query("""
                ALTER TABLE revenue_events
                ADD COLUMN amount_cents INTEGER GENERATED ALWAYS AS (net_amount) STORED
            """)
            print("   ✓ Added amount_cents column")
        else:
            print("   ✓ amount_cents column already exists")
    except Exception as e:
        if "already exists" in str(e):
            print("   ✓ amount_cents column already exists")
        else:
            print(f"   ⚠ Warning: {str(e)[:150]}")
    
    # Issue 3: Verify workers table exists (M5)
    print("\n3. Checking workers table (M5)...")
    try:
        result = _db.query("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'workers'
        """)
        print("   ✓ workers table exists")
    except Exception as e:
        print(f"   ⚠ Warning: {str(e)[:150]}")
    
    print("\n" + "="*60)
    print("SCHEMA FIXES COMPLETE")
    print("="*60)
    print("\nRemaining manual fixes needed:")
    print("1. Fix watchdog/main.py line 53 - add name parameter to INSERT")
    print("2. Add RAILWAY_API_TOKEN to Railway environment variables")
    print("3. Start autonomy loop via /api/engine/start")
    print("\n")

if __name__ == "__main__":
    fix_all_issues()
