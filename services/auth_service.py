import os
import hashlib
from typing import Dict, Optional
from datetime import datetime, timedelta
import jwt
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status

class AuthService:
    def __init__(self):
        self.secret_key = os.getenv("AUTH_SECRET_KEY")
        self.algorithm = "HS256"
        self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

    def create_access_token(self, data: Dict, expires_delta: Optional[timedelta] = None):
        """Create JWT token for authentication."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str):
        """Verify JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )

    async def get_current_user(self, token: str = Depends(self.oauth2_scheme)):
        """Get current authenticated user."""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
        try:
            payload = self.verify_token(token)
            return payload
        except jwt.PyJWTError:
            raise credentials_exception

    def hash_password(self, password: str) -> str:
        """Hash user password for storage."""
        salt = os.getenv("PASSWORD_SALT")
        return hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
