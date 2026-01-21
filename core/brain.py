"""
JUGGERNAUT Brain Module

Provides intelligent consultation capabilities using OpenRouter API with
conversation history persistence and memory recall.
"""

import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from .database import query_db, escape_sql_value

# Configure module logger
logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_MODEL = "openrouter/auto"  # Smart router - auto-selects best model
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
MAX_CONVERSATION_HISTORY = 20
MAX_MEMORIES_TO_RECALL = 10
DEFAULT_MAX_TOKENS = 4096

# Approximate token costs per 1M tokens (OpenRouter pricing)
TOKEN_COSTS = {
    "openrouter/auto": {"input": 5.0, "output": 15.0},
    "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
    "anthropic/claude-3-opus": {"input": 15.0, "output": 75.0},
    "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},
    "openai/gpt-4o": {"input": 2.5, "output": 10.0},
}

# The core system prompt that defines JUGGERNAUT's identity
JUGGERNAUT_SYSTEM_PROMPT = """# JUGGERNAUT BUILDER AGENT - V1

## IDENTITY
You are Josh's autonomous development agent in the HQ chat interface. NOT a consultant. NOT a coordinator. A BUILDER who ships code.

**Core philosophy:** When Josh says "build X" → You build X → You ship X → You say "Done."

## CREDENTIALS

You have full access to these systems via environment variables:

### GitHub
- Repository: SpartanPlumbingJosh/juggernaut-autonomy
- Token: Available via GITHUB_TOKEN env var

### Neon PostgreSQL
- HTTP Endpoint: Available via NEON_HTTP_ENDPOINT env var
- Connection String: Available via DATABASE_URL env var

### Railway API
- GraphQL Endpoint: https://backboard.railway.com/graphql/v2
- Token: Available via RAILWAY_TOKEN env var

## WORKFLOW

When Josh asks you to build something:

1. **Branch** → Create feature branch
2. **Code** → Write the implementation
3. **PR** → Open pull request with clear description
4. **Merge** → Merge to main
5. **Deploy** → Verify deployment (Railway auto-deploys on main merge)
6. **Confirm** → "Done. [link to PR]"

NO asking for permission. NO "shall I proceed?" Just DO IT.

## MCP TOOLS AVAILABLE (68+)

### GitHub Operations
- github_create_branch(branch_name, from_branch?)
- github_put_file(branch, path, content, message, sha?)
- github_get_file(path, branch?)
- github_list_files(path?, branch?)
- github_create_pr(head, title, body?, base?)
- github_merge_pr(pr_number, merge_method?)
- github_list_prs(state?)

### Database (Neon PostgreSQL)
- sql_query(sql) - Execute any SQL query

### Railway
- railway_list_services()
- railway_get_deployments(service_id?, limit?)
- railway_get_logs(deployment_id, limit?)
- railway_set_env(service_id, name, value)
- railway_redeploy(service_id)

### Web Operations
- web_search(query, detailed?) - Perplexity AI search
- fetch_url(url, method?, headers?, body?) - HTTP requests
- browser_navigate(url)
- browser_click(selector)
- browser_type(selector, text)
- browser_screenshot(full_page?)

### Communication
- email_list(folder?, filter?, top?)
- email_read(message_id)
- email_send(to, subject, body, cc?)
- email_reply(message_id, body)
- calendar_create(subject, start, end, attendees?, body?)
- war_room_post(bot, message) - Slack notifications
- war_room_history(limit?)

### Storage & Files
- storage_upload(key, content, content_type?)
- storage_download(key)
- storage_list(prefix?)
- storage_delete(key)

### AI Operations
- ai_chat(messages, model?, max_tokens?)
- ai_complete(prompt, model?)
- image_generate(prompt, size?, model?)

## CODE STANDARDS

All code must follow these rules:

1. **Type hints** - All function parameters and returns
2. **Docstrings** - Google style for all functions
3. **Error handling** - Specific exceptions, never bare `except:`
4. **Logging** - Use `logger.info/error`, not `print()`
5. **Constants** - Use CAPS for magic numbers/strings
6. **SQL** - Always parameterized queries via escape_sql_value()

Example:
```python
def create_task(
    title: str,
    task_type: str,
    priority: int = 5
) -> Dict[str, Any]:
    \"\"\"
    Create a new governance task.
    
    Args:
        title: Task title.
        task_type: Type of task (code, research, deployment).
        priority: Priority 1-10, default 5.
        
    Returns:
        Created task record.
        
    Raises:
        ValueError: If priority out of range.
    \"\"\"
    if not 1 <= priority <= 10:
        raise ValueError(f"Priority must be 1-10, got {priority}")
    
    logger.info(f"Creating task: {title}")
    # ... implementation
```

## DATABASE SCHEMA (Key Tables)

```sql
-- Task management
governance_tasks (id, title, description, task_type, status, priority, assigned_worker, created_at, started_at, completed_at, completion_evidence)

-- Worker tracking
worker_registry (worker_id, status, capabilities, last_heartbeat, current_task_id, created_at)

-- Execution logs
execution_logs (id, task_id, worker_id, action, level, message, error_data, created_at)

-- Active experiments
experiments (id, name, hypothesis, status, created_at, started_at, completed_at, results)

-- Revenue tracking
revenue_events (id, source, amount, category, occurred_at)
revenue_summary (period, total_revenue, event_count, last_updated)

-- Learnings
memories (id, key, content, memory_type, importance, created_at, accessed_at)
learnings (id, title, content, category, confidence, created_at)
```

## RESPONSE STYLE

✅ DO:
- Be action-oriented: "Creating branch... Writing code... Opening PR..."
- Be concise: "Done. PR #47"
- Link to artifacts: "Deployed: https://..."
- Auto-fix errors: "Initial deploy failed (missing env var). Fixed. Redeployed."

❌ DON'T:
- Ask permission: "Should I create the file?" → Just do it
- Explain unnecessarily: "I'm going to use Python because..." → Just ship
- Hedge: "This might work..." → Make it work
- Give options: "We could do A or B..." → Pick one and ship

## ERROR HANDLING

If something fails:
1. Try to auto-fix (missing file? create it. Wrong branch? switch it.)
2. If you can't auto-fix, report concisely: "Deploy failed: [error]. Need [what]."
3. Never say "I can't" - Say what's blocking you and ask for the specific thing you need

## REMEMBER

You have FULL ACCESS to:
- GitHub (create branches, files, PRs, merge)
- Database (read/write any table)
- Railway (deploy, check logs, set env vars)
- Web (search, fetch, browse)

You are NOT limited. You are NOT cautious. You SHIP.

Josh expects:
1. Speed - Don't overthink, ship and iterate
2. Autonomy - Don't ask, just do
3. Results - Working code > perfect code

Now go build."""


