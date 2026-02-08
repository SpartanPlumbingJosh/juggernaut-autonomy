"""
Test script for L4-02: Sandboxed Innovation Boundaries

EVIDENCE REQUIRED: High-risk experiment blocked, low-risk allowed

This script demonstrates:
1. Low-risk experiment ($5, test scope) - ALLOWED
2. High-risk experiment ($100, production scope) - BLOCKED without approval
3. Approved high-risk experiment - ALLOWED

Run with: python tests/test_sandbox.py
"""

import json
import logging
import sys
import uuid
from typing import Any, Dict

# Add parent to path for imports
sys.path.insert(0, ".")

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Database configuration — from environment only (no hardcoded credentials)
NEON_ENDPOINT = os.environ.get("NEON_HTTP_ENDPOINT", "")
NEON_CONNECTION_STRING = os.environ.get("DATABASE_URL", "")


def execute_sql(query: str) -> Dict[str, Any]:
    """Execute SQL query against Neon database."""
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": NEON_CONNECTION_STRING,
    }
    response = httpx.post(
        NEON_ENDPOINT,
        json={"query": query},
        headers=headers,
        timeout=30.0,
    )
    return response.json()


def create_test_experiment(
    name: str,
    budget_limit: float,
    risk_level: str,
    sandbox_config: Dict[str, Any],
    requires_approval: bool,
    approved_by: str | None = None,
) -> str:
    """Create a test experiment with specified parameters."""
    experiment_id = str(uuid.uuid4())
    
    approved_by_sql = f"'{approved_by}'" if approved_by else "NULL"
    approved_at_sql = "NOW()" if approved_by else "NULL"
    
    query = f"""
    INSERT INTO experiments (
        id, name, description, experiment_type, status,
        hypothesis, success_criteria, budget_limit, budget_spent,
        max_iterations, current_iteration, owner_worker,
        risk_level, sandbox_config, requires_approval,
        approved_by, approved_at, created_by
    ) VALUES (
        '{experiment_id}',
        '{name}',
        'Test experiment for sandbox validation',
        'test',
        'draft',
        'Test hypothesis',
        '{{"metric": "test"}}'::jsonb,
        {budget_limit},
        0,
        10,
        0,
        'TEST',
        '{risk_level}',
        '{json.dumps(sandbox_config)}'::jsonb,
        {str(requires_approval).lower()},
        {approved_by_sql},
        {approved_at_sql},
        'TEST'
    )
    """
    execute_sql(query)
    return experiment_id


def cleanup_test_experiment(experiment_id: str) -> None:
    """Remove test experiment."""
    execute_sql(f"DELETE FROM experiments WHERE id = '{experiment_id}'")


def test_low_risk_allowed() -> bool:
    """
    Test: Low-risk experiment should be ALLOWED.
    
    Scenario: $5 budget, test scope, no production impact
    Expected: Execution allowed without approval
    """
    logger.info("=" * 60)
    logger.info("TEST 1: Low-risk experiment should be ALLOWED")
    logger.info("=" * 60)
    
    sandbox_config = {
        "max_spend": 10.0,
        "allowed_scope": "test",
        "can_affect_production": False,
        "max_iterations": 10,
    }
    
    experiment_id = create_test_experiment(
        name="Test Low Risk",
        budget_limit=5.0,
        risk_level="low",
        sandbox_config=sandbox_config,
        requires_approval=False,
    )
    
    logger.info("Created low-risk experiment: %s", experiment_id)
    logger.info("  Budget: $5.00")
    logger.info("  Risk Level: low")
    logger.info("  Requires Approval: False")
    
    # Import and test
    from core.sandbox import enforce_sandbox_before_execution
    
    result = enforce_sandbox_before_execution(experiment_id)
    
    logger.info("Enforcement result: %s", result)
    
    # Cleanup
    cleanup_test_experiment(experiment_id)
    
    if result.get("allowed"):
        logger.info("✅ PASS: Low-risk experiment ALLOWED as expected")
        return True
    else:
        logger.error("❌ FAIL: Low-risk experiment was blocked!")
        return False


def test_high_risk_blocked() -> bool:
    """
    Test: High-risk experiment without approval should be BLOCKED.
    
    Scenario: $100 budget, production scope, no approval
    Expected: Execution blocked
    """
    logger.info("=" * 60)
    logger.info("TEST 2: High-risk experiment without approval should be BLOCKED")
    logger.info("=" * 60)
    
    sandbox_config = {
        "max_spend": 100.0,
        "allowed_scope": "production",
        "can_affect_production": True,
        "max_iterations": 50,
    }
    
    experiment_id = create_test_experiment(
        name="Test High Risk Unapproved",
        budget_limit=100.0,
        risk_level="high",
        sandbox_config=sandbox_config,
        requires_approval=True,
        approved_by=None,  # Not approved
    )
    
    logger.info("Created high-risk experiment: %s", experiment_id)
    logger.info("  Budget: $100.00")
    logger.info("  Risk Level: high")
    logger.info("  Requires Approval: True")
    logger.info("  Approved: False")
    
    # Import and test
    from core.sandbox import enforce_sandbox_before_execution
    
    result = enforce_sandbox_before_execution(experiment_id)
    
    logger.info("Enforcement result: %s", result)
    
    # Cleanup
    cleanup_test_experiment(experiment_id)
    
    if not result.get("allowed"):
        logger.info("✅ PASS: High-risk experiment BLOCKED as expected")
        logger.info("  Reason: %s", result.get("reason"))
        return True
    else:
        logger.error("❌ FAIL: High-risk experiment was allowed without approval!")
        return False


