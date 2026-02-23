from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class RevenueRecognition:
    """Handle revenue recognition according to accounting standards."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    async def recognize_revenue(self, invoice_id: str) -> Dict[str, Any]:
        """Recognize revenue for a paid invoice."""
        try:
            # Get invoice details
            sql = f"""
            SELECT id, subscription_id, amount, currency, created_at
            FROM invoices
            WHERE id = '{invoice_id}'
            """
            result = await self.execute_sql(sql)
            invoice = result.get("rows", [{}])[0]
            
            if not invoice.get("id"):
                return {"success": False, "error": "Invoice not found"}
                
            # Calculate recognition schedule
            recognition_schedule = self._calculate_recognition_schedule(invoice)
            
            # Create recognition entries
            for entry in recognition_schedule:
                rec_sql = f"""
                INSERT INTO revenue_recognition (
                    id, invoice_id, amount, currency,
                    recognition_date, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{invoice_id}',
                    {float(entry['amount'])},
                    '{invoice.get("currency")}',
                    '{entry['date'].isoformat()}',
                    NOW()
                )
                """
                await self.execute_sql(rec_sql)
                
            return {"success": True}
        except Exception as e:
            logger.error(f"Revenue recognition failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def _calculate_recognition_schedule(self, invoice: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Calculate revenue recognition schedule."""
        amount = Decimal(str(invoice.get("amount")))
        start_date = datetime.fromisoformat(invoice.get("created_at"))
        
        # Monthly recognition over 12 months
        schedule = []
        monthly_amount = amount / Decimal('12')
        
        for month in range(12):
            schedule.append({
                "date": start_date + timedelta(days=30 * (month + 1)),
                "amount": float(monthly_amount)
            })
            
        return schedule
        
    async def process_pending_revenue(self) -> Dict[str, Any]:
        """Process pending revenue recognition entries."""
        try:
            # Get entries ready for recognition
            sql = """
            SELECT id, invoice_id, amount, currency
            FROM revenue_recognition
            WHERE recognized_at IS NULL
              AND recognition_date <= NOW()
            LIMIT 100
            """
            result = await self.execute_sql(sql)
            entries = result.get("rows", [])
            
            processed = 0
            failures = []
            
            for entry in entries:
                process_result = await self._process_recognition_entry(entry)
                if process_result.get("success"):
                    processed += 1
                else:
                    failures.append({
                        "entry_id": entry.get("id"),
                        "error": process_result.get("error")
                    })
                    
            return {
                "success": True,
                "processed": processed,
                "failures": failures
            }
        except Exception as e:
            logger.error(f"Revenue recognition processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def _process_recognition_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Process an individual revenue recognition entry."""
        try:
            # Mark as recognized
            sql = f"""
            UPDATE revenue_recognition
            SET recognized_at = NOW()
            WHERE id = '{entry.get("id")}'
            """
            await self.execute_sql(sql)
            
            # Create accounting entry
            accounting_sql = f"""
            INSERT INTO accounting_entries (
                id, type, amount, currency,
                description, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                'revenue',
                {float(entry.get("amount"))},
                '{entry.get("currency")}',
                'Recognized revenue',
                NOW(),
                NOW()
            )
            """
            await self.execute_sql(accounting_sql)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
