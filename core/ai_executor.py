import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
DEFAULT_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "4096"))
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "60"))
DEFAULT_MAX_PRICE_PROMPT = os.getenv("OPENROUTER_MAX_PRICE_PROMPT", "1")
DEFAULT_MAX_PRICE_COMPLETION = os.getenv("OPENROUTER_MAX_PRICE_COMPLETION", "2")


@dataclass
class AIResponse:
    content: str
    raw: Dict[str, Any]


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
        self.api_key = (api_key or os.getenv("OPENROUTER_API_KEY") or "").strip()
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
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": int(max_tokens) if max_tokens is not None else self.max_tokens,
        }

        provider = self._provider_routing()
        if provider is not None:
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
            raise RuntimeError(f"OpenRouter HTTP {e.code}: {error_body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"OpenRouter connection error: {e}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"OpenRouter invalid JSON response: {e}") from e

        choices = raw.get("choices") or []
        if not choices:
            raise RuntimeError("OpenRouter response missing choices")

        content = ((choices[0] or {}).get("message") or {}).get("content") or ""
        return AIResponse(content=content, raw=raw)
