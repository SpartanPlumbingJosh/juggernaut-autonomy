from datetime import datetime, timedelta
from typing import Dict, List, Optional
from payment.payment_processor import PaymentProcessor
from core.database import query_db

class BillingManager:
    """Handle billing operations and subscriptions"""
    
    def __init__(self):
        self.payment_processor = PaymentProcessor()
    
    async def create_invoice(self, customer_id: str, amount: int, currency: str, 
                            description: str, metadata: Optional[Dict] = None) -> Dict:
        """Create an invoice for a customer"""
        # Record invoice in database
        invoice_id = await query_db(
            f"""
            INSERT INTO invoices (
                customer_id, amount, currency, description, status, created_at
            ) VALUES (
                '{customer_id}', {amount}, '{currency}', '{description}', 'pending', NOW()
            )
            RETURNING id
            """
        )
        
        # Create payment intent
        payment_intent = self.payment_processor.create_payment_intent(
            amount=amount,
            currency=currency,
            customer_id=customer_id,
            metadata={
                'invoice_id': invoice_id,
                **(metadata or {})
            }
        )
        
        # Update invoice with payment intent
        await query_db(
            f"""
            UPDATE invoices
            SET payment_intent_id = '{payment_intent['id']}',
                status = 'created'
            WHERE id = '{invoice_id}'
            """
        )
        
        return {
            'invoice_id': invoice_id,
            'payment_intent': payment_intent
        }
    
    async def handle_webhook(self, event: Dict) -> Dict:
        """Handle Stripe webhook events"""
        event_type = event['type']
        data = event['data']['object']
        
        if event_type == 'payment_intent.succeeded':
            # Update invoice status
            await query_db(
                f"""
                UPDATE invoices
                SET status = 'paid',
                    paid_at = NOW()
                WHERE payment_intent_id = '{data['id']}'
                """
            )
            return {'success': True, 'message': 'Payment succeeded'}
        
        return {'success': False, 'message': 'Unhandled event type'}
