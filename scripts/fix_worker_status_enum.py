#!/usr/bin/env python3
"""
Fix worker_status enum - add missing 'stopped' and 'busy' values
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import _db

def fix_worker_status():
    """Add missing values to worker_status enum."""
    
    print("Adding missing worker_status enum values...")
    
    statements = [
        "ALTER TYPE worker_status ADD VALUE IF NOT EXISTS 'stopped'",
        "ALTER TYPE worker_status ADD VALUE IF NOT EXISTS 'busy'"
    ]
    
    for stmt in statements:
        try:
            _db.query(stmt)
            print(f"✓ {stmt}")
        except Exception as e:
            error_msg = str(e)
            if "already exists" in error_msg or "duplicate" in error_msg:
                print(f"⚠ Value already exists (skipping)")
            else:
                print(f"✗ Error: {error_msg[:200]}")
    
    print("\n✅ worker_status enum fixed!")

if __name__ == "__main__":
    fix_worker_status()
