"""File upload endpoints for PDFs and other documents."""

import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from app.dependencies import DbSession, CurrentUser
from app.config import settings
from app.models.lot import Lot

router = APIRouter()


class UploadResponse(BaseModel):
    """Response model for file upload."""

    filename: str
    original_filename: str
    path: str
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
    - Saves to configured upload path
    - If lot_id provided, adds filename to lot's attached_pdfs
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

    # Create upload directory if needed
    upload_dir = Path(settings.upload_path) / "pdfs"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename: timestamp_uuid_originalname.pdf
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in (file.filename or "document.pdf"))
    new_filename = f"{timestamp}_{unique_id}_{safe_name}"

    # Save file
    file_path = upload_dir / new_filename
    with open(file_path, "wb") as f:
        f.write(content)

    # Associate with lot if lot_id provided
    if lot_id and db:
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if lot:
            # Initialize attached_pdfs if None
            if lot.attached_pdfs is None:
                lot.attached_pdfs = []
            # Add the new filename
            lot.attached_pdfs = lot.attached_pdfs + [new_filename]
            db.commit()

    return UploadResponse(
        filename=new_filename,
        original_filename=file.filename or "document.pdf",
        path=str(file_path),
        size=len(content),
        content_type=file.content_type,
    )


@router.get("/{filename}")
async def get_upload(
    filename: str,
    current_user: CurrentUser = None,
) -> FileResponse:
    """Get an uploaded file by filename."""
    upload_dir = Path(settings.upload_path) / "pdfs"
    file_path = upload_dir / filename

    # Security: ensure file is in upload directory (prevent path traversal)
    try:
        file_path.resolve().relative_to(upload_dir.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=filename,
    )


@router.delete("/{filename}")
async def delete_upload(
    filename: str,
    db: DbSession = None,
    current_user: CurrentUser = None,
) -> dict:
    """Delete an uploaded file."""
    upload_dir = Path(settings.upload_path) / "pdfs"
    file_path = upload_dir / filename

    # Security: ensure file is in upload directory
    try:
        file_path.resolve().relative_to(upload_dir.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    os.remove(file_path)
    return {"message": "File deleted successfully"}
