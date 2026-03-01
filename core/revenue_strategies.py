from typing import Dict, Any, Optional
import random
import stripe
import paypalrestsdk
from datetime import datetime
from core.database import query_db, execute_sql

class RevenueStrategy:
    """Base class for revenue generation strategies."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
    def generate_revenue(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate revenue based on strategy."""
        raise NotImplementedError

class AffiliateStrategy(RevenueStrategy):
    """Affiliate marketing revenue strategy."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.links = config.get("links", [])
        self.rotation_index = 0
        
    def generate_revenue(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Rotate affiliate links and track clicks."""
        if not self.links:
            return {"success": False, "error": "No affiliate links configured"}
            
        # Rotate links
        link = self.links[self.rotation_index]
        self.rotation_index = (self.rotation_index + 1) % len(self.links)
        
        # Track click
        try:
            execute_sql(f"""
                INSERT INTO affiliate_clicks (
                    id, link_url, click_time, user_agent, ip_address, referrer
                ) VALUES (
                    gen_random_uuid(),
                    '{link}',
                    NOW(),
                    '{context.get("user_agent", "")}',
                    '{context.get("ip", "")}',
                    '{context.get("referrer", "")}'
                )
            """)
        except Exception as e:
            return {"success": False, "error": str(e)}
            
        return {"success": True, "redirect_url": link}

class APIStrategy(RevenueStrategy):
    """API usage-based billing strategy."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        stripe.api_key = config.get("stripe_secret_key", "")
        
    def generate_revenue(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Track API usage and bill accordingly."""
        customer_id = context.get("customer_id")
        usage_units = context.get("usage_units", 0)
        
        if not customer_id or usage_units <= 0:
            return {"success": False, "error": "Invalid usage data"}
            
        try:
            # Create usage record
            stripe.SubscriptionItem.create_usage_record(
                context.get("subscription_item_id"),
                quantity=usage_units,
                timestamp=int(datetime.now().timestamp()),
                action="increment"
            )
            
            return {"success": True}
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

class ServiceStrategy(RevenueStrategy):
    """Service payment processing strategy."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        paypalrestsdk.configure({
            "mode": config.get("paypal_mode", "sandbox"),
            "client_id": config.get("paypal_client_id"),
            "client_secret": config.get("paypal_client_secret")
        })
        
    def generate_revenue(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment for service."""
        amount = context.get("amount")
        currency = context.get("currency", "USD")
        
        if not amount or amount <= 0:
            return {"success": False, "error": "Invalid amount"}
            
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "transactions": [{
                "amount": {
                    "total": str(amount),
                    "currency": currency
                },
                "description": context.get("description", "Service payment")
            }],
            "redirect_urls": {
                "return_url": context.get("return_url"),
                "cancel_url": context.get("cancel_url")
            }
        })
        
        if payment.create():
            return {"success": True, "payment_id": payment.id}
        else:
            return {"success": False, "error": payment.error}

def get_strategy(strategy_type: str, config: Dict[str, Any]) -> Optional[RevenueStrategy]:
    """Get revenue strategy implementation."""
    strategies = {
        "affiliate": AffiliateStrategy,
        "api": APIStrategy,
        "service": ServiceStrategy
    }
    
    strategy_class = strategies.get(strategy_type)
    if not strategy_class:
        return None
        
    return strategy_class(config)
