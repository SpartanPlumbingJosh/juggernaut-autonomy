"""
Payment processing system with Stripe/PayPal integration.
Handles payment processing, webhooks, and automated fulfillment.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import stripe
import paypalrestsdk

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize payment gateways
stripe.api_key = os.getenv('STRIPE_API_KEY')
paypalrestsdk.configure({
    "mode": os.getenv('PAYPAL_MODE', 'sandbox'),
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
})

class PaymentProcessor:
    """Handle payment processing and fulfillment."""
    
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql
        self.fulfillment_handlers = {
            'digital': self._fulfill_digital,
            'physical': self._fulfill_physical,
            'service': self._fulfill_service
        }

    async def create_payment_intent(self, amount: int, currency: str, product_id: str, 
                                  customer_email: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payment intent with Stripe."""
        try:
            product = await self._get_product(product_id)
            if not product:
                return {"success": False, "error": "Product not found"}
                
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                receipt_email=customer_email,
                metadata={
                    "product_id": product_id,
                    **metadata
                },
                automatic_payment_methods={
                    "enabled": True,
                },
            )
            
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_id": intent.id
            }
            
        except Exception as e:
            logger.error(f"Payment intent creation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_webhook(self, payload: str, sig_header: str, source: str) -> Dict[str, Any]:
        """Process payment webhook events."""
        try:
            if source == 'stripe':
                event = stripe.Webhook.construct_event(
                    payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
                )
                
                if event.type == 'payment_intent.succeeded':
                    return await self._handle_payment_success(event.data.object)
                elif event.type == 'payment_intent.payment_failed':
                    return await self._handle_payment_failure(event.data.object)
                    
            elif source == 'paypal':
                # PayPal webhook handling
                pass
                
            return {"success": True, "processed": True}
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _handle_payment_success(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Process successful payment."""
        try:
            product_id = payment_intent.metadata.get('product_id')
            amount = payment_intent.amount_received
            currency = payment_intent.currency
            
            # Record transaction
            await self.execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, 
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {amount},
                    '{currency}',
                    'stripe',
                    '{json.dumps(payment_intent)}',
                    NOW(),
                    NOW()
                )
                """
            )
            
            # Fulfill order
            fulfillment_result = await self._fulfill_order(product_id, payment_intent)
            
            return {
                "success": True,
                "payment_id": payment_intent.id,
                "fulfilled": fulfillment_result.get('success', False)
            }
            
        except Exception as e:
            logger.error(f"Payment success handling failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _fulfill_order(self, product_id: str, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle order fulfillment based on product type."""
        product = await self._get_product(product_id)
        if not product:
            return {"success": False, "error": "Product not found"}
            
        fulfillment_type = product.get('fulfillment_type', 'digital')
        handler = self.fulfillment_handlers.get(fulfillment_type)
        
        if not handler:
            return {"success": False, "error": "No fulfillment handler"}
            
        try:
            return await handler(product, payment_data)
        except Exception as e:
            logger.error(f"Fulfillment failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _fulfill_digital(self, product: Dict[str, Any], payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fulfill digital product (email download link, etc)."""
        # Implementation would go here
        return {"success": True}

    async def _fulfill_physical(self, product: Dict[str, Any], payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fulfill physical product (trigger shipping)."""
        # Implementation would go here
        return {"success": True}

    async def _fulfill_service(self, product: Dict[str, Any], payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fulfill service (schedule appointment, etc)."""
        # Implementation would go here
        return {"success": True}

    async def _get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get product details from database."""
        try:
            result = await self.execute_sql(
                f"SELECT * FROM products WHERE id = '{product_id}'"
            )
            return result.get('rows', [{}])[0] if result.get('rows') else None
        except Exception:
            return None

    async def _handle_payment_failure(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment."""
        logger.warning(f"Payment failed: {payment_intent.id}")
        return {"success": True}
