import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Callable

import stripe
import paypalrestsdk
from web3 import Web3

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        self.stripe = stripe
        self.paypal = paypalrestsdk
        self.web3 = Web3
        
        # Initialize payment providers
        self.stripe.api_key = "sk_test_..."  # Should be from config
        self.paypal.configure({
            "mode": "sandbox",  # or "live"
            "client_id": "your-client-id",
            "client_secret": "your-client-secret"
        })
        
    async def handle_stripe_webhook(self, payload: Dict[str, Any], sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook event."""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, "your-webhook-secret"
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                return await self._process_payment(
                    source="stripe",
                    payment_id=payment_intent['id'],
                    amount=int(payment_intent['amount']),
                    currency=payment_intent['currency'],
                    metadata=payment_intent.get('metadata', {})
                )
                
        except Exception as e:
            logger.error(f"Stripe webhook error: {str(e)}")
            return {"success": False, "error": str(e)}
            
        return {"success": True}

    async def handle_paypal_ipn(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process PayPal IPN notification."""
        try:
            if not self.paypal.notification.validate(payload):
                return {"success": False, "error": "Invalid IPN"}
                
            if payload['payment_status'] == 'Completed':
                return await self._process_payment(
                    source="paypal",
                    payment_id=payload['txn_id'],
                    amount=int(float(payload['mc_gross']) * 100),
                    currency=payload['mc_currency'],
                    metadata={
                        'payer_email': payload.get('payer_email'),
                        'item_name': payload.get('item_name')
                    }
                )
                
        except Exception as e:
            logger.error(f"PayPal IPN error: {str(e)}")
            return {"success": False, "error": str(e)}
            
        return {"success": True}

    async def handle_crypto_payment(self, tx_hash: str, currency: str) -> Dict[str, Any]:
        """Process cryptocurrency payment."""
        try:
            # Verify transaction on blockchain
            tx = self.web3.eth.get_transaction(tx_hash)
            if not tx or not tx['blockNumber']:
                return {"success": False, "error": "Transaction not found"}
                
            receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            if not receipt or receipt['status'] != 1:
                return {"success": False, "error": "Transaction failed"}
                
            return await self._process_payment(
                source="crypto",
                payment_id=tx_hash,
                amount=int(self.web3.fromWei(tx['value'], 'ether') * 100),
                currency=currency,
                metadata={
                    'from': tx['from'],
                    'to': tx['to'],
                    'block': tx['blockNumber']
                }
            )
            
        except Exception as e:
            logger.error(f"Crypto payment error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _process_payment(self, source: str, payment_id: str, amount: int, 
                             currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Record a confirmed payment."""
        try:
            # Check for duplicate
            res = self.execute_sql(f"""
                SELECT id FROM revenue_transactions 
                WHERE payment_id = '{payment_id}'
            """)
            if res.get('rows'):
                return {"success": False, "error": "Duplicate payment"}
                
            # Insert transaction
            self.execute_sql(f"""
                INSERT INTO revenue_transactions (
                    payment_id, source, amount_cents, currency,
                    status, metadata, recorded_at, created_at
                ) VALUES (
                    '{payment_id}', '{source}', {amount}, '{currency}',
                    'confirmed', '{json.dumps(metadata)}', NOW(), NOW()
                )
            """)
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Payment processing error: {str(e)}")
            return {"success": False, "error": str(e)}
