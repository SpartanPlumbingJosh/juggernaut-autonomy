"""
Self-healing workflow system for autonomous agent resilience.

This module provides enhanced self-healing capabilities beyond basic circuit breakers:
- Intelligent retry strategies based on failure type
- Alternative model fallback when primary model fails
- Workflow-level recovery with state preservation
- Health monitoring and telemetry
- Automatic degradation and recovery
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Classification of failure types for targeted recovery strategies."""
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    AUTH_ERROR = "auth_error"
    INVALID_RESPONSE = "invalid_response"
    MODEL_ERROR = "model_error"
    TOOL_ERROR = "tool_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


class RecoveryStrategy(Enum):
    """Recovery strategies for different failure types."""
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    SWITCH_MODEL = "switch_model"
    DEGRADE_GRACEFULLY = "degrade_gracefully"
    SKIP_AND_CONTINUE = "skip_and_continue"
    FAIL_FAST = "fail_fast"


@dataclass
class FailureContext:
    """Context information about a failure for recovery decisions."""
    failure_type: FailureType
    error_message: str
    component: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryAction:
    """Action to take for recovery."""
    strategy: RecoveryStrategy
    params: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


class SelfHealingManager:
    """Manages self-healing workflows with intelligent recovery strategies."""
    
    def __init__(self):
        """Initialize self-healing manager."""
        # Use deque with maxlen to prevent memory leak from unbounded growth
        self.failure_history: Deque[FailureContext] = deque(maxlen=1000)
        self.recovery_attempts: Dict[str, int] = {}
        self.successful_recoveries: Dict[str, int] = {}
        self.model_fallback_chain: List[str] = [
            "google/gemini-2.0-flash-exp:free",
            "deepseek/deepseek-v3.2",
            "deepseek/deepseek-v3.1",
        ]
        
    def classify_failure(self, error: Exception, component: str) -> FailureContext:
        """Classify a failure into a specific type for targeted recovery."""
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        if "rate limit" in error_str or "429" in error_str:
            failure_type = FailureType.RATE_LIMIT
        elif "timeout" in error_str or "timed out" in error_str:
            failure_type = FailureType.TIMEOUT
        elif "auth" in error_str or "401" in error_str or "403" in error_str:
            failure_type = FailureType.AUTH_ERROR
        elif "json" in error_str or "parse" in error_str or "invalid" in error_str:
            failure_type = FailureType.INVALID_RESPONSE
        elif "model" in error_str or "completion" in error_str:
            failure_type = FailureType.MODEL_ERROR
        elif "tool" in error_str or "execution" in error_str:
            failure_type = FailureType.TOOL_ERROR
        elif "connection" in error_str or "network" in error_str:
            failure_type = FailureType.NETWORK_ERROR
        else:
            failure_type = FailureType.UNKNOWN
            
        context = FailureContext(
            failure_type=failure_type,
            error_message=str(error),
            component=component,
            metadata={"error_type": error_type}
        )
        
        self.failure_history.append(context)
        logger.info(f"Classified failure as {failure_type.value} in {component}")
        
        return context
    
    def select_recovery_strategy(self, context: FailureContext) -> RecoveryAction:
        """Select appropriate recovery strategy based on failure context."""
        component_key = f"{context.component}:{context.failure_type.value}"
        retry_count = self.recovery_attempts.get(component_key, 0)
        
        if context.failure_type == FailureType.RATE_LIMIT:
            if retry_count < 2:
                return RecoveryAction(
                    strategy=RecoveryStrategy.RETRY_WITH_BACKOFF,
                    params={"delay": 60 * (retry_count + 1), "max_retries": 3},
                    reason="Rate limit - exponential backoff"
                )
            else:
                return RecoveryAction(
                    strategy=RecoveryStrategy.SWITCH_MODEL,
                    params={"fallback_chain": self.model_fallback_chain},
                    reason="Rate limit persists - switching model"
                )
                
        elif context.failure_type == FailureType.MODEL_ERROR:
            return RecoveryAction(
                strategy=RecoveryStrategy.SWITCH_MODEL,
                params={"fallback_chain": self.model_fallback_chain},
                reason="Model error - trying alternative model"
            )
            
        elif context.failure_type == FailureType.TIMEOUT:
            if retry_count < 2:
                return RecoveryAction(
                    strategy=RecoveryStrategy.RETRY_WITH_BACKOFF,
                    params={"delay": 10, "max_retries": 2},
                    reason="Timeout - retry with backoff"
                )
            else:
                return RecoveryAction(
                    strategy=RecoveryStrategy.DEGRADE_GRACEFULLY,
                    params={"reduce_complexity": True},
                    reason="Persistent timeout - degrading request"
                )
                
        elif context.failure_type == FailureType.TOOL_ERROR:
            if retry_count < 1:
                return RecoveryAction(
                    strategy=RecoveryStrategy.RETRY_WITH_BACKOFF,
                    params={"delay": 5, "max_retries": 1},
                    reason="Tool error - single retry"
                )
            else:
                return RecoveryAction(
                    strategy=RecoveryStrategy.SKIP_AND_CONTINUE,
                    params={"create_fallback_task": True},
                    reason="Tool error persists - skip and create fallback"
                )
                
        elif context.failure_type == FailureType.AUTH_ERROR:
            return RecoveryAction(
                strategy=RecoveryStrategy.FAIL_FAST,
                params={},
                reason="Auth error - requires manual intervention"
            )
            
        else:
            if retry_count < 1:
                return RecoveryAction(
                    strategy=RecoveryStrategy.RETRY_WITH_BACKOFF,
                    params={"delay": 5, "max_retries": 1},
                    reason="Unknown error - single retry attempt"
                )
            else:
                return RecoveryAction(
                    strategy=RecoveryStrategy.FAIL_FAST,
                    params={},
                    reason="Unknown error persists - failing fast"
                )
    
    def record_recovery_attempt(self, context: FailureContext) -> None:
        """Record a recovery attempt for telemetry."""
        component_key = f"{context.component}:{context.failure_type.value}"
        self.recovery_attempts[component_key] = self.recovery_attempts.get(component_key, 0) + 1
        
    def record_recovery_success(self, context: FailureContext) -> None:
        """Record a successful recovery for telemetry."""
        component_key = f"{context.component}:{context.failure_type.value}"
        self.successful_recoveries[component_key] = self.successful_recoveries.get(component_key, 0) + 1
        logger.info(f"Recovery successful for {component_key}")
        
    def get_next_fallback_model(self, current_model: str) -> Optional[str]:
        """Get next model in fallback chain."""
        try:
            current_index = self.model_fallback_chain.index(current_model)
            if current_index < len(self.model_fallback_chain) - 1:
                next_model = self.model_fallback_chain[current_index + 1]
                logger.info(f"Falling back from {current_model} to {next_model}")
                return next_model
        except ValueError:
            if self.model_fallback_chain:
                return self.model_fallback_chain[0]
        
        return None
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """Get self-healing health metrics for monitoring."""
        total_attempts = sum(self.recovery_attempts.values())
        total_successes = sum(self.successful_recoveries.values())
        recovery_rate = (total_successes / total_attempts * 100) if total_attempts > 0 else 0
        
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_failures = [f for f in self.failure_history if f.timestamp > one_hour_ago]
        
        failure_by_type = {}
        for failure in recent_failures:
            failure_type = failure.failure_type.value
            failure_by_type[failure_type] = failure_by_type.get(failure_type, 0) + 1
        
        return {
            "total_recovery_attempts": total_attempts,
            "successful_recoveries": total_successes,
            "recovery_rate_percent": round(recovery_rate, 2),
            "recent_failures_1h": len(recent_failures),
            "failure_breakdown": failure_by_type,
            "component_health": self._calculate_component_health(),
        }
    
    def _calculate_component_health(self) -> Dict[str, str]:
        """Calculate health status for each component."""
        health = {}
        
        for component_key, attempts in self.recovery_attempts.items():
            successes = self.successful_recoveries.get(component_key, 0)
            success_rate = (successes / attempts * 100) if attempts > 0 else 100
            
            if success_rate >= 80:
                health[component_key] = "healthy"
            elif success_rate >= 50:
                health[component_key] = "degraded"
            else:
                health[component_key] = "unhealthy"
        
        return health
    
    def should_trigger_alert(self) -> Tuple[bool, str]:
        """Check if system health warrants an alert."""
        metrics = self.get_health_metrics()
        
        if metrics["recovery_rate_percent"] < 50 and metrics["total_recovery_attempts"] > 5:
            return True, f"Low recovery rate: {metrics['recovery_rate_percent']}%"
        
        if metrics["recent_failures_1h"] > 20:
            return True, f"High failure rate: {metrics['recent_failures_1h']} failures in last hour"
        
        unhealthy = [k for k, v in metrics["component_health"].items() if v == "unhealthy"]
        if unhealthy:
            return True, f"Unhealthy components: {', '.join(unhealthy)}"
        
        return False, ""


_self_healing_manager: Optional[SelfHealingManager] = None


def get_self_healing_manager() -> SelfHealingManager:
    """Get or create global self-healing manager instance."""
    global _self_healing_manager
    if _self_healing_manager is None:
        _self_healing_manager = SelfHealingManager()
    return _self_healing_manager
