from datetime import datetime, timedelta
from typing import Dict, Optional
import uuid

class UserService:
    """Handles user accounts, subscriptions and billing"""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    async def create_user(self, email: str, plan: str = "free") -> Dict[str, Any]:
        """Create new user account"""
        user_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        
        await self.execute_sql(f"""
            INSERT INTO users (id, email, plan, created_at, updated_at)
            VALUES ('{user_id}', '{email}', '{plan}', '{created_at}', '{created_at}')
        """)
        
        return {
            "user_id": user_id,
            "email": email,
            "plan": plan,
            "created_at": created_at
        }
        
    async def upgrade_plan(self, user_id: str, plan: str) -> Dict[str, Any]:
        """Upgrade user's subscription plan"""
        updated_at = datetime.utcnow()
        
        await self.execute_sql(f"""
            UPDATE users
            SET plan = '{plan}', updated_at = '{updated_at}'
            WHERE id = '{user_id}'
        """)
        
        return {
            "user_id": user_id,
            "plan": plan,
            "updated_at": updated_at
        }
        
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user details"""
        res = await self.execute_sql(f"""
            SELECT id, email, plan, created_at, updated_at
            FROM users
            WHERE id = '{user_id}'
        """)
        
        return res.get("rows", [{}])[0] if res.get("rows") else None
