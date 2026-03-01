"""
Revenue recognition compliant with ASC 606 standards.

Handles:
- Recognizing revenue over subscription periods
- Deferred revenue tracking
- Revenue schedule creation
"""

from datetime import datetime, timedelta
from typing import Dict, List
import json

class RevenueRecognition:
    
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql
        
    async def create_schedule(self, invoice_id: str, amount_cents: int, 
                           period_days: int) -> Dict:
        """Create revenue recognition schedule."""
        # Create monthly recognition schedule
        monthly_amount = amount_cents // (period_days // 30)
        remaining_amount = amount_cents
        
        recognition_dates = []
        current_date = datetime.now()
        
        # Spread recognition over subscription period
        for month in range(period_days // 30):
            if month == (period_days // 30) - 1:  # Last month
                amount = remaining_amount
            else:
                amount = monthly_amount
                remaining_amount -= monthly_amount
                
            await self.execute_sql(
                f"""
                INSERT INTO revenue_recognition (
                    invoice_id, amount_cents, 
                    recognition_date, recognized,
                    created_at
                ) VALUES (
                    '{invoice_id}', {amount},
                    '{(current_date + timedelta(days=30*(month+1))).isoformat()}',
                    False, NOW()
                )
                """
            )
            recognition_dates.append({
                "date": (current_date + timedelta(days=30*(month+1))).isoformat(),
                "amount_cents": amount
            })
            
        return {
            "success": True,
            "invoice_id": invoice_id,
            "total_amount": amount_cents,
            "schedule": recognition_dates
        }
        
    async def process_due_revenue(self) -> Dict:
        """Recognize revenue that's come due."""
        try:
            # Get revenue due for recognition
            results = await self.execute_sql(
                """
                SELECT id, invoice_id, amount_cents 
                FROM revenue_recognition
                WHERE recognition_date <= NOW()
                AND recognized = False
                LIMIT 1000
                """
            )
            
            recognized = 0
            for row in results.get("rows", []):
                await self.execute_sql(
                    f"""
                    UPDATE revenue_recognition SET
                        recognized = True,
                        recognized_at = NOW()
                    WHERE id = '{row['id']}'
                    """
                )
                
                # Record in general ledger
                await self.execute_sql(
                    f"""
                    INSERT INTO recognized_revenue (
                        recognition_id, invoice_id, 
                        amount_cents, recognized_at
                    ) VALUES (
                        '{row['id']}', '{row['invoice_id']}',
                        {row['amount_cents']}, NOW()
                    )
                    """
                )
                recognized += 1
                
            return {"success": True, "recognized": recognized}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
