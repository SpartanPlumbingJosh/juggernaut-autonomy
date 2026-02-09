from fastapi import Request, HTTPException
from datetime import datetime, timezone
from typing import Dict, Any
from services.payment_processor import PaymentProcessor
from core.database import query_db

class WebhookHandler:
    def __init__(self, config: Dict[str, Any]):
        self.payment_processor = PaymentProcessor(config)
        self.stripe_endpoint_secret = config.get("stripe_endpoint_secret")
        self.paypal_webhook_id = config.get("paypal_webhook_id")

    async def handle_stripe_webhook(self, request: Request) -> Dict[str, Any]:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.stripe_endpoint_secret
            )
            
            if event["type"] == "payment_intent.succeeded":
                payment_intent = event["data"]["object"]
                await self._process_payment(payment_intent, "stripe")
                
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def handle_paypal_webhook(self, request: Request) -> Dict[str, Any]:
        payload = await request.json()
        headers = request.headers
        
        try:
            webhook_event = paypalrestsdk.WebhookEvent.verify(
                headers,
                payload,
                self.paypal_webhook_id
            )
            
            if webhook_event.event_type == "PAYMENT.SALE.COMPLETED":
                payment = webhook_event.resource
                await self._process_payment(payment, "paypal")
                
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def _process_payment(self, payment_data: Dict[str, Any], source: str) -> Dict[str, Any]:
        metadata = payment_data.get("metadata", {})
        amount = payment_data.get("amount") / 100 if source == "stripe" else float(payment_data.get("amount", {}).get("total", 0))
        
        transaction_data = {
            "experiment_id": metadata.get("experiment_id"),
            "amount": amount,
            "currency": payment_data.get("currency", "usd"),
            "source": source,
            "metadata": {
                "payment_id": payment_data.get("id"),
                "customer_email": metadata.get("customer_email"),
                "service_type": metadata.get("service_type")
            }
        }
        
        return await self.payment_processor.record_transaction(transaction_data)
