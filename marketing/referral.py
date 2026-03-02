"""
Referral System - Tracks and rewards customer referrals.
"""
import json
from datetime import datetime
from typing import Dict, List, Optional

from core.database import query_db

async def create_referral_code(user_id: int) -> Dict[str, Any]:
    """Generate unique referral code for user."""
    try:
        # Generate code
        code = f"REF-{user_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Save to database
        sql = """
        INSERT INTO referral_codes (user_id, code, status, created_at)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """
        result = await query_db(sql, [user_id, code, "active", datetime.utcnow()])
        
        return {
            "id": result["rows"][0]["id"],
            "user_id": user_id,
            "code": code,
            "status": "active"
        }
        
    except Exception as e:
        raise Exception(f"Failed to create referral code: {str(e)}")


async def track_referral(referrer_code: str, referred_user_id: int) -> Dict[str, Any]:
    """Track new referral."""
    try:
        # Get referrer details
        sql = "SELECT * FROM referral_codes WHERE code = %s"
        result = await query_db(sql, [referrer_code])
        if not result["rows"]:
            raise Exception("Invalid referral code")
            
        referrer = result["rows"][0]
        
        # Save referral
        referral_sql = """
        INSERT INTO referrals (
            referrer_id, referred_user_id, status, created_at
        )
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """
        referral_result = await query_db(referral_sql, [
            referrer["user_id"],
            referred_user_id,
            "pending",
            datetime.utcnow()
        ])
        
        return {
            "id": referral_result["rows"][0]["id"],
            "referrer_id": referrer["user_id"],
            "referred_user_id": referred_user_id,
            "status": "pending"
        }
        
    except Exception as e:
        raise Exception(f"Failed to track referral: {str(e)}")


async def process_referral_payout(referral_id: int) -> Dict[str, Any]:
    """Process referral payout when conditions are met."""
    try:
        # Get referral details
        sql = "SELECT * FROM referrals WHERE id = %s"
        result = await query_db(sql, [referral_id])
        referral = result["rows"][0]
        
        # Check if payout conditions are met
        # (e.g., referred user completed signup, made purchase, etc.)
        # This would call other services to verify conditions
        
        # Process payout
        payout_sql = """
        UPDATE referrals 
        SET status = 'paid', paid_at = %s
        WHERE id = %s
        """
        await query_db(payout_sql, [datetime.utcnow(), referral_id])
        
        return {
            "id": referral_id,
            "status": "paid",
            "paid_at": datetime.utcnow()
        }
        
    except Exception as e:
        raise Exception(f"Failed to process referral payout: {str(e)}")


__all__ = ["create_referral_code", "track_referral", "process_referral_payout"]
