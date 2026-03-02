import hashlib
import os
import jwt
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

class AuthManager:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.logger = logging.getLogger(__name__)
        
    def hash_password(self, password: str) -> str:
        """Hash password using PBKDF2"""
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return f"{salt.hex()}:{key.hex()}"
        
    def verify_password(self, stored_hash: str, password: str) -> bool:
        """Verify password against stored hash"""
        try:
            salt, key = stored_hash.split(':')
            salt = bytes.fromhex(salt)
            key = bytes.fromhex(key)
            new_key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                100000
            )
            return new_key == key
        except Exception as e:
            self.logger.error(f"Password verification failed: {str(e)}")
            return False
            
    def create_access_token(self, user_id: str, expires_minutes: int = 30) -> str:
        """Create JWT access token"""
        payload = {
            "sub": user_id,
            "exp": datetime.utcnow() + timedelta(minutes=exputes_minutes)
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")
        
    def verify_access_token(self, token: str) -> Optional[Dict]:
        """Verify JWT access token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError:
            self.logger.warning("Invalid token")
            return None
