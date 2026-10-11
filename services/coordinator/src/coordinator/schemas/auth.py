from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


class UserCreate(BaseModel):
    """Schema for registering a user account."""

    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr = Field(...)
    password: str = Field(..., min_length=8)
    role: str = Field(default="operator", pattern="^(admin|operator|user)$")


class UserLogin(BaseModel):
    """Schema for user credentials login."""

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    """Public user profile response."""

    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    """Authentication token response payload."""

    access_token: str
    token_type: str = "Bearer"
    expires_in_seconds: int
