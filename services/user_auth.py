import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class UserAuthService:
    def __init__(self):
        self.secret_key = os.getenv("AUTH_SECRET_KEY")
        self.token_expiry = timedelta(hours=1)

    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def verify_password(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())

    def generate_token(self, user_id: str, role: str = "user") -> str:
        payload = {
            "user_id": user_id,
            "role": role,
            "exp": datetime.utcnow() + self.token_expiry
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def verify_token(self, token: str) -> Optional[Dict]:
        try:
            return jwt.decode(token, self.secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return None
