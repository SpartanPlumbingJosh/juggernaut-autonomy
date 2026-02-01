from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.ai_executor import AIExecutor

logger = logging.getLogger(__name__)


@dataclass
class RevenueIdea:
    title: str
    description: str
    hypothesis: str
    estimates: Dict[str, Any]


class IdeaGenerator:
    """Generates revenue opportunities based on available capabilities."""

    PERPLEXITY_API_ENDPOINT = "https://api.perplexity.ai/chat/completions"

    def __init__(
        self,
        ai: Optional[AIExecutor] = None,
        perplexity_api_key: Optional[str] = None,
    ) -> None:
        self.ai = ai
        self.perplexity_api_key = (perplexity_api_key or os.environ.get("PERPLEXITY_API_KEY") or "").strip()

    def _extract_json_array(self, text: str) -> Optional[List[Dict[str, Any]]]:
        if not isinstance(text, str) or not text.strip():
            return None
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", cleaned)
            cleaned = re.sub(r"\n```$", "", cleaned)

        start = cleaned.find("[")
        if start < 0:
            return None

        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(cleaned)):
            ch = cleaned[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            else:
                if ch == '"':
                    in_str = True
                    continue
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        candidate = cleaned[start : i + 1]
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, list):
                                out: List[Dict[str, Any]] = []
                                for item in parsed:
                                    if isinstance(item, dict):
                                        out.append(item)
                                return out
                        except Exception:
                            return None
        return None

    def _perplexity_search(self, query: str, max_results: int = 5) -> Optional[Dict[str, Any]]:
        if not self.perplexity_api_key:
            logger.warning("Perplexity API key not configured")
            return None

        payload = {
            "model": "sonar",
            "messages": [{"role": "user", "content": query}],
        }

        req = urllib.request.Request(
            self.PERPLEXITY_API_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.perplexity_api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            logger.info(f"Perplexity search successful for: {query[:50]}...")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else "no body"
            logger.error(f"Perplexity HTTP error {e.code}: {error_body[:200]}")
            return None
        except Exception as e:
            logger.error(f"Perplexity search failed: {type(e).__name__}: {e}")
            return None

        choices = raw.get("choices") or []
        answer = ""
        if choices:
            answer = ((choices[0] or {}).get("message") or {}).get("content") or ""
        citations = raw.get("citations") or []

        urls: List[str] = []
        if isinstance(citations, list):
            for u in citations[: max(1, int(max_results))]:
                if isinstance(u, str) and u.startswith("http"):
                    urls.append(u)

        return {
            "query": query,
            "answer": answer,
            "citations": urls,
        }

    async def generate_ideas_async(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.generate_ideas(context)

    def generate_ideas(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        assets = context.get("assets") or {}
        constraints = context.get("constraints") or {}

        max_budget = float(constraints.get("max_budget", 50) or 50)
        automation_stack = str(assets.get("automation_stack") or assets.get("capabilities") or "AI + web research + scripting")

        indie_style = bool(constraints.get("indie_style", True))
        email_only = True
        no_employees = True
        forbid_calls = True
        prefer_digital_products = bool(constraints.get("prefer_digital_products", True))

        now_utc = datetime.now(timezone.utc)
        today = now_utc.strftime("%Y-%m-%d")
        year = now_utc.strftime("%Y")
        month_year = now_utc.strftime("%B %Y")

        search_queries = [
            f"what digital products are selling on Etsy right now {year}",
            "trending Gumroad products this week",
            f"domain flipping opportunities {month_year}",
            "AI automation business ideas no employees",
            "passive income ideas that work via email only",
            f"micro-SaaS one-person businesses {year}",
            "affiliate marketing niches trending now",
            "print on demand niches selling this month",
            "info products people are buying right now",
            f"newsletter monetization strategies {year}",
        ]

        logger.info(f"Starting idea generation with Perplexity configured: {bool(self.perplexity_api_key)}")

        research_results: List[Dict[str, Any]] = []
        for q in search_queries:
            r = self._perplexity_search(q, max_results=5)
            if r:
                research_results.append(r)

        logger.info(f"Perplexity returned {len(research_results)} research results")

        if not research_results:
            logger.warning("No research results - using fallback ideas")
            ideas: List[RevenueIdea] = [
                RevenueIdea(
                    title="Email-only digital template pack (Etsy/Gumroad)",
                    description="Ship a focused template pack (SOPs, prompts, spreadsheets, checklists) for a currently-trending buyer segment on Etsy/Gumroad, with fulfillment and support handled asynchronously via email.",
                    hypothesis="Can validate demand and earn the first $20 within 14 days using listings + email-only support and follow-up automation.",
                    estimates={
                        "capital_required": 0,
                        "time_to_first_dollar_days": 14,
                        "effort_hours": 8,
                        "monthly_potential": 300,
                        "scalability": 7,
                        "risk_level": 4,
                        "capability_fit": 8,
                    },
                )
            ]
            return [
                {
                    "title": i.title,
                    "description": i.description,
                    "hypothesis": i.hypothesis,
                    "research_sources": [],
                    "timeliness": f"Fallback (no web search configured) as of {today}",
                    "constraints": {
                        "indie_style": indie_style,
                        "email_only": email_only,
                        "no_employees": no_employees,
                        "forbid_calls": forbid_calls,
                        "prefer_digital_products": prefer_digital_products,
                    },
                    "estimates": i.estimates,
                    "researched_at": today,
                }
                for i in ideas
            ]

        if self.ai is None:
            try:
                self.ai = AIExecutor()
            except Exception:
                self.ai = None

        if self.ai is None:
            logger.info("No AI executor - returning raw research results as ideas")
            out: List[Dict[str, Any]] = []
            for rr in research_results[:5]:
                citations = rr.get("citations") or []
                out.append(
                    {
                        "title": f"Opportunity from: {rr.get('query')}",
                        "description": (rr.get("answer") or "")[:300],
                        "hypothesis": "Can validate demand and acquire 1 paying customer in 14 days via email-only outreach",
                        "research_sources": citations,
                        "timeliness": f"Derived from web research on {today}",
                        "constraints": {
                            "indie_style": indie_style,
                            "email_only": email_only,
                            "no_employees": no_employees,
                            "forbid_calls": forbid_calls,
                            "prefer_digital_products": prefer_digital_products,
                        },
                        "estimates": {
                            "capital_required": 0,
                            "time_to_first_dollar_days": 14,
                            "effort_hours": 10,
                            "monthly_potential": 200,
                            "scalability": 6,
                            "risk_level": 5,
                            "capability_fit": 7,
                        },
                        "researched_at": today,
                    }
                )
            return out[:5]

        prompt = (
            "Return ONLY valid JSON (no markdown, no code fences).\n\n"
            "You are an autonomous AI scanning the internet for revenue opportunities.\n"
            f"Today (UTC) is {today}.\n\n"
            "Research results (from web search):\n"
            f"{json.dumps(research_results)[:12000]}\n\n"
            "Operational capabilities:\n"
            f"- Automation stack: {automation_stack}\n"
            f"- Budget cap: ${max_budget}\n\n"
            "Constraints (MUST FOLLOW):\n"
            "- Email-only customer acquisition and support (no calls, meetings, or phone support).\n"
            "- Must be buildable/operable by AI with minimal human involvement.\n"
            "- Owner only provides initial setup and approval, then hands-off.\n"
            "- No employees or contractors required.\n"
            "- Prefer: digital products, automation, arbitrage, templates, info products.\n\n"
            "Search the web results for ANYTHING that fits these constraints.\n"
            "Do NOT anchor to any specific industry or expertise.\n"
            "Find what's WORKING RIGHT NOW and can be automated.\n\n"
            "Generate 3-5 SPECIFIC, TIMELY revenue ideas that comply with the constraints. Each must include:\n"
            "- title\n"
            "- description (include why now / timeliness)\n"
            "- hypothesis (testable, 14 days)\n"
            "- research_sources (array of URLs or source names)\n"
            "- timeliness (one sentence)\n"
            "- constraints: {indie_style, email_only, no_employees, forbid_calls, prefer_digital_products}\n"
            "- estimates: {capital_required, time_to_first_dollar_days, effort_hours, monthly_potential, scalability, risk_level, capability_fit}\n"
            "- researched_at (YYYY-MM-DD)\n\n"
            "Return a JSON array."
        )

        resp = self.ai.chat(
            [
                {"role": "system", "content": "Return ONLY JSON. No markdown. No code fences."},
                {"role": "user", "content": prompt},
            ]
        )

        parsed = self._extract_json_array(getattr(resp, "content", "") or "")
        if not parsed:
            logger.warning("Failed to parse AI response as JSON array")
            return []

        normalized: List[Dict[str, Any]] = []
        for idea in parsed:
            if not isinstance(idea, dict):
                continue
            estimates = idea.get("estimates") or {}
            if isinstance(estimates, dict):
                if "time_to_revenue_days" in estimates and "time_to_first_dollar_days" not in estimates:
                    try:
                        estimates["time_to_first_dollar_days"] = estimates.get("time_to_revenue_days")
                    except Exception:
                        pass
            idea["estimates"] = estimates
            if "constraints" not in idea:
                idea["constraints"] = {
                    "indie_style": indie_style,
                    "email_only": email_only,
                    "no_employees": no_employees,
                    "forbid_calls": forbid_calls,
                    "prefer_digital_products": prefer_digital_products,
                }
            if "researched_at" not in idea:
                idea["researched_at"] = today
            normalized.append(idea)

        logger.info(f"Generated {len(normalized)} revenue ideas from AI synthesis")
        return normalized[:5]
