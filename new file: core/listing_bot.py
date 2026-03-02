import json
import requests
from typing import Dict, Optional, List
from core.database import query_db, execute_sql

class ListingBot:
    """Automated listing bot for scanning and posting profitable items."""
    
    def __init__(self, api_key: str, platform: str = "ebay"):
        self.api_key = api_key
        self.platform = platform
        self.base_url = "https://api.ebay.com/buy/browse/v1" if platform == "ebay" else ""
    
    def scan_profitable_items(self, category: str, min_profit: float = 10.0) -> List[Dict]:
        """Scan platform for profitable items in given category."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
            }
            
            # Search for trending items in category
            params = {
                "q": category,
                "limit": 50,
                "sort": "price",
                "filter": "price:[100..500],conditionIds:{1000|1500|2000|2500|3000|4000|5000|6000}"
            }

            response = requests.get(
                f"{self.base_url}/item_summary/search",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            items = response.json().get("itemSummaries", [])
            profitable = []
            
            # Simple profitability check
            for item in items:
                buy_price = float(item.get("price", {}).get("value", 0))
                estimated_shipping = 10.0
                platform_fee = buy_price * 0.1  # 10% platform fee
                sell_price = buy_price * 1.5  # 50% markup
                
                profit = sell_price - buy_price - estimated_shipping - platform_fee
                if profit >= min_profit:
                    profitable.append({
                        "source_id": item.get("itemId"),
                        "title": item.get("title"),
                        "buy_price": buy_price,
                        "sell_price": sell_price,
                        "estimated_profit": profit,
                        "category": category,
                        "platform": self.platform
                    })
            
            return profitable
            
        except Exception as e:
            print(f"Scan failed: {str(e)}")
            return []

    def create_listing(self, item_data: Dict) -> Dict:
        """Create listing for profitable item."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "title": item_data["title"],
                "price": str(item_data["sell_price"]),
                "categoryPath": f"category:{item_data['category']}",
                "condition": "NEW",
                "availability": {"shipToLocation": {"region": "US"}},
                "imageUrls": ["https://example.com/placeholder.jpg"],
                "description": f"New {item_data['title']}. Free shipping."
            }

            response = requests.post(
                f"{self.base_url}/sell/inventory/v1/offer",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            listing_id = response.json().get("offerId")
            
            # Record in database
            execute_sql(f"""
                INSERT INTO marketplace_listings (
                    id, source_id, title, listing_price, 
                    purchase_price, estimated_profit, category,
                    platform, status, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{item_data['source_id']}',
                    '{item_data['title'].replace("'", "''")}',
                    {item_data['sell_price']},
                    {item_data['buy_price']},
                    {item_data['estimated_profit']},
                    '{item_data['category']}',
                    '{self.platform}'
                    'active',
                    NOW()
                )
            """)
            
            return {
                "success": True,
                "listing_id": listing_id,
                "item": item_data
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "item": item_data
            }

def run_listing_bot(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
    categories: List[str] = ["Electronics", "Home", "Clothing"],
    min_profit: float = 10.0,
    max_listings: int = 5,
) -> Dict[str, Any]:
    """Run the listing bot workflow."""
    api_key = "YOUR_API_KEY_HERE"  # Should come from config/env
    bot = ListingBot(api_key)
    
    listings_created = 0
    scanned = 0
    
    for category in categories:
        items = bot.scan_profitable_items(category, min_profit)
        scanned += len(items)
        
        for item in items[:max_listings]:
            result = bot.create_listing(item)
            if result.get("success"):
                listings_created += 1
    
    try:
        log_action(
            "listing_bot.run",
            f"Created {listings_created} listings ({scanned} scanned)",
            level="info",
            output_data={"created": listings_created, "scanned": scanned}
        )
    except Exception:
        pass
    
    return {"success": True, "created": listings_created, "scanned": scanned}
