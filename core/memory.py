"""
JUGGERNAUT Memory System
========================
Persistent memory for the autonomy engine.

L2 Requirement: Multi-Turn Memory - Tracks 5-10 previous exchanges.
Provides context across task execution sessions.

Memory Scopes:
- 'engine': Global engine context (shared across all workers)
- 'worker': Per-worker memories (e.g., 'worker:autonomy-engine-1')
- 'task': Per-task context (e.g., 'task:<task_id>')
- 'conversation': Conversation history tracking

Memory Types:
- 'context': Current execution context
- 'learning': Learned patterns/insights
- 'preference': User or system preferences
- 'error': Error patterns to avoid
- 'exchange': Conversation exchange record
"""

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MEMORY_IMPORTANCE = 0.5
MAX_MEMORY_CONTENT_LENGTH = 10000
MEMORY_EXPIRY_DAYS_DEFAULT = 90
MAX_EXCHANGE_HISTORY = 10  # L2: Tracks 5-10 previous exchanges


# Database configuration - reuse from environment
NEON_ENDPOINT = os.getenv(
    "NEON_ENDPOINT",
    "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
)
DATABASE_URL = os.getenv("DATABASE_URL", "")


def _escape_sql_value(value: Any) -> str:
    """
    Escape a value for SQL insertion.

    Args:
        value: The value to escape for SQL.

    Returns:
        SQL-safe string representation of the value.
    """
    if value is None:
        return "NULL"
    elif isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, (dict, list)):
        json_str = json.dumps(value)
        escaped = json_str.replace("\\", "\\\\").replace("'", "''").replace("\x00", "")
        return f"'{escaped}'"
    else:
        s = str(value)
        escaped = s.replace("\\", "\\\\").replace("'", "''").replace("\x00", "")
        return f"'{escaped}'"


def _execute_sql(sql: str) -> Dict[str, Any]:
    """
    Execute SQL via Neon HTTP API.

    Args:
        sql: The SQL query to execute.

    Returns:
        Query result dictionary with 'rows', 'rowCount', etc.

    Raises:
        urllib.error.HTTPError: If the HTTP request fails.
        Exception: For other execution errors.
    """
    if not DATABASE_URL:
        logger.error("DATABASE_URL not configured")
        raise ValueError("DATABASE_URL environment variable is required")

    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": DATABASE_URL
    }

    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        logger.error("Memory SQL error: %s", error_body)
        raise
    except urllib.error.URLError as e:
        logger.error("Memory network error: %s", str(e))
        raise


def store_memory(
    scope: str,
    content: str,
    memory_type: str = "context",
    scope_id: Optional[str] = None,
    key: Optional[str] = None,
    importance: float = DEFAULT_MEMORY_IMPORTANCE,
    source_worker: Optional[str] = None,
    source_task_id: Optional[str] = None,
    expires_in_days: Optional[int] = MEMORY_EXPIRY_DAYS_DEFAULT
) -> Optional[str]:
    """
    Store a memory in the persistent memory system.

    Args:
        scope: Memory scope ('engine', 'worker', 'task', 'conversation').
        content: The memory content (text).
        memory_type: Type of memory ('context', 'learning', 'preference', 'error', 'exchange').
        scope_id: Optional scope identifier (e.g., worker ID, task ID).
        key: Optional key for upsert operations.
        importance: Importance score from 0.0 to 1.0.
        source_worker: Worker that created this memory.
        source_task_id: Task that created this memory.
        expires_in_days: Days until memory expires (None = never).

    Returns:
        Memory UUID if successful, None on failure.
    """
    if len(content) > MAX_MEMORY_CONTENT_LENGTH:
        content = content[:MAX_MEMORY_CONTENT_LENGTH]
        logger.warning("Memory content truncated to %d characters", MAX_MEMORY_CONTENT_LENGTH)

    now = datetime.now(timezone.utc).isoformat()
    expires_at = None
    if expires_in_days:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat()

    # Build column/value lists
    columns = ["scope", "content", "memory_type", "importance", "created_at", "updated_at", "accessed_at"]
    values = [
        _escape_sql_value(scope),
        _escape_sql_value(content),
        _escape_sql_value(memory_type),
        str(importance),
        _escape_sql_value(now),
        _escape_sql_value(now),
        _escape_sql_value(now)
    ]

    if scope_id:
        columns.append("scope_id")
        values.append(_escape_sql_value(scope_id))
    if key:
        columns.append("key")
        values.append(_escape_sql_value(key))
    if source_worker:
        columns.append("source_worker")
        values.append(_escape_sql_value(source_worker))
    if source_task_id:
        columns.append("source_task_id")
        values.append(_escape_sql_value(source_task_id))
    if expires_at:
        columns.append("expires_at")
        values.append(_escape_sql_value(expires_at))

    sql = f"INSERT INTO memories ({', '.join(columns)}) VALUES ({', '.join(values)}) RETURNING id"

    try:
        result = _execute_sql(sql)
        memory_id = result.get("rows", [{}])[0].get("id")
        logger.info("Stored memory %s in scope '%s'", memory_id, scope)
        return memory_id
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as e:
        logger.error("Failed to store memory: %s", str(e))
        return None


