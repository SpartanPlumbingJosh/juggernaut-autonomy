"""
Billing System - Handles payment processing, subscriptions, and invoicing.
"""
import datetime
from typing import Dict, Optional
from enum import Enum

class PaymentStatus(Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

class PaymentMethod(Enum):
    CREDIT_CARD = "credit_card"
    BANK_TRANSFER = "bank_transfer"
    PAYPAL = "paypal"

class SubscriptionPlan(Enum):
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class BillingSystem:
    def __init__(self):
        self.payment_gateway = PaymentGateway()
        self.subscription_manager = SubscriptionManager()
    
    def create_invoice(self, user_id: str, amount: float, currency: str = "USD") -> Dict:
        """Create a new invoice for a user"""
        invoice = {
            "user_id": user_id,
            "amount": amount,
            "currency": currency,
            "status": PaymentStatus.PENDING.value,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "due_date": (datetime.datetime.utcnow() + datetime.timedelta(days=30)).isoformat()
        }
        return invoice
    
    def process_payment(self, invoice: Dict, payment_method: PaymentMethod) -> Dict:
        """Process payment for an invoice"""
        result = self.payment_gateway.process(
            amount=invoice["amount"],
            currency=invoice["currency"],
            payment_method=payment_method.value
        )
        
        if result["success"]:
            invoice["status"] = PaymentStatus.SUCCEEDED.value
            invoice["paid_at"] = datetime.datetime.utcnow().isoformat()
        else:
            invoice["status"] = PaymentStatus.FAILED.value
        
        return invoice
    
    def create_subscription(self, user_id: str, plan: SubscriptionPlan) -> Dict:
        """Create a new subscription for a user"""
        return self.subscription_manager.create(user_id, plan.value)
    
    def cancel_subscription(self, subscription_id: str) -> Dict:
        """Cancel an existing subscription"""
        return self.subscription_manager.cancel(subscription_id)

class PaymentGateway:
    def process(self, amount: float, currency: str, payment_method: str) -> Dict:
        """Process payment through payment gateway"""
        # Integration with Stripe/PayPal/etc would go here
        return {"success": True, "transaction_id": "txn_12345"}

class SubscriptionManager:
    def create(self, user_id: str, plan: str) -> Dict:
        """Create a new subscription"""
        return {
            "subscription_id": "sub_12345",
            "user_id": user_id,
            "plan": plan,
            "status": "active",
            "start_date": datetime.datetime.utcnow().isoformat(),
            "next_billing_date": (datetime.datetime.utcnow() + datetime.timedelta(days=30)).isoformat()
        }
    
    def cancel(self, subscription_id: str) -> Dict:
        """Cancel a subscription"""
        return {
            "subscription_id": subscription_id,
            "status": "cancelled",
            "cancelled_at": datetime.datetime.utcnow().isoformat()
        }
