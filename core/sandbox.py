"""
JUGGERNAUT Sandbox Innovation Boundaries (L4-02)

Implements sandboxed innovation for experiments with:
- Risk level classification (low, medium, high)
- Sandbox limits enforcement (max spend, scope)
- Approval workflow for high-risk experiments
- Protection against production impact without approval

L4 REQUIREMENT: Sandboxed Innovation - Experiments limited to low-risk unless approved
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx

from core.database import query_db as _db_query, escape_sql_value as _format_value

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS - Risk Thresholds
# =============================================================================

# Budget thresholds for risk classification
LOW_RISK_MAX_BUDGET = 10.0  # Experiments under $10 are low-risk
MEDIUM_RISK_MAX_BUDGET = 50.0  # Experiments $10-$50 are medium-risk
# Experiments over $50 are high-risk

# Scope types
SCOPE_TEST = "test"
SCOPE_STAGING = "staging"
SCOPE_PRODUCTION = "production"

# Default sandbox configuration
DEFAULT_SANDBOX_CONFIG = {
    "max_spend": LOW_RISK_MAX_BUDGET,
    "allowed_scope": SCOPE_TEST,
    "can_affect_production": False,
    "max_iterations": 10,
    "require_human_review": False,
}


class RiskLevel(str, Enum):
    """Risk levels for experiments."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# =============================================================================
# DATABASE HELPERS
# =============================================================================


def _execute_sql(query: str, return_results: bool = True) -> Dict[str, Any]:
    """Execute SQL query via centralized database module."""
    try:
        result = _db_query(query)
        if return_results and "rows" in result:
            return {"success": True, "rows": result["rows"], "rowCount": result.get("rowCount", 0)}
        return {"success": True, "rowCount": result.get("rowCount", 0)}
    except Exception as e:
        logger.error("Database error: %s", e)
        return {"success": False, "error": str(e)}


def _escape_string(value: Optional[str]) -> str:
    """Escape single quotes for SQL."""
    if value is None:
        return "NULL"
    return value.replace("'", "''")


# =============================================================================
# RISK CLASSIFICATION
# =============================================================================


def classify_risk_level(
    budget_limit: float,
    scope: str = SCOPE_TEST,
    affects_production: bool = False,
    experiment_type: str = "revenue",
) -> RiskLevel:
    """
    Classify experiment risk level based on budget and scope.
    
    Risk Classification Rules:
    - LOW: Budget <= $10 AND scope = test AND no production impact
    - MEDIUM: Budget $10-$50 OR scope = staging
    - HIGH: Budget > $50 OR scope = production OR affects production
    
    Args:
        budget_limit: Maximum experiment budget
        scope: Experiment scope (test, staging, production)
        affects_production: Whether experiment can affect production systems
        experiment_type: Type of experiment
        
    Returns:
        RiskLevel enum value
    """
    # High risk conditions
    if affects_production:
        logger.info(
            "Classified as HIGH risk: affects_production=True"
        )
        return RiskLevel.HIGH
    
    if scope == SCOPE_PRODUCTION:
        logger.info(
            "Classified as HIGH risk: scope=production"
        )
        return RiskLevel.HIGH
    
    if budget_limit > MEDIUM_RISK_MAX_BUDGET:
        logger.info(
            "Classified as HIGH risk: budget=%.2f > %.2f",
            budget_limit,
            MEDIUM_RISK_MAX_BUDGET,
        )
        return RiskLevel.HIGH
    
    # Medium risk conditions
    if scope == SCOPE_STAGING:
        logger.info(
            "Classified as MEDIUM risk: scope=staging"
        )
        return RiskLevel.MEDIUM
    
    if budget_limit > LOW_RISK_MAX_BUDGET:
        logger.info(
            "Classified as MEDIUM risk: budget=%.2f > %.2f",
            budget_limit,
            LOW_RISK_MAX_BUDGET,
        )
        return RiskLevel.MEDIUM
    
    # Low risk - within all safety bounds
    logger.info(
        "Classified as LOW risk: budget=%.2f, scope=%s",
        budget_limit,
        scope,
    )
    return RiskLevel.LOW


def requires_approval_for_risk(risk_level: RiskLevel) -> bool:
    """
    Determine if approval is required based on risk level.
    
    Args:
        risk_level: The experiment's risk level
        
    Returns:
        True if approval is required
    """
    return risk_level == RiskLevel.HIGH


# =============================================================================
# SANDBOX CONFIGURATION
# =============================================================================


