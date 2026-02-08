#!/usr/bin/env python3
"""
Run Migration 006: Tracked Repositories

Creates the tracked_repositories table and seeds default repo.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import execute_sql, fetch_all

def run_migration():
    print("=" * 80)
    print("RUNNING MIGRATION 006: TRACKED REPOSITORIES")
    print("=" * 80)
    
    # Read migration file
    migration_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'migrations',
        '006_tracked_repositories.sql'
    )
    
    print(f"\nReading migration from: {migration_path}")
    
    with open(migration_path, 'r') as f:
        migration_sql = f.read()
    
    print("\nExecuting migration...")
    print("-" * 80)
    
    try:
        # Split migration into separate statements
        statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
        
        for i, stmt in enumerate(statements, 1):
            if stmt:
                print(f"Executing statement {i}/{len(statements)}...")
                execute_sql(stmt)
        
        print("✅ Migration executed successfully")
        
        # Verify table was created
        print("\nVerifying table creation...")
        result = fetch_all("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = 'tracked_repositories'
        """)
        
        if result:
            print("✅ Table 'tracked_repositories' exists")
            
            # Check if default repo was seeded
            repos = fetch_all("SELECT * FROM tracked_repositories")
            print(f"\n✅ Found {len(repos)} repository(ies):")
            for repo in repos:
                print(f"   - {repo['owner']}/{repo['repo']}: {repo['display_name']}")
        else:
            print("❌ Table 'tracked_repositories' not found")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 80)
    print("MIGRATION COMPLETE")
    print("=" * 80)
    return True

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
