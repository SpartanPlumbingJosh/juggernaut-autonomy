"""
JUGGERNAUT Task Reasoning Module

Provides intelligent self-assessment of whether the system can handle a task
before attempting execution. Prevents infinite retry loops by identifying
tasks that require capabilities the system doesn't have.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .database import query_db, log_execution

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Known system capabilities - things Juggernaut can actually do
SYSTEM_CAPABILITIES: Dict[str, str] = {
    "database_read": "Query PostgreSQL database for information",
    "database_write": "Insert/update records in PostgreSQL database",
    "github_read": "Read files from GitHub repository",
    "github_write": "Create/update files in GitHub repository",
    "github_pr": "Create and manage pull requests",
    "code_generation": "Generate Python/JS/SQL code",
    "code_analysis": "Analyze existing code for issues",
    "documentation": "Write documentation and comments",
    "task_creation": "Create new tasks in governance system",
    "log_analysis": "Analyze execution logs for errors",
    "slack_notify": "Send Slack notifications (when configured)",
    "railway_api": "Interact with Railway deployment API",
    "vercel_api": "Interact with Vercel deployment API",
    "openai_api": "Call OpenAI API for LLM consultation",
    "web_search": "Search the web for information",
}

# Things Juggernaut CANNOT do autonomously
SYSTEM_LIMITATIONS: Dict[str, str] = {
    "human_approval": "Cannot auto-approve high-risk actions - requires Josh",
    "external_api_new": "Cannot integrate new external APIs without credentials",
    "production_deploy": "Cannot deploy to production without approval",
    "financial_transaction": "Cannot make payments or financial commitments",
    "data_deletion": "Cannot delete production data without approval",
    "human_contact": "Cannot contact customers or external parties",
    "contract_signing": "Cannot sign contracts or legal documents",
    "mcp_creation": "Cannot create MCP servers - requires manual config",
    "credential_creation": "Cannot generate or obtain new API keys",
    "infrastructure_creation": "Cannot provision new servers/services",
}

# Risk threshold for automatic execution (0-1 scale)
AUTO_EXECUTE_RISK_THRESHOLD: float = 0.5


class TaskDecision(Enum):
    """Possible outcomes of task feasibility assessment."""
    
    PROCEED = "proceed"  # System can handle this task
    DEFER = "defer"  # Needs human input or approval
    REJECT = "reject"  # System cannot handle this task at all
    RETRY_LATER = "retry_later"  # Temporarily unable (resources, etc)


@dataclass
class TaskAssessment:
    """Result of assessing whether a task can be handled."""
    
    decision: TaskDecision
    confidence: float  # 0-1, how confident the system is
    reasoning: str  # Explanation of why this decision was made
    can_handle: bool  # Simple boolean for quick checks
    missing_capabilities: List[str] = field(default_factory=list)
    required_actions: List[str] = field(default_factory=list)
    suggested_approach: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "decision": self.decision.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "can_handle": self.can_handle,
            "missing_capabilities": self.missing_capabilities,
            "required_actions": self.required_actions,
            "suggested_approach": self.suggested_approach,
        }


def _analyze_task_requirements(
    title: str,
    description: str,
    task_type: str
) -> Dict[str, Any]:
    """
    Analyze what capabilities a task likely requires.
    
    Uses keyword matching as a first pass to identify needed capabilities
    and potential blockers.
    
    Args:
        title: Task title.
        description: Task description.
        task_type: Task type from governance_tasks.
        
    Returns:
        Dict with required capabilities and potential blockers.
    """
    text = f"{title} {description} {task_type}".lower()
    
    required_capabilities: List[str] = []
    potential_blockers: List[str] = []
    
    # Keywords that map to required capabilities
    capability_keywords: Dict[str, List[str]] = {
        "database_read": ["query", "select", "fetch", "read data", "get from db"],
        "database_write": ["insert", "update", "write to db", "create record"],
        "github_read": ["read file", "get code", "check repo"],
        "github_write": ["commit", "push", "create file", "update file"],
        "github_pr": ["pull request", "pr", "merge", "review"],
        "code_generation": ["implement", "create module", "write code", "add function", "build"],
        "code_analysis": ["analyze code", "review code", "find bugs", "audit"],
        "documentation": ["document", "readme", "docstring"],
        "task_creation": ["create task", "add task", "schedule"],
        "log_analysis": ["check logs", "analyze errors", "diagnose"],
        "slack_notify": ["slack", "notify", "alert team"],
        "railway_api": ["railway", "deploy service"],
        "vercel_api": ["vercel", "frontend deploy"],
    }
    
    # Keywords that indicate potential blockers/limitations
    blocker_keywords: Dict[str, List[str]] = {
        "human_approval": ["approval", "approve", "high risk", "critical risk", "waiting_approval"],
        "production_deploy": ["production", "deploy to prod", "release to prod"],
        "financial_transaction": ["payment", "charge", "invoice", "billing", "purchase"],
        "data_deletion": ["delete all", "drop table", "purge", "remove data"],
        "human_contact": ["contact customer", "email client", "call", "reach out"],
        "contract_signing": ["contract", "agreement", "sign document", "legal"],
        "external_api_new": ["new api", "integrate with", "third party service"],
        "mcp_creation": ["create mcp", "mcp server", "model context protocol"],
        "credential_creation": ["api key", "credentials", "auth token", "password"],
        "infrastructure_creation": ["new server", "provision", "create service", "spin up"],
    }
    
    # Check what capabilities are needed
    for capability, keywords in capability_keywords.items():
        if any(kw in text for kw in keywords):
            required_capabilities.append(capability)
    
    # Check for potential blockers
    for blocker, keywords in blocker_keywords.items():
        if any(kw in text for kw in keywords):
            potential_blockers.append(blocker)
    
    return {
        "required_capabilities": required_capabilities,
        "potential_blockers": potential_blockers,
        "task_complexity": _estimate_complexity(text),
    }


def _estimate_complexity(text: str) -> str:
    """
    Estimate task complexity based on text analysis.
    
    Args:
        text: Combined task title and description.
        
    Returns:
        Complexity level: 'low', 'medium', 'high', or 'critical'.
    """
    # High complexity indicators
    high_indicators = [
        "multiple", "integrate", "redesign", "refactor entire",
        "migration", "infrastructure", "security", "production"
    ]
    
    # Medium complexity indicators
    medium_indicators = [
        "implement", "create module", "api", "database schema",
        "workflow", "automation"
    ]
    
    text_lower = text.lower()
    
    if any(ind in text_lower for ind in high_indicators):
        return "high"
    elif any(ind in text_lower for ind in medium_indicators):
        return "medium"
    else:
        return "low"


def _check_system_state() -> Dict[str, Any]:
    """
    Check current system state that might affect task execution.
    
    Returns:
        Dict with current system status.
    """
    try:
        # Check for tasks already waiting on approval
        approval_result = query_db(
            "SELECT COUNT(*) as count FROM governance_tasks WHERE status = 'waiting_approval'"
        )
        pending_approvals = approval_result.get("rows", [{}])[0].get("count", 0)
        
        # Check for recent errors (last 15 mins)
        error_result = query_db(
            """
            SELECT COUNT(*) as count FROM execution_logs 
            WHERE level = 'error' 
            AND created_at > NOW() - INTERVAL '15 minutes'
            """
        )
        recent_errors = error_result.get("rows", [{}])[0].get("count", 0)
        
        return {
            "pending_approvals": int(pending_approvals),
            "recent_errors": int(recent_errors),
            "system_healthy": int(recent_errors) < 10,
        }
    except Exception as e:
        logger.warning("Failed to check system state: %s", str(e))
        return {
            "pending_approvals": 0,
            "recent_errors": 0,
            "system_healthy": True,
        }


def assess_task(
    task_id: str,
    title: str,
    description: str,
    task_type: str,
    priority: str = "medium",
    risk_score: Optional[float] = None
) -> TaskAssessment:
    """
    Assess whether Juggernaut can handle a specific task.
    
    This is the main entry point for task reasoning. Call this before
    attempting to execute any task to determine if it's feasible.
    
    Args:
        task_id: Task UUID.
        title: Task title.
        description: Task description.
        task_type: Type of task (e.g., 'implementation', 'audit').
        priority: Task priority level.
        risk_score: Optional pre-calculated risk score (0-1).
        
    Returns:
        TaskAssessment with decision and reasoning.
    """
    logger.info("Assessing task feasibility: %s", task_id[:8])
    
    # Analyze task requirements
    requirements = _analyze_task_requirements(title, description, task_type)
    required_caps = requirements["required_capabilities"]
    blockers = requirements["potential_blockers"]
    complexity = requirements["task_complexity"]
    
    # Check system state
    system_state = _check_system_state()
    
    # Build reasoning
    reasoning_parts: List[str] = []
    missing_capabilities: List[str] = []
    required_actions: List[str] = []
    
    # Check if we have all required capabilities
    for cap in required_caps:
        if cap in SYSTEM_CAPABILITIES:
            reasoning_parts.append(f"Has capability: {cap}")
        else:
            missing_capabilities.append(cap)
            reasoning_parts.append(f"Missing capability: {cap}")
    
    # Check for blockers
    for blocker in blockers:
        if blocker in SYSTEM_LIMITATIONS:
            limitation = SYSTEM_LIMITATIONS[blocker]
            reasoning_parts.append(f"Limitation applies: {limitation}")
            required_actions.append(f"Need: {limitation}")
    
    # Determine decision
    decision: TaskDecision
    confidence: float
    can_handle: bool
    suggested_approach: Optional[str] = None
    
    # REJECT: Missing critical capabilities
    if missing_capabilities:
        decision = TaskDecision.REJECT
        confidence = 0.9
        can_handle = False
        reasoning_parts.append(
            f"REJECT: Missing required capabilities: {', '.join(missing_capabilities)}"
        )
        suggested_approach = "This task requires capabilities not currently available in the system."
    
    # DEFER: Has blockers that need human intervention
    elif blockers:
        # Check if it's the approval blocker specifically
        if "human_approval" in blockers:
            decision = TaskDecision.DEFER
            confidence = 0.95
            can_handle = False
            reasoning_parts.append(
                "DEFER: Task requires human approval due to risk level."
            )
            suggested_approach = "Submit to Josh for approval before proceeding."
            required_actions.append("Get approval from Josh")
        else:
            decision = TaskDecision.DEFER
            confidence = 0.8
            can_handle = False
            reasoning_parts.append(
                f"DEFER: Task hits system limitations: {', '.join(blockers)}"
            )
            suggested_approach = "Human intervention needed for: " + ", ".join(blockers)
    
    # RETRY_LATER: System not healthy
    elif not system_state["system_healthy"]:
        decision = TaskDecision.RETRY_LATER
        confidence = 0.7
        can_handle = False
        reasoning_parts.append(
            f"RETRY_LATER: System has {system_state['recent_errors']} recent errors."
        )
        suggested_approach = "Wait for system to stabilize before attempting."
    
    # PROCEED: We can handle this
    else:
        # High complexity might reduce confidence
        if complexity == "high":
            confidence = 0.7
        elif complexity == "medium":
            confidence = 0.85
        else:
            confidence = 0.95
            
        decision = TaskDecision.PROCEED
        can_handle = True
        reasoning_parts.append(
            f"PROCEED: All required capabilities available. Complexity: {complexity}"
        )
    
    # Build final reasoning string
    reasoning = "\n".join(reasoning_parts)
    
    # Log the assessment
    log_execution(
        worker_id="TASK_REASONER",
        action="task.assess",
        message=f"Task {task_id[:8]}: {decision.value} (confidence: {confidence:.2f})",
        level="info",
        task_id=task_id,
        output_data={
            "decision": decision.value,
            "confidence": confidence,
            "can_handle": can_handle,
            "complexity": complexity,
            "blockers": blockers,
        }
    )
    
    return TaskAssessment(
        decision=decision,
        confidence=confidence,
        reasoning=reasoning,
        can_handle=can_handle,
        missing_capabilities=missing_capabilities,
        required_actions=required_actions,
        suggested_approach=suggested_approach,
    )


def can_handle_task(
    task_id: str,
    title: str,
    description: str,
    task_type: str
) -> bool:
    """
    Quick check if a task can be handled.
    
    Convenience wrapper around assess_task() for simple boolean checks.
    
    Args:
        task_id: Task UUID.
        title: Task title.
        description: Task description.
        task_type: Task type.
        
    Returns:
        True if task can be handled, False otherwise.
    """
    assessment = assess_task(task_id, title, description, task_type)
    return assessment.can_handle


def mark_task_unhandleable(
    task_id: str,
    reason: str,
    suggested_action: str
) -> bool:
    """
    Mark a task as unhandleable and update its status.
    
    This should be called when a task is assessed as REJECT or DEFER
    to prevent further retry attempts.
    
    Args:
        task_id: Task UUID.
        reason: Why the task cannot be handled.
        suggested_action: What should happen next.
        
    Returns:
        True if successfully updated, False otherwise.
    """
    try:
        # Escape single quotes in reason and action
        safe_reason = reason.replace("'", "''")
        safe_action = suggested_action.replace("'", "''")
        
        result = query_db(
            f"""
            UPDATE governance_tasks
            SET status = 'blocked',
                metadata = COALESCE(metadata, '{{}}'::jsonb) || 
                    jsonb_build_object(
                        'blocked_reason', '{safe_reason}',
                        'suggested_action', '{safe_action}',
                        'blocked_at', NOW()::text
                    )
            WHERE id = '{task_id}'::uuid
            RETURNING id
            """
        )
        
        success = result.get("rowCount", 0) > 0
        
        if success:
            log_execution(
                worker_id="TASK_REASONER",
                action="task.blocked",
                message=f"Task {task_id[:8]} marked as blocked: {reason[:50]}",
                level="warn",
                task_id=task_id,
                output_data={"reason": reason, "suggested_action": suggested_action}
            )
        
        return success
        
    except Exception as e:
        logger.error("Failed to mark task %s as unhandleable: %s", task_id, str(e))
        return False


# Module exports
__all__ = [
    "TaskDecision",
    "TaskAssessment",
    "assess_task",
    "can_handle_task",
    "mark_task_unhandleable",
    "SYSTEM_CAPABILITIES",
    "SYSTEM_LIMITATIONS",
]
