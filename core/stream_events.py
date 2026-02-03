"""
Stream Event Types and Constants

Defines the authoritative streaming event contract for Chat Control Plane.
All streaming events must conform to these types.

Part of Milestone 1: Chat Control Plane
"""

from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import json


class StreamEventType(str, Enum):
    """Types of streaming events."""
    TOKEN = "token"                    # Partial assistant text
    STATUS = "status"                  # Status change
    TOOL_START = "tool_start"          # Tool execution begins
    TOOL_RESULT = "tool_result"        # Tool execution completes
    BUDGET = "budget"                  # Budget update
    STOP_REASON = "stop_reason"        # Why execution stopped
    GUARDRAILS = "guardrails"          # Guardrail counters
    THINKING = "thinking"              # Reasoning step
    SESSION = "session"                # Session metadata
    DONE = "done"                      # Stream complete


class StreamStatus(str, Enum):
    """Execution status values."""
    IDLE = "idle"
    THINKING = "thinking"
    REASONING = "reasoning"
    TOOL_RUNNING = "tool_running"
    SUMMARIZING = "summarizing"
    WAITING_APPROVAL = "waiting_approval"
    STOPPED = "stopped"


class StopReason(str, Enum):
    """Reasons why execution stopped."""
    COMPLETE = "complete"
    REPEATED_FAILURE = "repeated_failure"
    NO_PROGRESS = "no_progress"
    WAITING_APPROVAL = "waiting_approval"
    USER_STOP = "user_stop"
    BUDGET_EXCEEDED = "budget_exceeded"
    GUARDRAIL_TRIGGERED = "guardrail_triggered"
    ERROR = "error"


class StreamEvent:
    """Base class for streaming events."""
    
    def __init__(self, event_type: StreamEventType, data: Dict[str, Any]):
        """
        Initialize stream event.
        
        Args:
            event_type: Type of event
            data: Event data payload
        """
        self.event_type = event_type
        self.data = data
        self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.event_type.value,
            "data": {
                **self.data,
                "timestamp": self.timestamp
            }
        }
    
    def to_sse(self) -> str:
        """
        Convert to Server-Sent Events format.
        
        Returns:
            SSE formatted string
        """
        data_json = json.dumps(self.to_dict())
        return f"data: {data_json}\n\n"


class TokenEvent(StreamEvent):
    """Partial text token from LLM."""
    
    def __init__(self, text: str):
        super().__init__(StreamEventType.TOKEN, {"text": text})


class StatusEvent(StreamEvent):
    """Status change event."""
    
    def __init__(self, status: StreamStatus, detail: Optional[str] = None):
        data = {"status": status.value}
        if detail:
            data["detail"] = detail
        super().__init__(StreamEventType.STATUS, data)


class ToolStartEvent(StreamEvent):
    """Tool execution started."""
    
    def __init__(self, tool: str, arguments: Dict[str, Any], fingerprint: str):
        super().__init__(StreamEventType.TOOL_START, {
            "tool": tool,
            "arguments": arguments,
            "fingerprint": fingerprint
        })


class ToolResultEvent(StreamEvent):
    """Tool execution completed."""
    
    def __init__(
        self,
        tool: str,
        success: bool,
        duration_ms: int,
        fingerprint: str,
        result: Optional[Any] = None,
        error: Optional[str] = None
    ):
        data = {
            "tool": tool,
            "success": success,
            "duration_ms": duration_ms,
            "fingerprint": fingerprint
        }
        if result is not None:
            data["result"] = result
        if error:
            data["error"] = error
        super().__init__(StreamEventType.TOOL_RESULT, data)


class BudgetEvent(StreamEvent):
    """Budget status update."""
    
    def __init__(self, budget_dict: Dict[str, Any]):
        super().__init__(StreamEventType.BUDGET, budget_dict)


class GuardrailsEvent(StreamEvent):
    """Guardrails status update."""
    
    def __init__(self, guardrails_dict: Dict[str, Any]):
        super().__init__(StreamEventType.GUARDRAILS, guardrails_dict)


class StopReasonEvent(StreamEvent):
    """Execution stopped event."""
    
    def __init__(
        self,
        reason: StopReason,
        detail: Optional[str] = None,
        recovery_suggestion: Optional[str] = None,
        fingerprint: Optional[str] = None
    ):
        data = {"reason": reason.value}
        if detail:
            data["detail"] = detail
        if recovery_suggestion:
            data["recovery_suggestion"] = recovery_suggestion
        if fingerprint:
            data["fingerprint"] = fingerprint
        super().__init__(StreamEventType.STOP_REASON, data)


class SessionEvent(StreamEvent):
    """Session metadata event."""
    
    def __init__(
        self,
        session_id: str,
        mode: str,
        budget: Dict[str, Any],
        is_new_session: bool = False
    ):
        super().__init__(StreamEventType.SESSION, {
            "session_id": session_id,
            "mode": mode,
            "budget": budget,
            "is_new_session": is_new_session
        })


class DoneEvent(StreamEvent):
    """Stream complete event."""
    
    def __init__(self):
        super().__init__(StreamEventType.DONE, {})


def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """
    Format a streaming event as SSE.
    
    Args:
        event_type: Event type string
        data: Event data
    
    Returns:
        SSE formatted string
    """
    event = {
        "type": event_type,
        "data": {
            **data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }
    return f"data: {json.dumps(event)}\n\n"


__all__ = [
    "StreamEventType",
    "StreamStatus",
    "StopReason",
    "StreamEvent",
    "TokenEvent",
    "StatusEvent",
    "ToolStartEvent",
    "ToolResultEvent",
    "BudgetEvent",
    "GuardrailsEvent",
    "StopReasonEvent",
    "SessionEvent",
    "DoneEvent",
    "format_sse_event"
]
