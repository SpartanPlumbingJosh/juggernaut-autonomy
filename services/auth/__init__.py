"""
Authentication Service - Handles user authentication and authorization.
"""
from typing import Optional, Dict, Any
import bcrypt
import jwt
from datetime import datetime, timedelta

class AuthService:
    def __init__(self, config: Dict[str, Any]):
        self.secret_key = config.get("jwt_secret")
        self.token_expiry = config.get("token_expiry_minutes", 60)
        
    def hash_password(self, password: str) -> str:
        """Hash a password for storage."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

    def generate_token(self, user_id: str, roles: Optional[list] = None) -> str:
        """Generate a JWT token."""
        payload = {
            "sub": user_id,
            "roles": roles or [],
            "exp": datetime.utcnow() + timedelta(minutes=self.token_expiry)
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token."""
        try:
            return jwt.decode(token, self.secret_key, algorithms=["HS256"])
        except jwt.PyJWTError:
            return None
