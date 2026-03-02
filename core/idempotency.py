import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import hashlib

logger = logging.getLogger(__name__)


class IdempotencyKey:
    """Context manager for idempotent operations."""
    
    def __init__(self, key: Optional[str], action: str, ttl: int = 86400):
        self.key = self._generate_key(key, action) if key else None
        self.exists = False
        self.result = None
        self.ttl = ttl
        
    def _generate_key(self, key: str, action: str) -> str:
        """Generate consistent idempotency key."""
        return hashlib.sha256(f"{action}:{key}".encode()).hexdigest()
        
    async def __aenter__(self):
        if not self.key:
            return self
            
        # Check for existing operation
        existing = await query_db(
            """
            SELECT result FROM idempotency_keys
            WHERE key = %s AND expires_at > NOW()
            """,
            (self.key,)
        )
        
        if existing and existing.get('rows'):
            self.exists = True
            self.result = json.loads(existing['rows'][0]['result'])
        
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None or not self.key:
            return
            
        # Store result for future idempotency checks
        await execute_db(
            """
            INSERT INTO idempotency_keys
            (key, action, result, expires_at)
            VALUES (%s, %s, %s, NOW() + INTERVAL '%s seconds')
            ON CONFLICT (key) DO NOTHING
            """,
            (self.key, self.action, json.dumps(self.result), self.ttl)
        )
        
    def store_result(self, result: Dict[str, Any]):
        """Store successful operation result."""
        self.result = result
