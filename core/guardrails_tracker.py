"""
Guardrails Tracker for Chat Sessions

Tracks safety guardrails to prevent infinite loops and repeated failures:
- Failure fingerprints (same error repeated)
- No-progress detection (state not changing)
- Tool call patterns (same tool called repeatedly)

Part of Milestone 1: Chat Control Plane
"""

import hashlib
import json
from typing import Dict, List, Optional, Set
from datetime import datetime, timezone


class GuardrailsTracker:
    """Tracks guardrails to prevent unsafe execution patterns."""
    
    def __init__(self, max_failures_per_fingerprint: int = 3, max_no_progress_steps: int = 5):
        """
        Initialize guardrails tracker.
        
        Args:
            max_failures_per_fingerprint: Max failures for same fingerprint before stopping
            max_no_progress_steps: Max steps without state change before stopping
        """
        self.max_failures_per_fingerprint = max_failures_per_fingerprint
        self.max_no_progress_steps = max_no_progress_steps
        
        # Tracking state
        self.failure_fingerprints: Dict[str, int] = {}
        self.no_progress_steps = 0
        self.last_state_hash: Optional[str] = None
        self.tool_call_sequence: List[str] = []
        self.repeated_tool_calls: Dict[str, int] = {}
    
    def record_tool_call(self, tool_name: str, arguments: Dict, success: bool) -> str:
        """
        Record a tool call and check for patterns.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            success: Whether the call succeeded
        
        Returns:
            Fingerprint hash for this tool call
        """
        # Generate fingerprint
        fingerprint = self._generate_fingerprint(tool_name, arguments)
        
        # Track failures
        if not success:
            self.failure_fingerprints[fingerprint] = \
                self.failure_fingerprints.get(fingerprint, 0) + 1
        
        # Track tool call sequence
        self.tool_call_sequence.append(tool_name)
        if len(self.tool_call_sequence) > 10:
            self.tool_call_sequence.pop(0)
        
        # Count repeated tool calls
        self.repeated_tool_calls[tool_name] = \
            self.repeated_tool_calls.get(tool_name, 0) + 1
        
        return fingerprint
    
    def record_state(self, state_data: Dict) -> None:
        """
        Record current state for no-progress detection.
        
        Args:
            state_data: Current state to hash
        """
        state_hash = self._hash_state(state_data)
        
        if state_hash == self.last_state_hash:
            self.no_progress_steps += 1
        else:
            self.no_progress_steps = 0
        
        self.last_state_hash = state_hash
    
    def should_stop(self) -> bool:
        """
        Check if guardrails indicate execution should stop.
        
        Returns:
            True if should stop, False otherwise
        """
        # Check for repeated failures
        for fingerprint, count in self.failure_fingerprints.items():
            if count >= self.max_failures_per_fingerprint:
                return True
        
        # Check for no progress
        if self.no_progress_steps >= self.max_no_progress_steps:
            return True
        
        # Check for tool call loops (same tool 5+ times in sequence)
        if len(self.tool_call_sequence) >= 5:
            last_5 = self.tool_call_sequence[-5:]
            if len(set(last_5)) == 1:  # All same tool
                return True
        
        return False
    
    def get_stop_reason(self) -> Optional[str]:
        """
        Get the reason why guardrails triggered a stop.
        
        Returns:
            Stop reason string or None if not stopped
        """
        # Check repeated failures
        for fingerprint, count in self.failure_fingerprints.items():
            if count >= self.max_failures_per_fingerprint:
                return "repeated_failure"
        
        # Check no progress
        if self.no_progress_steps >= self.max_no_progress_steps:
            return "no_progress"
        
        # Check tool loops
        if len(self.tool_call_sequence) >= 5:
            last_5 = self.tool_call_sequence[-5:]
            if len(set(last_5)) == 1:
                return "tool_loop"
        
        return None
    
    def get_stop_detail(self) -> str:
        """
        Get detailed explanation of why guardrails stopped execution.
        
        Returns:
            Detailed stop reason
        """
        reason = self.get_stop_reason()
        
        if reason == "repeated_failure":
            # Find the fingerprint that exceeded limit
            for fingerprint, count in self.failure_fingerprints.items():
                if count >= self.max_failures_per_fingerprint:
                    return f"Tool failed {count} times with same error pattern (fingerprint: {fingerprint[:8]}...)"
        
        elif reason == "no_progress":
            return f"No progress detected for {self.no_progress_steps} consecutive steps"
        
        elif reason == "tool_loop":
            tool_name = self.tool_call_sequence[-1]
            return f"Tool '{tool_name}' called repeatedly without progress"
        
        return "Unknown guardrail trigger"
    
    def get_recovery_suggestion(self) -> str:
        """
        Get suggestion for recovering from guardrail stop.
        
        Returns:
            Recovery suggestion string
        """
        reason = self.get_stop_reason()
        
        if reason == "repeated_failure":
            return "Review the error and try a different approach, or request human assistance"
        
        elif reason == "no_progress":
            return "Try breaking down the task into smaller steps or changing strategy"
        
        elif reason == "tool_loop":
            tool_name = self.tool_call_sequence[-1]
            return f"Avoid using '{tool_name}' repeatedly - try alternative tools or approaches"
        
        return "Review execution logs and adjust approach"
    
    def reset(self) -> None:
        """Reset all guardrails tracking."""
        self.failure_fingerprints.clear()
        self.no_progress_steps = 0
        self.last_state_hash = None
        self.tool_call_sequence.clear()
        self.repeated_tool_calls.clear()
    
    def to_dict(self) -> Dict:
        """
        Convert to dictionary for serialization.
        
        Returns:
            Dictionary with guardrails state
        """
        return {
            "failure_fingerprints": self.failure_fingerprints,
            "no_progress_steps": self.no_progress_steps,
            "tool_call_sequence": self.tool_call_sequence[-10:],  # Last 10
            "repeated_tool_calls": self.repeated_tool_calls,
            "should_stop": self.should_stop(),
            "stop_reason": self.get_stop_reason(),
            "stop_detail": self.get_stop_detail() if self.should_stop() else None
        }
    
    def _generate_fingerprint(self, tool_name: str, arguments: Dict) -> str:
        """
        Generate a fingerprint hash for a tool call.
        
        Args:
            tool_name: Tool name
            arguments: Tool arguments
        
        Returns:
            SHA256 hash as fingerprint
        """
        # Create deterministic string representation
        fingerprint_data = {
            "tool": tool_name,
            "args": self._normalize_args(arguments)
        }
        
        fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()
    
    def _normalize_args(self, arguments: Dict) -> Dict:
        """
        Normalize arguments for fingerprinting (remove timestamps, IDs, etc).
        
        Args:
            arguments: Raw arguments
        
        Returns:
            Normalized arguments
        """
        normalized = {}
        
        # Keys to exclude from fingerprinting (too variable)
        exclude_keys = {'timestamp', 'id', 'created_at', 'updated_at', 'uuid'}
        
        for key, value in arguments.items():
            if key.lower() in exclude_keys:
                continue
            
            # Truncate long strings for fingerprinting
            if isinstance(value, str) and len(value) > 100:
                normalized[key] = value[:100] + "..."
            else:
                normalized[key] = value
        
        return normalized
    
    def _hash_state(self, state_data: Dict) -> str:
        """
        Hash state data for no-progress detection.
        
        Args:
            state_data: State to hash
        
        Returns:
            SHA256 hash
        """
        state_str = json.dumps(state_data, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()
    
    def __repr__(self) -> str:
        """String representation."""
        return f"GuardrailsTracker(failures={len(self.failure_fingerprints)}, no_progress={self.no_progress_steps}, should_stop={self.should_stop()})"


__all__ = ["GuardrailsTracker"]
