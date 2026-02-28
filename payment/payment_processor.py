"""
Payment Processor - Handle payment integrations and revenue recognition.

Features:
- Stripe integration for credit card/subscription payments
- PayPal integration for alternative payments
- Automated invoicing
- Revenue recognition tracking
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, Optional, List

import stripe
from paypalrestsdk import Payment

# Configure payment providers
stripe.api_key = os.getenv('STRIPE_API_KEY')
paypal_client_id = os.getenv('PAYPAL_CLIENT_ID')
paypal_secret = os.getenv('PAYPAL_SECRET')

class PaymentProcessor:
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    def create_stripe_customer(self, user_data: Dict) -> Optional[str]:
        try:
            customer = stripe.Customer.create(
                email=user_data['email'],
                name=user_data.get('name'),
                metadata={'user_id': user_data['id']}
            )
            return customer.id
        except Exception as e:
            self.log_action('payment.stripe_error', f"Failed to create Stripe customer: {str(e)}", level='error')
            return None
            
    def create_stripe_subscription(self, customer_id: str, plan_data: Dict) -> Optional[Dict]:
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_data['stripe_price_id']}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            return {
                'subscription_id': subscription.id,
                'payment_intent': subscription.latest_invoice.payment_intent,
                'status': subscription.status
            }
        except Exception as e:
            self.log_action('payment.stripe_error', f"Failed to create subscription: {str(e)}", level='error')
            return None
            
    def create_paypal_payment(self, amount: float, currency: str, description: str) -> Optional[Dict]:
        try:
            payment = Payment({
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {
                        "total": str(amount),
                        "currency": currency
                    },
                    "description": description
                }],
                "redirect_urls": {
                    "return_url": os.getenv('PAYPAL_RETURN_URL'),
                    "cancel_url": os.getenv('PAYPAL_CANCEL_URL')
                }
            })
            if payment.create():
                return {
                    'payment_id': payment.id,
                    'approval_url': next(link.href for link in payment.links if link.method == 'REDIRECT')
                }
            return None
        except Exception as e:
            self.log_action('payment.paypal_error', f"Failed to create PayPal payment: {str(e)}", level='error')
            return None
            
    def record_revenue_event(self, event_data: Dict) -> bool:
        """Record revenue event with proper accrual accounting"""
        try:
            now = datetime.now(timezone.utc)
            recognition_date = now
            if event_data.get('revenue_recognition_mode') == 'deferred':
                recognition_date = now + timedelta(days=30)
                
            self.execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency, source,
                    description, recorded_at, recognized_at, attribution,
                    metadata, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {int(event_data['amount_cents'])},
                    '{event_data['currency']}',
                    'stripe',
                    '{event_data.get('description', '').replace("'", "''")}',
                    '{now.isoformat()}',
                    '{recognition_date.isoformat()}',
                    '{json.dumps(event_data.get('attribution', {}))}',
                    '{json.dumps(event_data.get('metadata', {}))}',
                    NOW()
                )
                """
            )
            return True
        except Exception as e:
            self.log_action('payment.recording_error', f"Failed to record revenue: {str(e)}", level='error')
            return False