class BrainError(Exception):
    """Base exception for brain module errors."""
    pass


class APIError(BrainError):
    """Error calling OpenRouter API."""
    pass


class DatabaseError(BrainError):
    """Error accessing database."""
    pass


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    
    Uses a simple heuristic: ~4 characters per token on average.
    
    Args:
        text: Text to estimate tokens for.
        
    Returns:
        Estimated token count.
    """
    if not text:
        return 0
    return len(text) // 4


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int
) -> float:
    """
    Calculate cost in cents for API usage.
    
    Args:
        model: Model identifier.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        
    Returns:
        Cost in cents.
    """
    costs = TOKEN_COSTS.get(model, {"input": 3.0, "output": 15.0})
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    return round((input_cost + output_cost) * 100, 4)


def _get_system_state() -> str:
    """
    Get current system state for context injection.
    
    Returns:
        Formatted string with current system state.
    """
    try:
        state_parts = []
        
        # Get task queue status
        task_result = query_db(
            "SELECT status, COUNT(*) as count FROM governance_tasks GROUP BY status"
        )
        if task_result.get("rows"):
            tasks = {r["status"]: r["count"] for r in task_result["rows"]}
            state_parts.append(f"Tasks: {tasks}")
        
        # Get total revenue
        rev_result = query_db(
            "SELECT COALESCE(SUM(amount), 0) as total FROM revenue_events"
        )
        if rev_result.get("rows"):
            total_rev = rev_result["rows"][0].get("total", 0)
            state_parts.append(f"Total Revenue: ${total_rev}")
        
        # Get active experiments
        exp_result = query_db(
            "SELECT COUNT(*) as count FROM experiments WHERE status = 'running'"
        )
        if exp_result.get("rows"):
            active_exp = exp_result["rows"][0].get("count", 0)
            state_parts.append(f"Active Experiments: {active_exp}")
        
        # Get active opportunities
        opp_result = query_db(
            "SELECT COUNT(*) as count FROM opportunities WHERE status = 'active'"
        )
        if opp_result.get("rows"):
            active_opp = opp_result["rows"][0].get("count", 0)
            state_parts.append(f"Active Opportunities: {active_opp}")
        
        if state_parts:
            return "\n\n## Current State\n" + " | ".join(state_parts)
        return ""
        
    except Exception as e:
        logger.warning(f"Failed to get system state: {e}")
        return ""


class BrainService:
    """
    Intelligent consultation service with memory and conversation persistence.
    
    Provides a high-level interface for consulting an AI model with:
    - Persistent conversation history
    - Memory recall from the memories table
    - Token counting and cost tracking
    - Real-time system state injection
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS
    ):
        """
        Initialize the BrainService.
        
        Args:
            api_key: OpenRouter API key. Defaults to OPENROUTER_API_KEY env var.
            model: Model to use. Defaults to BRAIN_MODEL env var or DEFAULT_MODEL.
            max_tokens: Maximum tokens in response.
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model or os.getenv("BRAIN_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens
        
        if not self.api_key:
            logger.warning("No OPENROUTER_API_KEY found - API calls will fail")
    
    def consult(
        self,
        question: str,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        include_memories: bool = True,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Consult the brain with a question.
        
        Args:
            question: The question or prompt to send.
            session_id: Session ID for conversation continuity. Auto-generated if None.
            context: Additional context to include.
            include_memories: Whether to recall relevant memories.
            system_prompt: Custom system prompt. Uses JUGGERNAUT prompt if None.
            
        Returns:
            Dict containing:
                - response: The AI response text
                - session_id: Session ID used
                - input_tokens: Estimated input tokens
                - output_tokens: Estimated output tokens
                - cost_cents: Estimated cost in cents
                - memories_used: List of memories recalled
                - model: Model used
        """
        if not self.api_key:
            raise APIError("OPENROUTER_API_KEY not configured")
        
        # Generate or validate session ID
        if session_id is None:
            session_id = f"brain-{uuid4().hex[:12]}"
        
        # Recall relevant memories
        memories_used: List[Dict[str, Any]] = []
        memory_context = ""
        if include_memories:
            memories_used = self._recall_memories(question)
            if memories_used:
                memory_context = self._format_memories(memories_used)
        
        # Load conversation history
        history = self._load_history(session_id)
        
        # Build system prompt
        if system_prompt is None:
            system_prompt = self._build_system_prompt(context, memory_context)
        elif memory_context:
            system_prompt = f"{system_prompt}\n\n{memory_context}"
        
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": question})
        
        # Estimate input tokens
        input_text = system_prompt + question + "".join(
            m.get("content", "") for m in history
        )
        input_tokens = estimate_tokens(input_text)
        
        # Call API
        response_text = self._call_api(messages)
        output_tokens = estimate_tokens(response_text)
        
        # Calculate cost
        cost_cents = calculate_cost(self.model, input_tokens, output_tokens)
        
        # Store conversation
        self._store_message(session_id, "user", question, estimate_tokens(question))
        self._store_message(session_id, "assistant", response_text, output_tokens)
        
        logger.info(
            "Brain consultation complete",
            extra={
                "session_id": session_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_cents": cost_cents,
                "memories_count": len(memories_used)
            }
        )
        
        return {
            "response": response_text,
            "session_id": session_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_cents": cost_cents,
            "memories_used": memories_used,
            "model": self.model
        }
    
    def get_history(
        self,
        session_id: str,
        limit: int = MAX_CONVERSATION_HISTORY
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session ID to retrieve history for.
            limit: Maximum messages to return.
            
        Returns:
            List of message dicts with role, content, created_at.
        """
        try:
            result = query_db(
                f"""
                SELECT role, content, token_count, created_at, metadata
                FROM brain_conversations
                WHERE session_id = {escape_sql_value(session_id)}
                ORDER BY created_at DESC
                LIMIT {limit}
                """
            )
            rows = result.get("rows", [])
            # Reverse to get chronological order
            return list(reversed(rows))
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            raise DatabaseError(f"Failed to retrieve history: {e}")
    
    def clear_history(self, session_id: str) -> Dict[str, Any]:
        """
        Clear conversation history for a session.
        
        Args:
            session_id: Session ID to clear.
            
        Returns:
            Dict with deleted count.
        """
        try:
            result = query_db(
                f"""
                DELETE FROM brain_conversations
                WHERE session_id = {escape_sql_value(session_id)}
                """
            )
            deleted = result.get("rowCount", 0)
            logger.info(f"Cleared {deleted} messages for session {session_id}")
            return {"session_id": session_id, "deleted": deleted}
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
            raise DatabaseError(f"Failed to clear history: {e}")
    
    def _call_api(self, messages: List[Dict[str, str]]) -> str:
        """
        Call the OpenRouter API.
        
        Args:
            messages: List of message dicts with role and content.
            
        Returns:
            Response text from the model.
            
        Raises:
            APIError: If API call fails.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://juggernaut-autonomy.railway.app",
            "X-Title": "Juggernaut Brain"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens
        }
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            OPENROUTER_ENDPOINT,
            data=data,
            headers=headers,
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
                
                choices = result.get("choices", [])
                if not choices:
                    raise APIError("No choices in API response")
                
                return choices[0].get("message", {}).get("content", "")
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            logger.error(f"OpenRouter API error: HTTP {e.code} - {error_body}")
            raise APIError(f"API error {e.code}: {error_body}")
        except urllib.error.URLError as e:
            logger.error(f"OpenRouter API connection error: {e}")
            raise APIError(f"Connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse API response: {e}")
            raise APIError(f"Invalid API response: {e}")
    
    def _load_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        Load conversation history for API context.
        
        Args:
            session_id: Session to load history for.
            
        Returns:
            List of message dicts formatted for API.
        """
        try:
            result = query_db(
                f"""
                SELECT role, content
                FROM brain_conversations
                WHERE session_id = {escape_sql_value(session_id)}
                ORDER BY created_at DESC
                LIMIT {MAX_CONVERSATION_HISTORY}
                """
            )
            rows = result.get("rows", [])
            # Reverse for chronological order and format for API
            return [
                {"role": r["role"], "content": r["content"]}
                for r in reversed(rows)
            ]
        except Exception as e:
            logger.warning(f"Failed to load history: {e}")
            return []
    
    def _store_message(
        self,
        session_id: str,
        role: str,
        content: str,
        token_count: int,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Store a message in conversation history.
        
        Args:
            session_id: Session ID.
            role: Message role (user/assistant).
            content: Message content.
            token_count: Token count.
            metadata: Optional metadata.
        """
        try:
            msg_id = str(uuid4())
            meta_json = json.dumps(metadata or {})
            
            query_db(
                f"""
                INSERT INTO brain_conversations
                (id, session_id, role, content, token_count, created_at, metadata)
                VALUES (
                    {escape_sql_value(msg_id)},
                    {escape_sql_value(session_id)},
                    {escape_sql_value(role)},
                    {escape_sql_value(content)},
                    {token_count},
                    NOW(),
                    {escape_sql_value(meta_json)}::jsonb
                )
                """
            )
        except Exception as e:
            logger.error(f"Failed to store message: {e}")
            # Don't raise - conversation can continue without persistence
    
    def _recall_memories(self, query: str) -> List[Dict[str, Any]]:
        """
        Recall relevant memories based on query.
        
        Uses keyword matching on memory content.
        
        Args:
            query: Query to find relevant memories for.
            
        Returns:
            List of relevant memory records.
        """
        try:
            # Extract keywords (simple approach - words > 3 chars)
            words = [
                w.lower().strip(".,!?;:\"'")
                for w in query.split()
                if len(w) > 3
            ]
            
            if not words:
                return []
            
            # Build search condition
            conditions = " OR ".join(
                f"LOWER(content) LIKE {escape_sql_value(f'%{w}%')}"
                for w in words[:5]  # Limit to first 5 keywords
            )
            
            result = query_db(
                f"""
                SELECT id, key, content, memory_type, importance, created_at
                FROM memories
                WHERE ({conditions})
                AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY importance DESC, accessed_at DESC NULLS LAST
                LIMIT {MAX_MEMORIES_TO_RECALL}
                """
            )
            
            memories = result.get("rows", [])
            
            # Update access counts
            if memories:
                memory_ids = ", ".join(
                    escape_sql_value(m["id"]) for m in memories
                )
                query_db(
                    f"""
                    UPDATE memories
                    SET accessed_at = NOW(),
                        access_count = COALESCE(access_count, 0) + 1
                    WHERE id IN ({memory_ids})
                    """
                )
            
            return memories
            
        except Exception as e:
            logger.warning(f"Failed to recall memories: {e}")
            return []
    
    def _format_memories(self, memories: List[Dict[str, Any]]) -> str:
        """
        Format memories for inclusion in system prompt.
        
        Args:
            memories: List of memory records.
            
        Returns:
            Formatted memory context string.
        """
        if not memories:
            return ""
        
        memory_lines = []
        for mem in memories:
            key = mem.get("key", "unknown")
            content = mem.get("content", "")
            mem_type = mem.get("memory_type", "general")
            memory_lines.append(f"- [{mem_type}] {key}: {content}")
        
        return (
            "## Relevant Memories\n"
            "The following information from memory may be relevant:\n\n"
            + "\n".join(memory_lines)
        )
    
    def _build_system_prompt(
        self,
        context: Optional[Dict[str, Any]],
        memory_context: str
    ) -> str:
        """
        Build the system prompt with JUGGERNAUT identity.
        
        Args:
            context: Additional context dict.
            memory_context: Formatted memory context.
            
        Returns:
            Complete system prompt.
        """
        # Start with the core JUGGERNAUT prompt
        prompt = JUGGERNAUT_SYSTEM_PROMPT
        
        # Add real-time system state
        system_state = _get_system_state()
        if system_state:
            prompt += system_state
        
        # Add any additional context
        if context:
            context_str = "\n\n## Additional Context\n" + json.dumps(context, indent=2)
            prompt += context_str
        
        # Add memory context
        if memory_context:
            prompt += f"\n\n{memory_context}"
        
        return prompt


# Module-level convenience functions

def consult(
    question: str,
    session_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to consult the brain.
    
    Args:
        question: Question to ask.
        session_id: Optional session ID.
        **kwargs: Additional arguments passed to BrainService.consult().
        
    Returns:
        Consultation result dict.
    """
    service = BrainService()
    return service.consult(question, session_id=session_id, **kwargs)


def get_history(session_id: str) -> List[Dict[str, Any]]:
    """
    Convenience function to get conversation history.
    
    Args:
        session_id: Session ID to get history for.
        
    Returns:
        List of messages.
    """
    service = BrainService()
    return service.get_history(session_id)


def clear_history(session_id: str) -> Dict[str, Any]:
    """
    Convenience function to clear conversation history.
    
    Args:
        session_id: Session ID to clear.
        
    Returns:
        Result dict with deleted count.
    """
    service = BrainService()
    return service.clear_history(session_id)


__all__ = [
    "BrainService",
    "BrainError",
    "APIError",
    "DatabaseError",
    "consult",
    "get_history",
    "clear_history",
    "estimate_tokens",
    "calculate_cost",
    "JUGGERNAUT_SYSTEM_PROMPT",
]
