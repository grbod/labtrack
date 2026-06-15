"""User management endpoints."""

import os
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.v1.endpoints.auth import build_user_response
from app.config import settings
from app.core.security import get_password_hash
from app.dependencies import AdminUser, DbSession
from app.models import User
from app.schemas.auth import UserCreate, UserResponse, UserUpdate

router = APIRouter()

ALLOWED_SIGNATURE_TYPES = ["image/jpeg", "image/png", "image/webp"]
MAX_SIGNATURE_BYTES = 2 * 1024 * 1024


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
    return [build_user_response(u) for u in users]


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

    # Create user with bcrypt password
    user = User(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        password_hash=get_password_hash(user_in.password),
        role=user_in.role,
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return build_user_response(user)


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
    return build_user_response(user)


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
        update_data["password_hash"] = get_password_hash(update_data.pop("password"))
    # Map schema field is_active to model column active
    if "is_active" in update_data:
        update_data["active"] = update_data.pop("is_active")

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    return build_user_response(user)


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


@router.post("/{user_id}/signature", response_model=UserResponse)
async def upload_user_signature(
    user_id: int,
    db: DbSession,
    current_user: AdminUser,
    file: UploadFile = File(...),
) -> UserResponse:
    """Upload a signature image for any user (admin only).

    Mirrors the self-service ``/auth/me/signature`` endpoint but targets the
    user identified by ``user_id`` instead of the caller.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if file.content_type not in ALLOWED_SIGNATURE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_SIGNATURE_TYPES)}",
        )

    content = await file.read()
    if len(content) > MAX_SIGNATURE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 2MB.",
        )

    # Remove the previous signature file, if any.
    if user.signature_path:
        try:
            old_path = os.path.join(settings.upload_path, user.signature_path)
            if os.path.exists(old_path):
                os.remove(old_path)
        except Exception:
            pass

    ext = os.path.splitext(file.filename or "signature.png")[1].lower()
    new_filename = f"sig_{user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    signatures_dir = os.path.join(settings.upload_path, "signatures")
    os.makedirs(signatures_dir, exist_ok=True)
    with open(os.path.join(signatures_dir, new_filename), "wb") as f:
        f.write(content)

    user.signature_path = f"signatures/{new_filename}"
    db.commit()
    db.refresh(user)

    return build_user_response(user)


@router.delete("/{user_id}/signature", response_model=UserResponse)
async def delete_user_signature(
    user_id: int,
    db: DbSession,
    current_user: AdminUser,
) -> UserResponse:
    """Delete a user's signature image (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.signature_path:
        try:
            old_path = os.path.join(settings.upload_path, user.signature_path)
            if os.path.exists(old_path):
                os.remove(old_path)
        except Exception:
            pass

        user.signature_path = None
        db.commit()
        db.refresh(user)

    return build_user_response(user)
