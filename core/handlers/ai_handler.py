import json
import logging
import os
from typing import Any, Dict, Optional

from core.ai_executor import AIExecutor

from .base import BaseHandler, HandlerResult

logger = logging.getLogger(__name__)


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

    def execute(self, task: Dict[str, Any]) -> HandlerResult:
        self._execution_logs = []
        task_id = task.get("id")

        payload = task.get("payload") or {}
        title = task.get("title") or ""
        description = task.get("description") or ""
        task_type = task.get("task_type") or ""

        self._log(
            "handler.ai.starting",
            f"AI handling task_type='{task_type}' title='{title[:80]}'",
            task_id=task_id,
        )

        plan_only = _truthy_env("AIHANDLER_PLAN_ONLY", "0")

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
