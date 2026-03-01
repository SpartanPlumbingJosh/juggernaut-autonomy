"""
Core billing and payment processing system.

Handles:
- Subscription management
- Payment processing
- Invoice generation
- Revenue recognition
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class BillingSystem:
    """Handle all billing operations."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    async def process_payment(self, payment_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Process a payment transaction."""
        try:
            # Validate payment data
            required_fields = ['amount', 'currency', 'payment_method', 'customer_id']
            if not all(field in payment_data for field in required_fields):
                return False, "Missing required payment fields"
                
            # Record payment
            payment_id = await self._record_payment(payment_data)
            
            # Create revenue event
            await self._create_revenue_event({
                'amount_cents': int(float(payment_data['amount']) * 100),
                'currency': payment_data['currency'],
                'source': 'payment',
                'metadata': {
                    'payment_id': payment_id,
                    'customer_id': payment_data['customer_id']
                }
            })
            
            return True, None
            
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return False, str(e)
            
    async def _record_payment(self, payment_data: Dict[str, Any]) -> str:
        """Record payment in database."""
        sql = f"""
        INSERT INTO payments (
            id, customer_id, amount_cents, currency, 
            payment_method, status, created_at
        ) VALUES (
            gen_random_uuid(),
            '{payment_data['customer_id']}',
            {int(float(payment_data['amount']) * 100)},
            '{payment_data['currency']}',
            '{payment_data['payment_method']}',
            'completed',
            NOW()
        )
        RETURNING id
        """
        result = await self.execute_sql(sql)
        return result['rows'][0]['id']
        
    async def _create_revenue_event(self, event_data: Dict[str, Any]) -> None:
        """Create revenue event."""
        sql = f"""
        INSERT INTO revenue_events (
            id, amount_cents, currency, source,
            metadata, recorded_at, created_at
        ) VALUES (
            gen_random_uuid(),
            {event_data['amount_cents']},
            '{event_data['currency']}',
            '{event_data['source']}',
            '{json.dumps(event_data['metadata'])}',
            NOW(),
            NOW()
        )
        """
        await self.execute_sql(sql)
        
    async def generate_invoice(self, customer_id: str, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Generate invoice for a customer."""
        try:
            # Get usage data
            usage_sql = f"""
            SELECT SUM(amount_cents) as total_cents
            FROM usage_events
            WHERE customer_id = '{customer_id}'
              AND recorded_at BETWEEN '{period_start.isoformat()}' AND '{period_end.isoformat()}'
            """
            usage_result = await self.execute_sql(usage_sql)
            total_cents = usage_result['rows'][0]['total_cents'] or 0
            
            # Create invoice
            invoice_sql = f"""
            INSERT INTO invoices (
                id, customer_id, period_start, period_end,
                amount_cents, currency, status, created_at
            ) VALUES (
                gen_random_uuid(),
                '{customer_id}',
                '{period_start.isoformat()}',
                '{period_end.isoformat()}',
                {total_cents},
                'USD',
                'pending',
                NOW()
            )
            RETURNING id
            """
            invoice_result = await self.execute_sql(invoice_sql)
            
            return {
                'invoice_id': invoice_result['rows'][0]['id'],
                'total': total_cents / 100,
                'currency': 'USD',
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Invoice generation failed: {str(e)}")
            raise
            
    async def handle_failed_payments(self) -> None:
        """Handle failed payment retries."""
        try:
            # Get failed payments
            sql = """
            SELECT id, customer_id, amount_cents, payment_method
            FROM payments
            WHERE status = 'failed'
              AND retry_count < 3
              AND created_at > NOW() - INTERVAL '7 days'
            """
            result = await self.execute_sql(sql)
            
            for payment in result['rows']:
                # Retry payment logic
                retry_success = await self._retry_payment(payment)
                
                if retry_success:
                    await self.execute_sql(f"""
                        UPDATE payments
                        SET status = 'completed',
                            retry_count = retry_count + 1
                        WHERE id = '{payment['id']}'
                    """)
                else:
                    await self.execute_sql(f"""
                        UPDATE payments
                        SET retry_count = retry_count + 1
                        WHERE id = '{payment['id']}'
                    """)
                    
        except Exception as e:
            logger.error(f"Failed payment handling error: {str(e)}")
            
    async def _retry_payment(self, payment: Dict[str, Any]) -> bool:
        """Retry a failed payment."""
        # Implement payment gateway retry logic
        return True
