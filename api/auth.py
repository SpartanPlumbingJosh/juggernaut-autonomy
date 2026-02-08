"""
Authentication and User Management - Handle user signup, login, and onboarding.
"""

import os
import hashlib
import jwt
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

# JWT Configuration
SECRET_KEY = os.getenv('JWT_SECRET', 'your-secret-key')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class User(BaseModel):
    email: str
    password_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

async def create_user(email: str, password: str) -> Dict[str, Any]:
    """Create a new user."""
    # Hash password
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Insert user into database
    await query_db(f"""
        INSERT INTO users (
            email,
            password_hash,
            is_active,
            created_at,
            updated_at
        ) VALUES (
            '{email}',
            '{password_hash}',
            TRUE,
            NOW(),
            NOW()
        )
    """)
    
    return {'email': email, 'status': 'created'}

async def authenticate_user(email: str, password: str) -> Optional[User]:
    """Authenticate user."""
    # Get user from database
    result = await query_db(f"""
        SELECT * FROM users WHERE email = '{email}' LIMIT 1
    """)
    user_data = result.get('rows', [{}])[0]
    
    if not user_data:
        return None
        
    # Verify password
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if password_hash != user_data['password_hash']:
        return None
        
    return User(**user_data)

async def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str) -> Optional[User]:
    """Get current user from JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
    except jwt.PyJWTError:
        return None
        
    return await authenticate_user(email, "")

__all__ = ['create_user', 'authenticate_user', 'create_access_token', 'get_current_user', 'oauth2_scheme']
