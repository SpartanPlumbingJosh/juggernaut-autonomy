import json
import logging
from typing import Any, Dict, Optional

from core.ai_executor import AIExecutor

from .base import BaseHandler, HandlerResult

logger = logging.getLogger(__name__)


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            return json.loads(stripped)
        except Exception:
            return None

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    candidate = stripped[start : end + 1]
    try:
        return json.loads(candidate)
    except Exception:
        return None


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

        system = (
            "You are JUGGERNAUT ENGINE, an autonomous execution agent. "
            "Return a single JSON object. No markdown. No prose outside JSON.\n\n"
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

        data = {
            "executed": True,
            "summary": summary,
            "result": result_obj,
            "model": self.executor.model,
        }

        self._log(
            "handler.ai.complete",
            f"AI completed success={success}",
            task_id=task_id,
            output_data={"success": success},
        )

        return HandlerResult(success=success, data=data, error=None if success else summary, logs=self._execution_logs)
