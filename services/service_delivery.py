import json
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from stripe import Webhook

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Mock database
service_db = {}
user_db = {}

def authenticate_user(token: str) -> Dict[str, Any]:
    """Mock user authentication"""
    return user_db.get(token, {})

@app.post("/webhook/stripe")
async def stripe_webhook(payload: Dict[str, Any]):
    """Handle Stripe webhook events"""
    try:
        event = Webhook.construct_event(
            payload, 
            payload.get("stripe-signature"),
            "your_stripe_webhook_secret"
        )
        
        if event['type'] == 'payment_intent.succeeded':
            payment = event['data']['object']
            user_id = payment['metadata'].get('user_id')
            service_id = payment['metadata'].get('service_id')
            
            # Activate service
            service_db[service_id] = {
                'status': 'active',
                'activated_at': datetime.utcnow(),
                'user_id': user_id
            }
            
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/services")
async def create_service(
    service_data: Dict[str, Any], 
    token: str = Depends(oauth2_scheme)
) -> Dict[str, Any]:
    """Create a new service instance"""
    user = authenticate_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    service_id = f"svc_{datetime.utcnow().timestamp()}"
    service_db[service_id] = {
        **service_data,
        'status': 'pending',
        'created_at': datetime.utcnow(),
        'user_id': user.get('id')
    }
    
    return {
        "service_id": service_id,
        "payment_url": f"/payment/{service_id}"
    }

@app.get("/services/{service_id}")
async def get_service(
    service_id: str,
    token: str = Depends(oauth2_scheme)
) -> Dict[str, Any]:
    """Get service status"""
    user = authenticate_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    service = service_db.get(service_id)
    if not service or service['user_id'] != user['id']:
        raise HTTPException(status_code=404, detail="Service not found")
        
    return service

@app.post("/services/{service_id}/execute")
async def execute_service(
    service_id: str,
    token: str = Depends(oauth2_scheme)
) -> Dict[str, Any]:
    """Execute the service"""
    user = authenticate_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    service = service_db.get(service_id)
    if not service or service['user_id'] != user['id']:
        raise HTTPException(status_code=404, detail="Service not found")
        
    if service['status'] != 'active':
        raise HTTPException(status_code=400, detail="Service not active")
        
    # TODO: Implement actual service execution logic
    return {"status": "executed", "service_id": service_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
