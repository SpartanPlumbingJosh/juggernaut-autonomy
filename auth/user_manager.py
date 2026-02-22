"""
User Management System - Handles user accounts, roles, and permissions.
"""
from typing import Dict, Optional
from enum import Enum
import hashlib
import uuid

class UserRole(Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    MANAGER = "manager"

class UserStatus(Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"

class UserManager:
    def __init__(self):
        self.users = {}
    
    def create_user(self, email: str, password: str, role: UserRole = UserRole.CUSTOMER) -> Dict:
        """Create a new user account"""
        user_id = str(uuid.uuid4())
        user = {
            "user_id": user_id,
            "email": email,
            "password_hash": self._hash_password(password),
            "role": role.value,
            "status": UserStatus.ACTIVE.value,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        self.users[user_id] = user
        return user
    
    def authenticate_user(self, email: str, password: str) -> Optional[Dict]:
        """Authenticate a user"""
        for user in self.users.values():
            if user["email"] == email and self._verify_password(password, user["password_hash"]):
                return user
        return None
    
    def update_user_role(self, user_id: str, role: UserRole) -> Dict:
        """Update user's role"""
        if user_id in self.users:
            self.users[user_id]["role"] = role.value
            return self.users[user_id]
        return {"error": "User not found"}
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against stored hash"""
        return self._hash_password(password) == password_hash
