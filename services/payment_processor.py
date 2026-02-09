import os
import stripe
import json
from datetime import datetime
from typing import Dict, Optional, Tuple

class PaymentProcessor:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    async def create_payment_intent(
        self,
        amount: int,
        currency: str = 'usd',
        metadata: Optional[Dict] = None,
        customer_id: Optional[str] = None
    ) -> Tuple[bool, Dict]:
        """Create a Stripe payment intent"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata or {},
                customer=customer_id,
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            return True, {
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'amount': intent.amount,
                'currency': intent.currency
            }
        except Exception as e:
            return False, {'error': str(e)}

    async def handle_webhook(self, payload: bytes, sig_header: str) -> Tuple[bool, Dict]:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                return True, {
                    'event': 'payment_succeeded',
                    'payment_intent_id': payment_intent['id'],
                    'amount': payment_intent['amount'],
                    'metadata': payment_intent.get('metadata', {})
                }
            
            return True, {'event': event['type'], 'handled': False}
            
        except ValueError as e:
            return False, {'error': 'Invalid payload'}
        except stripe.error.SignatureVerificationError as e:
            return False, {'error': 'Invalid signature'}
        except Exception as e:
            return False, {'error': str(e)}

    async def create_invoice(self, customer_id: str, amount: int, description: str) -> Tuple[bool, Dict]:
        """Create and send invoice to customer"""
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                auto_advance=True,
                collection_method='send_invoice',
                days_until_due=30,
                description=description
            )
            
            stripe.InvoiceItem.create(
                customer=customer_id,
                invoice=invoice.id,
                amount=amount,
                currency='usd',
                description=description
            )
            
            sent_invoice = stripe.Invoice.send_invoice(invoice.id)
            return True, {
                'invoice_id': sent_invoice.id,
                'invoice_pdf': sent_invoice.invoice_pdf,
                'status': sent_invoice.status
            }
        except Exception as e:
            return False, {'error': str(e)}
