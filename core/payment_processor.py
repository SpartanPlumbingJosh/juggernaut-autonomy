from datetime import datetime, timezone
from typing import Any, Dict, Optional
import stripe
import logging

logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Handles payment processing and product delivery."""
    
    def __init__(self, stripe_api_key: str):
        stripe.api_key = stripe_api_key
    
    async def process_payment(self, amount: float, currency: str, payment_method: str, 
                            customer_email: str, product_id: str) -> Dict[str, Any]:
        """Process a payment and trigger product delivery."""
        try:
            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                payment_method=payment_method,
                confirmation_method='manual',
                confirm=True,
                receipt_email=customer_email,
                metadata={
                    'product_id': product_id,
                    'processed_at': datetime.now(timezone.utc).isoformat()
                }
            )
            
            if intent.status == 'succeeded':
                # Trigger product delivery
                delivery_result = await self.deliver_product(product_id, customer_email)
                
                return {
                    'success': True,
                    'payment_id': intent.id,
                    'amount': amount,
                    'currency': currency,
                    'delivery_status': delivery_result.get('status', 'success')
                }
            
            return {'success': False, 'error': f'Payment failed: {intent.status}'}
            
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def deliver_product(self, product_id: str, customer_email: str) -> Dict[str, Any]:
        """Handle product/service delivery."""
        try:
            # TODO: Implement actual product delivery logic
            # This could be digital download, API access, etc.
            return {
                'status': 'success',
                'product_id': product_id,
                'delivered_at': datetime.now(timezone.utc).isoformat(),
                'customer_email': customer_email
            }
        except Exception as e:
            logger.error(f"Product delivery failed: {str(e)}")
            return {'status': 'failed', 'error': str(e)}
    
    async def record_revenue_event(self, execute_sql: Callable[[str], Dict[str, Any]],
                                 payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record revenue event in the database."""
        try:
            sql = f"""
            INSERT INTO revenue_events (
                id, experiment_id, event_type, amount_cents,
                currency, source, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                NULL,
                'revenue',
                {int(payment_data['amount'] * 100)},
                '{payment_data['currency']}',
                'direct_sale',
                '{json.dumps(payment_data)}'::jsonb,
                NOW()
            )
            """
            await execute_sql(sql)
            return {'success': True}
        except Exception as e:
            logger.error(f"Failed to record revenue event: {str(e)}")
            return {'success': False, 'error': str(e)}
