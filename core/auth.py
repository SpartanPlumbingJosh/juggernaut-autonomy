from datetime import datetime, timedelta
import jwt
from typing import Dict, Any

SECRET_KEY = "your-secret-key-here"  # Should be from environment in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

async def authenticate_user(token: str) -> Dict[str, Any]:
    """Authenticate user using JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"authenticated": True, "user_id": payload.get("sub")}
    except jwt.ExpiredSignatureError:
        return {"authenticated": False, "error": "Token expired"}
    except jwt.InvalidTokenError:
        return {"authenticated": False, "error": "Invalid token"}

async def create_access_token(user_id: str) -> Dict[str, Any]:
    """Create JWT access token for authenticated user."""
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": user_id, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": encoded_jwt, "token_type": "bearer"}
