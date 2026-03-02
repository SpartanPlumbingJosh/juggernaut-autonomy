"""
Authentication API - Handle user authentication and authorization.

Endpoints:
- POST /auth/register - Register new user
- POST /auth/login - User login
- POST /auth/logout - User logout
- POST /auth/refresh - Refresh access token
"""

import os
import json
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from core.database import query_db

# Authentication settings
JWT_SECRET = os.getenv('JWT_SECRET')
JWT_ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

def _make_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(body)
    }

def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create error response."""
    return _make_response(status_code, {"error": message})

def create_tokens(user_id: str) -> Dict[str, str]:
    """Create access and refresh tokens."""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    access_token = jwt.encode({
        "sub": user_id,
        "exp": datetime.utcnow() + access_token_expires
    }, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    refresh_token = jwt.encode({
        "sub": user_id,
        "exp": datetime.utcnow() + refresh_token_expires
    }, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

async def register_user(email: str, password: str) -> Dict[str, Any]:
    """Register a new user."""
    try:
        # Check if user exists
        existing = await query_db(f"""
            SELECT id FROM users WHERE email = '{email}'
        """)
        if existing.get("rows"):
            return _error_response(400, "User already exists")
            
        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Create user
        await query_db(f"""
            INSERT INTO users (
                id, email, password_hash, created_at, updated_at
            ) VALUES (
                gen_random_uuid(),
                '{email}',
                '{hashed_password}',
                NOW(),
                NOW()
            )
        """)
        
        return _make_response(200, {"success": True})
    except Exception as e:
        return _error_response(500, f"Registration failed: {str(e)}")

async def login_user(email: str, password: str) -> Dict[str, Any]:
    """Authenticate user and return tokens."""
    try:
        # Get user
        user = await query_db(f"""
            SELECT id, password_hash FROM users WHERE email = '{email}'
        """)
        if not user.get("rows"):
            return _error_response(401, "Invalid credentials")
            
        user_data = user["rows"][0]
        stored_hash = user_data["password_hash"]
        
        # Verify password
        if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            return _error_response(401, "Invalid credentials")
            
        # Create tokens
        tokens = create_tokens(user_data["id"])
        return _make_response(200, tokens)
    except Exception as e:
        return _error_response(500, f"Login failed: {str(e)}")

def route_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route authentication API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # POST /auth/register
    if len(parts) == 2 and parts[0] == "auth" and parts[1] == "register" and method == "POST":
        try:
            data = json.loads(body or "{}")
            return register_user(
                email=data.get("email"),
                password=data.get("password")
            )
        except Exception as e:
            return _error_response(400, f"Invalid request: {str(e)}")
    
    # POST /auth/login
    if len(parts) == 2 and parts[0] == "auth" and parts[1] == "login" and method == "POST":
        try:
            data = json.loads(body or "{}")
            return login_user(
                email=data.get("email"),
                password=data.get("password")
            )
        except Exception as e:
            return _error_response(400, f"Invalid request: {str(e)}")
    
    return _error_response(404, "Not found")

__all__ = ["route_request"]
