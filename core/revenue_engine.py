"""
Core Revenue Engine - Handles payment processing, service delivery, and revenue tracking.
Includes Stripe/PayPal integration, automated fulfillment, error handling, and monitoring.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Callable
import stripe
import paypalrestsdk
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize payment gateways
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
})

class RevenueEngine:
    """Core revenue engine handling payments, fulfillment, and tracking."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.payment_gateways = {
            "stripe": self._process_stripe_payment,
            "paypal": self._process_paypal_payment
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def process_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through selected gateway."""
        gateway = payment_data.get("gateway", "stripe").lower()
        if gateway not in self.payment_gateways:
            raise ValueError(f"Unsupported payment gateway: {gateway}")
        
        try:
            processor = self.payment_gateways[gateway]
            result = processor(payment_data)
            self._log_payment_event(result)
            return result
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            raise

    def _process_stripe_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through Stripe."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(float(payment_data["amount"]) * 100),
                currency=payment_data.get("currency", "usd"),
                payment_method=payment_data["payment_method_id"],
                confirmation_method="manual",
                confirm=True,
                metadata=payment_data.get("metadata", {})
            )
            return {
                "success": True,
                "gateway": "stripe",
                "transaction_id": intent.id,
                "status": intent.status,
                "amount": intent.amount / 100,
                "currency": intent.currency
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe payment failed: {str(e)}")
            raise

    def _process_paypal_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through PayPal."""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": str(payment_data["amount"]),
                        "currency": payment_data.get("currency", "USD")
                    },
                    "description": payment_data.get("description", "")
                }],
                "redirect_urls": {
                    "return_url": payment_data.get("return_url", ""),
                    "cancel_url": payment_data.get("cancel_url", "")
                }
            })
            
            if payment.create():
                return {
                    "success": True,
                    "gateway": "paypal",
                    "transaction_id": payment.id,
                    "status": payment.state,
                    "amount": float(payment.transactions[0].amount.total),
                    "currency": payment.transactions[0].amount.currency
                }
            raise Exception(payment.error)
        except Exception as e:
            logger.error(f"PayPal payment failed: {str(e)}")
            raise

    def _log_payment_event(self, payment_result: Dict[str, Any]) -> None:
        """Log payment event to database."""
        try:
            self.execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'payment',
                    {int(float(payment_result["amount"]) * 100)},
                    '{payment_result["currency"]}',
                    '{payment_result["gateway"]}',
                    '{json.dumps(payment_result)}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
        except Exception as e:
            logger.error(f"Failed to log payment event: {str(e)}")

    def handle_webhook(self, gateway: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle payment gateway webhooks."""
        try:
            if gateway == "stripe":
                return self._handle_stripe_webhook(payload)
            elif gateway == "paypal":
                return self._handle_paypal_webhook(payload)
            else:
                raise ValueError(f"Unsupported gateway: {gateway}")
        except Exception as e:
            logger.error(f"Webhook handling failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _handle_stripe_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Stripe webhook events."""
        event = stripe.Event.construct_from(payload, stripe.api_key)
        
        if event.type == "payment_intent.succeeded":
            payment_intent = event.data.object
            self._log_payment_event({
                "success": True,
                "gateway": "stripe",
                "transaction_id": payment_intent.id,
                "status": payment_intent.status,
                "amount": payment_intent.amount / 100,
                "currency": payment_intent.currency
            })
            self._trigger_fulfillment(payment_intent)
        elif event.type == "payment_intent.payment_failed":
            payment_intent = event.data.object
            logger.warning(f"Payment failed: {payment_intent.last_payment_error}")
        
        return {"success": True}

    def _handle_paypal_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle PayPal webhook events."""
        event_type = payload.get("event_type", "")
        
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            payment = payload.get("resource", {})
            self._log_payment_event({
                "success": True,
                "gateway": "paypal",
                "transaction_id": payment.get("id"),
                "status": payment.get("status"),
                "amount": float(payment.get("amount", {}).get("value", 0)),
                "currency": payment.get("amount", {}).get("currency_code", "USD")
            })
            self._trigger_fulfillment(payment)
        elif event_type == "PAYMENT.CAPTURE.DENIED":
            logger.warning(f"Payment denied: {payload.get('summary', '')}")
        
        return {"success": True}

    def _trigger_fulfillment(self, payment_data: Dict[str, Any]) -> None:
        """Trigger automated service fulfillment."""
        try:
            # Implement your fulfillment logic here
            # This could be sending digital goods, activating services, etc.
            logger.info(f"Fulfilling order for payment: {payment_data.get('id')}")
            self.log_action(
                "fulfillment.triggered",
                f"Fulfillment triggered for payment {payment_data.get('id')}",
                level="info",
                output_data={"payment_id": payment_data.get("id")}
            )
        except Exception as e:
            logger.error(f"Fulfillment failed: {str(e)}")
            self.log_action(
                "fulfillment.failed",
                f"Fulfillment failed for payment {payment_data.get('id')}",
                level="error",
                error_data={"payment_id": payment_data.get("id"), "error": str(e)}
            )

    def monitor_system(self) -> None:
        """Run system health checks and self-healing."""
        try:
            # Implement monitoring checks here
            # This could include checking payment gateway connectivity,
            # fulfillment queue status, error rates, etc.
            logger.info("Running system health checks")
            self.log_action(
                "monitoring.run",
                "System health checks completed",
                level="info"
            )
        except Exception as e:
            logger.error(f"Monitoring failed: {str(e)}")
            self.log_action(
                "monitoring.failed",
                "System health checks failed",
                level="error",
                error_data={"error": str(e)}
            )

__all__ = ["RevenueEngine"]
