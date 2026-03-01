import os
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class AuthService:
    def __init__(self):
        self.secret = os.getenv('AUTH_SECRET')
        self.token_expiry = int(os.getenv('TOKEN_EXPIRY_HOURS', '24'))
        
    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode(), salt)
        return hashed.decode()
    
    def verify_password(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    
    def create_token(self, user_id: str, email: str, roles: list) -> str:
        payload = {
            'sub': user_id,
            'email': email,
            'roles': roles,
            'exp': datetime.utcnow() + timedelta(hours=self.token_expiry)
        }
        return jwt.encode(payload, self.secret, algorithm='HS256')
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, self.secret, algorithms=['HS256'])
            return payload
        except jwt.PyJWTError:
            return None