def recall_memories(
    scope: str,
    scope_id: Optional[str] = None,
    memory_type: Optional[str] = None,
    key: Optional[str] = None,
    min_importance: float = 0.0,
    limit: int = MAX_EXCHANGE_HISTORY,
    include_expired: bool = False
) -> List[Dict[str, Any]]:
    """
    Recall memories matching the specified criteria.

    Args:
        scope: Memory scope to search.
        scope_id: Optional scope identifier filter.
        memory_type: Optional memory type filter.
        key: Optional key filter.
        min_importance: Minimum importance threshold.
        limit: Maximum memories to return.
        include_expired: Whether to include expired memories.

    Returns:
        List of memory dictionaries, ordered by importance and recency.
    """
    conditions = [f"scope = {_escape_sql_value(scope)}"]

    if scope_id:
        conditions.append(f"scope_id = {_escape_sql_value(scope_id)}")
    if memory_type:
        conditions.append(f"memory_type = {_escape_sql_value(memory_type)}")
    if key:
        conditions.append(f"key = {_escape_sql_value(key)}")
    if min_importance > 0:
        conditions.append(f"importance >= {min_importance}")
    if not include_expired:
        conditions.append("(expires_at IS NULL OR expires_at > NOW())")

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT id, scope, scope_id, key, content, memory_type, importance, 
               created_at, updated_at, accessed_at, access_count, source_worker
        FROM memories
        WHERE {where_clause}
        ORDER BY importance DESC, updated_at DESC
        LIMIT {limit}
    """

    try:
        result = _execute_sql(sql)
        memories = result.get("rows", [])

        # Update access timestamps for retrieved memories
        if memories:
            memory_ids = [m["id"] for m in memories]
            _update_access_timestamps(memory_ids)

        logger.debug("Recalled %d memories from scope '%s'", len(memories), scope)
        return memories
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as e:
        logger.error("Failed to recall memories: %s", str(e))
        return []


def _update_access_timestamps(memory_ids: List[str]) -> None:
    """
    Update access timestamps and counts for retrieved memories.

    Args:
        memory_ids: List of memory UUIDs to update.
    """
    if not memory_ids:
        return

    ids_str = ", ".join([_escape_sql_value(mid) for mid in memory_ids])
    now = datetime.now(timezone.utc).isoformat()
    sql = f"""
        UPDATE memories 
        SET accessed_at = {_escape_sql_value(now)}, 
            access_count = COALESCE(access_count, 0) + 1
        WHERE id IN ({ids_str})
    """

    try:
        _execute_sql(sql)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as e:
        logger.warning("Failed to update memory access timestamps: %s", str(e))


def store_exchange(
    worker_id: str,
    task_id: Optional[str],
    input_summary: str,
    output_summary: str,
    importance: float = DEFAULT_MEMORY_IMPORTANCE
) -> Optional[str]:
    """
    Store a task execution exchange as a memory.

    This supports L2 Multi-Turn Memory by tracking previous exchanges.

    Args:
        worker_id: The worker that executed the exchange.
        task_id: Optional task ID associated with the exchange.
        input_summary: Summary of the input/request.
        output_summary: Summary of the output/result.
        importance: Importance score from 0.0 to 1.0.

    Returns:
        Memory UUID if successful, None on failure.
    """
    content = json.dumps({
        "input": input_summary[:500],  # Limit summary lengths
        "output": output_summary[:500],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return store_memory(
        scope="worker",
        scope_id=worker_id,
        content=content,
        memory_type="exchange",
        source_worker=worker_id,
        source_task_id=task_id,
        importance=importance,
        expires_in_days=MEMORY_EXPIRY_DAYS_DEFAULT
    )


def get_recent_exchanges(
    worker_id: str,
    limit: int = MAX_EXCHANGE_HISTORY
) -> List[Dict[str, Any]]:
    """
    Get recent exchanges for a worker (L2 Multi-Turn Memory).

    Args:
        worker_id: The worker ID to get exchanges for.
        limit: Maximum exchanges to return (default: 10).

    Returns:
        List of exchange dictionaries with parsed content.
    """
    memories = recall_memories(
        scope="worker",
        scope_id=worker_id,
        memory_type="exchange",
        limit=limit
    )

    exchanges = []
    for memory in memories:
        try:
            content = json.loads(memory.get("content", "{}"))
            exchanges.append({
                "id": memory.get("id"),
                "input": content.get("input", ""),
                "output": content.get("output", ""),
                "timestamp": content.get("timestamp"),
                "importance": memory.get("importance"),
                "source_task_id": memory.get("source_task_id")
            })
        except json.JSONDecodeError:
            logger.warning("Failed to parse exchange memory: %s", memory.get("id"))
            continue

    return exchanges


def store_task_context(
    task_id: str,
    context: Dict[str, Any],
    worker_id: Optional[str] = None
) -> Optional[str]:
    """
    Store context for a specific task.

    Args:
        task_id: The task ID to store context for.
        context: Dictionary of context data.
        worker_id: Optional worker ID.

    Returns:
        Memory UUID if successful, None on failure.
    """
    return store_memory(
        scope="task",
        scope_id=task_id,
        content=json.dumps(context),
        memory_type="context",
        key="task_context",
        source_worker=worker_id,
        source_task_id=task_id,
        importance=0.7,
        expires_in_days=30  # Task context expires sooner
    )


def get_task_context(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve stored context for a task.

    Args:
        task_id: The task ID to get context for.

    Returns:
        Context dictionary if found, None otherwise.
    """
    memories = recall_memories(
        scope="task",
        scope_id=task_id,
        key="task_context",
        limit=1
    )

    if memories:
        try:
            return json.loads(memories[0].get("content", "{}"))
        except json.JSONDecodeError:
            logger.warning("Failed to parse task context for task: %s", task_id)

    return None


