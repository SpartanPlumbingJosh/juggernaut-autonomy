from typing import Dict, List
from datetime import datetime, timedelta
from core.payment_processor import PaymentProcessor

class BillingSystem:
    """Handle billing operations and invoice management."""
    
    def __init__(self):
        self.payment_processor = PaymentProcessor()
        
    async def generate_invoice(self, customer_id: str, period_start: datetime, period_end: datetime) -> Dict:
        """Generate an invoice for a billing period."""
        try:
            # Get usage data
            usage = await self._get_usage_data(customer_id, period_start, period_end)
            
            # Calculate total
            total = sum(item['amount'] for item in usage['items'])
            
            # Create payment intent
            intent_res = await self.payment_processor.create_payment_intent(
                total,
                customer_id,
                f'Invoice for {period_start.date()} to {period_end.date()}'
            )
            
            if not intent_res['success']:
                return intent_res
                
            return {
                'success': True,
                'invoice_id': f'inv_{customer_id}_{period_start.date()}',
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'total': total,
                'items': usage['items'],
                'payment_intent': intent_res
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _get_usage_data(self, customer_id: str, start: datetime, end: datetime) -> Dict:
        """Get usage data for billing period."""
        # This would typically query a usage tracking system
        # For now, return mock data
        return {
            'customer_id': customer_id,
            'items': [
                {
                    'description': 'Base subscription',
                    'amount': 9900,
                    'quantity': 1
                },
                {
                    'description': 'Additional feature usage',
                    'amount': 500,
                    'quantity': 10
                }
            ]
        }
        
    async def process_recurring_billing(self) -> Dict:
        """Process all recurring billing for active subscriptions."""
        try:
            # Get all subscriptions due for billing
            subscriptions = await self._get_due_subscriptions()
            
            results = []
            for sub in subscriptions:
                invoice_res = await self.generate_invoice(
                    sub['customer_id'],
                    sub['period_start'],
                    sub['period_end']
                )
                results.append(invoice_res)
                
            return {
                'success': True,
                'processed': len(results),
                'results': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _get_due_subscriptions(self) -> List[Dict]:
        """Get subscriptions that are due for billing."""
        # This would typically query a database
        # For now, return mock data
        now = datetime.utcnow()
        return [
            {
                'customer_id': 'cus_123',
                'period_start': now - timedelta(days=30),
                'period_end': now
            }
        ]
