"""
Subscription management service with automated billing, provisioning, and dunning.
Handles high-volume transactions with idempotency and retry logic.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import stripe
import paddle

from core.database import query_db, execute_sql
from core.logging import log_action
from core.utils import exponential_backoff, idempotency_key

# Configure payment processors
stripe.api_key = "sk_live_..."  # TODO: Move to config
paddle.api_key = "pd_live_..."  # TODO: Move to config

class SubscriptionService:
    """Manage subscriptions with automated billing and provisioning."""
    
    def __init__(self):
        self.retry_policy = {
            'max_retries': 3,
            'initial_delay': 1,
            'backoff_factor': 2
        }

    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        payment_method: str,
        quantity: int = 1,
        trial_days: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create new subscription with automated provisioning."""
        idempotency = idempotency_key(f"sub_create_{customer_id}_{plan_id}")
        
        try:
            # Create in Stripe
            sub = stripe.Subscription.create(
                customer=customer_id,
                items=[{"plan": plan_id, "quantity": quantity}],
                default_payment_method=payment_method,
                trial_period_days=trial_days,
                metadata=metadata or {},
                idempotency_key=idempotency
            )
            
            # Store in DB
            await execute_sql(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status, 
                    current_period_start, current_period_end,
                    created_at, updated_at, metadata
                ) VALUES (
                    '{sub.id}', '{customer_id}', '{plan_id}', 'active',
                    '{datetime.fromtimestamp(sub.current_period_start).isoformat()}',
                    '{datetime.fromtimestamp(sub.current_period_end).isoformat()}',
                    NOW(), NOW(), '{json.dumps(metadata or {})}'
                )
                """
            )
            
            # Provision access
            await self._provision_access(customer_id, plan_id)
            
            return {"success": True, "subscription": sub.id}
            
        except Exception as e:
            log_action(
                "subscription.create_failed",
                f"Failed to create subscription: {str(e)}",
                level="error",
                error_data={
                    "customer_id": customer_id,
                    "plan_id": plan_id,
                    "error": str(e)
                }
            )
            return {"success": False, "error": str(e)}

    async def process_payment(
        self, 
        subscription_id: str,
        amount: int,
        currency: str = "usd"
    ) -> Dict[str, Any]:
        """Process subscription payment with retry logic."""
        idempotency = idempotency_key(f"payment_{subscription_id}_{amount}")
        
        @exponential_backoff(**self.retry_policy)
        async def _process():
            try:
                # Get subscription
                sub = stripe.Subscription.retrieve(subscription_id)
                
                # Create invoice
                invoice = stripe.Invoice.create(
                    customer=sub.customer,
                    subscription=subscription_id,
                    auto_advance=True,
                    idempotency_key=idempotency
                )
                
                # Pay invoice
                paid_invoice = stripe.Invoice.pay(
                    invoice.id,
                    payment_method=sub.default_payment_method
                )
                
                # Record payment
                await execute_sql(
                    f"""
                    INSERT INTO subscription_payments (
                        id, subscription_id, amount, currency,
                        invoice_id, payment_method, status,
                        created_at
                    ) VALUES (
                        gen_random_uuid(), '{subscription_id}', {amount}, '{currency}',
                        '{invoice.id}', '{sub.default_payment_method}', 'paid',
                        NOW()
                    )
                    """
                )
                
                return {"success": True, "invoice_id": invoice.id}
                
            except stripe.error.CardError as e:
                await self._handle_payment_failure(subscription_id, str(e))
                raise
            except Exception as e:
                log_action(
                    "payment.processing_failed",
                    f"Payment failed for {subscription_id}: {str(e)}",
                    level="error",
                    error_data={
                        "subscription_id": subscription_id,
                        "error": str(e)
                    }
                )
                raise

        return await _process()

    async def _handle_payment_failure(
        self,
        subscription_id: str,
        error: str
    ) -> None:
        """Handle payment failure with dunning logic."""
        try:
            # Get failure count
            res = await query_db(
                f"""
                SELECT COUNT(*) as failures 
                FROM subscription_payment_failures
                WHERE subscription_id = '{subscription_id}'
                AND created_at > NOW() - INTERVAL '30 days'
                """
            )
            failures = res.get("rows", [{}])[0].get("failures", 0) + 1
            
            # Record failure
            await execute_sql(
                f"""
                INSERT INTO subscription_payment_failures (
                    id, subscription_id, error, failure_count,
                    created_at
                ) VALUES (
                    gen_random_uuid(), '{subscription_id}', '{error}', {failures},
                    NOW()
                )
                """
            )
            
            # Apply dunning logic
            if failures >= 3:
                await self._handle_three_failures(subscription_id)
            else:
                await self._send_dunning_email(subscription_id, failures)

        except Exception as e:
            log_action(
                "payment.failure_handling_failed",
                f"Failed to handle payment failure: {str(e)}",
                level="error",
                error_data={
                    "subscription_id": subscription_id,
                    "original_error": error,
                    "handling_error": str(e)
                }
            )

    async def _handle_three_failures(self, subscription_id: str) -> None:
        """Handle 3+ payment failures."""
        try:
            # Cancel subscription
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            
            # Update status
            await execute_sql(
                f"""
                UPDATE subscriptions
                SET status = 'pending_cancelation',
                    updated_at = NOW()
                WHERE id = '{subscription_id}'
                """
            )
            
            # Send notification
            log_action(
                "subscription.canceled_payment_failures",
                f"Subscription {subscription_id} canceled due to payment failures",
                level="warning",
                output_data={"subscription_id": subscription_id}
            )
            
        except Exception as e:
            log_action(
                "subscription.cancel_failed",
                f"Failed to cancel subscription: {str(e)}",
                level="error",
                error_data={"subscription_id": subscription_id}
            )

    async def _send_dunning_email(self, subscription_id: str, failures: int) -> None:
        """Send dunning email for payment failure."""
        # TODO: Implement email sending logic
        pass

    async def _provision_access(self, customer_id: str, plan_id: str) -> None:
        """Provision access based on subscription plan."""
        # TODO: Implement provisioning logic
        pass

    async def run_billing_cycle(self) -> Dict[str, Any]:
        """Process all subscriptions due for billing."""
        try:
            # Get subscriptions due for billing
            res = await query_db(
                """
                SELECT id, customer_id, plan_id
                FROM subscriptions
                WHERE status = 'active'
                AND current_period_end <= NOW() + INTERVAL '1 day'
                ORDER BY current_period_end ASC
                LIMIT 1000
                """
            )
            subs = res.get("rows", [])
            
            processed = 0
            failures = 0
            
            for sub in subs:
                try:
                    # Get plan price
                    plan = stripe.Plan.retrieve(sub["plan_id"])
                    amount = plan.amount * plan.quantity
                    
                    # Process payment
                    result = await self.process_payment(
                        subscription_id=sub["id"],
                        amount=amount,
                        currency=plan.currency
                    )
                    
                    if result["success"]:
                        # Update subscription period
                        await execute_sql(
                            f"""
                            UPDATE subscriptions
                            SET 
                                current_period_start = NOW(),
                                current_period_end = NOW() + INTERVAL '{plan.interval_count} {plan.interval}',
                                updated_at = NOW()
                            WHERE id = '{sub["id"]}'
                            """
                        )
                        processed += 1
                    else:
                        failures += 1
                        
                except Exception as e:
                    failures += 1
                    log_action(
                        "billing.cycle_failed",
                        f"Failed to process subscription {sub['id']}: {str(e)}",
                        level="error",
                        error_data={
                            "subscription_id": sub["id"],
                            "error": str(e)
                        }
                    )
            
            return {
                "success": True,
                "processed": processed,
                "failures": failures,
                "total": len(subs)
            }
            
        except Exception as e:
            log_action(
                "billing.cycle_failed",
                f"Billing cycle failed: {str(e)}",
                level="error",
                error_data={"error": str(e)}
            )
            return {"success": False, "error": str(e)}
