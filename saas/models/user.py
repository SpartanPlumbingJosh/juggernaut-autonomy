from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

class User(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    subscription_status: str = "free"
    last_payment_date: Optional[datetime] = None
    payment_method_id: Optional[str] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str