def create_sandbox_config(
    max_spend: float = LOW_RISK_MAX_BUDGET,
    allowed_scope: str = SCOPE_TEST,
    can_affect_production: bool = False,
    max_iterations: int = 10,
    require_human_review: bool = False,
    additional_constraints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a sandbox configuration for an experiment.
    
    Args:
        max_spend: Maximum allowed spend within sandbox
        allowed_scope: Allowed execution scope
        can_affect_production: Whether production can be affected
        max_iterations: Maximum iterations allowed
        require_human_review: Whether human review is needed
        additional_constraints: Any extra constraints
        
    Returns:
        Sandbox configuration dictionary
    """
    config = {
        "max_spend": max_spend,
        "allowed_scope": allowed_scope,
        "can_affect_production": can_affect_production,
        "max_iterations": max_iterations,
        "require_human_review": require_human_review,
        "created_at": datetime.now().isoformat(),
    }
    
    if additional_constraints:
        config["additional_constraints"] = additional_constraints
    
    return config


def get_default_sandbox_for_risk(risk_level: RiskLevel) -> Dict[str, Any]:
    """
    Get default sandbox configuration based on risk level.
    
    Args:
        risk_level: The experiment's risk level
        
    Returns:
        Appropriate sandbox configuration
    """
    if risk_level == RiskLevel.LOW:
        return create_sandbox_config(
            max_spend=LOW_RISK_MAX_BUDGET,
            allowed_scope=SCOPE_TEST,
            can_affect_production=False,
            max_iterations=10,
            require_human_review=False,
        )
    elif risk_level == RiskLevel.MEDIUM:
        return create_sandbox_config(
            max_spend=MEDIUM_RISK_MAX_BUDGET,
            allowed_scope=SCOPE_STAGING,
            can_affect_production=False,
            max_iterations=20,
            require_human_review=True,
        )
    else:  # HIGH
        return create_sandbox_config(
            max_spend=100.0,
            allowed_scope=SCOPE_PRODUCTION,
            can_affect_production=True,
            max_iterations=50,
            require_human_review=True,
        )


# =============================================================================
# SANDBOX VALIDATION
# =============================================================================


def validate_sandbox_limits(
    experiment_id: str,
    sandbox_config: Dict[str, Any],
    current_spend: float = 0.0,
    current_iterations: int = 0,
    target_scope: str = SCOPE_TEST,
) -> Tuple[bool, List[str]]:
    """
    Validate that an experiment is within its sandbox limits.
    
    Args:
        experiment_id: ID of the experiment
        sandbox_config: Sandbox configuration to validate against
        current_spend: Current amount spent
        current_iterations: Current iteration count
        target_scope: Scope the experiment wants to execute in
        
    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations: List[str] = []
    
    max_spend = sandbox_config.get("max_spend", LOW_RISK_MAX_BUDGET)
    if current_spend > max_spend:
        violations.append(
            f"Budget exceeded: ${current_spend:.2f} > ${max_spend:.2f} limit"
        )
    
    max_iterations = sandbox_config.get("max_iterations", 10)
    if current_iterations >= max_iterations:
        violations.append(
            f"Iteration limit reached: {current_iterations} >= {max_iterations}"
        )
    
    allowed_scope = sandbox_config.get("allowed_scope", SCOPE_TEST)
    scope_hierarchy = {SCOPE_TEST: 0, SCOPE_STAGING: 1, SCOPE_PRODUCTION: 2}
    
    if scope_hierarchy.get(target_scope, 0) > scope_hierarchy.get(allowed_scope, 0):
        violations.append(
            f"Scope violation: '{target_scope}' not allowed, max is '{allowed_scope}'"
        )
    
    if target_scope == SCOPE_PRODUCTION:
        if not sandbox_config.get("can_affect_production", False):
            violations.append(
                "Production impact not allowed by sandbox configuration"
            )
    
    is_valid = len(violations) == 0
    
    if not is_valid:
        logger.warning(
            "Sandbox validation failed for experiment %s: %s",
            experiment_id,
            violations,
        )
    else:
        logger.info(
            "Sandbox validation passed for experiment %s",
            experiment_id,
        )
    
    return is_valid, violations


def enforce_sandbox_before_execution(experiment_id: str) -> Dict[str, Any]:
    """
    Enforce sandbox limits before allowing experiment execution.
    
    This is the main enforcement function called before any experiment
    iteration or action.
    
    Args:
        experiment_id: ID of the experiment to validate
        
    Returns:
        Dict with 'allowed' boolean and details
    """
    # Fetch experiment details
    query = f"""
    SELECT id, name, risk_level, sandbox_config, requires_approval,
           approved_by, approved_at, budget_spent, current_iteration,
           status, budget_limit
    FROM experiments
    WHERE id = '{experiment_id}'
    """
    
    result = _execute_sql(query)
    rows = result.get("rows", [])
    
    if not rows:
        return {
            "allowed": False,
            "reason": "Experiment not found",
            "experiment_id": experiment_id,
        }
    
    experiment = rows[0]
    risk_level = experiment.get("risk_level", "low")
    requires_approval = experiment.get("requires_approval", False)
    approved_by = experiment.get("approved_by")
    sandbox_config = experiment.get("sandbox_config") or DEFAULT_SANDBOX_CONFIG
    
    # Parse sandbox_config if it's a string
    if isinstance(sandbox_config, str):
        try:
            sandbox_config = json.loads(sandbox_config)
        except json.JSONDecodeError:
            sandbox_config = DEFAULT_SANDBOX_CONFIG
    
    # Check 1: High-risk experiments need approval
    if risk_level == RiskLevel.HIGH.value and requires_approval:
        if not approved_by:
            logger.warning(
                "Blocked experiment %s: high-risk requires approval",
                experiment_id,
            )
            return {
                "allowed": False,
                "reason": "High-risk experiment requires approval before execution",
                "risk_level": risk_level,
                "requires_approval": True,
                "approved": False,
            }
    
    # Check 2: Validate sandbox limits
    current_spend = float(experiment.get("budget_spent") or 0)
    current_iterations = int(experiment.get("current_iteration") or 0)
    
    # Determine target scope from sandbox config or default to test
    target_scope = sandbox_config.get("allowed_scope", SCOPE_TEST)
    
    is_valid, violations = validate_sandbox_limits(
        experiment_id=experiment_id,
        sandbox_config=sandbox_config,
        current_spend=current_spend,
        current_iterations=current_iterations,
        target_scope=target_scope,
    )
    
    if not is_valid:
        logger.warning(
            "Blocked experiment %s: sandbox violations: %s",
            experiment_id,
            violations,
        )
        return {
            "allowed": False,
            "reason": "Sandbox limit violations",
            "violations": violations,
            "risk_level": risk_level,
        }
    
    logger.info(
        "Allowed experiment %s execution: risk=%s, approved=%s",
        experiment_id,
        risk_level,
        bool(approved_by),
    )
    
    return {
        "allowed": True,
        "risk_level": risk_level,
        "sandbox_config": sandbox_config,
        "current_spend": current_spend,
        "current_iterations": current_iterations,
    }


# =============================================================================
# APPROVAL WORKFLOW
# =============================================================================


def request_approval(
    experiment_id: str,
    requested_by: str,
    reason: str,
) -> Dict[str, Any]:
    """
    Request approval for a high-risk experiment.
    
    Args:
        experiment_id: ID of the experiment
        requested_by: Who is requesting approval
        reason: Why approval is needed
        
    Returns:
        Dict with request status
    """
    query = f"""
    UPDATE experiments
    SET requires_approval = TRUE,
        config = COALESCE(config, '{{}}'::jsonb) || 
                 jsonb_build_object(
                     'approval_requested_by', '{_escape_string(requested_by)}',
                     'approval_requested_at', '{datetime.now().isoformat()}',
                     'approval_reason', '{_escape_string(reason)}'
                 ),
        updated_at = NOW()
    WHERE id = '{experiment_id}'
    """
    
    result = _execute_sql(query)
    
    if result.get("rowCount", 0) > 0:
        logger.info(
            "Approval requested for experiment %s by %s",
            experiment_id,
            requested_by,
        )
        return {
            "success": True,
            "message": f"Approval requested for experiment {experiment_id}",
        }
    
    return {"success": False, "error": "Failed to request approval"}


def approve_experiment(
    experiment_id: str,
    approved_by: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Approve a high-risk experiment for execution.
    
    Only authorized users (e.g., Josh) should call this function.
    
    Args:
        experiment_id: ID of the experiment to approve
        approved_by: Who is approving (should be authorized user)
        notes: Optional approval notes
        
    Returns:
        Dict with approval status
    """
    notes_json = f"'{_escape_string(notes)}'" if notes else "NULL"
    
    query = f"""
    UPDATE experiments
    SET approved_by = '{_escape_string(approved_by)}',
        approved_at = NOW(),
        config = COALESCE(config, '{{}}'::jsonb) || 
                 jsonb_build_object(
                     'approval_notes', {notes_json}
                 ),
        updated_at = NOW()
    WHERE id = '{experiment_id}'
      AND requires_approval = TRUE
    """
    
    result = _execute_sql(query)
    
    if result.get("rowCount", 0) > 0:
        logger.info(
            "Experiment %s approved by %s",
            experiment_id,
            approved_by,
        )
        return {
            "success": True,
            "message": f"Experiment {experiment_id} approved",
            "approved_by": approved_by,
            "approved_at": datetime.now().isoformat(),
        }
    
    return {
        "success": False,
        "error": "Failed to approve experiment (may not exist or not require approval)",
    }


def revoke_approval(
    experiment_id: str,
    revoked_by: str,
    reason: str,
) -> Dict[str, Any]:
    """
    Revoke approval for an experiment.
    
    Args:
        experiment_id: ID of the experiment
        revoked_by: Who is revoking
        reason: Why approval is being revoked
        
    Returns:
        Dict with revocation status
    """
    query = f"""
    UPDATE experiments
    SET approved_by = NULL,
        approved_at = NULL,
        config = COALESCE(config, '{{}}'::jsonb) || 
                 jsonb_build_object(
                     'approval_revoked_by', '{_escape_string(revoked_by)}',
                     'approval_revoked_at', '{datetime.now().isoformat()}',
                     'revocation_reason', '{_escape_string(reason)}'
                 ),
        updated_at = NOW()
    WHERE id = '{experiment_id}'
    """
    
    result = _execute_sql(query)
    
    if result.get("rowCount", 0) > 0:
        logger.info(
            "Approval revoked for experiment %s by %s: %s",
            experiment_id,
            revoked_by,
            reason,
        )
        return {"success": True, "message": "Approval revoked"}
    
    return {"success": False, "error": "Failed to revoke approval"}


# =============================================================================
# EXPERIMENT CREATION HELPER
# =============================================================================


def setup_experiment_sandbox(
    experiment_id: str,
    budget_limit: float,
    scope: str = SCOPE_TEST,
    affects_production: bool = False,
    experiment_type: str = "revenue",
) -> Dict[str, Any]:
    """
    Set up sandbox configuration for a new experiment.
    
    This should be called during experiment creation to automatically
    configure risk level and sandbox limits.
    
    Args:
        experiment_id: ID of the experiment
        budget_limit: Experiment budget limit
        scope: Experiment scope
        affects_production: Whether it affects production
        experiment_type: Type of experiment
        
    Returns:
        Dict with sandbox setup results
    """
    # Classify risk
    risk_level = classify_risk_level(
        budget_limit=budget_limit,
        scope=scope,
        affects_production=affects_production,
        experiment_type=experiment_type,
    )
    
    # Get appropriate sandbox config
    sandbox_config = get_default_sandbox_for_risk(risk_level)
    
    # Adjust sandbox max_spend to match budget_limit if lower
    if budget_limit < sandbox_config["max_spend"]:
        sandbox_config["max_spend"] = budget_limit
    
    # Determine if approval is required
    requires_approval = requires_approval_for_risk(risk_level)
    
    # Update experiment with sandbox config
    query = f"""
    UPDATE experiments
    SET risk_level = '{risk_level.value}',
        sandbox_config = '{json.dumps(sandbox_config)}'::jsonb,
        requires_approval = {str(requires_approval).lower()},
        updated_at = NOW()
    WHERE id = '{experiment_id}'
    """
    
    result = _execute_sql(query)
    
    if result.get("rowCount", 0) > 0:
        logger.info(
            "Sandbox configured for experiment %s: risk=%s, requires_approval=%s",
            experiment_id,
            risk_level.value,
            requires_approval,
        )
        return {
            "success": True,
            "risk_level": risk_level.value,
            "sandbox_config": sandbox_config,
            "requires_approval": requires_approval,
        }
    
    return {"success": False, "error": "Failed to configure sandbox"}


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def is_low_risk_experiment(experiment_id: str) -> bool:
    """
    Check if an experiment is low-risk.
    
    Args:
        experiment_id: ID of the experiment
        
    Returns:
        True if low-risk
    """
    query = f"SELECT risk_level FROM experiments WHERE id = '{experiment_id}'"
    result = _execute_sql(query)
    rows = result.get("rows", [])
    
    if rows:
        return rows[0].get("risk_level") == RiskLevel.LOW.value
    return False


def get_pending_approvals() -> List[Dict[str, Any]]:
    """
    Get list of experiments awaiting approval.
    
    Returns:
        List of experiments needing approval
    """
    query = """
    SELECT id, name, hypothesis, risk_level, budget_limit,
           config->>'approval_requested_by' as requested_by,
           config->>'approval_requested_at' as requested_at,
           config->>'approval_reason' as reason
    FROM experiments
    WHERE requires_approval = TRUE
      AND approved_by IS NULL
      AND status = 'draft'
    ORDER BY 
        CASE risk_level 
            WHEN 'high' THEN 1 
            WHEN 'medium' THEN 2 
            ELSE 3 
        END,
        created_at
    """
    
    result = _execute_sql(query)
    return result.get("rows", [])
