"""
Automated Revenue Operations System

Handles:
- Transaction processing
- Payment provider integrations
- Revenue channel management
- Automated decision making
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.database import query_db, execute_db
from core.payment_providers import PaymentProviderFactory

logger = logging.getLogger(__name__)

class RevenueOperations:
    """Main class for managing revenue operations."""
    
    def __init__(self):
        self.payment_providers = PaymentProviderFactory.get_providers()
        self.decision_thresholds = {
            'min_revenue': 1000,  # Minimum expected revenue in cents
            'max_risk': 0.2,      # Maximum acceptable risk score
            'min_roi': 1.5        # Minimum ROI ratio
        }
    
    async def process_transaction(self, transaction: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Process a revenue transaction."""
        try:
            # Validate transaction
            if not self._validate_transaction(transaction):
                return False, "Invalid transaction data"
            
            # Select payment provider
            provider = self._select_payment_provider(transaction)
            if not provider:
                return False, "No suitable payment provider found"
            
            # Process payment
            success, payment_id = await provider.process_payment(
                amount=transaction['amount_cents'],
                currency=transaction['currency'],
                metadata=transaction.get('metadata', {})
            )
            
            if not success:
                return False, "Payment processing failed"
            
            # Record transaction
            transaction_id = await self._record_transaction(
                transaction=transaction,
                payment_id=payment_id
            )
            
            return True, transaction_id
            
        except Exception as e:
            logger.error(f"Transaction processing failed: {str(e)}")
            return False, str(e)
    
    def _validate_transaction(self, transaction: Dict[str, Any]) -> bool:
        """Validate transaction data."""
        required_fields = ['amount_cents', 'currency', 'source', 'event_type']
        return all(field in transaction for field in required_fields)
    
    def _select_payment_provider(self, transaction: Dict[str, Any]) -> Optional[Any]:
        """Select appropriate payment provider."""
        currency = transaction['currency'].lower()
        amount = transaction['amount_cents']
        
        for provider in self.payment_providers:
            if currency in provider.supported_currencies:
                if provider.min_amount <= amount <= provider.max_amount:
                    return provider
        return None
    
    async def _record_transaction(self, transaction: Dict[str, Any], payment_id: str) -> str:
        """Record transaction in database."""
        sql = f"""
        INSERT INTO revenue_events (
            id, experiment_id, event_type, amount_cents,
            currency, source, metadata, recorded_at,
            payment_id, created_at
        ) VALUES (
            gen_random_uuid(),
            {f"'{transaction.get('experiment_id')}'" if transaction.get('experiment_id') else "NULL"},
            '{transaction['event_type']}',
            {transaction['amount_cents']},
            '{transaction['currency']}',
            '{transaction['source']}',
            '{json.dumps(transaction.get('metadata', {}))}',
            NOW(),
            '{payment_id}',
            NOW()
        )
        RETURNING id
        """
        
        result = await execute_db(sql)
        return result['rows'][0]['id']
    
    async def evaluate_revenue_opportunity(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a revenue opportunity using decision logic."""
        try:
            # Calculate expected ROI
            expected_revenue = opportunity.get('expected_revenue', 0)
            expected_cost = opportunity.get('expected_cost', 0)
            roi = (expected_revenue - expected_cost) / expected_cost if expected_cost > 0 else 0
            
            # Risk assessment
            risk_score = self._calculate_risk_score(opportunity)
            
            # Make decision
            decision = (
                expected_revenue >= self.decision_thresholds['min_revenue'] and
                risk_score <= self.decision_thresholds['max_risk'] and
                roi >= self.decision_thresholds['min_roi']
            )
            
            return {
                'decision': decision,
                'roi': roi,
                'risk_score': risk_score,
                'expected_revenue': expected_revenue,
                'expected_cost': expected_cost
            }
            
        except Exception as e:
            logger.error(f"Revenue opportunity evaluation failed: {str(e)}")
            return {
                'decision': False,
                'error': str(e)
            }
    
    def _calculate_risk_score(self, opportunity: Dict[str, Any]) -> float:
        """Calculate risk score for an opportunity."""
        # Basic risk scoring based on opportunity metadata
        risk_factors = {
            'market_volatility': opportunity.get('market_volatility', 0.1),
            'competition_level': opportunity.get('competition_level', 0.1),
            'implementation_complexity': opportunity.get('implementation_complexity', 0.1)
        }
        return sum(risk_factors.values()) / len(risk_factors)
    
    async def reconcile_payments(self) -> Dict[str, Any]:
        """Reconcile payments with payment providers."""
        try:
            # Get unreconciled transactions
            sql = """
            SELECT id, payment_id, amount_cents, currency
            FROM revenue_events
            WHERE reconciled_at IS NULL
            AND payment_id IS NOT NULL
            LIMIT 100
            """
            result = await query_db(sql)
            transactions = result.get('rows', [])
            
            reconciled = 0
            errors = []
            
            for tx in transactions:
                provider = self._get_provider_for_transaction(tx)
                if not provider:
                    errors.append({
                        'transaction_id': tx['id'],
                        'error': 'No provider found'
                    })
                    continue
                
                status = await provider.check_payment_status(tx['payment_id'])
                if status == 'completed':
                    await self._mark_transaction_reconciled(tx['id'])
                    reconciled += 1
                else:
                    errors.append({
                        'transaction_id': tx['id'],
                        'error': f'Payment status: {status}'
                    })
            
            return {
                'success': True,
                'reconciled': reconciled,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Payment reconciliation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_provider_for_transaction(self, transaction: Dict[str, Any]) -> Optional[Any]:
        """Get payment provider for a transaction."""
        for provider in self.payment_providers:
            if provider.payment_id_prefix in transaction['payment_id']:
                return provider
        return None
    
    async def _mark_transaction_reconciled(self, transaction_id: str) -> None:
        """Mark transaction as reconciled."""
        sql = f"""
        UPDATE revenue_events
        SET reconciled_at = NOW()
        WHERE id = '{transaction_id}'
        """
        await execute_db(sql)
