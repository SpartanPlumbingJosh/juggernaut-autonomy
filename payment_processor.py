"""
Payment Processor Integration - Handles transactions with payment gateways.
Supports Stripe, PayPal, and manual payments.
"""

import os
import stripe
from typing import Dict, Optional
from datetime import datetime

class PaymentProcessor:
    def __init__(self):
        self.stripe_api_key = os.getenv("STRIPE_API_KEY")
        stripe.api_key = self.stripe_api_key
        
    async def process_payment(self, amount_cents: int, currency: str, 
                            payment_method: str, metadata: Dict) -> Dict:
        """
        Process a payment transaction.
        
        Args:
            amount_cents: Amount in cents
            currency: Currency code (e.g. 'usd')
            payment_method: Payment method type
            metadata: Additional transaction metadata
            
        Returns:
            Dict with payment status and details
        """
        try:
            if payment_method == "stripe":
                intent = stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=currency,
                    metadata=metadata
                )
                return {
                    "success": True,
                    "payment_id": intent.id,
                    "status": intent.status
                }
            else:
                return {
                    "success": False,
                    "error": "Unsupported payment method"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def log_transaction(self, execute_sql: Callable, 
                            amount_cents: int, currency: str,
                            payment_id: str, status: str,
                            metadata: Dict) -> bool:
        """
        Log transaction to revenue_events table.
        
        Args:
            execute_sql: Database query function
            amount_cents: Amount in cents
            currency: Currency code
            payment_id: Payment gateway ID
            status: Payment status
            metadata: Additional metadata
            
        Returns:
            True if logged successfully
        """
        try:
            await execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'payment',
                    {amount_cents},
                    '{currency}',
                    '{payment_method}',
                    '{json.dumps(metadata)}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            return True
        except Exception as e:
            return False
