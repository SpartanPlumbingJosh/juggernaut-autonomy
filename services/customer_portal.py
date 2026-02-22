"""
Customer Portal Service - Self-service portal for customers.
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

class Customer(BaseModel):
    id: str
    name: str
    email: str
    subscriptions: list

@app.get("/portal/{customer_id}", response_class=HTMLResponse)
async def customer_portal(customer_id: str):
    # In a real app this would serve a full portal UI
    return """
    <html>
        <h1>Customer Portal</h1>
        <div id="portal-root"></div>
        <script src="/static/portal.js"></script>
    </html>
    """

@app.get("/api/customers/{customer_id}")
async def get_customer(customer_id: str):
    # Mock response
    return JSONResponse({
        "id": customer_id,
        "name": "Test Customer",
        "email": "test@example.com",
        "subscriptions": ["sub_mock123"]
    })
