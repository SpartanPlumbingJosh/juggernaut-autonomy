"""Research handler for web search and summarization tasks.

This module handles tasks of type 'research' that search the web for
information and summarize findings. Uses external search capabilities
when available, with fallback to structured research documentation.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .base import BaseHandler, HandlerResult

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MAX_RESULTS = 5
MAX_QUERY_LENGTH = 500
MAX_SUMMARY_LENGTH = 2000
REQUEST_TIMEOUT_SECONDS = 30
RESEARCH_FINDINGS_TABLE = "research_findings"
PERPLEXITY_API_ENDPOINT = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "").strip()
PUPPETEER_URL = os.environ.get("PUPPETEER_URL", "").strip()
PUPPETEER_AUTH_TOKEN = os.environ.get("PUPPETEER_AUTH_TOKEN", "jug-pup-auth-2024").strip()

_DOMAIN_RE = re.compile(r"\b[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.(?:com|net|org|io|co|xyz|ai|app|dev)\b", re.IGNORECASE)
_PRICE_RE = re.compile(r"(?:\$\s?\d{1,6}(?:[\.,]\d{1,2})?)|(?:\b\d{1,6}\s?(?:usd|\$)\b)", re.IGNORECASE)


class ResearchHandler(BaseHandler):
    """Handler for research task type.
    
    Executes research tasks that involve searching for information,
    analyzing sources, and producing summarized findings. Results
    are stored in the research_findings table for future reference.
    """

    task_type = "research"

    def execute(self, task: Dict[str, Any]) -> HandlerResult:
        """Execute a research task.
        
        Args:
            task: Task dictionary with payload containing:
                - query (str): The research query/topic
                - max_results (int, optional): Maximum sources to analyze
                - save_findings (bool, optional): Whether to persist results
        
        Returns:
            HandlerResult with research findings or error information.
        """
        self._execution_logs = []
        task_id = task.get("id")
        payload = task.get("payload", {})

        # Validate required fields
        query = payload.get("query") or payload.get("topic") or payload.get("search")
        if not query:
            error_msg = "Research task missing 'query', 'topic', or 'search' in payload"
            self._log(
                "handler.research.missing_query",
                error_msg,
                level="error",
                task_id=task_id
            )
            return HandlerResult(
                success=False,
                data={"expected_fields": ["query", "topic", "search"]},
                error=error_msg,
                logs=self._execution_logs
            )

        # Sanitize and validate query
        query = str(query).strip()[:MAX_QUERY_LENGTH]
        if not query:
            error_msg = "Research query is empty"
            self._log(
                "handler.research.empty_query",
                error_msg,
                level="error",
                task_id=task_id
            )
            return HandlerResult(
                success=False,
                data={},
                error=error_msg,
                logs=self._execution_logs
            )

        max_results = payload.get("max_results", DEFAULT_MAX_RESULTS)
        save_findings = payload.get("save_findings", True)

        self._log(
            "handler.research.starting",
            f"Starting research for query: {query[:100]}...",
            task_id=task_id
        )

        try:
            # Execute the research
            findings = self._conduct_research(query, max_results, task_id)
            
            # Optionally persist findings to database
            finding_id = None
            if save_findings and findings.get("sources"):
                finding_id = self._save_findings(task_id, query, findings)

            result_data = {
                "executed": True,
                "query": query,
                "sources_analyzed": len(findings.get("sources", [])),
                "findings": findings,
                "finding_id": finding_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            self._log(
                "handler.research.complete",
                f"Research complete: analyzed {len(findings.get('sources', []))} sources",
                task_id=task_id,
                output_data={
                    "sources_count": len(findings.get("sources", [])),
                    "finding_id": finding_id
                }
            )

            return HandlerResult(
                success=True,
                data=result_data,
                logs=self._execution_logs
            )

        except Exception as research_error:
            error_msg = str(research_error)
            self._log(
                "handler.research.failed",
                f"Research failed: {error_msg[:200]}",
                level="error",
                task_id=task_id
            )
            return HandlerResult(
                success=False,
                data={"query": query},
                error=error_msg,
                logs=self._execution_logs
            )

    def _conduct_research(
        self,
        query: str,
        max_results: int,
        task_id: Optional[str]
    ) -> Dict[str, Any]:
        """Conduct research by searching and analyzing sources.
        
        This implementation creates a structured research document.
        In production, this could integrate with search APIs or LLM services.
        
        Args:
            query: The research query.
            max_results: Maximum number of sources to analyze.
            task_id: Task ID for logging.
        
        Returns:
            Dictionary containing sources, summary, and key findings.
        """
        sources: List[Dict[str, Any]] = []
        
        # Check if we have web search capability via external service
        search_results = self._attempt_web_search(query, max_results)
        
        if search_results:
            sources = search_results
            self._log(
                "handler.research.web_search_success",
                f"Web search returned {len(sources)} results",
                task_id=task_id
            )
        else:
            # Fallback: Create a research request record
            self._log(
                "handler.research.web_search_unavailable",
                "Web search unavailable, creating research request record",
                level="warn",
                task_id=task_id
            )
            sources = [{
                "type": "research_request",
                "query": query,
                "status": "pending_manual_research",
                "note": "Automated web search unavailable - manual research required"
            }]

        # Build findings structure
        extracted_candidates = self._extract_domain_candidates_from_sources(sources, task_id)
        findings = {
            "query": query,
            "sources": sources,
            "candidates": extracted_candidates,
            "summary": self._generate_summary(query, sources),
            "key_points": self._extract_key_points(sources),
            "confidence": self._calculate_confidence(sources),
            "researched_at": datetime.now(timezone.utc).isoformat()
        }

        return findings

    def _attempt_web_search(
        self,
        query: str,
        max_results: int
    ) -> Optional[List[Dict[str, Any]]]:
        """Attempt to perform web search via available services.
        
        Args:
            query: Search query.
            max_results: Maximum results to return.
        
        Returns:
            List of search result dictionaries, or None if unavailable.
        """
        if not PERPLEXITY_API_KEY:
            logger.warning("PERPLEXITY_API_KEY not set or empty")
            return None

        payload = {
            "model": "sonar",
            "messages": [{"role": "user", "content": query}],
            "return_citations": True,
        }

        req = urllib.request.Request(
            PERPLEXITY_API_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8")
            except Exception:
                body = ""
            logger.error(f"Perplexity API HTTP {e.code}: {body[:500]}")
            return None
        except Exception as e:
            logger.error(f"Perplexity API call failed: {e}")
            return None

        choices = raw.get("choices") or []
        answer = ""
        if choices:
            answer = ((choices[0] or {}).get("message") or {}).get("content") or ""
        citations = raw.get("citations") or []

        sources: List[Dict[str, Any]] = []
        if isinstance(citations, list) and citations:
            for url in citations[: max(1, int(max_results))]:
                sources.append({
                    "type": "citation",
                    "url": url,
                    "title": url,
                    "snippet": (answer or "")[:400],
                })
        else:
            sources.append({
                "type": "perplexity",
                "title": query[:120],
                "snippet": (answer or "")[:400],
                "raw": {"citations": citations},
            })

        return sources


    def _puppeteer_action(self, action: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not PUPPETEER_URL:
            return None

        body = json.dumps({"action": action, **(params or {})}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if PUPPETEER_AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {PUPPETEER_AUTH_TOKEN}"

        req = urllib.request.Request(
            f"{PUPPETEER_URL.rstrip('/')}/action",
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None


    def _fetch_html_via_puppeteer(self, url: str) -> Optional[str]:
        if not url:
            return None

        nav = self._puppeteer_action("navigate", {"url": url})
        if not nav or not nav.get("success"):
            return None

        page = self._puppeteer_action("get_text", {})
        if not page or not page.get("success"):
            return None

        html = page.get("html")
        if not isinstance(html, str) or not html.strip():
            return None
        return html


    def _extract_domain_candidates_from_sources(
        self,
        sources: List[Dict[str, Any]],
        task_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        if not sources:
            return []

        urls: List[str] = []
        for s in sources:
            url = s.get("url")
            if isinstance(url, str) and url.startswith("http"):
                urls.append(url)

        urls = urls[:5]
        if not urls:
            return []

        candidates: Dict[str, Dict[str, Any]] = {}
        for url in urls:
            html = self._fetch_html_via_puppeteer(url)
            if not html:
                continue

            found_domains = _DOMAIN_RE.findall(html)
            if not found_domains:
                continue

            prices = _PRICE_RE.findall(html)
            price_hint = prices[0] if prices else None

            for d in found_domains[:100]:
                key = d.lower()
                if key not in candidates:
                    candidates[key] = {
                        "domain": d.lower(),
                        "source_url": url,
                        "price_hint": price_hint,
                    }

        if candidates:
            self._log(
                "handler.research.domain_candidates_extracted",
                f"Extracted {len(candidates)} domain candidates from {len(urls)} pages",
                task_id=task_id,
            )

        return list(candidates.values())[:50]

    def _generate_summary(
        self,
        query: str,
        sources: List[Dict[str, Any]]
    ) -> str:
        """Generate a summary of research findings.
        
        Args:
            query: The original research query.
            sources: List of source dictionaries.
        
        Returns:
            Summary string.
        """
        if not sources:
            return f"No sources found for query: {query}"
        
        source_count = len(sources)
        if sources[0].get("type") == "research_request":
            return (
                f"Research request created for: {query}. "
                "Manual research is required as automated search is unavailable."
            )
        
        return (
            f"Research conducted on: {query}. "
            f"Analyzed {source_count} source(s). "
            "See key_points for detailed findings."
        )

    def _extract_key_points(
        self,
        sources: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract key points from research sources.
        
        Args:
            sources: List of source dictionaries.
        
        Returns:
            List of key point strings.
        """
        key_points = []
        
        for source in sources:
            if source.get("title"):
                key_points.append(f"Source: {source.get('title', 'Unknown')}")
            if source.get("snippet"):
                key_points.append(f"Finding: {source.get('snippet', '')[:200]}")
        
        if not key_points:
            key_points.append("Further manual research recommended")
        
        return key_points[:10]  # Limit to 10 key points

    def _calculate_confidence(self, sources: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for research findings.
        
        Args:
            sources: List of source dictionaries.
        
        Returns:
            Confidence score between 0.0 and 1.0.
        """
        if not sources:
            return 0.0
        
        # Base confidence on number and quality of sources
        source_count = len(sources)
        
        if sources[0].get("type") == "research_request":
            return 0.1  # Low confidence for pending manual research
        
        # More sources = higher confidence, up to a point
        confidence = min(0.3 + (source_count * 0.1), 0.9)
        
        return round(confidence, 2)

    def _save_findings(
        self,
        task_id: Optional[str],
        query: str,
        findings: Dict[str, Any]
    ) -> Optional[str]:
        """Persist research findings to the database.
        
        Args:
            task_id: Associated task ID.
            query: The research query.
            findings: The research findings dictionary.
        
        Returns:
            The finding ID if saved successfully, None otherwise.
        """
        finding_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Escape values for SQL
        escaped_query = query.replace("'", "''")
        escaped_findings = json.dumps(findings).replace("'", "''")
        escaped_task_id = task_id if task_id else "NULL"
        
        try:
            # Check if table exists first
            check_sql = f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{RESEARCH_FINDINGS_TABLE}'
                )
            """
            result = self.execute_sql(check_sql)
            table_exists = result.get("rows", [{}])[0].get("exists", False)
            
            if not table_exists:
                self._log(
                    "handler.research.table_missing",
                    f"Table {RESEARCH_FINDINGS_TABLE} does not exist, skipping save",
                    level="warn",
                    task_id=task_id
                )
                return None
            
            insert_sql = f"""
                INSERT INTO {RESEARCH_FINDINGS_TABLE} 
                (id, task_id, query, findings, confidence, created_at)
                VALUES (
                    '{finding_id}',
                    {f"'{escaped_task_id}'" if task_id else 'NULL'},
                    '{escaped_query}',
                    '{escaped_findings}'::jsonb,
                    {findings.get('confidence', 0)},
                    '{now}'
                )
            """
            self.execute_sql(insert_sql)
            return finding_id
            
        except Exception as save_error:
            self._log(
                "handler.research.save_failed",
                f"Failed to save findings: {str(save_error)[:100]}",
                level="warn",
                task_id=task_id
            )
            return None
