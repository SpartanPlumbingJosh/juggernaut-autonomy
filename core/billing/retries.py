from datetime import datetime, timedelta
from typing import Dict, Any
from .models import PaymentAttempt
from .gateways import StripeGateway, PayPalGateway
from core.database import query_db

def retry_failed_payments(max_retries: int = 3) -> Dict[str, Any]:
    """
    Retry failed payment attempts.
    
    Args:
        max_retries: Maximum number of retry attempts
        
    Returns:
        Dict with success status and statistics
    """
    try:
        # Get failed payments eligible for retry
        res = query_db(f"""
            SELECT * FROM payment_attempts
            WHERE status = 'failed'
              AND retry_count < {max_retries}
              AND last_attempt <= NOW() - INTERVAL '1 day'
            LIMIT 100
        """)
        attempts = res.get('rows', [])
        
        retried = 0
        succeeded = 0
        failed = 0
        
        for attempt in attempts:
            payment_id = attempt['payment_id']
            gateway = attempt['gateway']
            
            if gateway == 'stripe':
                gateway = StripeGateway(attempt['gateway_config']['api_key'])
            elif gateway == 'paypal':
                gateway = PayPalGateway(
                    attempt['gateway_config']['client_id'],
                    attempt['gateway_config']['client_secret']
                )
            else:
                continue
                
            # Attempt to capture payment
            result = gateway.capture_payment(payment_id)
            
            # Update attempt record
            query_db(f"""
                UPDATE payment_attempts
                SET retry_count = retry_count + 1,
                    last_attempt = NOW(),
                    status = '{'succeeded' if result.get('success') else 'failed'}'
                WHERE attempt_id = '{attempt['attempt_id']}'
            """)
            
            retried += 1
            if result.get('success'):
                succeeded += 1
            else:
                failed += 1
                
        return {
            'success': True,
            'retried': retried,
            'succeeded': succeeded,
            'failed': failed
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
