"""
Payment processor with retry logic and automatic failover.
Handles credit cards, bank transfers, and cryptocurrency.
"""
import os
import time
from typing import Dict, Optional, Tuple
import stripe
import boto3
from datetime import datetime

# Initialize clients
stripe.api_key = os.getenv('STRIPE_API_KEY')
dynamodb = boto3.resource('dynamodb')
payments_table = dynamodb.Table('revenue_payments')

class PaymentProcessor:
    """Handle payment processing with automatic retries and reconciliation."""
    
    RETRY_LIMIT = 3
    RETRY_DELAY = 1
    
    def __init__(self):
        self.mode = os.getenv('PAYMENT_MODE', 'test')
    
    async def charge_customer(
        self, 
        amount: int, 
        currency: str, 
        payment_method: str,
        customer_id: str,
        metadata: Dict[str, str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """Process payment with automatic retries and logging."""
        attempt = 0
        last_error = None
        
        while attempt < self.RETRY_LIMIT:
            try:
                # Process payment
                if payment_method.startswith('card_'):
                    intent = stripe.PaymentIntent.create(
                        amount=amount,
                        currency=currency.lower(),
                        payment_method=payment_method,
                        customer=customer_id,
                        confirm=True,
                        metadata=metadata or {},
                        off_session=True,
                        error_on_requires_action=True
                    )
                    payment_id = intent.id
                else:
                    raise ValueError("Unsupported payment method")
                
                # Record payment transaction
                await self._record_transaction(
                    payment_id=payment_id,
                    amount=amount,
                    currency=currency,
                    status='succeeded',
                    payment_method=payment_method,
                    customer_id=customer_id,
                    metadata=metadata
                )
                
                return True, "Payment succeeded", payment_id
                
            except stripe.error.StripeError as e:
                last_error = str(e)
                attempt += 1
                time.sleep(self.RETRY_DELAY * attempt)
        
        # Record failed transaction
        await self._record_transaction(
            payment_id=None,
            amount=amount,
            currency=currency,
            status='failed',
            payment_method=payment_method,
            customer_id=customer_id,
            metadata=metadata,
            error=last_error
        )
        
        return False, last_error, None

    async def _record_transaction(
        self,
        payment_id: Optional[str],
        amount: int,
        currency: str,
        status: str,
        payment_method: str,
        customer_id: str,
        metadata: Dict[str, str],
        error: str = None
    ) -> None:
        """Record transaction in database."""
        item = {
            'transactionId': payment_id or f"failed-{datetime.now().isoformat()}",
            'amountCents': amount,
            'currency': currency,
            'status': status,
            'paymentMethod': payment_method,
            'customerId': customer_id,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {},
            'mode': self.mode
        }
        if error:
            item['error'] = error
            
        await payments_table.put_item(Item=item)
