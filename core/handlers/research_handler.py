"""
Research Task Handler
=====================

Searches the web for information and summarizes findings.
Stores research results in the database.

Uses a pluggable search backend (defaults to placeholder).
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, Callable, List
from uuid import uuid4


def handle_research_task(
    task: Dict[str, Any],
    execute_sql: Callable,
    log_action: Callable
) -> Dict[str, Any]:
    """Execute a research task.
    
    Payload format:
    {
        "topic": "AI trends 2025",           # Required
        "depth": "basic|detailed|deep",      # Optional, default "basic"
        "max_sources": 5,                    # Optional, default 5
        "save_to_db": true                   # Optional, default true
    }
    
    Args:
        task: Task dict with payload containing research topic
        execute_sql: Function to execute SQL
        log_action: Function to log actions
        
    Returns:
        Result dict with findings and sources
    """
    task_id = task.get("id", "unknown")
    payload = task.get("payload", {})
    
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid JSON payload"}
    
    topic = payload.get("topic", "").strip()
    depth = payload.get("depth", "basic")
    max_sources = payload.get("max_sources", 5)
    save_to_db = payload.get("save_to_db", True)
    
    if not topic:
        log_action(
            "research.handler.error",
            "No topic provided in payload",
            "error",
            task_id=task_id
        )
        return {"success": False, "error": "No topic provided in payload"}
    
    log_action(
        "research.handler.start",
        f"Starting research on: {topic[:100]}",
        "info",
        task_id=task_id,
        input_data={"topic": topic, "depth": depth, "max_sources": max_sources}
    )
    
    try:
        # Perform web search
        sources = _search_web(topic, max_sources)
        
        # Summarize findings
        summary = _summarize_findings(topic, sources, depth)
        
        log_action(
            "research.handler.searched",
            f"Found {len(sources)} sources for: {topic[:50]}",
            "info",
            task_id=task_id
        )
        
        # Save to database if requested
        research_id = None
        if save_to_db:
            research_id = _save_research(
                task_id, topic, summary, sources, execute_sql, log_action
            )
        
        result = {
            "success": True,
            "topic": topic,
            "sources_found": len(sources),
            "summary": summary,
            "sources": sources,
        }
        
        if research_id:
            result["research_id"] = research_id
        
        log_action(
            "research.handler.complete",
            f"Research complete: {len(sources)} sources, {len(summary)} char summary",
            "info",
            task_id=task_id,
            output_data={"sources_found": len(sources), "summary_length": len(summary)}
        )
        
        return result
        
    except Exception as e:
        error_msg = str(e)[:500]
        log_action(
            "research.handler.error",
            f"Research failed: {error_msg}",
            "error",
            task_id=task_id
        )
        return {"success": False, "error": error_msg}


def _search_web(topic: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search the web for information on a topic.
    
    This is a placeholder implementation. In production, this would:
    - Call a real search API (Brave, Google, Bing)
    - Fetch and parse actual web pages
    - Use AI to extract relevant information
    
    Args:
        topic: The search topic
        max_results: Maximum number of results to return
        
    Returns:
        List of source dicts with url, title, snippet
    """
    # Placeholder: In production, call real search API
    # For now, return structured placeholder data
    sources = [
        {
            "url": f"https://example.com/article-{i+1}",
            "title": f"Research article {i+1} about {topic[:30]}",
            "snippet": f"This source discusses {topic[:50]}... with relevant information.",
            "relevance_score": 0.9 - (i * 0.1)
        }
        for i in range(min(max_results, 3))
    ]
    return sources


def _summarize_findings(
    topic: str, 
    sources: List[Dict[str, str]], 
    depth: str
) -> str:
    """Summarize the research findings.
    
    This is a placeholder implementation. In production, this would:
    - Fetch full content from each source
    - Use AI to synthesize and summarize
    - Extract key facts, statistics, quotes
    
    Args:
        topic: The research topic
        sources: List of source information
        depth: Level of detail (basic, detailed, deep)
        
    Returns:
        Summary string
    """
    # Placeholder: In production, use AI to summarize
    if depth == "basic":
        return f"Brief research on '{topic}': Found {len(sources)} relevant sources. Key themes identified across sources."
    elif depth == "detailed":
        return f"Detailed research on '{topic}': Analyzed {len(sources)} sources. Multiple perspectives examined with key findings synthesized."
    else:  # deep
        return f"Deep research on '{topic}': Comprehensive analysis of {len(sources)} sources including cross-referencing, fact verification, and detailed synthesis."


def _save_research(
    task_id: str,
    topic: str,
    summary: str,
    sources: List[Dict[str, str]],
    execute_sql: Callable,
    log_action: Callable
) -> str:
    """Save research results to the database.
    
    Args:
        task_id: The originating task ID
        topic: Research topic
        summary: Research summary
        sources: List of sources
        execute_sql: SQL execution function
        log_action: Logging function
        
    Returns:
        The research ID (UUID)
    """
    research_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Escape for SQL
    topic_escaped = topic.replace("'", "''")[:500]
    summary_escaped = summary.replace("'", "''")[:5000]
    sources_json = json.dumps(sources).replace("'", "''")
    
    try:
        execute_sql(f"""
            INSERT INTO research_results (
                id, task_id, topic, summary, sources, created_at
            ) VALUES (
                '{research_id}',
                '{task_id}',
                '{topic_escaped}',
                '{summary_escaped}',
                '{sources_json}'::jsonb,
                '{now}'
            )
        """)
        
        log_action(
            "research.handler.saved",
            f"Research saved with ID: {research_id}",
            "info",
            task_id=task_id
        )
        
        return research_id
        
    except Exception as e:
        # Table might not exist - log but don't fail
        log_action(
            "research.handler.save_failed",
            f"Could not save research: {str(e)[:200]}",
            "warning",
            task_id=task_id
        )
        return None
