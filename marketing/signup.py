"""
Self-Service Signup - Handles user registration and onboarding.
"""
import json
from datetime import datetime
from typing import Dict, List, Optional

from core.database import query_db
from core.email import send_welcome_email

async def create_user_account(
    email: str,
    password: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Create new user account."""
    try:
        # Check if email exists
        check_sql = "SELECT id FROM users WHERE email = %s"
        check_result = await query_db(check_sql, [email])
        if check_result["rows"]:
            raise Exception("Email already registered")
            
        # Create user
        sql = """
        INSERT INTO users (
            email, password_hash, metadata, status, created_at
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """
        result = await query_db(sql, [
            email,
            hash_password(password),
            json.dumps(metadata),
            "active",
            datetime.utcnow()
        ])
        
        # Send welcome email
        await send_welcome_email(email)
        
        return {
            "id": result["rows"][0]["id"],
            "email": email,
            "status": "active"
        }
        
    except Exception as e:
        raise Exception(f"Failed to create user account: {str(e)}")


async def complete_onboarding(user_id: int, onboarding_data: Dict[str, Any]) -> Dict[str, Any]:
    """Complete user onboarding process."""
    try:
        # Update user metadata
        sql = """
        UPDATE users 
        SET metadata = metadata || %s, onboarding_completed_at = %s
        WHERE id = %s
        """
        await query_db(sql, [
            json.dumps(onboarding_data),
            datetime.utcnow(),
            user_id
        ])
        
        return {
            "id": user_id,
            "onboarding_completed_at": datetime.utcnow()
        }
        
    except Exception as e:
        raise Exception(f"Failed to complete onboarding: {str(e)}")


async def track_signup_source(user_id: int, source: str) -> Dict[str, Any]:
    """Track where user came from."""
    try:
        sql = """
        UPDATE users 
        SET signup_source = %s
        WHERE id = %s
        """
        await query_db(sql, [source, user_id])
        
        return {
            "id": user_id,
            "signup_source": source
        }
        
    except Exception as e:
        raise Exception(f"Failed to track signup source: {str(e)}")


__all__ = ["create_user_account", "complete_onboarding", "track_signup_source"]
