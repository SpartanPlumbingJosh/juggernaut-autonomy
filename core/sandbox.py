"""
Sandbox enforcement for experiments.

This module provides sandboxed innovation boundaries:
- Risk level classification for experiments
- High-risk experiments require approval
- Sandbox limits enforced (max spend, affected scope)
- Experiments cannot affect production without approval
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level classification for experiments."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SandboxScope(Enum):
    """Allowed scope for sandboxed experiments."""
    
    TEST_ONLY = "test_only"
    STAGING = "staging"
    PRODUCTION = "production"


# Default sandbox configuration constants
DEFAULT_MAX_SPEND_LOW_RISK = 10.0  # $10 for low-risk experiments
DEFAULT_MAX_SPEND_MEDIUM_RISK = 50.0  # $50 for medium-risk (needs approval)
DEFAULT_MAX_ITERATIONS_LOW = 100
DEFAULT_MAX_ITERATIONS_MEDIUM = 500
PRODUCTION_APPROVAL_REQUIRED = True


@dataclass
class SandboxConfig:
    """Configuration for experiment sandbox boundaries."""
    
    max_spend: float
    max_iterations: int
    allowed_scope: SandboxScope
    requires_approval: bool
    allowed_tables: list[str]
    blocked_operations: list[str]
    
    @classmethod
    def for_risk_level(cls, risk_level: RiskLevel) -> "SandboxConfig":
        """Create sandbox config based on risk level.
        
        Args:
            risk_level: The experiment's risk classification.
            
        Returns:
            SandboxConfig appropriate for the risk level.
        """
        configs = {
            RiskLevel.LOW: cls(
                max_spend=DEFAULT_MAX_SPEND_LOW_RISK,
                max_iterations=DEFAULT_MAX_ITERATIONS_LOW,
                allowed_scope=SandboxScope.TEST_ONLY,
                requires_approval=False,
                allowed_tables=["experiment_results", "experiment_logs"],
                blocked_operations=["DELETE", "DROP", "TRUNCATE", "ALTER"],
            ),
            RiskLevel.MEDIUM: cls(
                max_spend=DEFAULT_MAX_SPEND_MEDIUM_RISK,
                max_iterations=DEFAULT_MAX_ITERATIONS_MEDIUM,
                allowed_scope=SandboxScope.STAGING,
                requires_approval=True,
                allowed_tables=["experiment_results", "experiment_logs", "staging_data"],
                blocked_operations=["DROP", "TRUNCATE", "ALTER"],
            ),
            RiskLevel.HIGH: cls(
                max_spend=100.0,
                max_iterations=1000,
                allowed_scope=SandboxScope.STAGING,
                requires_approval=True,
                allowed_tables=["experiment_results", "experiment_logs", "staging_data"],
                blocked_operations=["DROP", "TRUNCATE"],
            ),
            RiskLevel.CRITICAL: cls(
                max_spend=500.0,
                max_iterations=5000,
                allowed_scope=SandboxScope.PRODUCTION,
                requires_approval=True,
                allowed_tables=[],  # Empty = all allowed with approval
                blocked_operations=["DROP"],
            ),
        }
        return configs.get(risk_level, configs[RiskLevel.LOW])
    
    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for JSON storage.
        
        Returns:
            Dictionary representation of the config.
        """
        return {
            "max_spend": self.max_spend,
            "max_iterations": self.max_iterations,
            "allowed_scope": self.allowed_scope.value,
            "requires_approval": self.requires_approval,
            "allowed_tables": self.allowed_tables,
            "blocked_operations": self.blocked_operations,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SandboxConfig":
        """Create config from dictionary.
        
        Args:
            data: Dictionary containing config values.
            
        Returns:
            SandboxConfig instance.
        """
        return cls(
            max_spend=data.get("max_spend", DEFAULT_MAX_SPEND_LOW_RISK),
            max_iterations=data.get("max_iterations", DEFAULT_MAX_ITERATIONS_LOW),
            allowed_scope=SandboxScope(data.get("allowed_scope", "test_only")),
            requires_approval=data.get("requires_approval", True),
            allowed_tables=data.get("allowed_tables", []),
            blocked_operations=data.get("blocked_operations", []),
        )


@dataclass
class SandboxViolation:
    """Represents a sandbox boundary violation."""
    
    violation_type: str
    message: str
    current_value: Any
    limit_value: Any
    timestamp: datetime
    
    def to_dict(self) -> dict[str, Any]:
        """Convert violation to dictionary.
        
        Returns:
            Dictionary representation of the violation.
        """
        return {
            "violation_type": self.violation_type,
            "message": self.message,
            "current_value": self.current_value,
            "limit_value": self.limit_value,
            "timestamp": self.timestamp.isoformat(),
        }


class SandboxEnforcer:
    """Enforces sandbox boundaries for experiments."""
    
    def __init__(self, config: SandboxConfig) -> None:
        """Initialize enforcer with sandbox config.
        
        Args:
            config: The sandbox configuration to enforce.
        """
        self.config = config
        self.violations: list[SandboxViolation] = []
    
    def check_spend_limit(
        self, current_spend: float, additional_spend: float
    ) -> tuple[bool, Optional[SandboxViolation]]:
        """Check if spending would exceed sandbox limits.
        
        Args:
            current_spend: Amount already spent.
            additional_spend: Amount to be spent.
            
        Returns:
            Tuple of (allowed, violation if any).
        """
        total = current_spend + additional_spend
        if total > self.config.max_spend:
            violation = SandboxViolation(
                violation_type="spend_limit_exceeded",
                message=f"Spend would exceed limit: ${total:.2f} > ${self.config.max_spend:.2f}",
                current_value=total,
                limit_value=self.config.max_spend,
                timestamp=datetime.utcnow(),
            )
            self.violations.append(violation)
            logger.warning("Sandbox violation: %s", violation.message)
            return False, violation
        return True, None
    
    def check_iteration_limit(
        self, current_iterations: int
    ) -> tuple[bool, Optional[SandboxViolation]]:
        """Check if iterations would exceed sandbox limits.
        
        Args:
            current_iterations: Current iteration count.
            
        Returns:
            Tuple of (allowed, violation if any).
        """
        if current_iterations >= self.config.max_iterations:
            violation = SandboxViolation(
                violation_type="iteration_limit_exceeded",
                message=f"Iterations exceeded: {current_iterations} >= {self.config.max_iterations}",
                current_value=current_iterations,
                limit_value=self.config.max_iterations,
                timestamp=datetime.utcnow(),
            )
            self.violations.append(violation)
            logger.warning("Sandbox violation: %s", violation.message)
            return False, violation
        return True, None
    
    def check_scope_allowed(
        self, target_scope: SandboxScope
    ) -> tuple[bool, Optional[SandboxViolation]]:
        """Check if target scope is allowed.
        
        Args:
            target_scope: The scope the experiment wants to access.
            
        Returns:
            Tuple of (allowed, violation if any).
        """
        scope_hierarchy = {
            SandboxScope.TEST_ONLY: 0,
            SandboxScope.STAGING: 1,
            SandboxScope.PRODUCTION: 2,
        }
        
        if scope_hierarchy[target_scope] > scope_hierarchy[self.config.allowed_scope]:
            violation = SandboxViolation(
                violation_type="scope_not_allowed",
                message=f"Scope {target_scope.value} not allowed. Max: {self.config.allowed_scope.value}",
                current_value=target_scope.value,
                limit_value=self.config.allowed_scope.value,
                timestamp=datetime.utcnow(),
            )
            self.violations.append(violation)
            logger.warning("Sandbox violation: %s", violation.message)
            return False, violation
        return True, None
    
    def check_table_access(
        self, table_name: str
    ) -> tuple[bool, Optional[SandboxViolation]]:
        """Check if table access is allowed.
        
        Args:
            table_name: Name of the table to access.
            
        Returns:
            Tuple of (allowed, violation if any).
        """
        # Empty allowed_tables means all tables allowed (with approval)
        if not self.config.allowed_tables:
            return True, None
            
        if table_name not in self.config.allowed_tables:
            violation = SandboxViolation(
                violation_type="table_access_denied",
                message=f"Access to table '{table_name}' not allowed",
                current_value=table_name,
                limit_value=self.config.allowed_tables,
                timestamp=datetime.utcnow(),
            )
            self.violations.append(violation)
            logger.warning("Sandbox violation: %s", violation.message)
            return False, violation
        return True, None
    
    def check_operation_allowed(
        self, operation: str
    ) -> tuple[bool, Optional[SandboxViolation]]:
        """Check if database operation is allowed.
        
        Args:
            operation: The SQL operation (SELECT, INSERT, DELETE, etc.)
            
        Returns:
            Tuple of (allowed, violation if any).
        """
        op_upper = operation.upper()
        if op_upper in self.config.blocked_operations:
            violation = SandboxViolation(
                violation_type="operation_blocked",
                message=f"Operation '{op_upper}' is blocked in this sandbox",
                current_value=op_upper,
                limit_value=self.config.blocked_operations,
                timestamp=datetime.utcnow(),
            )
            self.violations.append(violation)
            logger.warning("Sandbox violation: %s", violation.message)
            return False, violation
        return True, None
    
    def requires_approval(self) -> bool:
        """Check if this sandbox configuration requires approval.
        
        Returns:
            True if approval is required.
        """
        return self.config.requires_approval
    
    def get_violations(self) -> list[dict[str, Any]]:
        """Get all recorded violations.
        
        Returns:
            List of violation dictionaries.
        """
        return [v.to_dict() for v in self.violations]
    
    def clear_violations(self) -> None:
        """Clear recorded violations."""
        self.violations = []


def classify_risk_level(
    budget_limit: float,
    affects_production: bool,
    modifies_data: bool,
    uses_external_apis: bool,
) -> RiskLevel:
    """Classify experiment risk level based on characteristics.
    
    Args:
        budget_limit: Maximum budget for the experiment.
        affects_production: Whether it can affect production.
        modifies_data: Whether it modifies existing data.
        uses_external_apis: Whether it calls external paid APIs.
        
    Returns:
        Appropriate RiskLevel classification.
    """
    if affects_production:
        if budget_limit > 100 or modifies_data:
            return RiskLevel.CRITICAL
        return RiskLevel.HIGH
    
    if modifies_data or uses_external_apis:
        if budget_limit > 50:
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM
    
    if budget_limit > DEFAULT_MAX_SPEND_LOW_RISK:
        return RiskLevel.MEDIUM
    
    return RiskLevel.LOW


def validate_experiment_execution(
    experiment_id: str,
    risk_level: RiskLevel,
    current_spend: float,
    current_iterations: int,
    target_scope: SandboxScope,
    is_approved: bool,
) -> tuple[bool, list[dict[str, Any]]]:
    """Validate if experiment execution is allowed.
    
    Args:
        experiment_id: The experiment identifier.
        risk_level: Classified risk level.
        current_spend: Amount already spent.
        current_iterations: Current iteration count.
        target_scope: Scope the experiment wants to access.
        is_approved: Whether the experiment has been approved.
        
    Returns:
        Tuple of (allowed, list of violations).
    """
    config = SandboxConfig.for_risk_level(risk_level)
    enforcer = SandboxEnforcer(config)
    
    # Check if approval is required but not given
    if enforcer.requires_approval() and not is_approved:
        violation = SandboxViolation(
            violation_type="approval_required",
            message=f"Experiment {experiment_id} requires approval for risk level {risk_level.value}",
            current_value=is_approved,
            limit_value=True,
            timestamp=datetime.utcnow(),
        )
        logger.warning("Sandbox blocked: %s", violation.message)
        return False, [violation.to_dict()]
    
    # Check spend limit (allow $0 additional for now, actual check happens per-action)
    allowed, _ = enforcer.check_spend_limit(current_spend, 0)
    if not allowed:
        return False, enforcer.get_violations()
    
    # Check iteration limit
    allowed, _ = enforcer.check_iteration_limit(current_iterations)
    if not allowed:
        return False, enforcer.get_violations()
    
    # Check scope
    allowed, _ = enforcer.check_scope_allowed(target_scope)
    if not allowed:
        return False, enforcer.get_violations()
    
    logger.info(
        "Experiment %s passed sandbox validation (risk=%s, approved=%s)",
        experiment_id,
        risk_level.value,
        is_approved,
    )
    return True, []


def get_sandbox_config_for_experiment(
    risk_level_str: str,
) -> dict[str, Any]:
    """Get sandbox configuration for an experiment based on risk level string.
    
    Args:
        risk_level_str: Risk level as string (low, medium, high, critical).
        
    Returns:
        Sandbox configuration dictionary.
    """
    try:
        risk_level = RiskLevel(risk_level_str.lower())
    except ValueError:
        logger.warning("Invalid risk level '%s', defaulting to LOW", risk_level_str)
        risk_level = RiskLevel.LOW
    
    config = SandboxConfig.for_risk_level(risk_level)
    return config.to_dict()
