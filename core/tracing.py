"""
JUGGERNAUT LLM Tracing via Langfuse

Provides observability for all LLM calls — tracks prompts, completions,
token usage, latency, cost, and errors.

Uses Langfuse Cloud (free tier) or self-hosted instance.
Set LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY to enable.
When not configured, all calls are no-ops (zero overhead).

Usage:
    from core.tracing import get_tracer, trace_llm_call

    # Decorator style
    @trace_llm_call(name="brain_consult")
    def consult(prompt):
        ...

    # Context manager style
    tracer = get_tracer()
    with tracer.span(name="code_generation") as span:
        span.update(input=prompt)
        result = call_llm(prompt)
        span.update(output=result, usage={"total_tokens": 500})
"""

import logging
import os
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# Langfuse is optional — gracefully degrade if not installed
_langfuse = None
_langfuse_available = False

LANGFUSE_PUBLIC_KEY = (os.getenv("LANGFUSE_PUBLIC_KEY") or "").strip()
LANGFUSE_SECRET_KEY = (os.getenv("LANGFUSE_SECRET_KEY") or "").strip()
LANGFUSE_HOST = (os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com").strip()


def _init_langfuse():
    """Lazily initialize the Langfuse client."""
    global _langfuse, _langfuse_available

    if _langfuse is not None:
        return _langfuse

    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        logger.debug("Langfuse not configured (no LANGFUSE_PUBLIC_KEY/SECRET_KEY)")
        _langfuse_available = False
        return None

    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )
        _langfuse_available = True
        logger.info("Langfuse tracing initialized (host: %s)", LANGFUSE_HOST)
        return _langfuse
    except ImportError:
        logger.debug("langfuse package not installed — tracing disabled")
        _langfuse_available = False
        return None
    except Exception as e:
        logger.warning("Failed to initialize Langfuse: %s", e)
        _langfuse_available = False
        return None


def get_tracer():
    """Get the Langfuse client (or None if not configured)."""
    return _init_langfuse()


def is_tracing_enabled() -> bool:
    """Check if Langfuse tracing is active."""
    _init_langfuse()
    return _langfuse_available


class NoOpSpan:
    """No-op span when Langfuse is not available."""

    def update(self, **kwargs):
        pass

    def end(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TracedGeneration:
    """Wrapper around a Langfuse generation span with timing."""

    def __init__(self, generation=None):
        self._gen = generation
        self._start = time.time()

    def end(
        self,
        output: str = "",
        model: str = "",
        usage: Optional[Dict[str, int]] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """End the generation span with results."""
        duration_ms = int((time.time() - self._start) * 1000)

        if self._gen is not None:
            try:
                update_kwargs = {
                    "output": output[:4000] if output else "",
                    "model": model,
                    "completion_start_time": None,
                    "metadata": {
                        **(metadata or {}),
                        "duration_ms": duration_ms,
                    },
                }
                if usage:
                    update_kwargs["usage"] = usage
                if error:
                    update_kwargs["level"] = "ERROR"
                    update_kwargs["status_message"] = error[:500]

                self._gen.end(**update_kwargs)
            except Exception as e:
                logger.debug("Error ending Langfuse generation: %s", e)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.end(error=f"{exc_type.__name__}: {exc_val}")


def start_generation(
    name: str,
    input_text: str = "",
    model: str = "",
    task_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> TracedGeneration:
    """
    Start a traced LLM generation.

    Args:
        name: Name for this generation (e.g., "brain_consult", "code_gen").
        input_text: The prompt/input text.
        model: Model being used.
        task_id: Associated task ID.
        metadata: Additional metadata.

    Returns:
        TracedGeneration that must be .end()'d when complete.
    """
    lf = _init_langfuse()
    if lf is None:
        return TracedGeneration(None)

    try:
        trace = lf.trace(
            name=name,
            metadata={
                **(metadata or {}),
                "task_id": task_id,
                "worker_id": os.getenv("WORKER_ID", "unknown"),
            },
        )
        gen = trace.generation(
            name=name,
            input=input_text[:4000] if input_text else "",
            model=model,
            metadata=metadata,
        )
        return TracedGeneration(gen)
    except Exception as e:
        logger.debug("Error starting Langfuse generation: %s", e)
        return TracedGeneration(None)


def trace_llm_call(name: str = "", metadata: Optional[Dict[str, Any]] = None):
    """
    Decorator to trace an LLM call function.

    The decorated function should accept keyword args and return a dict
    or string result.

    Usage:
        @trace_llm_call(name="brain_consult")
        def consult(messages, model="openrouter/auto"):
            ...
            return {"content": "...", "tokens_used": 500}
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            trace_name = name or func.__name__
            model = kwargs.get("model", "")
            input_text = str(kwargs.get("messages", kwargs.get("prompt", "")))[:2000]

            gen = start_generation(
                name=trace_name,
                input_text=input_text,
                model=model,
                metadata=metadata,
            )

            try:
                result = func(*args, **kwargs)

                # Extract output and usage from result
                output = ""
                usage = None
                if isinstance(result, dict):
                    output = str(result.get("content", result.get("output", "")))[:2000]
                    tokens = result.get("tokens_used") or result.get("usage", {})
                    if isinstance(tokens, dict):
                        usage = tokens
                    elif isinstance(tokens, int):
                        usage = {"total_tokens": tokens}
                elif isinstance(result, str):
                    output = result[:2000]

                gen.end(output=output, model=model, usage=usage)
                return result

            except Exception as e:
                gen.end(error=f"{type(e).__name__}: {e}", model=model)
                raise

        return wrapper

    return decorator


def flush():
    """Flush any pending Langfuse events (call before shutdown)."""
    if _langfuse is not None:
        try:
            _langfuse.flush()
        except Exception:
            pass
