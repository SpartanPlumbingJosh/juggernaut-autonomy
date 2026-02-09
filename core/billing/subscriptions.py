from datetime import datetime, timedelta
from typing import Dict, Any
from .models import Subscription, Invoice
from .gateways import StripeGateway, PayPalGateway
from core.database import query_db

def manage_subscriptions() -> Dict[str, Any]:
    """
    Manage active subscriptions - renewals, cancellations, etc.
    
    Returns:
        Dict with success status and statistics
    """
    try:
        # Get subscriptions due for renewal
        res = query_db("""
            SELECT * FROM subscriptions
            WHERE status = 'active'
              AND current_period_end <= NOW()
            LIMIT 100
        """)
        subscriptions = res.get('rows', [])
        
        renewed = 0
        failed = 0
        
        for sub in subscriptions:
            subscription_id = sub['subscription_id']
            customer_id = sub['customer_id']
            plan_id = sub['plan_id']
            gateway = sub['gateway']
            
            # Create new invoice
            invoice_id = str(uuid.uuid4())
            query_db(f"""
                INSERT INTO invoices (
                    invoice_id, customer_id, amount, currency, status, due_date
                ) VALUES (
                    '{invoice_id}', '{customer_id}', {sub['amount']}, '{sub['currency']}', 'open', NOW() + INTERVAL '7 days'
                )
            """)
            
            # Attempt payment
            if gateway == 'stripe':
                gateway = StripeGateway(sub['gateway_config']['api_key'])
            elif gateway == 'paypal':
                gateway = PayPalGateway(
                    sub['gateway_config']['client_id'],
                    sub['gateway_config']['client_secret']
                )
            else:
                continue
                
            payment = gateway.create_payment_intent(
                amount=sub['amount'],
                currency=sub['currency'],
                metadata={
                    'subscription_id': subscription_id,
                    'invoice_id': invoice_id
                }
            )
            
            if payment.get('success'):
                renewed += 1
                # Update subscription period
                query_db(f"""
                    UPDATE subscriptions
                    SET current_period_end = NOW() + INTERVAL '1 month'
                    WHERE subscription_id = '{subscription_id}'
                """)
            else:
                failed += 1
                # Mark subscription as past due
                query_db(f"""
                    UPDATE subscriptions
                    SET status = 'past_due'
                    WHERE subscription_id = '{subscription_id}'
                """)
                
        return {
            'success': True,
            'renewed': renewed,
            'failed': failed,
            'total': len(subscriptions)
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
