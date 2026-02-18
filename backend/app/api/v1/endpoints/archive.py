"""Archive management endpoints for released COAs."""

from datetime import datetime
from pathlib import Path
from typing import Optional, List, Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.dependencies import DbSession, CurrentUser
from app.config import settings
from app.services.archive_service import ArchiveService
from app.schemas.archive import (
    ArchiveItem,
    ArchiveDetailResponse,
    ArchiveListResponse,
    ResendEmailRequest,
    EmailHistoryInArchive,
)

router = APIRouter()
archive_service = ArchiveService()


@router.get("", response_model=ArchiveListResponse)
async def search_archive(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    product_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    lot_number: Optional[str] = None,
    sort_by: Literal["released_at", "reference_number", "lot_number", "brand", "product_name"] = "released_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> ArchiveListResponse:
    """
    Search released COAs with filters.

    Returns paginated list of released COAs matching the filter criteria.
    All filters are optional and combined with AND logic.
    """
    skip = (page - 1) * page_size

    releases, total = archive_service.search(
        db=db,
        product_id=product_id,
        customer_id=customer_id,
        date_from=date_from,
        date_to=date_to,
        lot_number=lot_number,
        skip=skip,
        limit=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    items = [ArchiveItem.from_release(r) for r in releases]
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return ArchiveListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{id}", response_model=ArchiveDetailResponse)
async def get_archived_coa(
    id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ArchiveDetailResponse:
    """
    Get archived COA details by ID.

    Returns full details of a released COA including lot, product, customer info.
    """
    release = archive_service.get_by_id(db, id)
    if not release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archived COA not found",
        )

    return ArchiveDetailResponse.model_validate(release)


@router.get("/{id}/download")
async def download_archived_coa(
    id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    """
    Download the COA PDF file for an archived release.

    Returns the generated COA PDF file for download.
    """
    release = archive_service.get_by_id(db, id)
    if not release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archived COA not found",
        )

    if not release.coa_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="COA PDF file not found for this release",
        )

    from app.services.storage_service import get_storage_service

    # Use storage service to check if file exists
    storage = get_storage_service()
    if not storage.exists(release.coa_file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="COA PDF file not found in storage",
        )

    # Get full path by prepending upload_path
    full_path = settings.upload_path / release.coa_file_path

    # Generate filename from lot number
    filename = f"COA_{release.lot.lot_number}.pdf" if release.lot else f"COA_{release.id}.pdf"

    return FileResponse(
        path=str(full_path),
        filename=filename,
        media_type="application/pdf",
    )


@router.post("/{id}/resend", response_model=EmailHistoryInArchive)
async def resend_email(
    id: int,
    request: ResendEmailRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> EmailHistoryInArchive:
    """
    Re-send email for an archived COA to a different recipient.

    Note: This is a placeholder - no actual email is sent.
    Creates an EmailHistory record to track the re-send.
    """
    try:
        email_record = archive_service.resend_email(
            db=db,
            id=id,
            recipient_email=request.recipient_email,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return EmailHistoryInArchive.model_validate(email_record)


@router.get("/{id}/emails", response_model=List[EmailHistoryInArchive])
async def get_archive_email_history(
    id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> List[EmailHistoryInArchive]:
    """
    Get email history for an archived COA.

    Returns list of all emails sent for this COA, ordered by sent_at desc.
    """
    # Verify release exists
    release = archive_service.get_by_id(db, id)
    if not release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archived COA not found",
        )

    emails = archive_service.get_email_history(db, id)

    return [EmailHistoryInArchive.model_validate(e) for e in emails]
