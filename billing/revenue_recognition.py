from typing import Dict, List
from datetime import datetime, timedelta
from core.database import query_db, execute_db

class RevenueRecognizer:
    def recognize_revenue(self, invoice_id: str) -> Dict:
        """Recognize revenue for a paid invoice"""
        # Get invoice details
        res = query_db(
            f"""
            SELECT i.*, s.plan_id, s.start_date, s.end_date
            FROM invoices i
            JOIN subscriptions s ON i.subscription_id = s.id
            WHERE i.id = '{invoice_id}'
            """
        )
        invoice = res.get("rows", [{}])[0]
        
        if not invoice or invoice['status'] != 'paid':
            return {"success": False, "error": "Invoice not found or not paid"}
            
        # Calculate revenue recognition schedule
        start_date = invoice['start_date']
        end_date = invoice['end_date']
        total_days = (end_date - start_date).days
        daily_revenue = invoice['amount'] / total_days
        
        # Create revenue recognition entries
        current_date = start_date
        while current_date <= end_date:
            execute_db(
                f"""
                INSERT INTO revenue_recognition (
                    id, invoice_id, amount, currency,
                    recognition_date, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{invoice_id}',
                    {daily_revenue},
                    '{invoice['currency']}',
                    '{current_date.isoformat()}',
                    NOW(),
                    NOW()
                )
                """
            )
            current_date += timedelta(days=1)
            
        return {"success": True}
        
    def get_recognized_revenue(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get recognized revenue for a period"""
        res = query_db(
            f"""
            SELECT *
            FROM revenue_recognition
            WHERE recognition_date >= '{start_date.isoformat()}'
              AND recognition_date <= '{end_date.isoformat()}'
            ORDER BY recognition_date ASC
            """
        )
        return res.get("rows", [])
