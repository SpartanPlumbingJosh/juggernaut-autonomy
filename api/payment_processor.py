"""
Payment Processor - Handles payment integrations and transaction logging.
Supports Stripe, PayPal, and crypto payments.
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, Optional

import stripe
import paypalrestsdk
from web3 import Web3

# Initialize payment providers
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id": os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret": os.getenv("PAYPAL_SECRET")
})

# Initialize Web3 for crypto payments
WEB3_PROVIDER = os.getenv("WEB3_PROVIDER")
web3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER)) if WEB3_PROVIDER else None

async def process_payment(payment_method: str, payment_details: Dict, amount: float, currency: str = "USD") -> Dict:
    """
    Process payment using the specified method.
    Returns: {
        "success": bool,
        "transaction_id": str,
        "amount": float,
        "currency": str,
        "metadata": Dict
    }
    """
    try:
        amount_cents = int(amount * 100)
        metadata = {
            "payment_method": payment_method,
            "currency": currency,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }

        if payment_method == "stripe":
            # Process Stripe payment
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                payment_method=payment_details.get("payment_method_id"),
                confirmation_method="manual",
                confirm=True,
                metadata=metadata
            )
            if intent.status == "succeeded":
                return {
                    "success": True,
                    "transaction_id": intent.id,
                    "amount": amount,
                    "currency": currency,
                    "metadata": metadata
                }

        elif payment_method == "paypal":
            # Process PayPal payment
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": str(amount),
                        "currency": currency
                    }
                }],
                "redirect_urls": {
                    "return_url": os.getenv("PAYPAL_RETURN_URL"),
                    "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
                }
            })
            if payment.create():
                return {
                    "success": True,
                    "transaction_id": payment.id,
                    "amount": amount,
                    "currency": currency,
                    "metadata": metadata
                }

        elif payment_method == "crypto" and web3:
            # Process crypto payment
            tx_hash = web3.eth.send_transaction({
                "to": payment_details.get("to_address"),
                "from": payment_details.get("from_address"),
                "value": web3.toWei(amount, "ether"),
                "gas": 21000
            })
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            if receipt.status == 1:
                return {
                    "success": True,
                    "transaction_id": tx_hash.hex(),
                    "amount": amount,
                    "currency": "ETH",
                    "metadata": metadata
                }

        return {"success": False, "error": "Payment processing failed"}

    except Exception as e:
        return {"success": False, "error": str(e)}

async def log_transaction_to_db(execute_sql: Callable[[str], Dict], transaction_data: Dict) -> bool:
    """
    Log transaction to revenue_transactions table.
    """
    try:
        sql = f"""
        INSERT INTO revenue_transactions (
            id, transaction_id, amount_cents, currency,
            payment_method, metadata, recorded_at
        ) VALUES (
            gen_random_uuid(),
            '{transaction_data["transaction_id"]}',
            {int(transaction_data["amount"] * 100)},
            '{transaction_data["currency"]}',
            '{transaction_data["metadata"]["payment_method"]}',
            '{json.dumps(transaction_data["metadata"])}',
            NOW()
        )
        """
        await execute_sql(sql)
        return True
    except Exception:
        return False
