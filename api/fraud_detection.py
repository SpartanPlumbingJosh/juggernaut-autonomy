"""
Fraud Detection - Detect and prevent fraudulent transactions.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

class FraudDetector:
    def __init__(self):
        self.transaction_history = {}
        self.fraud_rules = [
            self._check_velocity,
            self._check_amount,
            self._check_geo_velocity
        ]

    async def analyze_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a transaction for fraud."""
        risk_score = 0
        reasons = []
        
        for rule in self.fraud_rules:
            result = await rule(transaction)
            if result["is_fraud"]:
                risk_score += result["risk_score"]
                reasons.append(result["reason"])
        
        return {
            "risk_score": risk_score,
            "is_fraud": risk_score > 80,
            "reasons": reasons
        }

    async def _check_velocity(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Check transaction velocity."""
        customer_id = transaction.get("customer_id")
        if customer_id in self.transaction_history:
            recent_transactions = [
                t for t in self.transaction_history[customer_id]
                if datetime.utcnow() - t["timestamp"] < timedelta(minutes=5)
            ]
            if len(recent_transactions) > 3:
                return {
                    "is_fraud": True,
                    "risk_score": 50,
                    "reason": "High transaction velocity"
                }
        return {"is_fraud": False, "risk_score": 0}

    async def _check_amount(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Check transaction amount."""
        amount = transaction.get("amount")
        if amount > 10000:  # Example threshold
            return {
                "is_fraud": True,
                "risk_score": 30,
                "reason": "High transaction amount"
            }
        return {"is_fraud": False, "risk_score": 0}

    async def _check_geo_velocity(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Check geographic velocity."""
        # Implement geo velocity check
        return {"is_fraud": False, "risk_score": 0}
