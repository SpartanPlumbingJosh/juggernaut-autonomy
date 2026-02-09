from typing import Dict, Any
from .gateways import StripeGateway, PayPalGateway
from .models import PaymentAttempt, Invoice
from core.database import query_db

def handle_webhook_event(event_type: str, payload: Dict[str, Any], gateway: str) -> Dict[str, Any]:
    """
    Handle webhook events from payment gateways.
    
    Args:
        event_type: Type of webhook event
        payload: Event payload data
        gateway: Payment gateway name ('stripe' or 'paypal')
        
    Returns:
        Dict with success status and any relevant data
    """
    if gateway == 'stripe':
        return handle_stripe_webhook(event_type, payload)
    elif gateway == 'paypal':
        return handle_paypal_webhook(event_type, payload)
    else:
        return {'success': False, 'error': 'Unsupported gateway'}

def handle_stripe_webhook(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Stripe webhook events"""
    try:
        if event_type == 'payment_intent.succeeded':
            payment_id = payload['data']['object']['id']
            amount = payload['data']['object']['amount'] / 100
            currency = payload['data']['object']['currency']
            
            # Record successful payment
            query_db(f"""
                INSERT INTO payment_attempts (
                    attempt_id, payment_id, amount, currency, status
                ) VALUES (
                    gen_random_uuid(), '{payment_id}', {amount}, '{currency}', 'succeeded'
                )
            """)
            
            return {'success': True, 'payment_id': payment_id}
            
        elif event_type == 'payment_intent.payment_failed':
            payment_id = payload['data']['object']['id']
            error = payload['data']['object']['last_payment_error']
            
            # Record failed payment
            query_db(f"""
                INSERT INTO payment_attempts (
                    attempt_id, payment_id, status, metadata
                ) VALUES (
                    gen_random_uuid(), '{payment_id}', 'failed', '{json.dumps(error)}'
                )
            """)
            
            return {'success': True, 'payment_id': payment_id}
            
        elif event_type == 'invoice.payment_succeeded':
            invoice_id = payload['data']['object']['id']
            payment_id = payload['data']['object']['payment_intent']
            
            # Update invoice status
            query_db(f"""
                UPDATE invoices
                SET status = 'paid'
                WHERE invoice_id = '{invoice_id}'
            """)
            
            return {'success': True, 'invoice_id': invoice_id}
            
        else:
            return {'success': True, 'message': 'Event not handled'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

def handle_paypal_webhook(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle PayPal webhook events"""
    try:
        if event_type == 'PAYMENT.CAPTURE.COMPLETED':
            payment_id = payload['resource']['id']
            amount = float(payload['resource']['amount']['value'])
            currency = payload['resource']['amount']['currency_code']
            
            # Record successful payment
            query_db(f"""
                INSERT INTO payment_attempts (
                    attempt_id, payment_id, amount, currency, status
                ) VALUES (
                    gen_random_uuid(), '{payment_id}', {amount}, '{currency}', 'succeeded'
                )
            """)
            
            return {'success': True, 'payment_id': payment_id}
            
        elif event_type == 'PAYMENT.CAPTURE.DENIED':
            payment_id = payload['resource']['id']
            error = payload['resource']['details']
            
            # Record failed payment
            query_db(f"""
                INSERT INTO payment_attempts (
                    attempt_id, payment_id, status, metadata
                ) VALUES (
                    gen_random_uuid(), '{payment_id}', 'failed', '{json.dumps(error)}'
                )
            """)
            
            return {'success': True, 'payment_id': payment_id}
            
        else:
            return {'success': True, 'message': 'Event not handled'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}
