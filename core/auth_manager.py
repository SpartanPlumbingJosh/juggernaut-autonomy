import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional
import jwt

class AuthManager:
    def __init__(self, secret_key: str, token_expiry_minutes: int = 60):
        self.secret_key = secret_key
        self.token_expiry_minutes = token_expiry_minutes
        
    def hash_password(self, password: str) -> str:
        """Hash a password for storage"""
        salt = secrets.token_hex(16)
        return f"{salt}${hashlib.sha256((salt + password).encode()).hexdigest()}"
    
    def verify_password(self, stored_hash: str, password: str) -> bool:
        """Verify a password against stored hash"""
        salt, hash_value = stored_hash.split('$')
        return hash_value == hashlib.sha256((salt + password).encode()).hexdigest()
    
    def generate_token(self, user_id: str) -> str:
        """Generate JWT token for user"""
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(minutes=self.token_expiry_minutes)
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token"""
        try:
            return jwt.decode(token, self.secret_key, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
