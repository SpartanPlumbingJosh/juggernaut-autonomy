import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_OPENROUTER_DEFAULT = "https://openrouter.ai/api/v1/chat/completions"
LLM_API_BASE = (os.getenv("LLM_API_BASE") or os.getenv("OPENROUTER_ENDPOINT") or _OPENROUTER_DEFAULT).strip().rstrip("/")
LLM_CHAT_ENDPOINT = f"{LLM_API_BASE}/chat/completions" if not LLM_API_BASE.endswith("/chat/completions") else LLM_API_BASE
# Backward compat alias
OPENROUTER_ENDPOINT = LLM_CHAT_ENDPOINT
DEFAULT_MODEL = os.getenv("LLM_MODEL") or os.getenv("OPENROUTER_MODEL") or "openrouter/auto"
DEFAULT_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "4096"))
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "60"))
DEFAULT_MAX_PRICE_PROMPT = os.getenv("OPENROUTER_MAX_PRICE_PROMPT", "1")
DEFAULT_MAX_PRICE_COMPLETION = os.getenv("OPENROUTER_MAX_PRICE_COMPLETION", "2")
DEFAULT_MAX_TOOL_ITERATIONS = int(os.getenv("OPENROUTER_MAX_TOOL_ITERATIONS", "15"))

# Model routing (cost-safe defaults)
MODEL_FREE_PRIMARY = os.getenv("LLM_MODEL_FREE_PRIMARY", "google/gemini-2.0-flash-exp:free")
MODEL_FREE_SECONDARY = os.getenv("LLM_MODEL_FREE_SECONDARY", "meta-llama/llama-3.3-70b-instruct:free")
MODEL_WORKHORSE = os.getenv("LLM_MODEL_WORKHORSE", "deepseek/deepseek-v3.2")
MODEL_STRATEGY = os.getenv("LLM_MODEL_STRATEGY", "moonshotai/kimi-k2.5")
MODEL_CODE = os.getenv("LLM_MODEL_CODE", "deepseek/deepseek-v3.2")
MODEL_FALLBACK = os.getenv("LLM_MODEL_FALLBACK", "deepseek/deepseek-v3.1-terminus")


def select_model_for_task(task_type: str) -> str:
    tt = (task_type or "").strip().lower()

    free_types = {
        "critical_monitoring",
        "error_scanning",
        "stale_task_reset",
        "health_check",
        "heartbeat",
        "monitoring",
        "scheduler",
        "watchdog",
        "status_update",
    }
    if tt in free_types:
        return MODEL_FREE_PRIMARY or MODEL_FREE_SECONDARY

    if tt in {"critical_monitoring", "error_scanning", "stale_task_reset"}:
        # Extremely frequent tasks: allow override to a secondary free model
        # by setting LLM_MODEL_FREE_PRIMARY empty and LLM_MODEL_FREE_SECONDARY.
        return MODEL_FREE_PRIMARY or MODEL_FREE_SECONDARY

    strategy_types = {"strategy", "planning", "strategic_analysis", "complex"}
    if tt in strategy_types:
        return MODEL_STRATEGY

    code_types = {
        "code",
        "code_fix",
        "code_change",
        "code_implementation",
        "fix_bug",
        "deploy_code",
        "create_pr",
        "debugging",
        "optimization",
        "workflow",
        "development",
        "integration",
    }
    if tt in code_types:
        return MODEL_CODE

    research_types = {"research", "analysis", "scan", "opportunity_scan", "idea_generation", "report"}
    if tt in research_types:
        return MODEL_WORKHORSE

    return MODEL_WORKHORSE


_LLM_CALL_LOCK = threading.Lock()
_LLM_CALL_TIMES = deque(maxlen=10000)


def _truthy_env(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or "").strip().lower() in ("1", "true", "yes", "y", "on")


def _using_openrouter_endpoint() -> bool:
    return "openrouter.ai" in (OPENROUTER_ENDPOINT or "").lower()


def _enforce_llm_limits() -> None:
    if _truthy_env("LLM_DISABLED", "0") or _truthy_env("LLM_EMERGENCY_STOP", "0"):
        raise RuntimeError("LLM execution disabled via LLM_DISABLED/LLM_EMERGENCY_STOP")

    safe_mode = _truthy_env("LLM_SAFE_MODE", "0")
    rpm_raw = os.getenv("LLM_MAX_REQUESTS_PER_MINUTE", "10" if safe_mode else "60")
    try:
        rpm = int(rpm_raw)
    except (TypeError, ValueError):
        rpm = 60

    if rpm <= 0:
        return

    now = time.time()
    cutoff = now - 60.0
    with _LLM_CALL_LOCK:
        while _LLM_CALL_TIMES and _LLM_CALL_TIMES[0] < cutoff:
            _LLM_CALL_TIMES.popleft()
        if len(_LLM_CALL_TIMES) >= rpm:
            raise RuntimeError(f"LLM rate limit exceeded ({rpm}/min) — refusing to call provider")
        _LLM_CALL_TIMES.append(now)


