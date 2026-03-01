from datetime import datetime, timedelta
from typing import Dict, Optional
import bcrypt
import jwt
from core.database import query_db

class UserManager:
    def __init__(self, jwt_secret: str):
        self.jwt_secret = jwt_secret
        
    async def register_user(self, email: str, password: str) -> Dict[str, Any]:
        """Register new user"""
        try:
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            res = await query_db(
                f"""
                INSERT INTO users (
                    id, email, password_hash, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{email}',
                    '{hashed.decode('utf-8')}',
                    NOW()
                )
                RETURNING id
                """
            )
            
            return {
                'success': True,
                'user_id': res['rows'][0]['id']
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
            
    async def authenticate_user(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate user and return JWT"""
        try:
            res = await query_db(
                f"""
                SELECT id, password_hash FROM users
                WHERE email = '{email}'
                LIMIT 1
                """
            )
            
            if not res['rows']:
                return {'success': False, 'error': 'User not found'}
                
            user = res['rows'][0]
            if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                return {'success': False, 'error': 'Invalid password'}
                
            token = jwt.encode({
                'user_id': user['id'],
                'exp': datetime.utcnow() + timedelta(days=7)
            }, self.jwt_secret, algorithm='HS256')
            
            return {
                'success': True,
                'token': token
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
            
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT and return user info"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            return {
                'success': True,
                'user_id': payload['user_id']
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
