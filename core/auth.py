from functools import wraps
from typing import Callable, Any, Dict
import jwt
from datetime import datetime, timedelta

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return {}

def auth_required(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(*args, **kwargs):
        token = kwargs.get("token", "")
        if not token:
            return {"error": "Authorization required"}
        
        user = verify_token(token)
        if not user:
            return {"error": "Invalid token"}
            
        return await func(*args, **kwargs)
    return wrapper