def cleanup_expired_memories() -> int:
    """
    Delete expired memories from the database.

    Returns:
        Number of memories deleted.
    """
    sql = "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at < NOW()"

    try:
        result = _execute_sql(sql)
        deleted = result.get("rowCount", 0) or 0
        if deleted > 0:
            logger.info("Cleaned up %d expired memories", deleted)
        return deleted
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as e:
        logger.error("Failed to cleanup expired memories: %s", str(e))
        return 0


def get_memory_stats() -> Dict[str, Any]:
    """
    Get statistics about the memory system.

    Returns:
        Dictionary with memory statistics.
    """
    sql = """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN scope = 'engine' THEN 1 END) as engine_count,
            COUNT(CASE WHEN scope = 'worker' THEN 1 END) as worker_count,
            COUNT(CASE WHEN scope = 'task' THEN 1 END) as task_count,
            COUNT(CASE WHEN memory_type = 'exchange' THEN 1 END) as exchange_count,
            COUNT(CASE WHEN expires_at IS NOT NULL AND expires_at < NOW() THEN 1 END) as expired_count
        FROM memories
    """

    try:
        result = _execute_sql(sql)
        if result.get("rows"):
            row = result["rows"][0]
            return {
                "total_memories": int(row.get("total", 0)),
                "engine_memories": int(row.get("engine_count", 0)),
                "worker_memories": int(row.get("worker_count", 0)),
                "task_memories": int(row.get("task_count", 0)),
                "exchange_memories": int(row.get("exchange_count", 0)),
                "expired_pending_cleanup": int(row.get("expired_count", 0))
            }
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as e:
        logger.error("Failed to get memory stats: %s", str(e))

    return {}
