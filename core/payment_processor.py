import os
import stripe
import logging
from datetime import datetime
from typing import Dict, Any, Optional

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Handle payment processing and automated service delivery."""
    
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
    
    def create_payment_intent(self, amount: int, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create Stripe payment intent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata,
                automatic_payment_methods={"enabled": True},
            )
            self.log_action(
                "payment.intent_created",
                f"Created payment intent for {amount/100:.2f}{currency}",
                level="info",
                output_data={"amount": amount, "currency": currency}
            )
            return {"success": True, "client_secret": intent.client_secret}
        except Exception as e:
            logger.error(f"Payment intent creation failed: {str(e)}")
            self.log_action(
                "payment.failed",
                f"Payment intent creation failed: {str(e)}",
                level="error",
                error_data={"error": str(e)}
            )
            return {"success": False, "error": str(e)}
    
    def fulfill_order(self, payment_intent_id: str) -> Dict[str, Any]:
        """Handle successful payment and deliver service."""
        try:
            # Get payment details from Stripe
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            # Record transaction
            self.execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {intent.amount},
                    '{intent.currency}',
                    'stripe',
                    '{json.dumps(intent.metadata)}'::jsonb,
                    NOW(),
                    NOW()
                )
                """
            )
            
            # TODO: Add your service delivery logic here
            # This could be API calls, file generation, email sending, etc.
            # Example:
            # self.deliver_service(intent.metadata.get('product_id'))
            
            self.log_action(
                "payment.fulfilled",
                f"Payment fulfilled for {intent.amount/100:.2f}{intent.currency}",
                level="info",
                output_data={"amount": intent.amount, "currency": intent.currency}
            )
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Order fulfillment failed: {str(e)}")
            self.log_action(
                "payment.fulfillment_failed",
                f"Order fulfillment failed: {str(e)}",
                level="error",
                error_data={"error": str(e)}
            )
            return {"success": False, "error": str(e)}
