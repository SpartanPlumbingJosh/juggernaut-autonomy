from typing import Dict, Optional, Any
from .models import Invoice, Payment
import stripe
import paddle

class PaymentProvider:
    def __init__(self, provider_name: str, config: Dict):
        self.provider = provider_name
        self.config = config
        
    async def charge_invoice(self, invoice: Invoice, payment_method: Dict) -> Dict:
        pass
        
    async def create_customer(self, customer_data: Dict) -> Dict:
        pass
        
    async def add_payment_method(self, customer_id: str, method_data: Dict) -> Dict:
        pass
        
    async def handle_webhook(self, payload: Dict) -> Dict:
        pass

class StripeProvider(PaymentProvider):
    def __init__(self, config: Dict):
        super().__init__('stripe', config)
        stripe.api_key = config['api_key']
        
    async def charge_invoice(self, invoice: Invoice, payment_method: Dict):
        return stripe.PaymentIntent.create(
            amount=invoice.amount_cents,
            currency=invoice.currency,
            customer=payment_method['customer_id'],
            payment_method=payment_method['id'],
            confirm=True
        )

class PaddleProvider(PaymentProvider):
    def __init__(self, config: Dict):
        super().__init__('paddle', config)
        paddle.set_vendor_id(config['vendor_id'])
        paddle.set_api_key(config['api_key'])
