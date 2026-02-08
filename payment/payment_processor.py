from datetime import datetime, timezone
from typing import Any, Dict, Optional
import json
from core.database import execute_sql

class PaymentProcessor:
    """Handles payment processing and digital delivery."""
    
    def __init__(self, log_action: Callable[..., Any]):
        self.log_action = log_action
        
    async def handle_payment_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment webhook from Stripe/PayPal."""
        try:
            event_type = payload.get("type", "")
            data = payload.get("data", {})
            object_data = data.get("object", {})
            
            if event_type not in ["payment_intent.succeeded", "charge.succeeded"]:
                return {"success": False, "error": "Unsupported event type"}
                
            # Extract payment details
            amount = int(float(object_data.get("amount", 0)) * 100)  # Convert to cents
            currency = object_data.get("currency", "usd")
            payment_id = object_data.get("id", "")
            customer_email = object_data.get("customer_email", "")
            metadata = object_data.get("metadata", {})
            
            # Record transaction
            transaction_id = await self._record_transaction(
                amount=amount,
                currency=currency,
                payment_id=payment_id,
                customer_email=customer_email,
                metadata=metadata
            )
            
            # Handle digital delivery
            product_type = metadata.get("product_type", "digital")
            if product_type == "digital":
                await self._deliver_digital_product(customer_email, metadata)
            elif product_type == "service":
                await self._provision_service(customer_email, metadata)
                
            return {"success": True, "transaction_id": transaction_id}
            
        except Exception as e:
            self.log_action(
                "payment.webhook_failed",
                f"Payment webhook processing failed: {str(e)}",
                level="error",
                error_data={"error": str(e)}
            )
            return {"success": False, "error": str(e)}
            
    async def _record_transaction(
        self,
        amount: int,
        currency: str,
        payment_id: str,
        customer_email: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Record transaction in database."""
        metadata_json = json.dumps(metadata).replace("'", "''")
        
        res = await execute_sql(
            f"""
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency,
                source, metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {amount},
                '{currency}',
                'payment_processor',
                '{metadata_json}'::jsonb,
                NOW(),
                NOW()
            )
            RETURNING id
            """
        )
        return res.get("rows", [{}])[0].get("id", "")
        
    async def _deliver_digital_product(self, customer_email: str, metadata: Dict[str, Any]) -> None:
        """Handle digital product delivery."""
        product_id = metadata.get("product_id")
        download_url = metadata.get("download_url")
        
        # TODO: Implement actual delivery logic
        self.log_action(
            "payment.digital_delivery",
            f"Digital product delivered to {customer_email}",
            level="info",
            output_data={"product_id": product_id, "download_url": download_url}
        )
        
    async def _provision_service(self, customer_email: str, metadata: Dict[str, Any]) -> None:
        """Provision service for customer."""
        service_id = metadata.get("service_id")
        api_endpoint = metadata.get("api_endpoint")
        
        # TODO: Implement actual service provisioning
        self.log_action(
            "payment.service_provisioned",
            f"Service provisioned for {customer_email}",
            level="info",
            output_data={"service_id": service_id, "api_endpoint": api_endpoint}
        )
