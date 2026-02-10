"""
Minimal customer onboarding flow with digital delivery.
"""
from typing import Dict
from datetime import datetime
import uuid
from core.services.payment_service import create_payment_intent, capture_payment

async def start_onboarding(
    execute_sql: callable,
    email: str,
    product_id: str,
    amount_cents: int
) -> Dict:
    """Begin customer onboarding with payment."""
    # Create or get customer record
    customer_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, email))
    
    # Create payment intent
    payment = await create_payment_intent(
        amount_cents=amount_cents,
        metadata={
            'product_id': product_id,
            'customer_email': email,
            'customer_id': customer_id
        }
    )
    
    if 'error' in payment:
        return {'success': False, 'error': payment['error']}
        
    return {
        'success': True,
        'payment_intent': payment,
        'customer_id': customer_id,
        'next_step': 'payment_confirmation'
    }

async def complete_onboarding(
    execute_sql: callable,
    payment_intent_id: str,
    customer_id: str,
    product_id: str
) -> Dict:
    """Finalize onboarding after payment confirmation."""
    # Capture payment
    capture = await capture_payment(payment_intent_id)
    if 'error' in capture:
        return {'success': False, 'error': capture['error']}
    
    # Record revenue event
    await record_revenue_event(
        execute_sql=execute_sql,
        payment_intent_id=payment_intent_id,
        amount_cents=capture['amount_captured'],
        product_id=product_id,
        customer_id=customer_id
    )
    
    # TODO: Trigger product delivery/service fulfillment
    
    return {
        'success': True,
        'payment_captured': capture['amount_captured'],
        'delivery_status': 'pending'  # Will be async updated
    }
