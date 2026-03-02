from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    is_active: bool
    stripe_customer_id: Optional[str]
    subscription_status: Optional[str]
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        orm_mode = True


class UserInDB(User):
    hashed_password: str
