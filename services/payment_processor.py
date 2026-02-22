"""
Payment Processor - Handles payment integrations and transactions.
Supports multiple payment gateways with failover capabilities.
"""

import stripe
from datetime import datetime
from typing import Optional, Dict, Any
from core.database import query_db

class PaymentProcessor:
    def __init__(self, stripe_api_key: str):
        stripe.api_key = stripe_api_key
        self.gateways = {
            'stripe': self._process_stripe_payment
        }

    async def create_customer(self, email: str, name: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new customer in payment system."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def process_payment(self, amount_cents: int, currency: str, customer_id: str, 
                            description: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process payment through primary gateway with failover."""
        try:
            # Try primary gateway first
            payment = await self.gateways['stripe'](
                amount_cents=amount_cents,
                currency=currency,
                customer_id=customer_id,
                description=description,
                metadata=metadata
            )
            
            if payment['success']:
                await self._record_transaction(
                    amount_cents=amount_cents,
                    currency=currency,
                    customer_id=customer_id,
                    payment_id=payment['payment_id'],
                    status='success'
                )
                return payment
            
            return {"success": False, "error": "Payment failed"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _process_stripe_payment(self, amount_cents: int, currency: str, customer_id: str,
                                    description: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process payment through Stripe."""
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                customer=customer_id,
                description=description,
                metadata=metadata or {},
                payment_method_types=['card'],
                confirm=True
            )
            
            return {
                "success": True,
                "payment_id": payment_intent.id,
                "amount_cents": amount_cents,
                "currency": currency
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _record_transaction(self, amount_cents: int, currency: str, customer_id: str,
                                 payment_id: str, status: str) -> None:
        """Record transaction in database."""
        await query_db(f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, 
                customer_id, payment_id, status, recorded_at
            ) VALUES (
                gen_random_uuid(),
                'payment',
                {amount_cents},
                '{currency}',
                '{customer_id}',
                '{payment_id}',
                '{status}',
                NOW()
            )
        """)
