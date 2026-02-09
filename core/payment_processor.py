import os
import stripe
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
logger = logging.getLogger(__name__)

@dataclass
class PaymentConfig:
    """Configuration for payment processing"""
    retry_attempts: int = 3
    retry_delay: int = 60  # seconds
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 300  # seconds

class PaymentProcessor:
    """Handles payment processing with circuit breakers and retries"""
    
    def __init__(self):
        self.failure_count = 0
        self.circuit_open = False
        self.last_failure_time = None
        self.config = PaymentConfig()
        
    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker should be tripped"""
        if self.circuit_open:
            if datetime.now() - self.last_failure_time > timedelta(
                seconds=self.config.circuit_breaker_timeout
            ):
                self.circuit_open = False
                logger.info("Circuit breaker reset")
            else:
                return True
        return False
        
    def _record_failure(self):
        """Record a payment failure and trip circuit breaker if needed"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        if self.failure_count >= self.config.circuit_breaker_threshold:
            self.circuit_open = True
            logger.warning("Circuit breaker tripped due to payment failures")
            
    def create_payment_intent(self, amount: int, currency: str, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a payment intent with retries and circuit breaker"""
        if self._check_circuit_breaker():
            logger.error("Payment processing blocked by circuit breaker")
            return None
            
        for attempt in range(self.config.retry_attempts):
            try:
                intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency=currency,
                    metadata=metadata,
                    payment_method_types=['card'],
                    capture_method='automatic'
                )
                self.failure_count = 0
                return intent
            except stripe.error.StripeError as e:
                logger.error(f"Payment attempt {attempt + 1} failed: {str(e)}")
                self._record_failure()
                time.sleep(self.config.retry_delay)
                
        logger.error("All payment attempts failed")
        return None

    def handle_webhook(self, payload: str, sig_header: str) -> bool:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
            )
            
            if event['type'] == 'payment_intent.succeeded':
                self._handle_payment_success(event['data']['object'])
            elif event['type'] == 'payment_intent.payment_failed':
                self._handle_payment_failure(event['data']['object'])
            elif event['type'] == 'invoice.payment_failed':
                self._handle_dunning(event['data']['object'])
                
            return True
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return False
            
    def _handle_payment_success(self, payment_intent: Dict[str, Any]):
        """Handle successful payment"""
        logger.info(f"Payment succeeded: {payment_intent['id']}")
        # TODO: Trigger fulfillment workflow
        
    def _handle_payment_failure(self, payment_intent: Dict[str, Any]):
        """Handle payment failure"""
        logger.warning(f"Payment failed: {payment_intent['id']}")
        self._record_failure()
        # TODO: Trigger dunning workflow
        
    def _handle_dunning(self, invoice: Dict[str, Any]):
        """Handle failed invoice payment"""
        logger.warning(f"Invoice payment failed: {invoice['id']}")
        # TODO: Implement dunning management logic
