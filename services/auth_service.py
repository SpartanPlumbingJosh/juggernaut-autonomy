from typing import Dict, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext
from core.database import query_db
from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    async def authenticate_user(email: str, password: str) -> Optional[Dict]:
        try:
            result = await query_db(
                f"""
                SELECT * FROM users
                WHERE email = '{email}'
                LIMIT 1
                """
            )
            user = result.get("rows", [{}])[0]
            if not user or not AuthService.verify_password(password, user.get("password_hash")):
                return None
            return user
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Dict:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
