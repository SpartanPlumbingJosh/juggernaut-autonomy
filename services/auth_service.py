import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional
from core.database import query_db

class AuthService:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    async def create_user(self, email: str, password: str) -> Dict:
        """Create a new user account"""
        try:
            # Check if user exists
            existing = await query_db(f"SELECT id FROM users WHERE email = '{email}'")
            if existing.get("rows"):
                return {"success": False, "error": "User already exists"}

            # Hash password
            salt = secrets.token_hex(16)
            hashed_password = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                100000
            ).hex()

            # Create user
            sql = f"""
            INSERT INTO users (
                id, email, password_hash, salt, created_at, updated_at
            ) VALUES (
                gen_random_uuid(),
                '{email}',
                '{hashed_password}',
                '{salt}',
                NOW(),
                NOW()
            )
            """
            await query_db(sql)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def authenticate_user(self, email: str, password: str) -> Dict:
        """Authenticate a user"""
        try:
            user = await query_db(f"SELECT * FROM users WHERE email = '{email}' LIMIT 1")
            if not user.get("rows"):
                return {"success": False, "error": "User not found"}

            user_data = user.get("rows")[0]
            hashed_password = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                user_data["salt"].encode('utf-8'),
                100000
            ).hex()

            if hashed_password != user_data["password_hash"]:
                return {"success": False, "error": "Invalid credentials"}

            return {"success": True, "user_id": user_data["id"]}
        except Exception as e:
            return {"success": False, "error": str(e)}
