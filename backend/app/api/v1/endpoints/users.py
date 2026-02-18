"""User management endpoints."""

import hashlib
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.dependencies import DbSession, AdminUser
from app.schemas.auth import UserCreate, UserUpdate, UserResponse
from app.models import User

# SHA256 salt must match auth.py login verification
_PASSWORD_SALT = "coa_system_salt_"


def _hash_password(password: str) -> str:
    return hashlib.sha256(f"{_PASSWORD_SALT}{password}".encode()).hexdigest()

router = APIRouter()


# Admin endpoints (admin only)


@router.get("", response_model=List[UserResponse])
async def list_users(
    db: DbSession,
    current_user: AdminUser,
    skip: int = 0,
    limit: int = 100,
) -> List[UserResponse]:
    """List all users (admin only)."""
    users = db.query(User).offset(skip).limit(limit).all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    db: DbSession,
    current_user: AdminUser,
) -> UserResponse:
    """Create a new user (admin only)."""
    # Check if username exists
    existing = db.query(User).filter(User.username == user_in.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Create user with SHA256+salt password (matches login verification)
    user = User(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        password_hash=_hash_password(user_in.password),
        role=user_in.role,
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: DbSession,
    current_user: AdminUser,
) -> UserResponse:
    """Get a user by ID (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: DbSession,
    current_user: AdminUser,
) -> UserResponse:
    """Update a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update fields
    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = _hash_password(update_data.pop("password"))
    # Map schema field is_active to model column active
    if "is_active" in update_data:
        update_data["active"] = update_data.pop("is_active")

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: DbSession,
    current_user: AdminUser,
) -> None:
    """Delete a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Don't allow deleting self
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    db.delete(user)
    db.commit()
