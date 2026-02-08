#!/usr/bin/env python3
"""
Fix routing migration indexes
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import _db

def fix_indexes():
    """Create the remaining indexes and insert default data."""
    
    statements = [
        "CREATE INDEX IF NOT EXISTS idx_budgets_period ON cost_budgets(budget_period, period_start DESC)",
        "CREATE INDEX IF NOT EXISTS idx_budgets_active ON cost_budgets(is_active, budget_period)",
        "COMMENT ON TABLE routing_policies IS 'Model selection policies for different task types'",
        "COMMENT ON TABLE model_selections IS 'Tracks which model was used for each task'",
        "COMMENT ON TABLE model_performance IS 'Aggregated performance metrics per model'",
        "COMMENT ON TABLE cost_budgets IS 'Budget tracking and enforcement'",
        """INSERT INTO routing_policies (name, description, policy_config)
VALUES 
    (
        'normal',
        'Balanced cost and performance for general tasks',
        '{"models": [{"provider": "openai", "model": "gpt-4o-mini", "priority": 1}, {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022", "priority": 2}], "max_cost_per_task": 0.10, "max_tokens": 4000, "temperature": 0.7}'::jsonb
    ),
    (
        'deep_research',
        'Maximum intelligence for complex analysis',
        '{"models": [{"provider": "openai", "model": "gpt-4o", "priority": 1}, {"provider": "anthropic", "model": "claude-3-opus-20240229", "priority": 2}], "max_cost_per_task": 1.00, "max_tokens": 8000, "temperature": 0.7}'::jsonb
    ),
    (
        'code',
        'Specialized for code analysis and debugging',
        '{"models": [{"provider": "openai", "model": "gpt-4o", "priority": 1}, {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022", "priority": 2}], "max_cost_per_task": 0.50, "max_tokens": 6000, "temperature": 0.3}'::jsonb
    ),
    (
        'ops',
        'Ultra-cheap for simple operational tasks',
        '{"models": [{"provider": "openai", "model": "gpt-3.5-turbo", "priority": 1}, {"provider": "anthropic", "model": "claude-3-haiku-20240307", "priority": 2}], "max_cost_per_task": 0.01, "max_tokens": 2000, "temperature": 0.5}'::jsonb
    )
ON CONFLICT (name) DO NOTHING""",
        """INSERT INTO cost_budgets (budget_type, budget_period, budget_amount, period_start, period_end)
VALUES (
    'total',
    'daily',
    10.00,
    DATE_TRUNC('day', NOW()),
    DATE_TRUNC('day', NOW() + INTERVAL '1 day')
)"""
    ]
    
    for i, statement in enumerate(statements, 1):
        print(f"\n[{i}/{len(statements)}] Executing...")
        
        try:
            result = _db.query(statement)
            print(f"✓ Success")
        except Exception as e:
            error_msg = str(e)
            if "already exists" in error_msg or "duplicate key" in error_msg:
                print(f"⚠ Already exists (skipping)")
            else:
                print(f"✗ Error: {error_msg[:200]}")
    
    print("\n✅ Complete!")

if __name__ == "__main__":
    fix_indexes()
