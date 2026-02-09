from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import hashlib
import secrets

@dataclass
class User:
    id: str
    email: str
    password_hash: str
    api_key: str
    created_at: datetime
    last_login: datetime
    is_active: bool
    roles: List[str]

    @classmethod
    def create(cls, email: str, password: str) -> 'User':
        """Create new user with hashed password"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        
        return cls(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=f"{salt}${password_hash}",
            api_key=secrets.token_urlsafe(32),
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow(),
            is_active=True,
            roles=['customer']
        )

    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash"""
        salt, stored_hash = self.password_hash.split('$')
        new_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        return secrets.compare_digest(new_hash, stored_hash)
