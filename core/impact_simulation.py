"""
JUGGERNAUT Impact Simulation Framework (L4-05)

Provides impact simulation capabilities for risky actions:
- Simulate expected outcomes before executing changes
- Log simulation results for audit trail
- Block or warn on negative predicted impacts
- Track actual vs predicted for learning

L4 Requirement: Impact Simulation - Models expected outcomes before deploying
"""

# Standard library imports
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Third-party imports
import httpx

from core.database import query_db as _db_query, escape_sql_value as _format_value

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Simulation thresholds
DEFAULT_RISK_THRESHOLD = 0.7
HIGH_RISK_THRESHOLD = 0.85
CRITICAL_RISK_THRESHOLD = 0.95
DEFAULT_COST_THRESHOLD_CENTS = 1000
HIGH_COST_THRESHOLD_CENTS = 5000

# Timeout settings
HTTP_TIMEOUT_SECONDS = 30


# =============================================================================
# ENUMS
# =============================================================================


class ImpactSeverity(Enum):
    """Severity levels for predicted impacts."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SimulationDecision(Enum):
    """Decisions based on simulation results."""

    PROCEED = "proceed"
    WARN = "warn"
    BLOCK = "block"
    ESCALATE = "escalate"


class ActionType(Enum):
    """Types of actions that can be simulated."""

    EXPERIMENT_START = "experiment_start"
    BUDGET_ALLOCATION = "budget_allocation"
    TASK_EXECUTION = "task_execution"
    TOOL_INVOCATION = "tool_invocation"
    CONFIGURATION_CHANGE = "configuration_change"
    DEPLOYMENT = "deployment"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class SimulationResult:
    """Result of an impact simulation."""

    simulation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: ActionType = ActionType.TASK_EXECUTION
    action_id: Optional[str] = None
    predicted_impact: Dict[str, Any] = field(default_factory=dict)
    risk_score: float = 0.0
    severity: ImpactSeverity = ImpactSeverity.LOW
    decision: SimulationDecision = SimulationDecision.PROCEED
    warnings: List[str] = field(default_factory=list)
    predicted_cost_cents: int = 0
    predicted_duration_minutes: int = 0
    confidence: float = 0.5
    reasoning: str = ""
    simulated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "simulation_id": self.simulation_id,
            "action_type": self.action_type.value,
            "action_id": self.action_id,
            "predicted_impact": self.predicted_impact,
            "risk_score": self.risk_score,
            "severity": self.severity.value,
            "decision": self.decision.value,
            "warnings": self.warnings,
            "predicted_cost_cents": self.predicted_cost_cents,
            "predicted_duration_minutes": self.predicted_duration_minutes,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "simulated_at": self.simulated_at.isoformat(),
        }


# =============================================================================
# DATABASE HELPERS
# =============================================================================


def _execute_sql(query: str) -> Dict[str, Any]:
    """Execute SQL query via centralized database module."""
    result = _db_query(query)
    return {
        "success": True,
        "rows": result.get("rows", []),
        "rowCount": result.get("rowCount", 0),
    }


# =============================================================================
# TABLE CREATION
# =============================================================================


def create_impact_simulations_table() -> bool:
    """
    Create the impact_simulations table if it doesn't exist.

    Returns:
        True if table created or already exists, False on error
    """
    query = """
    CREATE TABLE IF NOT EXISTS impact_simulations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        action_type VARCHAR(50) NOT NULL,
        action_id UUID,
        experiment_id UUID,
        task_id UUID,
        predicted_impact JSONB NOT NULL DEFAULT '{}',
        risk_score NUMERIC(4,3) NOT NULL DEFAULT 0,
        severity VARCHAR(20) NOT NULL DEFAULT 'low',
        decision VARCHAR(20) NOT NULL DEFAULT 'proceed',
        warnings JSONB DEFAULT '[]',
        predicted_cost_cents INTEGER DEFAULT 0,
        predicted_duration_minutes INTEGER DEFAULT 0,
        confidence NUMERIC(4,3) DEFAULT 0.5,
        reasoning TEXT,
        actual_outcome JSONB,
        actual_cost_cents INTEGER,
        actual_duration_minutes INTEGER,
        outcome_recorded_at TIMESTAMPTZ,
        accuracy_score NUMERIC(4,3),
        simulated_by VARCHAR(100) DEFAULT 'SYSTEM',
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_impact_sim_action_type 
        ON impact_simulations(action_type);
    CREATE INDEX IF NOT EXISTS idx_impact_sim_decision 
        ON impact_simulations(decision);
    CREATE INDEX IF NOT EXISTS idx_impact_sim_created 
        ON impact_simulations(created_at);
    """
    try:
        _execute_sql(query)
        logger.info("impact_simulations table created or verified")
        return True
    except Exception as e:
        logger.error("Failed to create impact_simulations table: %s", str(e))
        return False


# =============================================================================
# CORE SIMULATION FUNCTIONS
# =============================================================================


def simulate_impact(
    action_type: ActionType,
    action_data: Dict[str, Any],
    action_id: Optional[str] = None,
    simulated_by: str = "SYSTEM",
) -> SimulationResult:
    """
    Simulate the expected impact of an action before execution.

    Analyzes the action data to predict:
    - Risk score (0.0 to 1.0)
    - Expected cost
    - Potential negative impacts
    - Recommended decision (proceed/warn/block/escalate)

    Args:
        action_type: Type of action being simulated
        action_data: Details about the action (varies by type)
        action_id: Optional ID of the action (experiment_id, task_id, etc.)
        simulated_by: Who/what initiated the simulation

    Returns:
        SimulationResult with predicted impact and decision
    """
    result = SimulationResult(
        action_type=action_type,
        action_id=action_id,
    )

    # Calculate risk based on action type
    risk_score = 0.0
    warnings: List[str] = []
    predicted_cost = 0

    if action_type == ActionType.EXPERIMENT_START:
        risk_score, warnings, predicted_cost = _simulate_experiment_impact(
            action_data
        )
    elif action_type == ActionType.BUDGET_ALLOCATION:
        risk_score, warnings, predicted_cost = _simulate_budget_impact(
            action_data
        )
    elif action_type == ActionType.TASK_EXECUTION:
        risk_score, warnings, predicted_cost = _simulate_task_impact(
            action_data
        )
    elif action_type == ActionType.TOOL_INVOCATION:
        risk_score, warnings, predicted_cost = _simulate_tool_impact(
            action_data
        )
    elif action_type == ActionType.CONFIGURATION_CHANGE:
        risk_score, warnings, predicted_cost = _simulate_config_impact(
            action_data
        )
    elif action_type == ActionType.DEPLOYMENT:
        risk_score, warnings, predicted_cost = _simulate_deployment_impact(
            action_data
        )

    # Determine severity
    severity = _calculate_severity(risk_score)

    # Determine decision
    decision = _determine_decision(risk_score, predicted_cost, warnings)

    # Build reasoning
    reasoning = _build_reasoning(
        action_type, risk_score, warnings, predicted_cost
    )

    result.risk_score = risk_score
    result.severity = severity
    result.decision = decision
    result.warnings = warnings
    result.predicted_cost_cents = predicted_cost
    result.predicted_impact = {
        "risk_factors": warnings,
        "cost_estimate": predicted_cost,
        "action_data": action_data,
    }
    result.reasoning = reasoning
    result.confidence = _calculate_confidence(action_type, action_data)

    # Log the simulation
    _log_simulation(result, simulated_by)

    return result


def _simulate_experiment_impact(
    data: Dict[str, Any]
) -> Tuple[float, List[str], int]:
    """
    Simulate impact of starting an experiment.

    Args:
        data: Experiment configuration data

    Returns:
        Tuple of (risk_score, warnings, predicted_cost)
    """
    risk = 0.0
    warnings: List[str] = []
    cost = data.get("budget_limit", 0)

    # Check budget
    if cost > HIGH_COST_THRESHOLD_CENTS:
        risk += 0.3
        warnings.append(f"High budget: ${cost/100:.2f}")

    # Check if similar experiments failed
    experiment_type = data.get("experiment_type", "")
    if experiment_type:
        failure_rate = _get_experiment_type_failure_rate(experiment_type)
        if failure_rate > 0.5:
            risk += 0.2
            warnings.append(
                f"High failure rate for {experiment_type}: {failure_rate:.0%}"
            )

    # Check risk level
    risk_level = data.get("risk_level", "low")
    if risk_level == "high":
        risk += 0.3
        warnings.append("Marked as high-risk experiment")
    elif risk_level == "medium":
        risk += 0.15

    return min(risk, 1.0), warnings, int(cost)


def _simulate_budget_impact(
    data: Dict[str, Any]
) -> Tuple[float, List[str], int]:
    """
    Simulate impact of budget allocation.

    Args:
        data: Budget allocation data

    Returns:
        Tuple of (risk_score, warnings, predicted_cost)
    """
    risk = 0.0
    warnings: List[str] = []
    amount = data.get("amount_cents", 0)

    # Check if exceeds daily limit
    daily_limit = data.get("daily_limit_cents", DEFAULT_COST_THRESHOLD_CENTS)
    if amount > daily_limit:
        risk += 0.4
        warnings.append(f"Exceeds daily limit: ${amount/100:.2f}")

    # Check remaining budget
    remaining = data.get("remaining_budget_cents", 0)
    if amount > remaining:
        risk += 0.5
        warnings.append("Insufficient remaining budget")

    return min(risk, 1.0), warnings, amount


def _simulate_task_impact(
    data: Dict[str, Any]
) -> Tuple[float, List[str], int]:
    """
    Simulate impact of task execution.

    Args:
        data: Task execution data

    Returns:
        Tuple of (risk_score, warnings, predicted_cost)
    """
    risk = 0.0
    warnings: List[str] = []
    cost = data.get("estimated_cost_cents", 0)

    # Check task type
    task_type = data.get("task_type", "")
    if task_type in ("deployment", "delete", "modify_production"):
        risk += 0.4
        warnings.append(f"High-impact task type: {task_type}")

    # Check priority
    priority = data.get("priority", "medium")
    if priority == "critical":
        risk += 0.1
        warnings.append("Critical priority - verify before proceeding")

    return min(risk, 1.0), warnings, cost


def _simulate_tool_impact(
    data: Dict[str, Any]
) -> Tuple[float, List[str], int]:
    """
    Simulate impact of tool invocation.

    Args:
        data: Tool invocation data

    Returns:
        Tuple of (risk_score, warnings, predicted_cost)
    """
    risk = 0.0
    warnings: List[str] = []
    cost = data.get("estimated_cost_cents", 0)

    # Check if tool is external/paid
    tool_name = data.get("tool_name", "")
    if data.get("is_paid_api", False):
        risk += 0.2
        warnings.append(f"Paid API call: {tool_name}")

    # Check rate limits
    if data.get("near_rate_limit", False):
        risk += 0.3
        warnings.append("Approaching rate limit")

    return min(risk, 1.0), warnings, cost


def _simulate_config_impact(
    data: Dict[str, Any]
) -> Tuple[float, List[str], int]:
    """
    Simulate impact of configuration change.

    Args:
        data: Configuration change data

    Returns:
        Tuple of (risk_score, warnings, predicted_cost)
    """
    risk = 0.3  # Config changes inherently risky
    warnings: List[str] = ["Configuration changes require review"]

    if data.get("affects_production", False):
        risk += 0.4
        warnings.append("Affects production environment")

    if data.get("requires_restart", False):
        risk += 0.2
        warnings.append("Requires service restart")

    return min(risk, 1.0), warnings, 0


def _simulate_deployment_impact(
    data: Dict[str, Any]
) -> Tuple[float, List[str], int]:
    """
    Simulate impact of deployment.

    Args:
        data: Deployment data

    Returns:
        Tuple of (risk_score, warnings, predicted_cost)
    """
    risk = 0.5  # Deployments are inherently high-risk
    warnings: List[str] = ["Deployment requires Josh approval"]
    cost = data.get("estimated_cost_cents", 0)

    if data.get("is_production", False):
        risk += 0.3
        warnings.append("Production deployment")

    if not data.get("has_rollback_plan", False):
        risk += 0.2
        warnings.append("No rollback plan defined")

    return min(risk, 1.0), warnings, cost


def _get_experiment_type_failure_rate(experiment_type: str) -> float:
    """
    Get historical failure rate for an experiment type.

    Args:
        experiment_type: Type of experiment

    Returns:
        Failure rate as float (0.0 to 1.0)
    """
    query = f"""
    SELECT 
        COUNT(*) FILTER (WHERE status = 'failed') as failed,
        COUNT(*) as total
    FROM experiments
    WHERE experiment_type = {_format_value(experiment_type)}
      AND status IN ('completed', 'failed')
    """
    try:
        result = _execute_sql(query)
        rows = result.get("rows", [])
        if rows and rows[0].get("total", 0) > 0:
            failed = int(rows[0].get("failed", 0) or 0)
            total = int(rows[0].get("total", 1))
            return failed / total
    except Exception as e:
        logger.warning("Could not get failure rate: %s", str(e))
    return 0.0


def _calculate_severity(risk_score: float) -> ImpactSeverity:
    """
    Calculate severity level from risk score.

    Args:
        risk_score: Risk score (0.0 to 1.0)

    Returns:
        ImpactSeverity enum value
    """
    if risk_score >= CRITICAL_RISK_THRESHOLD:
        return ImpactSeverity.CRITICAL
    elif risk_score >= HIGH_RISK_THRESHOLD:
        return ImpactSeverity.HIGH
    elif risk_score >= DEFAULT_RISK_THRESHOLD:
        return ImpactSeverity.MEDIUM
    return ImpactSeverity.LOW


def _determine_decision(
    risk_score: float,
    predicted_cost: int,
    warnings: List[str],
) -> SimulationDecision:
    """
    Determine action decision based on simulation results.

    Args:
        risk_score: Calculated risk score
        predicted_cost: Predicted cost in cents
        warnings: List of warning messages

    Returns:
        SimulationDecision enum value
    """
    # Block on critical risk
    if risk_score >= CRITICAL_RISK_THRESHOLD:
        return SimulationDecision.BLOCK

    # Escalate on high risk or high cost
    if risk_score >= HIGH_RISK_THRESHOLD:
        return SimulationDecision.ESCALATE
    if predicted_cost >= HIGH_COST_THRESHOLD_CENTS:
        return SimulationDecision.ESCALATE

    # Warn on medium risk
    if risk_score >= DEFAULT_RISK_THRESHOLD:
        return SimulationDecision.WARN
    if len(warnings) >= 3:
        return SimulationDecision.WARN

    return SimulationDecision.PROCEED


def _build_reasoning(
    action_type: ActionType,
    risk_score: float,
    warnings: List[str],
    predicted_cost: int,
) -> str:
    """
    Build human-readable reasoning for the decision.

    Args:
        action_type: Type of action
        risk_score: Calculated risk score
        warnings: List of warnings
        predicted_cost: Predicted cost

    Returns:
        Reasoning string
    """
    parts = [f"Simulated {action_type.value} action."]
    parts.append(f"Risk score: {risk_score:.2f}")

    if predicted_cost > 0:
        parts.append(f"Predicted cost: ${predicted_cost/100:.2f}")

    if warnings:
        parts.append(f"Warnings: {', '.join(warnings)}")

    return " ".join(parts)


def _calculate_confidence(
    action_type: ActionType,
    action_data: Dict[str, Any],
) -> float:
    """
    Calculate confidence level in the simulation.

    Args:
        action_type: Type of action
        action_data: Action data

    Returns:
        Confidence score (0.0 to 1.0)
    """
    # Base confidence by action type
    base_confidence = {
        ActionType.EXPERIMENT_START: 0.6,
        ActionType.BUDGET_ALLOCATION: 0.8,
        ActionType.TASK_EXECUTION: 0.7,
        ActionType.TOOL_INVOCATION: 0.7,
        ActionType.CONFIGURATION_CHANGE: 0.5,
        ActionType.DEPLOYMENT: 0.4,
    }
    confidence = base_confidence.get(action_type, 0.5)

    # Increase confidence if we have historical data
    if action_data.get("has_historical_data", False):
        confidence = min(confidence + 0.2, 1.0)

    return confidence


def _log_simulation(result: SimulationResult, simulated_by: str) -> None:
    """
    Log simulation result to database.

    Args:
        result: SimulationResult to log
        simulated_by: Who initiated the simulation
    """
    query = f"""
    INSERT INTO impact_simulations (
        id, action_type, action_id, predicted_impact,
        risk_score, severity, decision, warnings,
        predicted_cost_cents, predicted_duration_minutes,
        confidence, reasoning, simulated_by
    ) VALUES (
        '{result.simulation_id}',
        '{result.action_type.value}',
        {_format_value(result.action_id)},
        '{json.dumps(result.predicted_impact).replace("'", "''")}',
        {result.risk_score},
        '{result.severity.value}',
        '{result.decision.value}',
        '{json.dumps(result.warnings)}',
        {result.predicted_cost_cents},
        {result.predicted_duration_minutes},
        {result.confidence},
        {_format_value(result.reasoning)},
        {_format_value(simulated_by)}
    )
    """
    try:
        _execute_sql(query)
        logger.info(
            "Logged simulation %s: decision=%s, risk=%.2f",
            result.simulation_id,
            result.decision.value,
            result.risk_score,
        )
    except Exception as e:
        logger.error("Failed to log simulation: %s", str(e))


# =============================================================================
# OUTCOME TRACKING
# =============================================================================


def record_actual_outcome(
    simulation_id: str,
    actual_outcome: Dict[str, Any],
    actual_cost_cents: Optional[int] = None,
    actual_duration_minutes: Optional[int] = None,
) -> bool:
    """
    Record the actual outcome after action execution.

    Compares predicted vs actual for learning/calibration.

    Args:
        simulation_id: ID of the original simulation
        actual_outcome: What actually happened
        actual_cost_cents: Actual cost incurred
        actual_duration_minutes: Actual duration

    Returns:
        True if recorded successfully
    """
    # Calculate accuracy if we have predictions to compare
    accuracy_query = f"""
    SELECT predicted_cost_cents, predicted_duration_minutes, risk_score
    FROM impact_simulations
    WHERE id = {_format_value(simulation_id)}
    """
    try:
        result = _execute_sql(accuracy_query)
        rows = result.get("rows", [])
        if not rows:
            logger.warning("Simulation %s not found", simulation_id)
            return False

        predicted = rows[0]
        accuracy = _calculate_accuracy(
            predicted, actual_cost_cents, actual_duration_minutes, actual_outcome
        )

        update_query = f"""
        UPDATE impact_simulations SET
            actual_outcome = '{json.dumps(actual_outcome).replace("'", "''")}',
            actual_cost_cents = {actual_cost_cents if actual_cost_cents else 'NULL'},
            actual_duration_minutes = {actual_duration_minutes if actual_duration_minutes else 'NULL'},
            outcome_recorded_at = NOW(),
            accuracy_score = {accuracy}
        WHERE id = {_format_value(simulation_id)}
        """
        _execute_sql(update_query)
        logger.info(
            "Recorded outcome for simulation %s, accuracy: %.2f",
            simulation_id,
            accuracy,
        )
        return True

    except Exception as e:
        logger.error("Failed to record outcome: %s", str(e))
        return False


def _calculate_accuracy(
    predicted: Dict[str, Any],
    actual_cost: Optional[int],
    actual_duration: Optional[int],
    actual_outcome: Dict[str, Any],
) -> float:
    """
    Calculate prediction accuracy score.

    Args:
        predicted: Predicted values from simulation
        actual_cost: Actual cost in cents
        actual_duration: Actual duration in minutes
        actual_outcome: Actual outcome dict

    Returns:
        Accuracy score (0.0 to 1.0)
    """
    scores: List[float] = []

    # Cost accuracy
    pred_cost = predicted.get("predicted_cost_cents", 0)
    if pred_cost and actual_cost:
        cost_diff = abs(pred_cost - actual_cost) / max(pred_cost, actual_cost, 1)
        scores.append(1.0 - min(cost_diff, 1.0))

    # Duration accuracy
    pred_duration = predicted.get("predicted_duration_minutes", 0)
    if pred_duration and actual_duration:
        dur_diff = abs(pred_duration - actual_duration) / max(
            pred_duration, actual_duration, 1
        )
        scores.append(1.0 - min(dur_diff, 1.0))

    # Outcome match (did we predict success/failure correctly?)
    if actual_outcome.get("success") is not None:
        pred_risk = float(predicted.get("risk_score", 0.5))
        predicted_success = pred_risk < DEFAULT_RISK_THRESHOLD
        actual_success = actual_outcome.get("success", True)
        scores.append(1.0 if predicted_success == actual_success else 0.0)

    return sum(scores) / len(scores) if scores else 0.5


# =============================================================================
# GATE FUNCTIONS
# =============================================================================


def check_before_action(
    action_type: ActionType,
    action_data: Dict[str, Any],
    action_id: Optional[str] = None,
    override_decision: bool = False,
    simulated_by: str = "SYSTEM",
) -> Tuple[bool, SimulationResult]:
    """
    Check whether an action should proceed based on simulation.

    This is the main gate function to call before risky actions.

    Args:
        action_type: Type of action to simulate
        action_data: Data about the action
        action_id: Optional ID of the action
        override_decision: If True, proceed regardless of simulation
        simulated_by: Who is running the check

    Returns:
        Tuple of (should_proceed: bool, simulation: SimulationResult)
    """
    result = simulate_impact(
        action_type=action_type,
        action_data=action_data,
        action_id=action_id,
        simulated_by=simulated_by,
    )

    if override_decision:
        logger.warning(
            "Override applied for simulation %s (decision was %s)",
            result.simulation_id,
            result.decision.value,
        )
        return True, result

    should_proceed = result.decision in (
        SimulationDecision.PROCEED,
        SimulationDecision.WARN,
    )

    if not should_proceed:
        logger.warning(
            "Action blocked by simulation %s: %s",
            result.simulation_id,
            result.reasoning,
        )

    return should_proceed, result


def get_simulation_accuracy_stats() -> Dict[str, Any]:
    """
    Get aggregate statistics on simulation accuracy.

    Used for calibrating and improving simulations.

    Returns:
        Dict with accuracy statistics by action type
    """
    query = """
    SELECT 
        action_type,
        COUNT(*) as total_simulations,
        COUNT(accuracy_score) as with_outcomes,
        AVG(accuracy_score) as avg_accuracy,
        AVG(risk_score) as avg_risk_predicted,
        COUNT(*) FILTER (WHERE decision = 'block') as blocked,
        COUNT(*) FILTER (WHERE decision = 'proceed') as proceeded
    FROM impact_simulations
    GROUP BY action_type
    ORDER BY total_simulations DESC
    """
    try:
        result = _execute_sql(query)
        return {
            "by_action_type": result.get("rows", []),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error("Failed to get accuracy stats: %s", str(e))
        return {"error": str(e)}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "ImpactSeverity",
    "SimulationDecision",
    "ActionType",
    # Data Classes
    "SimulationResult",
    # Core Functions
    "simulate_impact",
    "check_before_action",
    "record_actual_outcome",
    "get_simulation_accuracy_stats",
    # Setup
    "create_impact_simulations_table",
]
