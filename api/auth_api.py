import hashlib
import os
from datetime import datetime, timedelta
import jwt
from typing import Dict, Any
from core.database import query_db

SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key")  # Use strong secret in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

async def register_user(email: str, password: str) -> Dict[str, Any]:
    """Register new user"""
    try:
        # Check if user exists
        res = await query_db(
            f"SELECT id FROM users WHERE email = '{email}'"
        )
        if res.get("rows"):
            return {"success": False, "error": "User already exists"}
            
        # Hash password
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        
        # Create user
        await query_db(
            f"""
            INSERT INTO users (email, password_hash, salt, created_at)
            VALUES ('{email}', '{key.hex()}', '{salt.hex()}', NOW())
            """
        )
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def authenticate_user(email: str, password: str) -> Dict[str, Any]:
    """Authenticate user"""
    try:
        res = await query_db(
            f"SELECT id, password_hash, salt FROM users WHERE email = '{email}'"
        )
        if not res.get("rows"):
            return {"success": False, "error": "Invalid credentials"}
            
        user = res["rows"][0]
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            bytes.fromhex(user["salt"]),
            100000
        )
        
        if key.hex() != user["password_hash"]:
            return {"success": False, "error": "Invalid credentials"}
            
        # Create JWT token
        access_token = create_access_token({"sub": user["id"]})
        return {"success": True, "access_token": access_token}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_access_token(data: Dict[str, Any]) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Dict[str, Any]:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"success": True, "user_id": payload.get("sub")}
    except Exception as e:
        return {"success": False, "error": str(e)}
