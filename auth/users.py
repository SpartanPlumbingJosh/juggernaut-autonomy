from typing import Dict, Any, Optional
from datetime import datetime
from core.database import execute_sql
import hashlib
import secrets
import string

def generate_password_hash(password: str) -> str:
    """Generate secure password hash."""
    salt = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
    return hashlib.sha256((password + salt).encode()).hexdigest() + ':' + salt

def check_password_hash(password_hash: str, password: str) -> bool:
    """Verify password against hash."""
    stored_hash, salt = password_hash.split(':')
    return hashlib.sha256((password + salt).encode()).hexdigest() == stored_hash

async def create_user(email: str, password: str) -> Dict[str, Any]:
    """Create new user account."""
    try:
        password_hash = generate_password_hash(password)
        result = await execute_sql(
            f"""
            INSERT INTO users (
                id, email, password_hash,
                created_at, updated_at
            ) VALUES (
                gen_random_uuid(), '{email.replace("'", "''")}',
                '{password_hash}', NOW(), NOW()
            )
            RETURNING id
            """
        )
        return {'success': True, 'user_id': result['rows'][0]['id']}
    except Exception as e:
        return {'error': str(e)}

async def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user and return user data if valid."""
    try:
        result = await execute_sql(
            f"""
            SELECT id, password_hash FROM users 
            WHERE email = '{email.replace("'", "''")}'
            LIMIT 1
            """
        )
        if not result['rows']:
            return None
            
        user = result['rows'][0]
        if not check_password_hash(user['password_hash'], password):
            return None
            
        return {'user_id': user['id']}
    except Exception:
        return None
