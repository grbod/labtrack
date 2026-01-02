"""Authentication schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str
    exp: datetime
    type: str


class LoginRequest(BaseModel):
    """Login request body."""

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class UserBase(BaseModel):
    """Base user schema."""

    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    role: UserRole = UserRole.READ_ONLY


class UserCreate(UserBase):
    """Schema for creating a user."""

    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6)


class UserResponse(BaseModel):
    """User response schema."""

    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool = Field(validation_alias="active")
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
