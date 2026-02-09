import os
import stripe
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def landing_page(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

@app.post("/create-stripe-session")
async def create_stripe_session():
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Product Name',
                    },
                    'unit_amount': 4999,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='https://yourdomain.com/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://yourdomain.com/cancel',
        )
        return JSONResponse({"id": session.id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/success")
async def success_page(request: Request, session_id: str):
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        return templates.TemplateResponse("success.html", {
            "request": request,
            "session": session
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download")
async def download_file(transaction: str):
    # Here you would implement your delivery mechanism
    # This could be a file download, API access, or service activation
    return RedirectResponse(url="https://yourdomain.com/your-product-file.zip")

@app.get("/cancel")
async def cancel_page(request: Request):
    return templates.TemplateResponse("cancel.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
