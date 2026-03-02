"""
Payment data models and ORM definitions.
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

class PaymentMethodType(Enum):
    CARD = "card"
    ACH = "ach"
    SEPA = "sepa"
    WIRE = "wire"
    CRYPTO = "crypto"

class BillingFrequency(Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    TRIALING = "trialing"

class InvoiceStatus(Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"

class PaymentGateway(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"
    BRAINTREE = "braintree"

class RevenueRecognitionRule(Enum):
    IMMEDIATE = "immediate"
    DEFERRED = "deferred"
    USAGE = "usage"
