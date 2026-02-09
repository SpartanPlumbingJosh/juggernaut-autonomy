"""
Value Delivery - Handles listing generation and order fulfillment.
"""

import asyncio
import logging
from typing import Dict, List, Optional

from core.content_generator import generate_content
from core.listing_builder import build_listings
from core.fulfillment import fulfill_order

class ValueDelivery:
    """Manages the value delivery process."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    async def generate_listings(self, opportunities: List[Dict]) -> List[Dict]:
        """Generate listings from market opportunities."""
        try:
            listings = []
            for opportunity in opportunities:
                content = await generate_content(opportunity)
                listing = await build_listings(content)
                listings.append(listing)
            return listings
        except Exception as e:
            self.logger.error(f"Listing generation failed: {str(e)}")
            return []
            
    async def fulfill_orders(self, listings: List[Dict]) -> Dict:
        """Fulfill orders for generated listings."""
        try:
            results = {
                "success": True,
                "completed_orders": [],
                "failed_orders": []
            }
            
            for listing in listings:
                fulfillment = await fulfill_order(listing)
                if fulfillment.get("success"):
                    results["completed_orders"].append(fulfillment)
                else:
                    results["failed_orders"].append(fulfillment)
                    
            if results["failed_orders"]:
                results["success"] = False
                
            return results
            
        except Exception as e:
            self.logger.error(f"Order fulfillment failed: {str(e)}")
            return {"success": False}

async def generate_listings(opportunities: List[Dict]) -> List[Dict]:
    """Public interface for listing generation."""
    deliverer = ValueDelivery()
    return await deliverer.generate_listings(opportunities)

async def fulfill_orders(listings: List[Dict]) -> Dict:
    """Public interface for order fulfillment."""
    deliverer = ValueDelivery()
    return await deliverer.fulfill_orders(listings)
