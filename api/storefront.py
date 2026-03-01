"""
Digital Product Storefront MVP

Features:
- Product listing
- Stripe checkout integration
- Digital product delivery via email
"""

import os
import json
from datetime import datetime
from typing import Any, Dict, Optional

import stripe
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

# Sample products database
PRODUCTS = [
    {
        'id': 'prod_001',
        'name': 'Premium Report',
        'description': 'In-depth market analysis report',
        'price_cents': 1999,
        'currency': 'usd',
        'download_url': 'https://cloud.example.com/reports/premium',
        'image_url': 'https://example.com/images/report.jpg'
    },
    {
        'id': 'prod_002', 
        'name': 'Data Pack',
        'description': 'Curated dataset with API access',
        'price_cents': 999,
        'currency': 'usd',
        'download_url': 'https://api.example.com/data/pack',
        'image_url': 'https://example.com/images/data.jpg'
    }
]

async def _make_html_response(content: str) -> Response:
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Digital Products Store</title>
            <style>
                body {{ font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .products {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
                .product {{ border: 1px solid #ddd; padding: 20px; border-radius: 8px; }}
                .product img {{ max-width: 100%; height: auto; }}
                .buy-btn {{ background: #6772E5; color: white; padding: 10px 20px; 
                          border: none; border-radius: 4px; cursor: pointer; }}
            </style>
        </head>
        <body>
            <h1>Digital Products</h1>
            {content}
        </body>
        </html>
        """
    )

@app.get("/")
async def product_listing(request: Request):
    product_html = ""
    for product in PRODUCTS:
        product_html += f"""
        <div class="product">
            <h2>{product['name']}</h2>
            <img src="{product['image_url']}" alt="{product['name']}">
            <p>{product['description']}</p>
            <p>${product['price_cents'] / 100:.2f}</p>
            <form action="/checkout" method="POST">
                <input type="hidden" name="product_id" value="{product['id']}">
                <button type="submit" class="buy-btn">Buy Now</button>
                <input type="email" name="email" placeholder="Your email" required>
            </form>
        </div>
        """
    return await _make_html_response(f'<div class="products">{product_html}</div>')

@app.post("/checkout")
async def create_checkout(request: Request):
    form_data = await request.form()
    product_id = form_data.get('product_id')
    email = form_data.get('email')
    
    product = next((p for p in PRODUCTS if p['id'] == product_id), None)
    if not product:
        return Response("Product not found", status_code=404)
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': product['currency'],
                    'product_data': {
                        'name': product['name'],
                    },
                    'unit_amount': product['price_cents'],
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{request.url_for('payment_success')}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=str(request.url_for('product_listing')),
            metadata={
                'product_id': product_id,
                'customer_email': email
            }
        )
        return RedirectResponse(url=checkout_session.url, status_code=303)
    except Exception as e:
        return Response(f"Checkout error: {str(e)}", status_code=500)

@app.get("/success")
async def payment_success(request: Request, session_id: str):
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Here you would:
        # 1. Record the sale in your database 
        # 2. Send the download link to customer_email
        # 3. Fulfill order
        
        return await _make_html_response(
            f"""
            <div class="success">
                <h2>Thank you for your purchase!</h2>
                <p>We've sent your download link to {session.metadata.get('customer_email')}</p>
                <a href="/">Continue shopping</a>
            </div>
            """
        )
    except Exception as e:
        return Response(f"Error processing payment: {str(e)}", status_code=500)

@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        return Response(str(e), status_code=400)
    except stripe.error.SignatureVerificationError as e:
        return Response(str(e), status_code=400)

    # Handle checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        await fulfill_order(session)

    return Response(status_code=200)

async def fulfill_order(session):
    """Process completed order and deliver product"""
    # Get product info
    product_id = session.metadata.get('product_id')
    customer_email = session.metadata.get('customer_email')
    product = next((p for p in PRODUCTS if p['id'] == product_id), None)
    
    if product:
        # In production, you would:
        # 1. Save order to database
        # 2. Generate unique download link
        # 3. Send email with download instructions
        print(f"Order fulfilled for {product['name']} to {customer_email}")