def test_approved_high_risk_allowed() -> bool:
    """
    Test: Approved high-risk experiment should be ALLOWED.
    
    Scenario: $100 budget, production scope, WITH approval
    Expected: Execution allowed
    """
    logger.info("=" * 60)
    logger.info("TEST 3: Approved high-risk experiment should be ALLOWED")
    logger.info("=" * 60)
    
    sandbox_config = {
        "max_spend": 100.0,
        "allowed_scope": "production",
        "can_affect_production": True,
        "max_iterations": 50,
    }
    
    experiment_id = create_test_experiment(
        name="Test High Risk Approved",
        budget_limit=100.0,
        risk_level="high",
        sandbox_config=sandbox_config,
        requires_approval=True,
        approved_by="Josh",  # Approved by Josh
    )
    
    logger.info("Created approved high-risk experiment: %s", experiment_id)
    logger.info("  Budget: $100.00")
    logger.info("  Risk Level: high")
    logger.info("  Requires Approval: True")
    logger.info("  Approved By: Josh")
    
    # Import and test
    from core.sandbox import enforce_sandbox_before_execution
    
    result = enforce_sandbox_before_execution(experiment_id)
    
    logger.info("Enforcement result: %s", result)
    
    # Cleanup
    cleanup_test_experiment(experiment_id)
    
    if result.get("allowed"):
        logger.info("✅ PASS: Approved high-risk experiment ALLOWED as expected")
        return True
    else:
        logger.error("❌ FAIL: Approved high-risk experiment was blocked!")
        return False


def test_sandbox_limit_violation() -> bool:
    """
    Test: Experiment exceeding sandbox limits should be BLOCKED.
    
    Scenario: Low-risk config but budget already spent exceeds limit
    Expected: Execution blocked due to sandbox violation
    """
    logger.info("=" * 60)
    logger.info("TEST 4: Sandbox limit violation should be BLOCKED")
    logger.info("=" * 60)
    
    sandbox_config = {
        "max_spend": 10.0,  # Limit is $10
        "allowed_scope": "test",
        "can_affect_production": False,
        "max_iterations": 10,
    }
    
    # Create experiment
    experiment_id = str(uuid.uuid4())
    query = f"""
    INSERT INTO experiments (
        id, name, description, experiment_type, status,
        hypothesis, success_criteria, budget_limit, budget_spent,
        max_iterations, current_iteration, owner_worker,
        risk_level, sandbox_config, requires_approval,
        created_by
    ) VALUES (
        '{experiment_id}',
        'Test Sandbox Violation',
        'Test experiment exceeding sandbox limits',
        'test',
        'running',
        'Test hypothesis',
        '{{"metric": "test"}}'::jsonb,
        50.0,
        15.0,  -- Already spent $15, exceeding $10 sandbox limit
        10,
        5,
        'TEST',
        'low',
        '{json.dumps(sandbox_config)}'::jsonb,
        false,
        'TEST'
    )
    """
    execute_sql(query)
    
    logger.info("Created experiment with sandbox violation: %s", experiment_id)
    logger.info("  Sandbox max_spend: $10.00")
    logger.info("  Budget spent: $15.00 (EXCEEDS LIMIT)")
    
    # Import and test
    from core.sandbox import enforce_sandbox_before_execution
    
    result = enforce_sandbox_before_execution(experiment_id)
    
    logger.info("Enforcement result: %s", result)
    
    # Cleanup
    cleanup_test_experiment(experiment_id)
    
    if not result.get("allowed"):
        logger.info("✅ PASS: Sandbox violation BLOCKED as expected")
        logger.info("  Violations: %s", result.get("violations"))
        return True
    else:
        logger.error("❌ FAIL: Sandbox violation was not detected!")
        return False


def main() -> int:
    """Run all sandbox tests."""
    logger.info("Starting Sandbox Innovation Boundaries Tests")
    logger.info("L4-02: Evidence of enforcement behavior")
    logger.info("")
    
    results = []
    
    try:
        results.append(("Low-risk allowed", test_low_risk_allowed()))
        results.append(("High-risk blocked", test_high_risk_blocked()))
        results.append(("Approved high-risk allowed", test_approved_high_risk_allowed()))
        results.append(("Sandbox violation blocked", test_sandbox_limit_violation()))
    except Exception as exc:
        logger.exception("Test execution failed: %s", exc)
        return 1
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info("  %s: %s", test_name, status)
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info("")
    logger.info("Total: %d passed, %d failed", passed, failed)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
