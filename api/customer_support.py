"""
Customer Support Handlers - Automated support ticket management.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db

async def handle_support_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Process customer support request."""
    customer_id = request.get("customer_id")
    subject = request.get("subject")
    message = request.get("message")
    
    try:
        # Create support ticket
        await query_db(f"""
            INSERT INTO support_tickets (
                id, customer_id, subject, message,
                status, created_at, updated_at
            ) VALUES (
                gen_random_uuid(),
                '{customer_id}',
                '{subject}',
                '{message}',
                'open',
                NOW(),
                NOW()
            )
        """)
        
        # Send automated response
        await send_automated_response(customer_id, subject)
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def send_automated_response(customer_id: str, subject: str) -> None:
    """Send automated response to support request."""
    # Basic keyword matching for common issues
    if "payment" in subject.lower():
        response = "We've received your payment inquiry..."
    elif "account" in subject.lower():
        response = "Regarding your account question..."
    else:
        response = "We've received your support request..."
    
    try:
        await query_db(f"""
            INSERT INTO support_messages (
                id, customer_id, message,
                created_at, updated_at
            ) VALUES (
                gen_random_uuid(),
                '{customer_id}',
                '{response}',
                NOW(),
                NOW()
            )
        """)
    except Exception as e:
        print(f"Error sending automated response: {str(e)}")
