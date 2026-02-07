import json
import logging
import os
from typing import Any, Dict, List, Optional

from core.ai_executor import AIExecutor
from core import tool_executor

from .base import BaseHandler, HandlerResult

logger = logging.getLogger(__name__)

# Task types that get real tool access (vs. plan-only)
_TOOL_ENABLED_TYPES = {
    "code", "code_fix", "code_change", "code_implementation",
    "debugging", "optimization", "workflow", "development",
    "integration",
}


def _truthy_env(name: str, default: str = "") -> bool:
    value = os.getenv(name, default)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _strip_code_fences(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```"):
        first_newline = s.find("\n")
        if first_newline != -1:
            s = s[first_newline + 1 :]
        if s.endswith("```"):
            s = s[: -3]
    return s.strip()


def _find_first_json_object(text: str) -> Optional[str]:
    s = _strip_code_fences(text)
    start = s.find("{")
    if start == -1:
        return None

    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]

    return None


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    candidate = _find_first_json_object(text)
    if not candidate:
        return None

    try:
        obj = json.loads(candidate)
    except Exception:
        return None

    return obj if isinstance(obj, dict) else None


class AIHandler(BaseHandler):
    task_type = "ai"

    def __init__(
        self,
        execute_sql,
        log_action,
    ) -> None:
        super().__init__(execute_sql, log_action)
        self.executor = AIExecutor()

    def _should_use_tools(self, task_type: str) -> bool:
        """Determine if this task type should get real tool access."""
        if _truthy_env("AIHANDLER_PLAN_ONLY", "0"):
            return False
        if _truthy_env("AIHANDLER_TOOLS_DISABLED", "0"):
            return False
        return task_type in _TOOL_ENABLED_TYPES

    def execute(self, task: Dict[str, Any]) -> HandlerResult:
        self._execution_logs = []
        task_id = task.get("id")

        payload = task.get("payload") or {}
        title = task.get("title") or ""
        description = task.get("description") or ""
        task_type = task.get("task_type") or ""

        use_tools = self._should_use_tools(task_type)
        plan_only = _truthy_env("AIHANDLER_PLAN_ONLY", "0")

        mode = "tool-assisted" if use_tools else ("plan-only" if plan_only else "chat-only")
        self._log(
            "handler.ai.starting",
            f"AI handling task_type='{task_type}' title='{title[:80]}' mode={mode}",
            task_id=task_id,
        )

        if use_tools:
            return self._execute_with_tools(task_id, task_type, title, description, payload)
        else:
            return self._execute_chat_only(task_id, task_type, title, description, payload, plan_only)

    def _execute_with_tools(
        self, task_id: str, task_type: str, title: str, description: str, payload: Dict[str, Any]
    ) -> HandlerResult:
        """Execute task using the agentic tool-calling loop."""

        system = (
            "You are JUGGERNAUT ENGINE, an autonomous execution agent with real tool access.\n"
            "You have tools to read/write files, run shell commands, search code, and query the database.\n\n"
            "IMPORTANT RULES:\n"
            "- Use tools to actually perform the work, not just describe it.\n"
            "- Read relevant files before making changes.\n"
            "- Make targeted, minimal edits using patch_file rather than rewriting entire files.\n"
            "- After making changes, verify them (e.g. read the file back, run tests).\n"
            "- Never expose secrets, tokens, or passwords in your output.\n"
            "- If you cannot complete the task, explain what's blocking you.\n\n"
            "When you are done, return a final JSON message (no tool calls) with this schema:\n"
            '{"success": boolean, "summary": "what you did (under 600 chars)", '
            '"result": {"files_changed": [...], "commands_run": [...], ...}}\n'
        )

        user_content = json.dumps({
            "task_type": task_type,
            "title": title,
            "description": description,
            "payload": payload,
        }, ensure_ascii=False)

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

        try:
            resp = self.executor.chat_with_tools(
                messages=messages,
                tools=tool_executor.TOOL_DEFINITIONS,
                tool_executor=tool_executor,
            )
        except Exception as e:
            msg = str(e)
            self._log("handler.ai.failed", f"AI tool loop failed: {msg[:200]}", level="error", task_id=task_id)
            return HandlerResult(success=False, data={"executed": True}, error=msg, logs=self._execution_logs)

        # Log tool usage summary
        tool_summary = [f"{tc['name']}" for tc in resp.tool_calls_made]
        self._log(
            "handler.ai.tools_used",
            f"Tool calls: {len(resp.tool_calls_made)} across {resp.iterations} iterations: {', '.join(tool_summary[:20])}",
            task_id=task_id,
        )

        # Parse the final response
        parsed = _extract_json_object(resp.content)
        if isinstance(parsed, dict):
            success = bool(parsed.get("success"))
            summary = parsed.get("summary", "")
            result_obj = parsed.get("result", {})
        else:
            # Model returned prose instead of JSON — still may have done work via tools
            # Check if any tool calls actually succeeded, not just that calls were made
            successful_calls = [tc for tc in resp.tool_calls_made if tc.get("result_success")]
            success = len(successful_calls) > 0
            summary = resp.content[:600] if resp.content else "Task completed via tool calls"
            result_obj = {}

        if not isinstance(summary, str):
            summary = str(summary)
        if not isinstance(result_obj, dict):
            result_obj = {"value": result_obj}

        data = {
            "executed": True,
            "summary": summary,
            "result": result_obj,
            "model": self.executor.model,
            "tool_calls": resp.tool_calls_made,
            "tool_iterations": resp.iterations,
        }

        self._log(
            "handler.ai.complete",
            f"AI completed success={success} tools_used={len(resp.tool_calls_made)}",
            task_id=task_id,
            output_data={"success": success, "tool_count": len(resp.tool_calls_made)},
        )

        return HandlerResult(success=success, data=data, error=None if success else summary, logs=self._execution_logs)

    def _execute_chat_only(
        self, task_id: str, task_type: str, title: str, description: str,
        payload: Dict[str, Any], plan_only: bool
    ) -> HandlerResult:
        """Original chat-only execution (no tools). Used for planning/content/design tasks."""

        system = (
            "You are JUGGERNAUT ENGINE, an autonomous execution agent. "
            "Return a single JSON object. No markdown, no code fences, no prose outside JSON.\n\n"
            "Schema:\n"
            "{\n"
            "  \"success\": boolean,\n"
            "  \"summary\": string,\n"
            "  \"result\": object\n"
            "}\n\n"
            "Rules:\n"
            "- If required inputs are missing, set success=false and explain in summary.\n"
            "- Never include secrets.\n"
            "- Keep summary under 600 characters.\n"
        )

        if plan_only:
            system = (
                system
                + "\nPlan-only mode is enabled. Do not claim execution. "
                + "Return success=false and put a concise executable plan inside result. "
                + "The plan should include steps, required tools, and expected artifacts.\n"
            )

        user = {
            "task_type": task_type,
            "title": title,
            "description": description,
            "payload": payload,
        }

        try:
            resp = self.executor.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
                ]
            )
        except Exception as e:
            msg = str(e)
            self._log("handler.ai.failed", f"AI call failed: {msg[:200]}", level="error", task_id=task_id)
            return HandlerResult(success=False, data={"executed": True}, error=msg, logs=self._execution_logs)

        parsed = _extract_json_object(resp.content)
        if not isinstance(parsed, dict):
            self._log(
                "handler.ai.bad_response",
                "AI did not return valid JSON",
                level="error",
                task_id=task_id,
                error_data={"preview": resp.content[:500]},
            )
            return HandlerResult(
                success=False,
                data={"executed": True, "raw": resp.content[:2000]},
                error="AI response was not valid JSON",
                logs=self._execution_logs,
            )

        success = bool(parsed.get("success"))
        summary = parsed.get("summary")
        result_obj = parsed.get("result")
        if not isinstance(summary, str):
            summary = ""
        if not isinstance(result_obj, dict):
            result_obj = {"value": result_obj}

        if plan_only:
            success = False

        data = {
            "executed": True,
            "summary": summary,
            "result": result_obj,
            "model": self.executor.model,
        }

        if plan_only:
            data["waiting_approval"] = True
            data["reason"] = "AI plan-only mode enabled (AIHANDLER_PLAN_ONLY=1)"

        self._log(
            "handler.ai.complete",
            f"AI completed success={success}",
            task_id=task_id,
            output_data={"success": success},
        )

        return HandlerResult(success=success, data=data, error=None if success else summary, logs=self._execution_logs)
