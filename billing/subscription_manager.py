"""
Subscription Manager - Handle recurring billing and subscriptions.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List
import json

class SubscriptionManager:
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    def create_subscription_plan(self, plan_data: Dict) -> Optional[str]:
        """Create a new subscription plan"""
        try:
            plan_id = self.execute_sql(
                f"""
                INSERT INTO subscription_plans (
                    id, name, description, amount_cents, currency,
                    billing_interval, trial_period_days, is_active,
                    stripe_price_id, paypal_plan_id, metadata, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{plan_data['name'].replace("'", "''")}',
                    '{plan_data.get('description', '').replace("'", "''")}',
                    {int(plan_data['amount_cents'])},
                    '{plan_data['currency']}',
                    '{plan_data['billing_interval']}',
                    {int(plan_data.get('trial_period_days', 0))},
                    {plan_data.get('is_active', True)},
                    {f"'{plan_data['stripe_price_id']}'" if plan_data.get('stripe_price_id') else 'NULL'},
                    {f"'{plan_data['paypal_plan_id']}'" if plan_data.get('paypal_plan_id') else 'NULL'},
                    '{json.dumps(plan_data.get('metadata', {}))}',
                    NOW()
                )
                RETURNING id
                """
            )
            return plan_id.get('rows', [{}])[0].get('id')
        except Exception as e:
            self.log_action('billing.plan_creation_error', f"Failed to create plan: {str(e)}", level='error')
            return None
            
    def generate_invoice(self, subscription_id: str) -> Optional[Dict]:
        """Generate invoice for a subscription"""
        try:
            subscription = self.execute_sql(
                f"""
                SELECT s.*, p.amount_cents, p.currency, p.billing_interval
                FROM subscriptions s
                JOIN subscription_plans p ON s.plan_id = p.id
                WHERE s.id = '{subscription_id}'
                """
            ).get('rows', [{}])[0]

            if not subscription:
                return None
                
            invoice_data = {
                'subscription_id': subscription_id,
                'amount_due': subscription['amount_cents'],
                'currency': subscription['currency'],
                'billing_period_start': datetime.now(timezone.utc).date().isoformat(),
                'billing_period_end': (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                'status': 'pending',
                'due_date': (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat()
            }
            
            invoice_id = self.execute_sql(
                f"""
                INSERT INTO invoices (
                    subscription_id, amount_due, currency, status,
                    billing_period_start, billing_period_end, due_date,
                    created_at
                ) VALUES (
                    '{subscription_id}',
                    {invoice_data['amount_due']},
                    '{invoice_data['currency']}',
                    'pending',
                    '{invoice_data['billing_period_start']}',
                    '{invoice_data['billing_period_end']}',
                    '{invoice_data['due_date']}',
                    NOW()
                )
                RETURNING id
                """
            ).get('rows', [{}])[0].get('id')
            
            invoice_data['invoice_id'] = invoice_id
            return invoice_data
        except Exception as e:
            self.log_action('billing.invoice_error', f"Failed to generate invoice: {str(e)}", level='error')
            return None
