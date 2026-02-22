from typing import Dict, Any
from core.database import query_db
from payments.payment_processor import PaymentProcessor

class CustomerOnboarding:
    """Handle customer onboarding flow"""
    
    @staticmethod
    async def create_customer(email: str, name: str) -> Dict[str, Any]:
        """Create customer record"""
        try:
            await query_db(f"""
                INSERT INTO customers (
                    id, email, name, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{email}',
                    '{name}',
                    NOW(),
                    NOW()
                )
            """)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def initiate_purchase(email: str, product_id: str) -> Dict[str, Any]:
        """Start purchase flow for customer"""
        try:
            # Create checkout session
            success_url = f"https://yourdomain.com/success?session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"https://yourdomain.com/cancel"
            
            session = await PaymentProcessor.create_checkout_session(
                product_id=product_id,
                success_url=success_url,
                cancel_url=cancel_url
            )
            
            if 'error' in session:
                return session
                
            return {
                "success": True,
                "session_id": session['session_id'],
                "checkout_url": session['url']
            }
            
        except Exception as e:
            return {"error": str(e)}

__all__ = ["CustomerOnboarding"]
