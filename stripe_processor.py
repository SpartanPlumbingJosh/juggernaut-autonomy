import stripe
from datetime import datetime, timezone
from typing import Dict, Optional, Any
import json

class StripePaymentProcessor:
    """Handle Stripe payment processing and revenue event logging"""
    
    def __init__(self, api_key: str, db_executor):
        """
        Args:
            api_key: Stripe secret key
            db_executor: Function to execute DB queries (Async)
        """
        stripe.api_key = api_key
        self.db = db_executor
        
    async def process_payment(self, amount: float, currency: str, source: str, 
                            customer_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process payment and log revenue event
        
        Args:
            amount: Payment amount in currency units
            currency: 3-letter currency code
            source: Payment source identifier
            customer_id: Customer identifier  
            metadata: Additional transaction data
            
        Returns:
            Payment result with status and details
        """
        try:
            # Convert to cents for Stripe
            amount_cents = int(amount * 100)
            
            # Create Stripe charge
            charge = stripe.Charge.create(
                amount=amount_cents,
                currency=currency.lower(),
                source=source,
                customer=customer_id,
                description=f"Payment for {metadata.get('product', '')}",
                metadata=metadata
            )
            
            # Log successful revenue event
            await self.log_revenue_event(
                event_type='revenue',
                amount_cents=amount_cents,
                currency=currency,
                source='stripe',
                metadata={
                    'charge_id': charge.id,
                    'balance_transaction': charge.balance_transaction,
                    **metadata
                }
            )
            
            return {
                'status': 'completed',
                'charge_id': charge.id,
                'amount': amount,
                'currency': currency
            }
            
        except stripe.error.StripeError as e:
            # Log failed payment attempt
            await self.log_revenue_event(
                event_type='failed_payment',
                amount_cents=amount_cents,
                currency=currency,
                source='stripe',
                metadata={
                    'error': str(e),
                    'error_type': e.__class__.__name__,
                    **metadata
                }
            )
            raise
            
    async def log_revenue_event(self, event_type: str, amount_cents: int, 
                              currency: str, source: str, metadata: Dict[str, Any]) -> None:
        """Record revenue event in database"""
        try:
            await self.db(f"""
                INSERT INTO revenue_events (
                    id, 
                    event_type,
                    amount_cents, 
                    currency,
                    source,
                    metadata,
                    recorded_at,
                    created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{event_type.lower()}',
                    {amount_cents},
                    '{currency}',
                    '{source}',
                    '{json.dumps(metadata)}',
                    NOW(),
                    NOW()
                )
            """)
        except Exception as e:
            # TODO: Add error reporting
            raise
            
    async def create_customer(self, email: str, payment_method: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Register new customer in Stripe"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                payment_method=payment_method,
                invoice_settings={
                    'default_payment_method': payment_method
                }
            )
            
            return {
                'status': 'created',
                'customer_id': customer.id,
                'email': customer.email
            }
        except stripe.error.StripeError as e:
            raise
