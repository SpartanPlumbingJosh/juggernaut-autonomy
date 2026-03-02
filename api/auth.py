"""
User authentication and authorization.
Supports API keys, JWT, and OAuth.
"""

import os
import uuid
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key')
JWT_ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_HOURS = 24

class AuthHandler:
    """Handle user authentication and token management."""

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against stored hash."""
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Generate password hash."""
        return bcrypt.hashpw(
            password.encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')

    @staticmethod
    def create_access_token(
        data: Dict[str, Any], 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        expires = datetime.now(timezone.utc) + (
            expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        )
        to_encode.update({"exp": expires})
        return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """Decode JWT token."""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.PyJWTError:
            return None

    @staticmethod
    def create_api_key(user_id: str, execute_sql: callable) -> str:
        """Generate and store API key for user."""
        api_key = str(uuid.uuid4())
        execute_sql(
            f"""
            INSERT INTO user_api_keys (
                id, user_id, api_key, created_at, updated_at, is_active
            ) VALUES (
                gen_random_uuid(),
                '{user_id}',
                '{api_key}',
                NOW(),
                NOW(),
                TRUE
            )
            """
        )
        return api_key

    @staticmethod
    def verify_api_key(api_key: str, execute_sql: callable) -> Optional[str]:
        """Verify API key and return user ID if valid."""
        result = execute_sql(
            f"""
            SELECT user_id FROM user_api_keys 
            WHERE api_key = '{api_key}' AND is_active = TRUE
            LIMIT 1
            """
        )
        if result.get('rows'):
            return result['rows'][0]['user_id']
        return None


__all__ = ['AuthHandler']
