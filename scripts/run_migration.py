#!/usr/bin/env python3
"""
Run Database Migration

Executes SQL migration files against the database.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import execute_sql


def run_migration(migration_file: str):
    """Run a migration file."""
    print(f"Running migration: {migration_file}")
    
    # Read migration file
    with open(migration_file, 'r') as f:
        sql = f.read()
    
    # Split into individual statements
    statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
    
    # Execute each statement
    for i, statement in enumerate(statements, 1):
        try:
            print(f"  Executing statement {i}/{len(statements)}...")
            execute_sql(statement)
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False
    
    print("✅ Migration completed successfully")
    return True


if __name__ == "__main__":
    migration_path = "migrations/001_chat_control_plane.sql"
    
    if not os.path.exists(migration_path):
        print(f"❌ Migration file not found: {migration_path}")
        sys.exit(1)
    
    success = run_migration(migration_path)
    sys.exit(0 if success else 1)
