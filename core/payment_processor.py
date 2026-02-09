"""
Payment Processing - Handles payment transactions and reconciliation.
"""

import asyncio
import logging
from typing import Dict, List, Optional

from core.payment_gateways import process_payment
from core.reconciliation import reconcile_transactions

class PaymentProcessor:
    """Manages payment processing operations."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    async def process_payments(self, orders: List[Dict]) -> Dict:
        """Process payments for completed orders."""
        try:
            results = {
                "success": True,
                "processed_payments": [],
                "failed_payments": []
            }
            
            for order in orders:
                payment = await process_payment(order)
                if payment.get("success"):
                    results["processed_payments"].append(payment)
                else:
                    results["failed_payments"].append(payment)
                    
            if results["failed_payments"]:
                results["success"] = False
                
            # Reconcile transactions
            await reconcile_transactions(results["processed_payments"])
            
            return results
            
        except Exception as e:
            self.logger.error(f"Payment processing failed: {str(e)}")
            return {"success": False}

async def process_payments(orders: List[Dict]) -> Dict:
    """Public interface for payment processing."""
    processor = PaymentProcessor()
    return await processor.process_payments(orders)
