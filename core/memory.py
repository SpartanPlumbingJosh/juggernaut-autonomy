"""
JUGGERNAUT Persistent Memory System
====================================

L2 Requirement: Multi-Turn Memory - Tracks 5-10 previous exchanges

This module provides:
- store_memory(): Save conversation/task context
- recall_memories(): Retrieve relevant memories
- get_recent_memories(): Get last N exchanges
- update_memory_access(): Track access patterns

Memory Scopes:
- worker: Specific to a worker instance
- task: Specific to a task execution
- conversation: Specific to a conversation session
- global: Available to all workers
"""

import os
import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
import uuid

# Database configuration (shared with database.py)
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Memory configuration
DEFAULT_MEMORY_LIMIT = 10  # L2 requirement: 5-10 exchanges
MEMORY_EXPIRY_DAYS = 30  # Auto-expire old memories


def _execute_sql(sql: str) -> Dict[str, Any]:
    """Execute SQL via Neon HTTP API."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not set")
    
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": DATABASE_URL
    }
    
    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        raise Exception(f"HTTP {e.code}: {error_body}")


def _escape_value(v: Any) -> str:
    """Escape a value for SQL insertion."""
    if v is None:
        return "NULL"
    elif isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    elif isinstance(v, (int, float)):
        return str(v)
    elif isinstance(v, (dict, list)):
        json_str = json.dumps(v).replace("'", "''")
        return f"'{json_str}'"
    else:
        escaped = str(v).replace("'", "''")
        return f"'{escaped}'"


# ============================================================
# MEMORY STORAGE FUNCTIONS
# ============================================================

def store_memory(
    key: str,
    content: str,
    scope: str = "worker",
    scope_id: str = None,
    memory_type: str = "conversation",
    importance: float = 0.5,
    source_worker: str = None,
    source_task_id: str = None,
    expires_in_days: int = None
) -> Optional[str]:
    """
    Store a memory in the persistent memory system.
    
    Args:
        key: Unique identifier for this memory (e.g., 'task_context', 'user_preference')
        content: The actual memory content (text)
        scope: Memory scope - 'worker', 'task', 'conversation', 'global'
        scope_id: ID within the scope (e.g., worker_id, task_id)
        memory_type: Type of memory - 'conversation', 'learning', 'context', 'decision'
        importance: 0.0-1.0 importance score
        source_worker: Which worker created this memory
        source_task_id: Which task generated this memory
        expires_in_days: Number of days until memory expires (None = never)
    
    Returns:
        Memory UUID or None on failure
    """
    now = datetime.now(timezone.utc)
    memory_id = str(uuid.uuid4())
    
    # Calculate expiration
    expires_at = None
    if expires_in_days:
        expires_at = (now + timedelta(days=expires_in_days)).isoformat()
    
    cols = ["id", "scope", "key", "content", "memory_type", "importance", 
            "created_at", "updated_at", "access_count"]
    vals = [_escape_value(memory_id), _escape_value(scope), _escape_value(key),
            _escape_value(content), _escape_value(memory_type), str(importance),
            _escape_value(now.isoformat()), _escape_value(now.isoformat()), "0"]
    
    if scope_id:
        cols.append("scope_id")
        vals.append(_escape_value(scope_id))
    if source_worker:
        cols.append("source_worker")
        vals.append(_escape_value(source_worker))
    if source_task_id:
        cols.append("source_task_id")
        vals.append(_escape_value(source_task_id))
    if expires_at:
        cols.append("expires_at")
        vals.append(_escape_value(expires_at))
    
    sql = f"INSERT INTO memories ({', '.join(cols)}) VALUES ({', '.join(vals)}) RETURNING id"
    
    try:
        result = _execute_sql(sql)
        return result.get("rows", [{}])[0].get("id")
    except Exception as e:
        print(f"Failed to store memory: {e}")
        return None


# ============================================================
# MEMORY RETRIEVAL FUNCTIONS
# ============================================================

def recall_memories(
    query: str = None,
    scope: str = None,
    scope_id: str = None,
    memory_type: str = None,
    min_importance: float = 0.0,
    limit: int = DEFAULT_MEMORY_LIMIT,
    include_expired: bool = False
) -> List[Dict]:
    """
    Recall memories matching the given criteria.
    
    Args:
        query: Text to search for in memory content (uses ILIKE)
        scope: Filter by scope
        scope_id: Filter by scope ID
        memory_type: Filter by memory type
        min_importance: Minimum importance score
        limit: Max memories to return (default: 10)
        include_expired: Whether to include expired memories
    
    Returns:
        List of memory dictionaries, ordered by importance and recency
    """
    conditions = []
    
    if query:
        # Simple text search using ILIKE
        escaped_query = query.replace("'", "''").replace("%", "\\%")
        conditions.append(f"content ILIKE '%{escaped_query}%'")
    
    if scope:
        conditions.append(f"scope = {_escape_value(scope)}")
    
    if scope_id:
        conditions.append(f"scope_id = {_escape_value(scope_id)}")
    
    if memory_type:
        conditions.append(f"memory_type = {_escape_value(memory_type)}")
    
    if min_importance > 0:
        conditions.append(f"importance >= {min_importance}")
    
    if not include_expired:
        now = datetime.now(timezone.utc).isoformat()
        conditions.append(f"(expires_at IS NULL OR expires_at > '{now}')")
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    # Order by importance (desc), then by recency
    sql = f"""
        SELECT id, scope, scope_id, key, content, memory_type, 
               importance, created_at, updated_at, accessed_at,
               access_count, source_worker, source_task_id
        FROM memories
        {where}
        ORDER BY importance DESC, created_at DESC
        LIMIT {limit}
    """
    
    try:
        result = _execute_sql(sql)
        memories = result.get("rows", [])
        
        # Update access timestamps for retrieved memories
        if memories:
            memory_ids = [m["id"] for m in memories]
            _update_access_times(memory_ids)
        
        return memories
    except Exception as e:
        print(f"Failed to recall memories: {e}")
        return []


def get_recent_memories(
    scope: str = None,
    scope_id: str = None,
    limit: int = DEFAULT_MEMORY_LIMIT
) -> List[Dict]:
    """
    Get the most recent memories (L2 requirement: 5-10 exchanges).
    
    Args:
        scope: Filter by scope
        scope_id: Filter by scope ID
        limit: Max memories to return (default: 10 for L2 requirement)
    
    Returns:
        List of recent memories, ordered by creation time (newest first)
    """
    conditions = []
    now = datetime.now(timezone.utc).isoformat()
    
    # Exclude expired memories
    conditions.append(f"(expires_at IS NULL OR expires_at > '{now}')")
    
    if scope:
        conditions.append(f"scope = {_escape_value(scope)}")
    
    if scope_id:
        conditions.append(f"scope_id = {_escape_value(scope_id)}")
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    sql = f"""
        SELECT id, scope, scope_id, key, content, memory_type, 
               importance, created_at, updated_at, accessed_at,
               access_count, source_worker, source_task_id
        FROM memories
        {where}
        ORDER BY created_at DESC
        LIMIT {limit}
    """
    
    try:
        result = _execute_sql(sql)
        memories = result.get("rows", [])
        
        # Update access timestamps
        if memories:
            memory_ids = [m["id"] for m in memories]
            _update_access_times(memory_ids)
        
        return memories
    except Exception as e:
        print(f"Failed to get recent memories: {e}")
        return []


def _update_access_times(memory_ids: List[str]) -> None:
    """Update access timestamp and count for accessed memories."""
    if not memory_ids:
        return
    
    now = datetime.now(timezone.utc).isoformat()
    ids_str = ", ".join([_escape_value(id) for id in memory_ids])
    
    sql = f"""
        UPDATE memories 
        SET accessed_at = '{now}', 
            access_count = COALESCE(access_count, 0) + 1
        WHERE id IN ({ids_str})
    """
    
    try:
        _execute_sql(sql)
    except Exception:
        pass  # Don't fail on access tracking errors


# ============================================================
# MEMORY MANAGEMENT FUNCTIONS
# ============================================================

def cleanup_expired_memories() -> int:
    """
    Delete expired memories.
    
    Returns:
        Number of memories deleted
    """
    now = datetime.now(timezone.utc).isoformat()
    sql = f"DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at < '{now}'"
    
    try:
        result = _execute_sql(sql)
        return result.get("rowCount", 0) or 0
    except Exception as e:
        print(f"Failed to cleanup expired memories: {e}")
        return 0


def get_memory_stats() -> Dict[str, Any]:
    """
    Get memory system statistics.
    
    Returns:
        Dict with counts, types, scopes, etc.
    """
    try:
        # Total count
        total_sql = "SELECT COUNT(*) as count FROM memories"
        total = _execute_sql(total_sql).get("rows", [{}])[0].get("count", 0)
        
        # By scope
        scope_sql = "SELECT scope, COUNT(*) as count FROM memories GROUP BY scope"
        scopes = {r["scope"]: int(r["count"]) for r in _execute_sql(scope_sql).get("rows", [])}
        
        # By type
        type_sql = "SELECT memory_type, COUNT(*) as count FROM memories GROUP BY memory_type"
        types = {r["memory_type"]: int(r["count"]) for r in _execute_sql(type_sql).get("rows", [])}
        
        return {
            "total_memories": int(total),
            "by_scope": scopes,
            "by_type": types
        }
    except Exception as e:
        print(f"Failed to get memory stats: {e}")
        return {"total_memories": 0, "by_scope": {}, "by_type": {}}


# ============================================================
# TASK CONTEXT HELPERS
# ============================================================

def store_task_context(
    task_id: str,
    context: str,
    worker_id: str = None,
    importance: float = 0.6
) -> Optional[str]:
    """
    Store context for a specific task execution.
    
    Args:
        task_id: The task UUID
        context: Context/conversation to remember
        worker_id: Which worker is storing this
        importance: Importance score (0.0-1.0)
    
    Returns:
        Memory UUID or None
    """
    return store_memory(
        key=f"task_context_{task_id[:8]}",
        content=context,
        scope="task",
        scope_id=task_id,
        memory_type="context",
        importance=importance,
        source_worker=worker_id,
        source_task_id=task_id,
        expires_in_days=7  # Task context expires after a week
    )


def get_task_context(task_id: str) -> List[Dict]:
    """
    Get all stored context for a task.
    
    Args:
        task_id: The task UUID
    
    Returns:
        List of context memories
    """
    return recall_memories(
        scope="task",
        scope_id=task_id,
        limit=20
    )


def store_learning(
    learning: str,
    worker_id: str = None,
    task_id: str = None,
    importance: float = 0.7
) -> Optional[str]:
    """
    Store a learning/insight that should be remembered globally.
    
    Args:
        learning: The insight to remember
        worker_id: Which worker discovered this
        task_id: Which task led to this learning
        importance: Importance score
    
    Returns:
        Memory UUID or None
    """
    return store_memory(
        key="learning",
        content=learning,
        scope="global",
        scope_id="all_workers",
        memory_type="learning",
        importance=importance,
        source_worker=worker_id,
        source_task_id=task_id
        # Learnings don't expire
    )


def get_relevant_learnings(query: str, limit: int = 5) -> List[Dict]:
    """
    Get learnings relevant to a query.
    
    Args:
        query: Text to search for
        limit: Max learnings to return
    
    Returns:
        List of relevant learnings
    """
    return recall_memories(
        query=query,
        memory_type="learning",
        limit=limit
    )
