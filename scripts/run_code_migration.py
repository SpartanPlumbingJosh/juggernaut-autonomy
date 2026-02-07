#!/usr/bin/env python3
"""
Run GitHub Code Crawler Migration (005_github_code_crawler.sql)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import _db

def run_migration():
    """Run the code crawler migration."""
    migration_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'migrations',
        '005_github_code_crawler.sql'
    )
    
    print(f"Reading migration file: {migration_file}")
    
    with open(migration_file, 'r') as f:
        sql = f.read()
    
    lines = sql.split('\n')
    clean_lines = []
    for line in lines:
        if '--' in line:
            line = line[:line.index('--')]
        clean_lines.append(line)
    
    clean_sql = '\n'.join(clean_lines)
    
    statements = []
    for s in clean_sql.split(';'):
        s = s.strip()
        if s and not s.startswith('--'):
            statements.append(s)
    
    print(f"Found {len(statements)} SQL statements to execute")
    
    for i, statement in enumerate(statements, 1):
        if not statement:
            continue
            
        first_line = statement.split('\n')[0][:80]
        print(f"\n[{i}/{len(statements)}] {first_line}...")
        
        try:
            result = _db.query(statement)
            print("✓ Success")
        except Exception as e:
            error_msg = str(e)
            if "already exists" in error_msg:
                print("⚠ Already exists (skipping)")
            else:
                print(f"✗ Error: {error_msg[:200]}")
                raise
    
    print("\n✅ Migration complete!")

if __name__ == "__main__":
    run_migration()
