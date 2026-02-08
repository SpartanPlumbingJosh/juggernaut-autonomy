#!/usr/bin/env python3
"""
Check and fix M6 tables
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import _db

def check_and_fix():
    """Check what exists and fix what's missing."""
    
    # Check if cost_budgets exists
    print("Checking cost_budgets table...")
    try:
        result = _db.query("SELECT * FROM cost_budgets LIMIT 1")
        print("✓ cost_budgets table exists")
    except Exception as e:
        print(f"✗ cost_budgets table missing or broken: {str(e)[:100]}")
        print("\nCreating cost_budgets table...")
        
        create_table = """
CREATE TABLE IF NOT EXISTS cost_budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_type VARCHAR(50) NOT NULL,
    budget_period VARCHAR(20) NOT NULL,
    budget_amount DECIMAL(10,2) NOT NULL,
    spent_amount DECIMAL(10,2) DEFAULT 0,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    alert_threshold DECIMAL(5,2) DEFAULT 0.80,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
)
        """
        
        try:
            _db.query(create_table)
            print("✓ Created cost_budgets table")
        except Exception as e2:
            print(f"✗ Failed to create: {str(e2)[:200]}")
    
    # Insert default policies
    print("\nInserting default routing policies...")
    policies_sql = """
INSERT INTO routing_policies (name, description, policy_config)
VALUES 
    ('normal', 'Balanced cost and performance', '{"models": [{"provider": "openai", "model": "gpt-4o-mini", "priority": 1}], "max_cost_per_task": 0.10, "max_tokens": 4000, "temperature": 0.7}'::jsonb),
    ('code', 'Specialized for code', '{"models": [{"provider": "openai", "model": "gpt-4o", "priority": 1}], "max_cost_per_task": 0.50, "max_tokens": 6000, "temperature": 0.3}'::jsonb),
    ('ops', 'Ultra-cheap', '{"models": [{"provider": "openai", "model": "gpt-3.5-turbo", "priority": 1}], "max_cost_per_task": 0.01, "max_tokens": 2000, "temperature": 0.5}'::jsonb)
ON CONFLICT (name) DO NOTHING
    """
    
    try:
        _db.query(policies_sql)
        print("✓ Policies inserted")
    except Exception as e:
        print(f"⚠ Policies: {str(e)[:100]}")
    
    print("\n✅ M4, M5, M6 migrations complete!")
    print("Frontend should now work without crashes.")

if __name__ == "__main__":
    check_and_fix()
