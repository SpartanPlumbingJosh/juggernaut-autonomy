import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional
from core.database import query_db

class AuthService:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        
    async def register_user(self, email: str, password: str) -> Dict:
        """Register a new user"""
        # Check if user exists
        existing = await query_db(f"""
            SELECT id FROM users WHERE email = '{email}'
        """)
        if existing.get("rows"):
            return {"success": False, "error": "User already exists"}
            
        # Hash password
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Create user
        await query_db(f"""
            INSERT INTO users (email, password_hash, created_at)
            VALUES (
                '{email}',
                '{hashed.decode('utf-8')}',
                NOW()
            )
        """)
        return {"success": True}
        
    async def authenticate_user(self, email: str, password: str) -> Optional[Dict]:
        """Authenticate user"""
        result = await query_db(f"""
            SELECT id, password_hash FROM users WHERE email = '{email}'
        """)
        user = result.get("rows", [{}])[0]
        
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return None
            
        return {"id": user["id"], "email": email}
        
    def create_access_token(self, data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.PyJWTError:
            return None
