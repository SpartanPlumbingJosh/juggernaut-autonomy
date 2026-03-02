from typing import Dict, Any
import json
import uuid
from datetime import datetime, timezone

async def create_digital_product(execute_sql, idea: Dict[str, Any]) -> Dict[str, Any]:
    """Automatically create a digital product from an idea."""
    try:
        product_id = str(uuid.uuid4())
        title = idea.get("title", "New Digital Product")
        description = idea.get("description", "")
        price = float(idea.get("estimates", {}).get("price", 9.99))
        
        await execute_sql(f"""
            INSERT INTO digital_products (
                id,
                title,
                description,
                base_price,
                currency,
                delivery_method,
                assets,
                created_at,
                updated_at
            ) VALUES (
                '{product_id}',
                '{title.replace("'", "''")}',
                '{description.replace("'", "''")}',
                {price},
                'USD',
                'automatic',
                '[]'::jsonb,
                NOW(),
                NOW()
            )
        """)
        
        # Generate landing page
        landing_page = f"""
        <html>
        <head>
            <title>{title}</title>
            <meta name="description" content="{description}">
        </head>
        <body>
            <h1>{title}</h1>
            <p>{description}</p>
            <div id="checkout"></div>
            <script src="/static/checkout.js?product_id={product_id}"></script>
        </body>
        </html>
        """
        
        await execute_sql(f"""
            INSERT INTO assets (
                id,
                name,
                type,
                content,
                product_id,
                created_at
            ) VALUES (
                gen_random_uuid(),
                'landing_page',
                'html',
                '{landing_page.replace("'", "''")}',
                '{product_id}',
                NOW()
            )
        """)
        
        return {
            "success": True,
            "product_id": product_id,
            "price": price,
            "landing_page": f"https://yourdomain.com/products/{product_id}"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
