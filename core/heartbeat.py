"""
Redis-based heartbeat system for JUGGERNAUT workers.

Implements a robust heartbeat mechanism using Redis SETEX pattern with:
- 30s heartbeat interval
- 90s timeout (consider worker stale)
- 120s grace period (consider worker dead)

Also supports leader election for redundant WATCHDOG instances.
"""

import os
import time
import asyncio
import logging
import redis
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Configuration constants
HEARTBEAT_INTERVAL = 30  # seconds
HEARTBEAT_TIMEOUT = 90   # seconds - consider stale after this
GRACE_PERIOD = 120       # seconds - consider dead after this

# Redis connection (lazy-loaded)
_redis_client = None

def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        redis_url = os.environ.get('REDIS_URL')
        if not redis_url:
            # Fallback to DATABASE_URL if REDIS_URL not set
            # This is temporary until Redis is properly configured
            logger.warning("REDIS_URL not set, using database for heartbeats")
            _redis_client = None
            return None
            
        _redis_client = redis.Redis.from_url(
            redis_url,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True
        )
    return _redis_client

def heartbeat_key(worker_id: str) -> str:
    """Generate Redis key for worker heartbeat."""
    return f"juggernaut:heartbeat:{worker_id}"

def send_heartbeat(worker_id: str) -> bool:
    """
    Send heartbeat using Redis SETEX pattern.
    
    Args:
        worker_id: ID of the worker sending heartbeat
        
    Returns:
        bool: True if heartbeat was sent successfully
    """
    redis_client = get_redis_client()
    if redis_client is None:
        # Fallback to database
        from core.database import execute_query
        try:
            execute_query(
                """
                UPDATE worker_registry
                SET last_heartbeat = NOW(), consecutive_failures = 0
                WHERE worker_id = $1
                """,
                [worker_id]
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to send heartbeat to database: {e}")
            return False
    
    try:
        # Set key with expiration = timeout + grace period
        redis_client.setex(
            heartbeat_key(worker_id),
            HEARTBEAT_TIMEOUT + GRACE_PERIOD,
            datetime.now().isoformat()
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to send Redis heartbeat: {e}")
        return False

def check_worker_heartbeat(worker_id: str) -> Tuple[bool, Optional[float]]:
    """
    Check if a worker's heartbeat is fresh.
    
    Args:
        worker_id: ID of the worker to check
        
    Returns:
        Tuple[bool, Optional[float]]: (is_alive, seconds_since_heartbeat)
    """
    redis_client = get_redis_client()
    if redis_client is None:
        # Fallback to database
        from core.database import execute_query
        try:
            result = execute_query(
                """
                SELECT 
                    last_heartbeat,
                    EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as seconds_since
                FROM worker_registry
                WHERE worker_id = $1
                """,
                [worker_id]
            )
            if result and result.get("rows") and len(result["rows"]) > 0:
                seconds_since = float(result["rows"][0].get("seconds_since", GRACE_PERIOD + 1))
                return seconds_since <= GRACE_PERIOD, seconds_since
            return False, None
        except Exception as e:
            logger.warning(f"Failed to check heartbeat in database: {e}")
            return False, None
    
    try:
        # Check if key exists
        heartbeat = redis_client.get(heartbeat_key(worker_id))
        if not heartbeat:
            return False, None
            
        # Parse timestamp and calculate age
        timestamp = datetime.fromisoformat(heartbeat.decode('utf-8'))
        seconds_since = (datetime.now() - timestamp).total_seconds()
        
        return seconds_since <= GRACE_PERIOD, seconds_since
    except Exception as e:
        logger.warning(f"Failed to check Redis heartbeat: {e}")
        return False, None

def get_stale_workers() -> List[Dict[str, any]]:
    """
    Get list of workers with stale heartbeats.
    
    Returns:
        List[Dict]: List of worker info dictionaries with stale heartbeats
    """
    redis_client = get_redis_client()
    if redis_client is None:
        # Fallback to database
        from core.database import execute_query
        try:
            result = execute_query(
                f"""
                SELECT 
                    worker_id, status, last_heartbeat,
                    EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as seconds_since
                FROM worker_registry
                WHERE EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) > {HEARTBEAT_TIMEOUT}
                AND status = 'active'
                """,
                []
            )
            if result and result.get("rows"):
                return result["rows"]
            return []
        except Exception as e:
            logger.warning(f"Failed to get stale workers from database: {e}")
            return []
    
    # With Redis, we'd need to scan all keys and check their values
    # This is a simplified implementation
    try:
        stale_workers = []
        for key in redis_client.scan_iter(match="juggernaut:heartbeat:*"):
            worker_id = key.decode('utf-8').split(':')[-1]
            is_alive, seconds_since = check_worker_heartbeat(worker_id)
            if seconds_since and seconds_since > HEARTBEAT_TIMEOUT:
                stale_workers.append({
                    "worker_id": worker_id,
                    "seconds_since": seconds_since
                })
        return stale_workers
    except Exception as e:
        logger.warning(f"Failed to get stale workers from Redis: {e}")
        return []

async def heartbeat_loop(worker_id: str):
    """
    Asynchronous heartbeat loop that runs continuously.
    
    Args:
        worker_id: ID of the worker sending heartbeats
    """
    while True:
        try:
            send_heartbeat(worker_id)
        except Exception as e:
            logger.error(f"Heartbeat failed for {worker_id}: {e}")
            # Don't crash - keep trying
        await asyncio.sleep(HEARTBEAT_INTERVAL)

# Leader election for redundant WATCHDOG instances
def claim_watchdog_leadership() -> bool:
    """
    Try to claim leadership for this WATCHDOG instance.
    
    Returns:
        bool: True if leadership was claimed
    """
    redis_client = get_redis_client()
    if redis_client is None:
        # Fallback to database - always claim leadership
        # This is a simplification until Redis is available
        return True
    
    watchdog_id = os.environ.get('WORKER_ID', 'WATCHDOG')
    leader_key = "juggernaut:watchdog:leader"
    
    try:
        # Try to set leader key if it doesn't exist
        return redis_client.set(leader_key, watchdog_id, nx=True, ex=HEARTBEAT_INTERVAL * 2)
    except Exception as e:
        logger.warning(f"Failed to claim leadership: {e}")
        return False

def renew_leadership() -> bool:
    """
    Renew leadership claim for this WATCHDOG instance.
    
    Returns:
        bool: True if leadership was renewed
    """
    redis_client = get_redis_client()
    if redis_client is None:
        # Fallback to database - always claim leadership
        return True
    
    watchdog_id = os.environ.get('WORKER_ID', 'WATCHDOG')
    leader_key = "juggernaut:watchdog:leader"
    
    try:
        # Check if we're the leader
        current_leader = redis_client.get(leader_key)
        if current_leader and current_leader.decode('utf-8') == watchdog_id:
            # Renew our leadership
            redis_client.expire(leader_key, HEARTBEAT_INTERVAL * 2)
            return True
        return False
    except Exception as e:
        logger.warning(f"Failed to renew leadership: {e}")
        return False

def is_leader() -> bool:
    """
    Check if this WATCHDOG instance is the leader.
    
    Returns:
        bool: True if this instance is the leader
    """
    redis_client = get_redis_client()
    if redis_client is None:
        # Fallback to database - always claim leadership
        return True
    
    watchdog_id = os.environ.get('WORKER_ID', 'WATCHDOG')
    leader_key = "juggernaut:watchdog:leader"
    
    try:
        # Check if we're the leader
        current_leader = redis_client.get(leader_key)
        return current_leader and current_leader.decode('utf-8') == watchdog_id
    except Exception as e:
        logger.warning(f"Failed to check leadership: {e}")
        return False
