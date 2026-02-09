from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum

class PaymentStatus(str, Enum):
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'
    REFUNDED = 'refunded'

class OrderStatus(str, Enum):
    CREATED = 'created'
    PROCESSING = 'processing'
    FULFILLED = 'fulfilled'
    CANCELLED = 'cancelled'

class Customer:
    def __init__(self, email: str, name: Optional[str] = None):
        self.email = email
        self.name = name
        self.created_at = datetime.utcnow()
        self.orders: List[Order] = []

class Order:
    def __init__(self, product_id: str, customer: Customer):
        self.id: str = f"ord_{datetime.utcnow().timestamp()}"
        self.product_id = product_id
        self.customer = customer
        self.created_at = datetime.utcnow()
        self.status: OrderStatus = OrderStatus.CREATED
        self.payment_status: PaymentStatus = PaymentStatus.PENDING
        self.payment_id: Optional[str] = None
        self.amount: Optional[int] = None
        self.currency: Optional[str] = None
        self.metadata: Dict = {}

class Product:
    def __init__(self, id: str, name: str, price: int, currency: str = 'usd'):
        self.id = id
        self.name = name
        self.price = price
        self.currency = currency
