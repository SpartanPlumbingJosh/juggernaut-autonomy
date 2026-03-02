from datetime import datetime, timedelta
from typing import Dict, Optional, List
from enum import Enum
import logging

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"

class SubscriptionService:
    def __init__(self, db):
        self.db = db
        self.logger = logging.getLogger(__name__)

    async def create_subscription(self, user_id: str, plan_id: str, payment_method: str) -> Dict:
        """Create new subscription"""
        try:
            # Get user details
            user = await self.db.get_user(user_id)
            if not user:
                return {"error": "User not found"}

            # Create customer in payment gateway
            customer = await self._create_payment_customer(user)
            if customer.get("error"):
                return customer

            # Create subscription
            subscription = await self._create_payment_subscription(
                customer["customer_id"],
                plan_id
            )
            if subscription.get("error"):
                return subscription

            # Save subscription to database
            sub_data = {
                "user_id": user_id,
                "subscription_id": subscription["subscription_id"],
                "status": SubscriptionStatus.ACTIVE.value,
                "plan_id": plan_id,
                "payment_method": payment_method,
                "start_date": datetime.utcnow(),
                "current_period_end": datetime.fromtimestamp(
                    subscription["current_period_end"]
                )
            }
            await self.db.create_subscription(sub_data)

            return {
                "subscription_id": subscription["subscription_id"],
                "status": subscription["status"],
                "current_period_end": sub_data["current_period_end"]
            }

        except Exception as e:
            self.logger.error(f"Subscription creation failed: {str(e)}")
            return {"error": str(e)}

    async def cancel_subscription(self, subscription_id: str) -> Dict:
        """Cancel existing subscription"""
        try:
            # Get subscription details
            subscription = await self.db.get_subscription(subscription_id)
            if not subscription:
                return {"error": "Subscription not found"}

            # Cancel in payment gateway
            result = await self._cancel_payment_subscription(subscription_id)
            if result.get("error"):
                return result

            # Update database
            await self.db.update_subscription(
                subscription_id,
                {"status": SubscriptionStatus.CANCELED.value}
            )

            return {"success": True}

        except Exception as e:
            self.logger.error(f"Subscription cancellation failed: {str(e)}")
            return {"error": str(e)}

    async def handle_webhook(self, event: Dict) -> Dict:
        """Process subscription-related webhook events"""
        try:
            event_type = event.get("type")
            data = event.get("data", {})

            if event_type == "invoice.payment_succeeded":
                return await self._handle_payment_success(data)
            elif event_type == "invoice.payment_failed":
                return await self._handle_payment_failure(data)
            elif event_type == "customer.subscription.deleted":
                return await self._handle_subscription_cancelled(data)

            return {"status": "unhandled_event"}

        except Exception as e:
            self.logger.error(f"Webhook handling failed: {str(e)}")
            return {"error": str(e)}

    async def _create_payment_customer(self, user: Dict) -> Dict:
        """Create customer in payment gateway"""
        # Implementation depends on payment gateway
        pass

    async def _create_payment_subscription(self, customer_id: str, plan_id: str) -> Dict:
        """Create subscription in payment gateway"""
        # Implementation depends on payment gateway
        pass

    async def _cancel_payment_subscription(self, subscription_id: str) -> Dict:
        """Cancel subscription in payment gateway"""
        # Implementation depends on payment gateway
        pass

    async def _handle_payment_success(self, invoice: Dict) -> Dict:
        """Handle successful payment"""
        try:
            # Update subscription in database
            await self.db.update_subscription(
                invoice["subscription"],
                {
                    "status": SubscriptionStatus.ACTIVE.value,
                    "current_period_end": datetime.fromtimestamp(
                        invoice["current_period_end"]
                    )
                }
            )
            return {"success": True}
        except Exception as e:
            self.logger.error(f"Payment success handling failed: {str(e)}")
            return {"error": str(e)}

    async def _handle_payment_failure(self, invoice: Dict) -> Dict:
        """Handle failed payment"""
        try:
            # Update subscription status
            await self.db.update_subscription(
                invoice["subscription"],
                {"status": SubscriptionStatus.PAST_DUE.value}
            )
            return {"success": True}
        except Exception as e:
            self.logger.error(f"Payment failure handling failed: {str(e)}")
            return {"error": str(e)}

    async def _handle_subscription_cancelled(self, subscription: Dict) -> Dict:
        """Handle subscription cancellation"""
        try:
            # Update subscription status
            await self.db.update_subscription(
                subscription["id"],
                {"status": SubscriptionStatus.CANCELED.value}
            )
            return {"success": True}
        except Exception as e:
            self.logger.error(f"Subscription cancellation handling failed: {str(e)}")
            return {"error": str(e)}
