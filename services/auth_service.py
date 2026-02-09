import hashlib
import os
import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional

class AuthService:
    def __init__(self, secret_key: str, token_expiry_minutes: int = 60):
        self.secret_key = secret_key
        self.token_expiry_minutes = token_expiry_minutes
        
    def hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return salt.hex() + key.hex()
        
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        salt = bytes.fromhex(hashed_password[:64])
        key = hashed_password[64:]
        new_key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return new_key.hex() == key
        
    def create_access_token(self, user_id: str, roles: list) -> str:
        """Create JWT access token"""
        payload = {
            'sub': user_id,
            'roles': roles,
            'exp': datetime.utcnow() + timedelta(minutes=self.token_expiry_minutes)
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
        
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload
        except jwt.PyJWTError:
            return None
