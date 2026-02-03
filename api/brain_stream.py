"""
Brain Streaming API with Chat Control Plane Integration

Enhanced streaming endpoint with full event support:
- Status updates (thinking, tool_running, etc)
- Tool execution timeline
- Budget tracking
- Guardrails monitoring
- Stop reasons

Part of Milestone 1: Chat Control Plane
"""

import json
import logging
import time
from typing import AsyncGenerator, Dict, Any, Optional
from datetime import datetime, timezone

from core.budget_tracker import BudgetTracker, get_default_budget_for_mode
from core.guardrails_tracker import GuardrailsTracker
from core.stream_events import (
    StreamStatus, StopReason,
    TokenEvent, StatusEvent, ToolStartEvent, ToolResultEvent,
    BudgetEvent, GuardrailsEvent, StopReasonEvent, SessionEvent, DoneEvent
)

logger = logging.getLogger(__name__)

# Try to import BrainService
try:
    from core.unified_brain import BrainService
    BRAIN_AVAILABLE = True
except ImportError as e:
    BRAIN_AVAILABLE = False
    logger.warning(f"BrainService not available: {e}")


async def stream_chat_response(
    session_id: str,
    question: str,
    mode: str = "normal",
    context: Optional[Dict] = None,
    enable_tools: bool = True,
    system_prompt: Optional[str] = None,
    budget_config: Optional[Dict] = None
) -> AsyncGenerator[str, None]:
    """
    Stream chat response with full Chat Control Plane events.
    
    Args:
        session_id: Chat session ID
        question: User question
        mode: Chat mode (normal, deep_research, code, ops)
        context: Additional context
        enable_tools: Whether to enable tool execution
        system_prompt: Custom system prompt
        budget_config: Custom budget configuration
    
    Yields:
        SSE formatted event strings
    """
    # Initialize tracking
    budget = BudgetTracker(
        session_id,
        budget_config or get_default_budget_for_mode(mode)
    )
    guardrails = GuardrailsTracker()
    status = StreamStatus.THINKING
    
    # Emit session start
    session_event = SessionEvent(
        session_id=session_id,
        mode=mode,
        budget=budget.to_dict(),
        is_new_session=False
    )
    yield session_event.to_sse()
    
    # Emit initial status
    status_event = StatusEvent(status)
    yield status_event.to_sse()
    
    try:
        # Get brain service
        if not BRAIN_AVAILABLE:
            stop_event = StopReasonEvent(
                StopReason.ERROR,
                detail="Brain service not available"
            )
            yield stop_event.to_sse()
            yield DoneEvent().to_sse()
            return
        
        brain = BrainService()
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add context if provided
        if context:
            context_str = json.dumps(context, indent=2)
            messages.append({"role": "system", "content": f"Context:\n{context_str}"})
        
        messages.append({"role": "user", "content": question})
        
        # Main execution loop
        accumulated_text = ""
        tool_executions = []
        
        while not budget.is_exceeded() and not guardrails.should_stop():
            budget.increment_step()
            
            # Update status to reasoning
            status = StreamStatus.REASONING
            yield StatusEvent(status).to_sse()
            
            # Call brain (simplified - actual implementation would use OpenRouter)
            # For now, simulate a response
            if enable_tools:
                # Simulate tool execution
                status = StreamStatus.TOOL_RUNNING
                yield StatusEvent(status, detail="execute_sql").to_sse()
                
                # Emit tool start
                tool_args = {"query": "SELECT COUNT(*) FROM governance_tasks"}
                fingerprint = guardrails.record_tool_call("execute_sql", tool_args, True)
                
                tool_start = ToolStartEvent("execute_sql", tool_args, fingerprint)
                yield tool_start.to_sse()
                
                # Simulate execution
                time.sleep(0.1)
                duration_ms = 100
                
                # Emit tool result
                tool_result = ToolResultEvent(
                    "execute_sql",
                    success=True,
                    duration_ms=duration_ms,
                    fingerprint=fingerprint,
                    result={"rows": [{"count": 42}]}
                )
                yield tool_result.to_sse()
                
                tool_executions.append({
                    "tool": "execute_sql",
                    "success": True,
                    "duration_ms": duration_ms
                })
            
            # Emit budget update
            yield BudgetEvent(budget.to_dict()).to_sse()
            
            # Emit guardrails update
            yield GuardrailsEvent(guardrails.to_dict()).to_sse()
            
            # Stream response tokens
            status = StreamStatus.THINKING
            yield StatusEvent(status).to_sse()
            
            response_text = "Based on the database query, there are 42 tasks in the system."
            for char in response_text:
                yield TokenEvent(char).to_sse()
                accumulated_text += char
                time.sleep(0.01)  # Simulate streaming delay
            
            # Check if we should continue
            break  # For now, single iteration
        
        # Check stop reason
        if budget.is_exceeded():
            stop_reason = budget.get_exceeded_reason()
            yield StopReasonEvent(
                StopReason.BUDGET_EXCEEDED,
                detail=f"Budget limit reached: {stop_reason}"
            ).to_sse()
        elif guardrails.should_stop():
            stop_reason = guardrails.get_stop_reason()
            recovery = guardrails.get_recovery_suggestion()
            yield StopReasonEvent(
                StopReason.GUARDRAIL_TRIGGERED,
                detail=guardrails.get_stop_detail(),
                recovery_suggestion=recovery
            ).to_sse()
        else:
            yield StopReasonEvent(StopReason.COMPLETE).to_sse()
        
        # Final status
        yield StatusEvent(StreamStatus.IDLE).to_sse()
        
        # Done
        yield DoneEvent().to_sse()
        
    except Exception as e:
        logger.exception(f"Error in stream_chat_response: {e}")
        yield StopReasonEvent(
            StopReason.ERROR,
            detail=str(e)
        ).to_sse()
        yield StatusEvent(StreamStatus.STOPPED).to_sse()
        yield DoneEvent().to_sse()


def format_sse(data: str) -> str:
    """Format data as Server-Sent Event."""
    return f"data: {data}\n\n"


__all__ = ["stream_chat_response", "format_sse"]
