import os
import hashlib
from typing import Dict, Optional
from datetime import datetime, timedelta
import jwt
from fastapi.security import OAuth2PasswordBearer

class UserManager:
    def __init__(self):
        self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
        self.jwt_secret = os.getenv('JWT_SECRET')
        self.jwt_algorithm = "HS256"
        self.jwt_expire_minutes = int(os.getenv('JWT_EXPIRE_MINUTES', 1440))

    def hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        salt = os.getenv('PASSWORD_SALT', '')
        return hashlib.sha256((password + salt).encode()).hexdigest()

    async def create_user(self, email: str, password: str, user_data: Dict) -> Dict:
        """Create new user account"""
        try:
            # Check if user exists
            existing = await query_db(f"""
                SELECT id FROM users WHERE email = '{email}'
            """)
            if existing.get('rows'):
                return {"success": False, "error": "User already exists"}

            # Create user
            await query_db(f"""
                INSERT INTO users (
                    id, email, password_hash, user_data, 
                    created_at, updated_at, last_login_at
                ) VALUES (
                    gen_random_uuid(),
                    '{email}',
                    '{self.hash_password(password)}',
                    '{json.dumps(user_data)}',
                    NOW(),
                    NOW(),
                    NULL
                )
            """)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def authenticate_user(self, email: str, password: str) -> Dict:
        """Authenticate user and return JWT token"""
        try:
            user = await query_db(f"""
                SELECT id, password_hash FROM users 
                WHERE email = '{email}'
            """)
            if not user.get('rows'):
                return {"success": False, "error": "User not found"}
            
            user_row = user['rows'][0]
            if self.hash_password(password) != user_row['password_hash']:
                return {"success": False, "error": "Invalid password"}
            
            # Generate JWT token
            token_data = {
                "sub": user_row['id'],
                "exp": datetime.utcnow() + timedelta(minutes=self.jwt_expire_minutes)
            }
            token = jwt.encode(token_data, self.jwt_secret, algorithm=self.jwt_algorithm)
            
            # Update last login
            await query_db(f"""
                UPDATE users SET last_login_at = NOW() 
                WHERE id = '{user_row['id']}'
            """)
            
            return {"success": True, "token": token}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def verify_token(self, token: str) -> Dict:
        """Verify JWT token and return user data"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            user_id = payload.get("sub")
            if not user_id:
                return {"success": False, "error": "Invalid token"}
            
            user = await query_db(f"""
                SELECT id, email, user_data FROM users 
                WHERE id = '{user_id}'
            """)
            if not user.get('rows'):
                return {"success": False, "error": "User not found"}
            
            return {"success": True, "user": user['rows'][0]}
        except jwt.ExpiredSignatureError:
            return {"success": False, "error": "Token expired"}
        except jwt.InvalidTokenError:
            return {"success": False, "error": "Invalid token"}