@dataclass
class AIResponse:
    content: str
    raw: Dict[str, Any]
    tool_calls_made: List[Dict[str, Any]] = field(default_factory=list)
    iterations: int = 0


class AIExecutor:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        http_referer: Optional[str] = None,
        title: Optional[str] = None,
    ) -> None:
        self.api_key = (api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY") or "").strip()
        self.model = model
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.http_referer = http_referer or os.getenv("OPENROUTER_HTTP_REFERER") or "https://juggernaut-engine-production.up.railway.app"
        self.title = title or os.getenv("OPENROUTER_TITLE") or "Juggernaut Engine"

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.http_referer,
            "X-Title": self.title,
        }

    def _provider_routing(self) -> Optional[Dict[str, Any]]:
        try:
            prompt_price = float((os.getenv("OPENROUTER_MAX_PRICE_PROMPT", DEFAULT_MAX_PRICE_PROMPT) or "").strip() or 0)
            completion_price = float(
                (os.getenv("OPENROUTER_MAX_PRICE_COMPLETION", DEFAULT_MAX_PRICE_COMPLETION) or "").strip() or 0
            )
        except ValueError:
            return None

        if prompt_price <= 0 or completion_price <= 0:
            return None

        return {"max_price": {"prompt": prompt_price, "completion": completion_price}}

    def chat(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None) -> AIResponse:
        from core.tracing import start_generation

        _enforce_llm_limits()

        safe_mode = _truthy_env("LLM_SAFE_MODE", "0")
        if safe_mode:
            try:
                token_cap = int(os.getenv("LLM_MAX_TOKENS_CAP", "800"))
            except (TypeError, ValueError):
                token_cap = 800
        else:
            token_cap = None

        input_preview = json.dumps(messages[-1:], ensure_ascii=False)[:2000] if messages else ""
        gen = start_generation(name="ai_executor.chat", input_text=input_preview, model=self.model)

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": int(max_tokens) if max_tokens is not None else self.max_tokens,
        }

        if token_cap is not None:
            payload["max_tokens"] = max(1, min(int(payload["max_tokens"]), int(token_cap)))

        provider = self._provider_routing()
        if provider is not None and _using_openrouter_endpoint():
            payload["provider"] = provider

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            OPENROUTER_ENDPOINT,
            data=data,
            headers=self._headers(),
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            gen.end(error=f"HTTP {e.code}: {error_body[:200]}", model=self.model)
            raise RuntimeError(f"OpenRouter HTTP {e.code}: {error_body}") from e
        except urllib.error.URLError as e:
            gen.end(error=f"Connection error: {e}", model=self.model)
            raise RuntimeError(f"OpenRouter connection error: {e}") from e
        except json.JSONDecodeError as e:
            gen.end(error=f"Invalid JSON: {e}", model=self.model)
            raise RuntimeError(f"OpenRouter invalid JSON response: {e}") from e

        choices = raw.get("choices") or []
        if not choices:
            gen.end(error="Response missing choices", model=self.model)
            raise RuntimeError("OpenRouter response missing choices")

        content = ((choices[0] or {}).get("message") or {}).get("content") or ""
        usage = raw.get("usage") or {}
        gen.end(
            output=content[:2000],
            model=raw.get("model", self.model),
            usage={"prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0), "total_tokens": usage.get("total_tokens", 0)} if usage else None,
        )
        return AIResponse(content=content, raw=raw)

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        tool_executor: Any,
        max_tokens: Optional[int] = None,
        max_iterations: int = DEFAULT_MAX_TOOL_ITERATIONS,
    ) -> AIResponse:
        """
        Agentic tool-calling loop.

        Sends messages + tool definitions to the model. If the model returns
        tool_calls, executes them via tool_executor and feeds results back.
        Repeats until the model returns a final text response or max_iterations
        is reached.

        Args:
            messages: Conversation messages (system + user).
            tools: OpenAI-format tool definitions.
            tool_executor: Module/object with execute_tool_call(name, args) -> dict.
            max_tokens: Per-turn token limit.
            max_iterations: Safety cap on tool-call rounds.

        Returns:
            AIResponse with final content and list of tool calls made.
        """
        from core.tracing import start_generation

        input_preview = json.dumps(messages[-1:], ensure_ascii=False)[:2000] if messages else ""
        _trace_gen = start_generation(
            name="ai_executor.chat_with_tools",
            input_text=input_preview,
            model=self.model,
            metadata={"max_iterations": max_iterations, "tool_count": len(tools)},
        )

        _enforce_llm_limits()

        safe_mode = _truthy_env("LLM_SAFE_MODE", "0")
        if safe_mode:
            try:
                token_cap = int(os.getenv("LLM_MAX_TOKENS_CAP", "800"))
            except (TypeError, ValueError):
                token_cap = 800
            try:
                iter_cap = int(os.getenv("LLM_MAX_TOOL_ITERATIONS_CAP", "5"))
            except (TypeError, ValueError):
                iter_cap = 5
            max_iterations = max(1, min(int(max_iterations), int(iter_cap)))
        else:
            token_cap = None

        all_tool_calls = []
        iteration = 0
        conversation = list(messages)  # mutable copy

        while iteration < max_iterations:
            iteration += 1

            # Build request payload
            payload = {
                "model": self.model,
                "messages": conversation,
                "max_tokens": int(max_tokens) if max_tokens is not None else self.max_tokens,
                "tools": tools,
                "tool_choice": "auto",
            }

            if token_cap is not None:
                payload["max_tokens"] = max(1, min(int(payload["max_tokens"]), int(token_cap)))

            provider = self._provider_routing()
            if provider is not None and _using_openrouter_endpoint():
                payload["provider"] = provider

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                OPENROUTER_ENDPOINT,
                data=data,
                headers=self._headers(),
                method="POST",
            )

            try:
                _enforce_llm_limits()
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    raw = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8")
                raise RuntimeError(f"OpenRouter HTTP {e.code}: {error_body}") from e
            except urllib.error.URLError as e:
                raise RuntimeError(f"OpenRouter connection error: {e}") from e
            except json.JSONDecodeError as e:
                raise RuntimeError(f"OpenRouter returned invalid JSON: {e}") from e

            choices = raw.get("choices") or []
            if not choices:
                raise RuntimeError("OpenRouter response missing choices")

            message = (choices[0] or {}).get("message") or {}
            finish_reason = (choices[0] or {}).get("finish_reason") or ""
            tool_calls = message.get("tool_calls")

            # If the model returned tool calls, execute them
            if tool_calls:
                # Append the assistant message (with tool_calls) to conversation
                conversation.append(message)

                for tc in tool_calls:
                    tc_id = tc.get("id", "")
                    func = tc.get("function") or {}
                    tc_name = func.get("name", "")

                    # Parse arguments
                    try:
                        tc_args = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        tc_args = {}

                    logger.info(
                        "[tool-call iter=%d] %s(%s)",
                        iteration,
                        tc_name,
                        json.dumps(tc_args)[:200],
                    )

                    # Execute the tool
                    try:
                        result = tool_executor.execute_tool_call(tc_name, tc_args)
                    except Exception as exc:
                        result = {"success": False, "error": f"Tool execution error: {exc}"}

                    all_tool_calls.append({
                        "iteration": iteration,
                        "name": tc_name,
                        "arguments": tc_args,
                        "result_success": result.get("success", False),
                    })

                    # Append tool result to conversation
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": json.dumps(result, ensure_ascii=False, default=str)[:16384],
                    })

                # Continue the loop — model may want to call more tools
                continue

            # No tool calls — model returned a final text response
            content = message.get("content") or ""
            _trace_gen.end(
                output=content[:2000],
                model=raw.get("model", self.model),
                metadata={"iterations": iteration, "tool_calls": len(all_tool_calls)},
            )
            return AIResponse(
                content=content,
                raw=raw,
                tool_calls_made=all_tool_calls,
                iterations=iteration,
            )

        # Max iterations reached — return whatever we have
        logger.warning("chat_with_tools hit max iterations (%d)", max_iterations)
        _trace_gen.end(
            error=f"Max iterations reached ({max_iterations})",
            model=self.model,
            metadata={"iterations": iteration, "tool_calls": len(all_tool_calls)},
        )
        return AIResponse(
            content=f"[Tool loop reached max {max_iterations} iterations. Last tool calls: {len(all_tool_calls)}]",
            raw={},
            tool_calls_made=all_tool_calls,
            iterations=iteration,
        )
