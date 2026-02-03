"""
Budget Tracker for Chat Sessions

Tracks and enforces budget limits for chat sessions:
- Maximum steps (tool calls + reasoning iterations)
- Maximum wall clock time
- Maximum retries per failure fingerprint
- No-progress detection

Part of Milestone 1: Chat Control Plane
"""

import time
from typing import Dict, Optional
from datetime import datetime, timezone


class BudgetTracker:
    """Tracks budget usage for a chat session."""
    
    def __init__(self, session_id: str, config: Optional[Dict] = None):
        """
        Initialize budget tracker.
        
        Args:
            session_id: Chat session ID
            config: Budget configuration with keys:
                - max_steps: Maximum number of steps (default: 100)
                - max_wall_clock_seconds: Maximum time in seconds (default: 300)
                - max_retries_per_fingerprint: Max retries for same error (default: 3)
                - max_no_progress_steps: Max steps without progress (default: 5)
        """
        self.session_id = session_id
        
        # Load config or use defaults
        config = config or {}
        self.max_steps = config.get("max_steps", 100)
        self.max_wall_clock = config.get("max_wall_clock_seconds", 300)
        self.max_retries_per_fingerprint = config.get("max_retries_per_fingerprint", 3)
        self.max_no_progress_steps = config.get("max_no_progress_steps", 5)
        
        # Initialize counters
        self.steps_used = 0
        self.start_time = time.time()
        self.retries_by_fingerprint: Dict[str, int] = {}
        self.no_progress_steps = 0
        self.last_state_hash: Optional[str] = None
    
    def increment_step(self) -> None:
        """Increment step counter."""
        self.steps_used += 1
    
    def record_retry(self, fingerprint: str) -> None:
        """
        Record a retry for a specific error fingerprint.
        
        Args:
            fingerprint: Error fingerprint hash
        """
        self.retries_by_fingerprint[fingerprint] = \
            self.retries_by_fingerprint.get(fingerprint, 0) + 1
    
    def record_state(self, state_hash: str) -> None:
        """
        Record current state for no-progress detection.
        
        Args:
            state_hash: Hash of current state
        """
        if state_hash == self.last_state_hash:
            self.no_progress_steps += 1
        else:
            self.no_progress_steps = 0
        self.last_state_hash = state_hash
    
    def is_exceeded(self) -> bool:
        """
        Check if any budget limit is exceeded.
        
        Returns:
            True if any limit exceeded, False otherwise
        """
        # Check steps limit
        if self.steps_used >= self.max_steps:
            return True
        
        # Check time limit
        if time.time() - self.start_time >= self.max_wall_clock:
            return True
        
        # Check retry limits
        for count in self.retries_by_fingerprint.values():
            if count >= self.max_retries_per_fingerprint:
                return True
        
        # Check no-progress limit
        if self.no_progress_steps >= self.max_no_progress_steps:
            return True
        
        return False
    
    def get_exceeded_reason(self) -> Optional[str]:
        """
        Get the reason why budget was exceeded.
        
        Returns:
            Reason string or None if not exceeded
        """
        if self.steps_used >= self.max_steps:
            return f"budget_exceeded_steps"
        
        if time.time() - self.start_time >= self.max_wall_clock:
            return f"budget_exceeded_time"
        
        for fingerprint, count in self.retries_by_fingerprint.items():
            if count >= self.max_retries_per_fingerprint:
                return f"budget_exceeded_retries"
        
        if self.no_progress_steps >= self.max_no_progress_steps:
            return f"no_progress"
        
        return None
    
    def get_time_used_seconds(self) -> int:
        """Get time used in seconds."""
        return int(time.time() - self.start_time)
    
    def get_time_remaining_seconds(self) -> int:
        """Get time remaining in seconds."""
        return max(0, self.max_wall_clock - self.get_time_used_seconds())
    
    def get_steps_remaining(self) -> int:
        """Get steps remaining."""
        return max(0, self.max_steps - self.steps_used)
    
    def to_dict(self) -> Dict:
        """
        Convert to dictionary for serialization.
        
        Returns:
            Dictionary with budget status
        """
        return {
            "session_id": self.session_id,
            "steps_used": self.steps_used,
            "steps_max": self.max_steps,
            "steps_remaining": self.get_steps_remaining(),
            "time_used_seconds": self.get_time_used_seconds(),
            "time_max_seconds": self.max_wall_clock,
            "time_remaining_seconds": self.get_time_remaining_seconds(),
            "retries_by_fingerprint": self.retries_by_fingerprint,
            "no_progress_steps": self.no_progress_steps,
            "is_exceeded": self.is_exceeded(),
            "exceeded_reason": self.get_exceeded_reason()
        }
    
    def __repr__(self) -> str:
        """String representation."""
        return f"BudgetTracker(session={self.session_id}, steps={self.steps_used}/{self.max_steps}, time={self.get_time_used_seconds()}s/{self.max_wall_clock}s)"


def get_default_budget_for_mode(mode: str) -> Dict:
    """
    Get default budget configuration for a mode.
    
    Args:
        mode: Chat mode (normal, deep_research, code, ops)
    
    Returns:
        Budget configuration dictionary
    """
    budgets = {
        "normal": {
            "max_steps": 100,
            "max_wall_clock_seconds": 300,  # 5 minutes
            "max_retries_per_fingerprint": 3,
            "max_no_progress_steps": 5
        },
        "deep_research": {
            "max_steps": 500,
            "max_wall_clock_seconds": 1800,  # 30 minutes
            "max_retries_per_fingerprint": 5,
            "max_no_progress_steps": 10
        },
        "code": {
            "max_steps": 200,
            "max_wall_clock_seconds": 600,  # 10 minutes
            "max_retries_per_fingerprint": 3,
            "max_no_progress_steps": 5
        },
        "ops": {
            "max_steps": 50,
            "max_wall_clock_seconds": 120,  # 2 minutes
            "max_retries_per_fingerprint": 2,
            "max_no_progress_steps": 3
        }
    }
    
    return budgets.get(mode, budgets["normal"])


__all__ = ["BudgetTracker", "get_default_budget_for_mode"]
