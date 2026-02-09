import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
import jwt

class AuthManager:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        
    def hash_password(self, password: str) -> str:
        """Hash a password for storage"""
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return salt.hex() + key.hex()
        
    def verify_password(self, stored_hash: str, password: str) -> bool:
        """Verify a password against stored hash"""
        salt = bytes.fromhex(stored_hash[:64])
        stored_key = stored_hash[64:]
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        ).hex()
        return key == stored_key
        
    def create_access_token(self, user_id: str, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
        payload = {
            "sub": user_id,
            "exp": expire
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")
        
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify a JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.PyJWTError:
            return None
