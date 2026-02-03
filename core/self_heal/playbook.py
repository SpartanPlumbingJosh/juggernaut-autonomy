"""
Self-Heal Playbook System

Base classes for creating diagnosis and repair playbooks.
Playbooks are bounded, safe procedures with verification.

Part of Milestone 2: Self-Heal Workflows
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timezone
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class StepType(str, Enum):
    """Types of playbook steps."""
    CHECK = "check"           # Read-only check
    QUERY = "query"           # Database query
    API_CALL = "api_call"     # External API call
    REPAIR = "repair"         # Safe repair action
    VERIFY = "verify"         # Verification check
    MANUAL = "manual"         # Requires manual action


class StepStatus(str, Enum):
    """Status of a playbook step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlaybookStep:
    """A single step in a playbook."""
    
    def __init__(
        self,
        name: str,
        step_type: StepType,
        description: str,
        action: Callable,
        safe: bool = True,
        required: bool = True,
        timeout_seconds: int = 30
    ):
        """
        Initialize a playbook step.
        
        Args:
            name: Step name
            step_type: Type of step
            description: Human-readable description
            action: Callable to execute
            safe: Whether step is safe (read-only or bounded)
            required: Whether step is required for playbook success
            timeout_seconds: Maximum execution time
        """
        self.name = name
        self.step_type = step_type
        self.description = description
        self.action = action
        self.safe = safe
        self.required = required
        self.timeout_seconds = timeout_seconds
        
        self.status = StepStatus.PENDING
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
    
    def execute(self) -> bool:
        """
        Execute the step.
        
        Returns:
            True if successful, False otherwise
        """
        self.status = StepStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)
        
        try:
            self.result = self.action()
            self.status = StepStatus.COMPLETED
            self.completed_at = datetime.now(timezone.utc)
            return True
        except Exception as e:
            logger.exception(f"Step '{self.name}' failed: {e}")
            self.error = str(e)
            self.status = StepStatus.FAILED
            self.completed_at = datetime.now(timezone.utc)
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "step_type": self.step_type.value,
            "description": self.description,
            "safe": self.safe,
            "required": self.required,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class Playbook(ABC):
    """Base class for self-heal playbooks."""
    
    def __init__(self, max_steps: int = 10, safe_actions_only: bool = True):
        """
        Initialize playbook.
        
        Args:
            max_steps: Maximum number of steps allowed
            safe_actions_only: Only allow safe (read-only/bounded) actions
        """
        self.max_steps = max_steps
        self.safe_actions_only = safe_actions_only
        self.steps: List[PlaybookStep] = []
        self.findings: Dict[str, Any] = {}
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
    
    @abstractmethod
    def get_name(self) -> str:
        """Get playbook name."""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get playbook description."""
        pass
    
    @abstractmethod
    def build_steps(self) -> List[PlaybookStep]:
        """Build the list of steps for this playbook."""
        pass
    
    def validate_steps(self) -> bool:
        """
        Validate that steps meet safety requirements.
        
        Returns:
            True if valid, False otherwise
        """
        if len(self.steps) > self.max_steps:
            logger.error(f"Playbook has {len(self.steps)} steps, max is {self.max_steps}")
            return False
        
        if self.safe_actions_only:
            unsafe_steps = [s for s in self.steps if not s.safe]
            if unsafe_steps:
                logger.error(f"Playbook has unsafe steps: {[s.name for s in unsafe_steps]}")
                return False
        
        return True
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute the playbook.
        
        Returns:
            Execution results dictionary
        """
        self.started_at = datetime.now(timezone.utc)
        
        # Build steps
        self.steps = self.build_steps()
        
        # Validate
        if not self.validate_steps():
            return {
                "success": False,
                "error": "Playbook validation failed",
                "steps": []
            }
        
        # Execute steps
        results = []
        for step in self.steps:
            success = step.execute()
            results.append(step.to_dict())
            
            # Stop on required step failure
            if not success and step.required:
                logger.warning(f"Required step '{step.name}' failed, stopping playbook")
                break
        
        self.completed_at = datetime.now(timezone.utc)
        duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
        
        # Determine overall success
        required_steps = [s for s in self.steps if s.required]
        required_success = all(s.status == StepStatus.COMPLETED for s in required_steps)
        
        return {
            "success": required_success,
            "playbook_name": self.get_name(),
            "steps_completed": len([s for s in self.steps if s.status == StepStatus.COMPLETED]),
            "steps_total": len(self.steps),
            "steps": results,
            "findings": self.findings,
            "duration_ms": duration_ms,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
        }


class DiagnosisPlaybook(Playbook):
    """Base class for diagnosis playbooks."""
    
    def __init__(self):
        super().__init__(max_steps=10, safe_actions_only=True)
    
    def add_finding(self, key: str, value: Any, severity: str = "info"):
        """
        Add a diagnosis finding.
        
        Args:
            key: Finding key
            value: Finding value
            severity: Severity level (info, warning, critical)
        """
        self.findings[key] = {
            "value": value,
            "severity": severity,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


class RepairPlaybook(Playbook):
    """Base class for repair playbooks."""
    
    def __init__(self, safe_actions_only: bool = True):
        super().__init__(max_steps=10, safe_actions_only=safe_actions_only)
        self.actions_taken: List[Dict[str, Any]] = []
    
    def record_action(self, action: str, details: Dict[str, Any]):
        """
        Record a repair action taken.
        
        Args:
            action: Action name
            details: Action details
        """
        self.actions_taken.append({
            "action": action,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })


__all__ = [
    "StepType",
    "StepStatus",
    "PlaybookStep",
    "Playbook",
    "DiagnosisPlaybook",
    "RepairPlaybook"
]
