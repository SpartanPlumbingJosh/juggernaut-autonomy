import os
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict

class AuthHandler:
    def __init__(self):
        self.secret_key = os.getenv('JWT_SECRET_KEY')
        self.algorithm = 'HS256'

    def create_access_token(self, user_id: str, email: str) -> str:
        """Create JWT access token."""
        payload = {
            'sub': user_id,
            'email': email,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.PyJWTError:
            return None

    def get_current_user(self, token: str) -> Optional[Dict]:
        """Get current user from token."""
        payload = self.verify_token(token)
        if payload:
            return {'user_id': payload['sub'], 'email': payload['email']}
        return None
