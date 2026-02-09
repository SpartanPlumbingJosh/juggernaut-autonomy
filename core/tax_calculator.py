from __future__ import annotations
import os
import logging
from typing import Dict, Optional, Tuple

import taxjar

logger = logging.getLogger(__name__)

class TaxCalculator:
    """Handle tax calculations and compliance reporting."""
    
    def __init__(self):
        self.taxjar_api_key = os.getenv("TAXJAR_API_KEY")
        self.client = taxjar.Client(api_key=self.taxjar_api_key) if self.taxjar_api_key else None
    
    def calculate_tax(
        self,
        amount: float,
        currency: str,
        customer_country: str,
        customer_state: Optional[str] = None,
        customer_zip: Optional[str] = None,
        seller_country: str = "US",
        seller_state: Optional[str] = None,
        seller_zip: Optional[str] = None,
        nexus_countries: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Calculate taxes for a transaction."""
        if not self.client:
            return {"success": False, "error": "TaxJar not configured"}
        
        try:
            tax = self.client.tax_for_order({
                "amount": amount,
                "shipping": 0,
                "to_country": customer_country,
                "to_state": customer_state,
                "to_zip": customer_zip,
                "from_country": seller_country,
                "from_state": seller_state,
                "from_zip": seller_zip,
                "nexus_addresses": [
                    {"country": c} for c in (nexus_countries or [seller_country])
                ]
            })
            
            return {
                "success": True,
                "tax_amount": tax.amount_to_collect,
                "tax_rate": tax.rate,
                "breakdown": tax.breakdown,
                "currency": currency
            }
        except taxjar.Error as e:
            logger.error(f"Tax calculation failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def create_sales_tax_report(
        self,
        start_date: str,
        end_date: str,
        region: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate sales tax report for a period."""
        if not self.client:
            return {"success": False, "error": "TaxJar not configured"}
        
        try:
            report = self.client.list_orders({
                "from_transaction_date": start_date,
                "to_transaction_date": end_date,
                "region": region
            })
            
            return {
                "success": True,
                "report": report,
                "start_date": start_date,
                "end_date": end_date,
                "region": region
            }
        except taxjar.Error as e:
            logger.error(f"Sales tax report generation failed: {str(e)}")
            return {"success": False, "error": str(e)}
