# backend/schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# =======================================================
# AUTHENTICATION SCHEMAS
# =======================================================
class UserRegister(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str
    name: str
    whatsapp: str
    branch: str
    personal_code: Optional[str] = None


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Schema for token response."""
    access_token: str
    token_type: str
    user: dict


class TokenData(BaseModel):
    """Schema for token payload data."""
    email: Optional[str] = None
    role: Optional[str] = None


# =======================================================
# USER SCHEMAS
# =======================================================
class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    name: str
    whatsapp: str
    branch: str
    personal_code: str


class UserCreate(UserBase):
    """Schema for creating a user (admin only)."""
    password: str
    role: str = "client"


class UserOut(UserBase):
    """Schema for user output."""
    id: int
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    name: Optional[str] = None
    whatsapp: Optional[str] = None
    branch: Optional[str] = None
    is_active: Optional[bool] = None


# =======================================================
# TRACK SCHEMAS
# =======================================================
class TrackAssignment(BaseModel):
    """Schema for assigning a track to a user."""
    track_number: str
    personal_code: str


class TrackOut(BaseModel):
    """Schema for track output."""
    id: int
    track_number: str
    status: Optional[str]
    personal_code: Optional[str]
    departure_date: Optional[str]
    is_archived: bool
    
    class Config:
        from_attributes = True
