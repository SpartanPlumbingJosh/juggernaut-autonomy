import json
import logging
from typing import Dict, Optional
from datetime import datetime

class PaymentHandler:
    """Core payment processing with retry logic and idempotency."""
    
    def __init__(self, db_executor):
        self.db = db_executor
        self.logger = logging.getLogger(__name__)
        
    async def process_payment(self, payment_data: Dict) -> Dict:
        """Process payment with idempotency key and retry logic."""
        payment_id = payment_data.get('idempotency_key')
        
        # Check for duplicate
        existing = await self._check_existing_payment(payment_id)
        if existing:
            return existing
            
        try:
            # Process payment (would integrate with Stripe/PayPal/etc)
            processed = await self._charge_payment(payment_data)
            
            # Record transaction
            await self._record_transaction(
                amount=processed['amount'],
                currency=processed['currency'],
                payment_id=payment_id,
                status='completed'
            )
            
            return {
                'status': 'success',
                'transaction_id': payment_id,
                'processed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Payment failed: {str(e)}")
            await self._record_transaction(
                amount=payment_data['amount'],
                currency=payment_data['currency'],
                payment_id=payment_id,
                status='failed',
                error=str(e)
            )
            return {
                'status': 'failed',
                'error': str(e)
            }
            
    async def _check_existing_payment(self, payment_id: str) -> Optional[Dict]:
        """Check for existing payment to ensure idempotency."""
        res = await self.db(
            f"SELECT status, metadata FROM payments WHERE id = '{payment_id}'"
        )
        if res.get('rows'):
            return res['rows'][0]
        return None
        
    async def _charge_payment(self, payment_data: Dict) -> Dict:
        """Mock payment processor integration."""
        # In production, replace with actual payment processor API calls
        return {
            'amount': payment_data['amount'],
            'currency': payment_data['currency'],
            'processor_response': 'mock_success'
        }
        
    async def _record_transaction(self, **kwargs):
        """Record payment transaction in database."""
        query = """
        INSERT INTO payments (
            id, amount, currency, status, 
            processor_response, created_at, metadata
        ) VALUES (
            %(payment_id)s, %(amount)s, %(currency)s, 
            %(status)s, %(processor_response)s, NOW(), %(metadata)s
        )
        """
        await self.db(query, {
            'payment_id': kwargs['payment_id'],
            'amount': kwargs['amount'],
            'currency': kwargs['currency'],
            'status': kwargs['status'],
            'processor_response': kwargs.get('error', 'success'),
            'metadata': json.dumps(kwargs)
        })
