import os
from datetime import datetime
from typing import Dict, Optional
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from core.database import query_db

class InvoiceManager:
    """Handle automated invoice generation and delivery."""
    
    def __init__(self):
        self.template_dir = os.path.join(os.path.dirname(__file__), "templates")
        self.env = Environment(loader=FileSystemLoader(self.template_dir))
        
    async def generate_invoice(self, transaction_id: str) -> Optional[str]:
        """Generate PDF invoice for a transaction."""
        try:
            # Get transaction details
            res = await query_db(
                f"""
                SELECT 
                    id, amount_cents, currency, source, metadata,
                    recorded_at, created_at
                FROM revenue_events
                WHERE id = '{transaction_id}'
                LIMIT 1
                """
            )
            transaction = res.get("rows", [{}])[0]
            if not transaction:
                return None
                
            # Render invoice template
            template = self.env.get_template("invoice.html")
            html = template.render({
                "transaction": transaction,
                "invoice_date": datetime.now().strftime("%Y-%m-%d"),
                "invoice_number": f"INV-{transaction['id'][:8].upper()}"
            })
            
            # Generate PDF
            pdf = HTML(string=html).write_pdf()
            return pdf
            
        except Exception as e:
            print(f"Error generating invoice: {str(e)}")
            return None
            
    async def send_invoice(self, transaction_id: str, email: str) -> Dict[str, Any]:
        """Send invoice to customer via email."""
        try:
            pdf = await self.generate_invoice(transaction_id)
            if not pdf:
                return {"success": False, "error": "Failed to generate invoice"}
                
            # TODO: Implement email sending logic
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
