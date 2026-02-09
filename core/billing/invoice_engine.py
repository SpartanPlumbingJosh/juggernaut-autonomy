from typing import Dict, Any, List
from datetime import datetime
from decimal import Decimal

class InvoiceEngine:
    """Generate and send invoices."""
    
    def __init__(self):
        self.tax_rates = self._load_tax_rates()
        
    def _load_tax_rates(self) -> Dict[str, Decimal]:
        """Load tax rates by jurisdiction."""
        # TODO: Load from config/database
        return {
            "US": Decimal("0.07"),
            "EU": Decimal("0.20")
        }
        
    def generate_invoice(self, customer_id: str, charges: List[Dict[str, Any]], currency: str = "USD") -> Dict[str, Any]:
        """Generate an invoice for charges."""
        subtotal = sum(Decimal(str(charge["amount"])) for charge in charges)
        tax_rate = self.tax_rates.get("US", Decimal("0.0"))  # TODO: Get customer's jurisdiction
        tax = subtotal * tax_rate
        total = subtotal + tax
        
        return {
            "customer_id": customer_id,
            "invoice_number": f"INV-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            "invoice_date": datetime.utcnow().isoformat(),
            "currency": currency,
            "subtotal": float(subtotal),
            "tax": float(tax),
            "total": float(total),
            "charges": charges,
            "status": "pending"
        }
        
    def send_invoice(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        """Send invoice to customer."""
        # TODO: Implement email/SMS delivery
        return {
            **invoice,
            "sent_at": datetime.utcnow().isoformat(),
            "status": "sent"
        }
