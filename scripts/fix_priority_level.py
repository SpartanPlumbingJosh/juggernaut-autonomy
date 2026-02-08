#!/usr/bin/env python3
"""
Fix priority_level type error
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import _db

def fix_priority_level():
    """Create the missing priority_level type."""
    
    # Check if type exists
    print("Checking if priority_level type exists...")
    try:
        result = _db.query("SELECT 1 FROM pg_type WHERE typname = 'priority_level'")
        if result:
            print("✓ priority_level type already exists")
            return
    except Exception as e:
        print(f"Checking type: {str(e)[:100]}")
    
    # Create the enum type
    print("\nCreating priority_level enum type...")
    create_type = """
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'priority_level') THEN
        CREATE TYPE priority_level AS ENUM ('low', 'medium', 'high', 'critical');
    END IF;
END $$;
    """
    
    try:
        _db.query(create_type)
        print("✓ Created priority_level type")
    except Exception as e:
        print(f"✗ Error: {str(e)[:200]}")
        
        # Try alternative approach - just create it directly
        print("\nTrying direct creation...")
        try:
            _db.query("CREATE TYPE priority_level AS ENUM ('low', 'medium', 'high', 'critical')")
            print("✓ Created priority_level type (direct)")
        except Exception as e2:
            if "already exists" in str(e2):
                print("✓ Type already exists")
            else:
                print(f"✗ Failed: {str(e2)[:200]}")
    
    print("\n✅ priority_level type fixed!")

if __name__ == "__main__":
    fix_priority_level()
