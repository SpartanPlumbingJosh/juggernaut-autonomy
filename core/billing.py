import stripe
from typing import Dict, Optional
from datetime import datetime
import json
import logging

class BillingManager:
    """Handle automated billing operations with Stripe."""
    
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.logger = logging.getLogger(__name__)
        
    def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {"success": True, "customer_id": customer.id}
        except Exception as e:
            self.logger.error(f"Failed to create customer: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        quantity: int = 1,
        trial_days: int = 0
    ) -> Dict:
        """Create a subscription with Stripe."""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{
                    'price': price_id,
                    'quantity': quantity
                }],
                trial_period_days=trial_days
            )
            return {"success": True, "subscription_id": subscription.id}
        except Exception as e:
            self.logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def handle_webhook(self, payload: str, sig_header: str, webhook_secret: str) -> Dict:
        """Process Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            event_type = event['type']
            self.logger.info(f"Processing Stripe event: {event_type}")
            
            if event_type == 'invoice.paid':
                return self._handle_invoice_paid(event)
            elif event_type == 'invoice.payment_failed':
                return self._handle_payment_failed(event)
            elif event_type == 'customer.subscription.deleted':
                return self._handle_subscription_canceled(event)
                
            return {"success": True, "status": "event_not_handled"}
        except Exception as e:
            self.logger.error(f"Webhook error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _handle_invoice_paid(self, event: Dict) -> Dict:
        """Trigger fulfillment when payment is received."""
        invoice = event['data']['object']
        customer_id = invoice['customer']
        amount_paid = invoice['amount_paid']
        
        # Trigger fulfillment pipeline
        try:
            # Assuming we have a fulfillment service
            from core.fulfillment import FulfillmentManager
            fm = FulfillmentManager()
            fulfillment = fm.process_payment(customer_id, amount_paid)
            
            if not fulfillment.get('success'):
                raise Exception(fulfillment.get('error', 'Fulfillment failed'))
                
            return {
                "success": True,
                "status": "fulfillment_triggered",
                "customer_id": customer_id,
                "amount": amount_paid
            }
        except Exception as e:
            self.logger.error(f"Fulfillment failed for customer {customer_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "customer_id": customer_id
            }
    
    def _handle_payment_failed(self, event: Dict) -> Dict:
        """Handle failed payment scenarios."""
        invoice = event['data']['object']
        customer_id = invoice['customer']
        self.logger.warning(f"Payment failed for customer {customer_id}")
        return {"success": True, "status": "payment_failure_handled"}
    
    def _handle_subscription_canceled(self, event: Dict) -> Dict:
        """Handle subscription cancellations."""
        subscription = event['data']['object']
        customer_id = subscription['customer']
        self.logger.info(f"Subscription canceled for customer {customer_id}")
        return {"success": True, "status": "subscription_canceled"}
