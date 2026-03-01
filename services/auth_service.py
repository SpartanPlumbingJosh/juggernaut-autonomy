"""
Authentication service for SaaS platform.
Handles user onboarding, sessions, and email verification.
"""
import json
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Literal

from core.database import query_db

SESSION_EXPIRE_DAYS = 30

async def create_user(email: str, password: str, name: str) -> Dict[str, Any]:
    """Create new user account and return verification token."""
    # Validate inputs
    existing = await query_db(
        f"SELECT id FROM users WHERE email = '{email.replace("'", "''")}'"
    )
    if existing.get("rows"):
        return {"error": "Email already registered"}
    
    # Hash password
    salt = secrets.token_hex(16)
    hashed_pwd = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    ).hex()

    # Create user
    verification_token = secrets.token_urlsafe(32)
    result = await query_db(
        f"""
        INSERT INTO users (
            email, password_hash, salt, name,
            verification_token, created_at
        ) VALUES (
            '{email.replace("'", "''")}',
            '{hashed_pwd}',
            '{salt}',
            '{name.replace("'", "''")}',
            '{verification_token}',
            NOW()
        )
        RETURNING id
        """
    )
    user_id = result["rows"][0]["id"]
    
    return {
        "success": True,
        "user_id": user_id,
        "verification_token": verification_token
    }

async def verify_user(token: str) -> Dict[str, Any]:
    """Verify user email and mark account as active."""
    result = await query_db(
        f"UPDATE users SET verified = TRUE, verified_at = NOW() "
        f"WHERE verification_token = '{token.replace("'", "''")}' "
        f"RETURNING id, email"
    )
    if not result.get("rows"):
        return {"error": "Invalid verification token"}
    return {"success": True, "user_id": result["rows"][0]["id"]}

async def create_session(user_id: str, user_agent: str) -> str:
    """Create new login session and return session token."""
    session_token = secrets.token_urlsafe(64)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRE_DAYS)
    
    await query_db(
        f"""
        INSERT INTO sessions (
            user_id, token, user_agent, expires_at, created_at
        ) VALUES (
            '{user_id.replace("'", "''")}',
            '{session_token}',
            '{user_agent.replace("'", "''")}',
            '{expires_at.isoformat()}',
            NOW()
        )
        """
    )
    return session_token

async def validate_session(token: str) -> Optional[Dict[str, Any]]:
    """Validate session token and return user data if valid."""
    result = await query_db(
        f"""
        SELECT u.id, u.email, u.name, u.verified
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = '{token.replace("'", "''")}'
        AND s.expires_at > NOW()
        LIMIT 1
        """
    )
    if not result.get("rows"):
        return None
    return result["rows"][0]
