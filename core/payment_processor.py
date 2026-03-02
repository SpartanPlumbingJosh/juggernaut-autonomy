import os
import stripe
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from decimal import Decimal
import logging
from web3 import Web3

logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Handles payment processing across multiple payment methods."""
    
    def __init__(self):
        self.stripe = stripe
        self.stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.web3 = Web3(Web3.HTTPProvider(os.getenv('ETHEREUM_NODE_URL')))
        self.circuit_breaker = False
        self.max_daily_loss = Decimal(os.getenv('MAX_DAILY_LOSS', '1000'))
        self.today_loss = Decimal('0')
        
    async def process_payment(self, 
                            amount: Decimal,
                            currency: str,
                            payment_method: str,
                            metadata: Dict) -> Tuple[bool, Optional[str]]:
        """Process payment using selected method."""
        
        if self.circuit_breaker:
            return False, "Circuit breaker active - payments suspended"
            
        try:
            if payment_method == 'stripe':
                return await self._process_stripe(amount, currency, metadata)
            elif payment_method == 'crypto':
                return await self._process_crypto(amount, currency, metadata)
            else:
                return False, "Unsupported payment method"
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            self._check_loss_threshold()
            return False, str(e)
            
    async def _process_stripe(self, 
                            amount: Decimal,
                            currency: str,
                            metadata: Dict) -> Tuple[bool, Optional[str]]:
        """Process payment via Stripe."""
        try:
            payment_intent = self.stripe.PaymentIntent.create(
                amount=int(amount * 100),
                currency=currency,
                metadata=metadata
            )
            return True, payment_intent.id
        except stripe.error.CardError as e:
            logger.error(f"Stripe card error: {str(e)}")
            return False, str(e)
            
    async def _process_crypto(self,
                            amount: Decimal,
                            currency: str,
                            metadata: Dict) -> Tuple[bool, Optional[str]]:
        """Process cryptocurrency payment."""
        try:
            # Convert amount to wei
            wei_amount = self.web3.toWei(amount, 'ether')
            tx_hash = self.web3.eth.send_transaction({
                'to': metadata['wallet_address'],
                'value': wei_amount,
                'gas': 21000,
                'gasPrice': self.web3.eth.gas_price
            })
            return True, tx_hash.hex()
        except Exception as e:
            logger.error(f"Crypto payment failed: {str(e)}")
            return False, str(e)
            
    def _check_loss_threshold(self):
        """Check if daily loss threshold has been exceeded."""
        today = datetime.now(timezone.utc).date()
        if self.last_loss_check != today:
            self.today_loss = Decimal('0')
            self.last_loss_check = today
            
        if self.today_loss >= self.max_daily_loss:
            self.circuit_breaker = True
            logger.critical("Daily loss threshold exceeded - activating circuit breaker")
            
    def reset_circuit_breaker(self):
        """Manually reset the circuit breaker."""
        self.circuit_breaker = False
        logger.info("Circuit breaker reset")
