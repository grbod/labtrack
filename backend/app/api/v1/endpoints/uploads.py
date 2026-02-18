"""File upload endpoints for PDFs and other documents."""

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional

from app.dependencies import DbSession, CurrentUser
from app.config import settings
from app.models.lot import Lot
from app.services.storage_service import get_storage_service

router = APIRouter()


class UploadResponse(BaseModel):
    """Response model for file upload."""

    filename: str
    original_filename: str
    key: str  # Storage key (path in R2 or local)
    size: int
    content_type: str


@router.post("/pdf", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    lot_id: Optional[int] = Form(None),
    db: DbSession = None,
    current_user: CurrentUser = None,
) -> UploadResponse:
    """
    Upload a PDF file and optionally associate it with a lot.

    - Validates file is a PDF
    - Generates unique filename with timestamp
    - Saves to storage (R2 in production, local in development)
    - If lot_id provided, adds storage key to lot's attached_pdfs
    - Returns file metadata
    """
    # Validate file type
    if not file.content_type or file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed",
        )

    # Validate file size (max 10MB from config)
    max_size = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum of {settings.max_upload_size_mb}MB",
        )

    # Generate unique filename: timestamp_uuid_originalname.pdf
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in (file.filename or "document.pdf"))
    new_filename = f"{timestamp}_{unique_id}_{safe_name}"

    # Storage key with prefix
    storage_key = f"pdfs/{new_filename}"

    # Upload to storage
    storage = get_storage_service()
    storage.upload(content, storage_key, content_type="application/pdf")

    # Associate with lot if lot_id provided
    if lot_id and db:
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if lot:
            # Initialize attached_pdfs if None
            if lot.attached_pdfs is None:
                lot.attached_pdfs = []
            # Add the storage key
            lot.attached_pdfs = lot.attached_pdfs + [storage_key]
            db.commit()

    return UploadResponse(
        filename=new_filename,
        original_filename=file.filename or "document.pdf",
        key=storage_key,
        size=len(content),
        content_type=file.content_type,
    )


@router.get("/{filename:path}")
async def get_upload(
    filename: str,
    current_user: CurrentUser = None,
):
    """
    Get an uploaded file by filename or storage key.

    For R2 storage: Returns a redirect to a presigned URL (1-hour expiry).
    For local storage: Returns the file directly.
    """
    storage = get_storage_service()

    # Handle both old-style filenames and new storage keys
    if not filename.startswith("pdfs/"):
        storage_key = f"pdfs/{filename}"
    else:
        storage_key = filename

    # Check if file exists
    if not storage.exists(storage_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # For R2, redirect to presigned URL
    if settings.storage_backend == "r2":
        presigned_url = storage.get_presigned_url(storage_key)
        return RedirectResponse(url=presigned_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    # For local storage, serve the file directly
    content = storage.download(storage_key)

    # Get just the filename for the response
    actual_filename = storage_key.split("/")[-1]

    # For local storage, we need to return the file
    # Create a temp response with the content
    from fastapi.responses import Response
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{actual_filename}"'},
    )


@router.delete("/{filename:path}")
async def delete_upload(
    filename: str,
    db: DbSession = None,
    current_user: CurrentUser = None,
) -> dict:
    """Delete an uploaded file."""
    storage = get_storage_service()

    # Handle both old-style filenames and new storage keys
    if not filename.startswith("pdfs/"):
        storage_key = f"pdfs/{filename}"
    else:
        storage_key = filename

    # Check if file exists
    if not storage.exists(storage_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Delete from storage
    storage.delete(storage_key)

    return {"message": "File deleted successfully"}
