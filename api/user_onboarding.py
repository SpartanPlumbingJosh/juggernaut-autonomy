"""
User Onboarding API - Handle new user signup and activation.

Features:
- User registration
- Email verification
- Account activation
- Welcome sequence
"""

import os
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from core.database import query_db
from api.revenue_api import _make_response, _error_response
import smtplib
from email.mime.text import MIMEText

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

async def register_user(email: str, password: str) -> Dict[str, Any]:
    """Register a new user."""
    try:
        # Check if user exists
        existing = await query_db(f"""
            SELECT id FROM users WHERE email = '{email}'
        """)
        if existing.get("rows"):
            return _error_response(400, "User already exists")
            
        # Hash password
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        
        # Create verification token
        verification_token = hashlib.sha256(os.urandom(32)).hexdigest()
        
        # Insert user
        await query_db(f"""
            INSERT INTO users (email, password_hash, salt, verification_token, created_at)
            VALUES ('{email}', '{key.hex()}', '{salt.hex()}', '{verification_token}', NOW())
        """)
        
        # Send verification email
        await send_verification_email(email, verification_token)
        
        return _make_response(200, {"status": "success"})
        
    except Exception as e:
        return _error_response(500, f"Registration failed: {str(e)}")

async def verify_user(token: str) -> Dict[str, Any]:
    """Verify user email address."""
    try:
        # Find user by token
        user = await query_db(f"""
            SELECT id FROM users 
            WHERE verification_token = '{token}'
            AND verified = FALSE
        """)
        
        if not user.get("rows"):
            return _error_response(404, "Invalid or expired token")
            
        # Mark user as verified
        await query_db(f"""
            UPDATE users
            SET verified = TRUE,
                verified_at = NOW()
            WHERE id = '{user['rows'][0]['id']}'
        """)
        
        # Trigger welcome sequence
        await trigger_welcome_sequence(user['rows'][0]['id'])
        
        return _make_response(200, {"status": "success"})
        
    except Exception as e:
        return _error_response(500, f"Verification failed: {str(e)}")

async def send_verification_email(email: str, token: str) -> None:
    """Send verification email."""
    try:
        verification_url = f"{os.getenv('APP_URL')}/verify?token={token}"
        
        msg = MIMEText(f"""
            Welcome! Please verify your email by clicking the link below:
            {verification_url}
        """)
        msg['Subject'] = 'Verify your email address'
        msg['From'] = SMTP_USER
        msg['To'] = email
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            
    except Exception as e:
        raise Exception(f"Failed to send verification email: {str(e)}")

async def trigger_welcome_sequence(user_id: str) -> None:
    """Trigger welcome email sequence."""
    try:
        # Send welcome email
        await send_welcome_email(user_id)
        
        # Add to onboarding campaign
        await query_db(f"""
            INSERT INTO onboarding_campaigns (user_id, step, sent_at)
            VALUES ('{user_id}', 1, NOW())
        """)
        
    except Exception as e:
        raise Exception(f"Failed to trigger welcome sequence: {str(e)}")

async def send_welcome_email(user_id: str) -> None:
    """Send welcome email."""
    try:
        user = await query_db(f"""
            SELECT email FROM users WHERE id = '{user_id}'
        """)
        email = user['rows'][0]['email']
        
        msg = MIMEText("""
            Welcome to our platform! We're excited to have you on board.
        """)
        msg['Subject'] = 'Welcome!'
        msg['From'] = SMTP_USER
        msg['To'] = email
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            
    except Exception as e:
        raise Exception(f"Failed to send welcome email: {str(e)}")

def route_onboarding_request(path: str, method: str, query_params: Dict[str, Any], body: Optional[str] = None) -> Dict[str, Any]:
    """Route onboarding API requests."""
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})
    
    # Parse path
    parts = [p for p in path.split("/") if p]
    
    # POST /onboarding/register
    if len(parts) == 2 and parts[0] == "onboarding" and parts[1] == "register" and method == "POST":
        return register_user(body.get("email"), body.get("password"))
    
    # GET /onboarding/verify
    if len(parts) == 2 and parts[0] == "onboarding" and parts[1] == "verify" and method == "GET":
        return verify_user(query_params.get("token"))
    
    return _error_response(404, "Not found")

__all__ = ["route_onboarding_request"]
