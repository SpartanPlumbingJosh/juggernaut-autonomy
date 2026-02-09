"""PayPal payment processing integration."""
from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment
from paypalcheckoutsdk.orders import OrdersCreateRequest
from datetime import datetime
import os
from typing import Dict, Optional, Tuple

from payment_processors.base_processor import BasePaymentProcessor

class PayPalProcessor(BasePaymentProcessor):
    def __init__(self):
        client_id = os.getenv('PAYPAL_CLIENT_ID')
        client_secret = os.getenv('PAYPAL_CLIENT_SECRET')
        
        if os.getenv('PAYPAL_ENVIRONMENT') == 'production':
            self.env = PayPalEnvironment(client_id, client_secret)
        else:
            self.env = SandboxEnvironment(client_id, client_secret)
            
        self.client = PayPalHttpClient(self.env)

    async def create_order(
        self,
        amount: float,
        currency: str,
        description: str,
        customer_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Create PayPal order for payment."""
        request = OrdersCreateRequest()
        request.request_body({
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {
                    "currency_code": currency,
                    "value": f"{amount:.2f}"
                },
                "description": description,
                "custom_id": customer_id
            }]
        })

        try:
            response = self.client.execute(request)
            return response.result.id, None
        except Exception as e:
            return None, str(e)

    async def record_payment_event(
        self,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record PayPal payment event in our revenue tracking system."""
        if event_data.get('event_type') != 'CHECKOUT.ORDER.APPROVED':
            return
            
        purchase_unit = event_data.get('resource', {}).get('purchase_units', [{}])[0]
        amount = purchase_unit.get('amount', {}).get('value', '0')
        
        return {
            'event_type': 'revenue',
            'amount_cents': int(float(amount) * 100),
            'currency': purchase_unit.get('amount', {}).get('currency_code', 'USD'),
            'source': 'paypal',
            'recorded_at': datetime.utcnow().isoformat(),
            'metadata': {
                'paypal_order_id': event_data.get('resource', {}).get('id'),
            }
        }
