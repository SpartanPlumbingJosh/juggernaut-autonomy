"""
Payment processing and subscription management.
Integrates with Stripe and PayPal APIs.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List

import stripe
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
        self.stripe = stripe

    def create_customer(self, email: str, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new customer in payment system."""
        try:
            customer = self.stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {
                "success": True,
                "customer_id": customer.id,
                "payment_method": "stripe"
            }
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}")
            return {"success": False, "error": str(e)}

    def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        payment_method_id: str,
        trial_days: int = 0
    ) -> Dict:
        """Create a new subscription."""
        try:
            # Attach payment method
            self.stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )

            # Set as default payment method
            self.stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    "default_payment_method": payment_method_id
                }
            )

            # Create subscription
            subscription = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{"plan": plan_id}],
                trial_period_days=trial_days
            )

            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end
            }
        except Exception as e:
            logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}

    def generate_invoice(self, subscription_id: str) -> Dict:
        """Generate invoice for subscription."""
        try:
            invoice = self.stripe.Invoice.create(
                subscription=subscription_id,
                auto_advance=True
            )
            invoice = self.stripe.Invoice.finalize_invoice(invoice.id)
            
            return {
                "success": True,
                "invoice_id": invoice.id,
                "invoice_pdf": invoice.invoice_pdf,
                "amount_due": invoice.amount_due,
                "status": invoice.status
            }
        except Exception as e:
            logger.error(f"Failed to generate invoice: {str(e)}")
            return {"success": False, "error": str(e)}

    def process_payment(self, amount: int, currency: str, payment_method_id: str, customer_id: Optional[str] = None) -> Dict:
        """Process one-time payment."""
        try:
            intent = self.stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                payment_method=payment_method_id,
                customer=customer_id,
                confirm=True,
                off_session=True
            )
            
            return {
                "success": True,
                "payment_id": intent.id,
                "amount_received": intent.amount_received,
                "status": intent.status
            }
        except Exception as e:
            logger.error(f"Failed to process payment: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_upcoming_invoices(self, days: int = 7) -> List[Dict]:
        """Get invoices that will be generated in next X days."""
        try:
            now = datetime.now()
            end_date = now + timedelta(days=days)
            
            invoices = self.stripe.Invoice.upcoming(
                subscription_items=[],
                subscription_billing_cycle_anchor=now,
                subscription_proration_behavior='none',
                subscription_trial_end=end_date
            )
            
            return [{
                "customer_id": inv.customer,
                "amount_due": inv.amount_due,
                "due_date": inv.due_date,
                "invoice_pdf": inv.invoice_pdf
            } for inv in invoices]
        except Exception as e:
            logger.error(f"Failed to get upcoming invoices: {str(e)}")
            return []
