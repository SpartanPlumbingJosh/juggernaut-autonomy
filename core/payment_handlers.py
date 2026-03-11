import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
from paypalhttp import HttpResponse

from core.database import execute_sql
from core.utils import generate_idempotency_key

logger = logging.getLogger(__name__)

class PaymentHandler:
    """Base class for payment processors."""
    
    def __init__(self):
        self.webhook_secret = None
        self.test_mode = False
        
    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature."""
        raise NotImplementedError
        
    def handle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment event."""
        raise NotImplementedError
        
    def _record_transaction(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record transaction in database."""
        idempotency_key = generate_idempotency_key(event_data)
        
        try:
            existing = execute_sql(
                f"""
                SELECT id 
                FROM revenue_events
                WHERE idempotency_key = '{idempotency_key}'
                LIMIT 1
                """
            )
            if existing.get("rows"):
                return {"success": True, "existing": True}
                
            execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, idempotency_key, event_type, amount_cents,
                    currency, source, metadata, recorded_at,
                    created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{idempotency_key}',
                    '{event_data['event_type']}',
                    {int(event_data['amount_cents'])},
                    '{event_data['currency']}',
                    '{event_data['source']}',
                    '{json.dumps(event_data['metadata'])}'::jsonb,
                    '{event_data['recorded_at']}',
                    NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to record transaction: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def _handle_payment_success(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment."""
        # Record transaction
        result = self._record_transaction(event_data)
        if not result.get("success"):
            return result
            
        # Trigger service delivery
        self._deliver_service(event_data)
        return {"success": True}
        
    def _deliver_service(self, event_data: Dict[str, Any]) -> None:
        """Deliver purchased service."""
        # Implement service delivery logic
        pass
        
    def _handle_refund(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle refund event."""
        result = self._record_transaction(event_data)
        if not result.get("success"):
            return result
            
        # Trigger service revocation
        self._revoke_service(event_data)
        return {"success": True}
        
    def _revoke_service(self, event_data: Dict[str, Any]) -> None:
        """Revoke service due to refund."""
        # Implement service revocation logic
        pass

class StripeHandler(PaymentHandler):
    """Handle Stripe payments."""
    
    def __init__(self, api_key: str, webhook_secret: str):
        super().__init__()
        self.webhook_secret = webhook_secret
        stripe.api_key = api_key
        
    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return True
        except Exception as e:
            logger.error(f"Stripe webhook verification failed: {str(e)}")
            return False
            
    def handle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        event_type = event['type']
        
        if event_type == 'payment_intent.succeeded':
            return self._handle_payment_success({
                'event_type': 'revenue',
                'amount_cents': event['data']['object']['amount'],
                'currency': event['data']['object']['currency'],
                'source': 'stripe',
                'metadata': event['data']['object'],
                'recorded_at': datetime.fromtimestamp(
                    event['data']['object']['created'], tz=timezone.utc
                ).isoformat()
            })
        elif event_type == 'charge.refunded':
            return self._handle_refund({
                'event_type': 'refund',
                'amount_cents': -event['data']['object']['amount_refunded'],
                'currency': event['data']['object']['currency'],
                'source': 'stripe',
                'metadata': event['data']['object'],
                'recorded_at': datetime.fromtimestamp(
                    event['data']['object']['created'], tz=timezone.utc
                ).isoformat()
            })
        else:
            return {"success": True}

class PayPalHandler(PaymentHandler):
    """Handle PayPal payments."""
    
    def __init__(self, client_id: str, client_secret: str, webhook_id: str):
        super().__init__()
        self.webhook_id = webhook_id
        
    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        try:
            # PayPal webhook verification logic
            return True
        except Exception as e:
            logger.error(f"PayPal webhook verification failed: {str(e)}")
            return False
            
    def handle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        event_type = event['event_type']
        
        if event_type == 'PAYMENT.CAPTURE.COMPLETED':
            return self._handle_payment_success({
                'event_type': 'revenue',
                'amount_cents': int(float(event['resource']['amount']['value']) * 100),
                'currency': event['resource']['amount']['currency_code'],
                'source': 'paypal',
                'metadata': event['resource'],
                'recorded_at': event['create_time']
            })
        elif event_type == 'PAYMENT.CAPTURE.REFUNDED':
            return self._handle_refund({
                'event_type': 'refund',
                'amount_cents': -int(float(event['resource']['amount']['value']) * 100),
                'currency': event['resource']['amount']['currency_code'],
                'source': 'paypal',
                'metadata': event['resource'],
                'recorded_at': event['create_time']
            })
        else:
            return {"success": True}
