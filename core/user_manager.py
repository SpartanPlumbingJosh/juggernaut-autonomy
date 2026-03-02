"""
User authentication and management system for revenue platform.
Handles user registration, authentication, and permissions.
"""
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional, Union

import jwt
from fastapi.security import OAuth2PasswordBearer


class UserManager:
    SECRET_KEY = os.getenv("AUTH_SECRET", secrets.token_hex(32))
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours
    
    @staticmethod
    def create_hash(password: str) -> str:
        """Create secure password hash."""
        salt = secrets.token_hex(16)
        return f"{salt}${hashlib.sha512((salt + password).encode()).hexdigest()}"
    
    @staticmethod
    def verify_hash(password: str, hashed: str) -> bool:
        """Verify password against stored hash."""
        try:
            salt, stored_hash = hashed.split('$')
            generated_hash = hashlib.sha512((salt + password).encode()).hexdigest()
            return secrets.compare_digest(generated_hash, stored_hash)
        except:
            return False
    
    @staticmethod
    def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        """Generate JWT access token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=UserManager.ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, UserManager.SECRET_KEY, algorithm=UserManager.ALGORITHM)
    
    @staticmethod
    def verify_token(token: str) -> Union[Dict, None]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, UserManager.SECRET_KEY, algorithms=[UserManager.ALGORITHM])
            return payload
        except jwt.PyJWTError:
            return None


def initialize_users(execute_sql: Callable) -> bool:
    """Set up initial users table if not exists."""
    try:
        execute_sql("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            is_admin BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS users_email_idx ON users(email);
        """)
        return True
    except Exception:
        return False
