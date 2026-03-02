from datetime import datetime, timedelta
from typing import Dict
import hashlib

def generate_invoice_number() -> str:
    """Create unique invoice number."""
    now = datetime.utcnow()
    prefix = now.strftime("%Y%m")
    unique = hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:8]
    return f"INV-{prefix}-{unique}"

def calculate_prorate_amount(
    start_date: datetime,
    end_date: datetime,
    current_sub_end: datetime,
    amount_cents: int
) -> int:
    """Calculate prorated amount for subscription changes."""
    remaining_days = (current_sub_end - start_date).days
    total_days = (end_date - start_date).days
    return int((remaining_days / total_days) * amount_cents)

def validate_billing_address(address: Dict) -> bool:
    """Validate billing address format."""
    required = ['line1', 'city', 'country', 'postal_code']
    return all(address.get(field) for field in required)
