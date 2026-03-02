from functools import wraps
from typing import Callable, Any
from fastapi import Request, HTTPException
import jwt

SECRET_KEY = "your-secret-key"  # Replace with a secure secret key
ALGORITHM = "HS256"

def authenticate_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return True
    except:
        return False

def auth_required(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs) -> Any:
        token = request.headers.get("Authorization")
        if not token or not authenticate_token(token):
            raise HTTPException(status_code=401, detail="Unauthorized")
        return await func(request, *args, **kwargs)
    return wrapper
