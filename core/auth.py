import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

# Security constants
SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "default_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT access token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def hash_password(password: str) -> str:
    """Hash password using HMAC-SHA256"""
    return hmac.new(
        SECRET_KEY.encode(),
        password.encode(),
        hashlib.sha256
    ).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return hmac.compare_digest(
        hash_password(plain_password),
        hashed_password
    )
