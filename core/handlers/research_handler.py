"""
Research Task Handler
=====================
Searches web and summarizes findings.
Uses free APIs and web scraping for research.
"""

import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, Tuple, List
from datetime import datetime, timezone


# DuckDuckGo Instant Answer API (free, no auth required)
DUCKDUCKGO_API = "https://api.duckduckgo.com/"


def _search_duckduckgo(query: str) -> Dict[str, Any]:
    """
    Search using DuckDuckGo Instant Answer API.
    Free and requires no API key.
    """
    params = {
        "q": query,
        "format": "json",
        "no_html": "1",
        "skip_disambig": "1"
    }
    url = f"{DUCKDUCKGO_API}?{urllib.parse.urlencode(params)}"
    
    req = urllib.request.Request(url, headers={
        "User-Agent": "JUGGERNAUT-Autonomy/1.0"
    })
    
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode('utf-8'))


def _extract_search_results(ddg_response: Dict) -> List[Dict]:
    """Extract useful results from DuckDuckGo response."""
    results = []
    
    # Abstract (Wikipedia-style summary)
    if ddg_response.get("Abstract"):
        results.append({
            "type": "abstract",
            "title": ddg_response.get("Heading", ""),
            "text": ddg_response.get("Abstract", ""),
            "source": ddg_response.get("AbstractSource", ""),
            "url": ddg_response.get("AbstractURL", "")
        })
    
    # Related topics
    for topic in ddg_response.get("RelatedTopics", [])[:5]:
        if isinstance(topic, dict) and "Text" in topic:
            results.append({
                "type": "related",
                "text": topic.get("Text", ""),
                "url": topic.get("FirstURL", "")
            })
    
    # Infobox data
    if ddg_response.get("Infobox"):
        infobox = ddg_response["Infobox"]
        content = infobox.get("content", [])
        results.append({
            "type": "infobox",
            "data": [{
                "label": item.get("label", ""),
                "value": item.get("value", "")
            } for item in content[:10]]
        })
    
    return results


def handle_research_task(task_id: str, payload: Dict[str, Any], log_action_fn) -> Tuple[bool, Dict[str, Any]]:
    """
    Research a topic using web search and summarize findings.
    
    Args:
        task_id: Task identifier for logging
        payload: Task payload containing 'topic' or 'query' key
        log_action_fn: Function to log actions
    
    Returns:
        Tuple of (success: bool, result: dict)
    """
    topic = payload.get("topic") or payload.get("query") or payload.get("search")
    
    if not topic:
        log_action_fn(
            "task.research_handler",
            "No topic provided in payload (expected 'topic', 'query', or 'search' key)",
            level="error",
            task_id=task_id
        )
        return False, {"error": "No topic provided in payload"}
    
    try:
        log_action_fn(
            "task.research_searching",
            f"Researching topic: {topic}",
            level="info",
            task_id=task_id,
            input_data={"topic": topic}
        )
        
        # Search using DuckDuckGo
        ddg_response = _search_duckduckgo(topic)
        results = _extract_search_results(ddg_response)
        
        # Build summary
        summary_parts = []
        sources = []
        
        for result in results:
            if result["type"] == "abstract":
                summary_parts.append(f"Overview: {result['text']}")
                if result.get("url"):
                    sources.append({"name": result.get("source", "Unknown"), "url": result["url"]})
            elif result["type"] == "related":
                summary_parts.append(f"- {result['text'][:200]}")
        
        summary = "\n".join(summary_parts) if summary_parts else f"No detailed information found for '{topic}'. Consider searching with different terms."
        
        log_action_fn(
            "task.research_completed",
            f"Research completed: found {len(results)} results for '{topic}'",
            level="info",
            task_id=task_id,
            output_data={
                "topic": topic,
                "results_count": len(results),
                "summary_preview": summary[:500]
            }
        )
        
        return True, {
            "executed": True,
            "topic": topic,
            "summary": summary,
            "results": results,
            "sources": sources,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except urllib.error.URLError as e:
        log_action_fn(
            "task.research_error",
            f"Network error during research: {str(e)}",
            level="error",
            task_id=task_id,
            error_data={"exception": str(e)}
        )
        return False, {"error": f"Network error: {str(e)}"}
        
    except Exception as e:
        log_action_fn(
            "task.research_error",
            f"Research exception: {str(e)}",
            level="error",
            task_id=task_id,
            error_data={"exception": str(e)}
        )
        return False, {"error": str(e)}
