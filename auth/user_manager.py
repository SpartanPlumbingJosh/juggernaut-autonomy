import hashlib
import os
from typing import Dict, Optional
from core.database import query_db

class UserManager:
    def __init__(self):
        self.salt = os.getenv("AUTH_SALT", "default_salt")

    def _hash_password(self, password: str) -> str:
        """Hash password with salt"""
        return hashlib.sha256((password + self.salt).encode()).hexdigest()

    async def create_user(self, email: str, password: str) -> Dict:
        """Create new user account"""
        try:
            hashed = self._hash_password(password)
            await query_db(f"""
                INSERT INTO users (
                    id, email, password_hash, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), '{email}', '{hashed}', NOW(), NOW()
                )
            """)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def authenticate_user(self, email: str, password: str) -> Dict:
        """Authenticate user credentials"""
        try:
            hashed = self._hash_password(password)
            res = await query_db(f"""
                SELECT id FROM users 
                WHERE email = '{email}' 
                AND password_hash = '{hashed}'
                LIMIT 1
            """)
            if res.get("rows"):
                return {"success": True, "user_id": res["rows"][0]["id"]}
            return {"success": False, "error": "Invalid credentials"}
        except Exception as e:
            return {"success": False, "error": str(e)}
