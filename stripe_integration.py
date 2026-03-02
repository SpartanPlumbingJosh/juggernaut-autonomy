import stripe
from typing import Dict, Any
from datetime import datetime
from core.database import query_db

stripe.api_key = "sk_test_..."  # Use environment variable in production

async def create_checkout_session(user_id: str, price_id: str) -> Dict[str, Any]:
    """Create Stripe checkout session"""
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='payment',
            success_url='https://yourdomain.com/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://yourdomain.com/cancel',
            metadata={
                'user_id': user_id
            }
        )
        return {"success": True, "session_id": session.id, "url": session.url}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def handle_webhook(payload: str, sig_header: str) -> Dict[str, Any]:
    """Handle Stripe webhook events"""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, "whsec_..."  # Use env var in production
        )
        
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            user_id = session['metadata']['user_id']
            
            # Update user status in database
            await query_db(
                f"UPDATE users SET is_active = true WHERE id = '{user_id}'"
            )
            
            # Record payment
            await query_db(
                f"""
                INSERT INTO payments (user_id, amount, currency, stripe_session_id, created_at)
                VALUES ('{user_id}', {session['amount_total']/100}, '{session['currency']}', 
                        '{session['id']}', NOW())
                """
            )
            
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
