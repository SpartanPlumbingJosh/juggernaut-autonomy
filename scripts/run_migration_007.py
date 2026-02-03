#!/usr/bin/env python3
"""
Run Migration 007: Add Progress Tracking Columns

Adds progress_message and files_analyzed columns to enable live progress tracking.
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import execute_sql, fetch_all

def run_migration():
    """Run migration 007."""
    
    try:
        print("=" * 80)
        print("MIGRATION 007: Add Progress Tracking Columns")
        print("=" * 80)
        print(f"Started at: {datetime.now().isoformat()}")
        print()
        
        # Read migration file
        migration_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'migrations',
            '007_add_progress_tracking.sql'
        )
        
        print(f"Reading migration file: {migration_file}")
        with open(migration_file, 'r') as f:
            sql = f.read()
        print("✅ Migration file loaded")
        print()
        
        # Remove comment lines and split into statements
        lines = []
        for line in sql.split('\n'):
            stripped = line.strip()
            if stripped and not stripped.startswith('--'):
                lines.append(line)
        
        clean_sql = '\n'.join(lines)
        statements = [s.strip() for s in clean_sql.split(';') if s.strip()]
        
        print(f"Executing {len(statements)} SQL statements...")
        print()
        
        for idx, statement in enumerate(statements, 1):
            if statement:
                print(f"[{idx}/{len(statements)}] Executing...")
                print(f"  {statement[:100]}...")
                execute_sql(statement)
                print(f"  ✅ Success")
                print()
        
        # Verify columns exist
        print("Verifying columns...")
        
        # Check code_analysis_runs
        code_cols = fetch_all("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'code_analysis_runs' 
            AND column_name IN ('progress_message', 'files_analyzed')
            ORDER BY column_name
        """)
        
        col_names = [row['column_name'] for row in code_cols]
        print(f"code_analysis_runs columns: {col_names}")
        if 'progress_message' in col_names and 'files_analyzed' in col_names:
            print("✅ code_analysis_runs columns verified")
        else:
            print("❌ Missing columns in code_analysis_runs")
            return False
        
        # Check log_crawler_state
        crawler_cols = fetch_all("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'log_crawler_state' 
            AND column_name = 'progress_message'
        """)
        
        crawler_col_names = [row['column_name'] for row in crawler_cols]
        print(f"log_crawler_state columns: {crawler_col_names}")
        if 'progress_message' in crawler_col_names:
            print("✅ log_crawler_state columns verified")
        else:
            print("❌ Missing columns in log_crawler_state")
            return False
        
        print()
        print("=" * 80)
        print("✅ MIGRATION 007 COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print(f"Completed at: {datetime.now().isoformat()}")
        
        return True
        
    except Exception as e:
        print()
        print("=" * 80)
        print("❌ MIGRATION FAILED")
        print("=" * 80)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
