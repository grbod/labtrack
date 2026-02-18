"""Retest management endpoints."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.dependencies import DbSession, CurrentUser, QCManagerOrAdmin
from app.services.retest_service import retest_service
from app.services.daane_coc_service import daane_coc_service
from app.schemas.retest import (
    CreateRetestRequest,
    RetestRequestResponse,
    RetestRequestListResponse,
    RetestItemResponse,
    RetestOriginalValue,
)

router = APIRouter()


def _format_retest_response(retest_request) -> RetestRequestResponse:
    """Format a RetestRequest object to RetestRequestResponse."""
    return RetestRequestResponse(
        id=retest_request.id,
        lot_id=retest_request.lot_id,
        reference_number=retest_request.reference_number,
        retest_number=retest_request.retest_number,
        reason=retest_request.reason,
        status=retest_request.status,
        requested_by_id=retest_request.requested_by_id,
        requested_by_name=(
            retest_request.requested_by.full_name or retest_request.requested_by.username
            if retest_request.requested_by
            else None
        ),
        completed_at=retest_request.completed_at,
        created_at=retest_request.created_at,
        items=[
            RetestItemResponse(
                id=item.id,
                test_result_id=item.test_result_id,
                original_value=item.original_value,
                current_value=item.test_result.result_value if item.test_result else None,
                test_type=item.test_result.test_type if item.test_result else None,
            )
            for item in retest_request.items
        ],
    )


@router.post("/lots/{lot_id}/retest-requests", response_model=RetestRequestResponse)
async def create_retest_request(
    lot_id: int,
    request_data: CreateRetestRequest,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> RetestRequestResponse:
    """
    Create a retest request for a lot.

    Only QC Managers and Admins can create retest requests.
    """
    try:
        retest_request = retest_service.create_retest_request(
            db=db,
            lot_id=lot_id,
            test_result_ids=request_data.test_result_ids,
            reason=request_data.reason,
            user_id=current_user.id,
        )
        return _format_retest_response(retest_request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/lots/{lot_id}/retest-requests", response_model=RetestRequestListResponse)
async def get_retest_requests_for_lot(
    lot_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> RetestRequestListResponse:
    """Get all retest requests for a lot."""
    # Verify lot exists
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lot with ID {lot_id} not found",
        )

    retest_requests = retest_service.get_retests_for_lot(db, lot_id)

    return RetestRequestListResponse(
        items=[_format_retest_response(r) for r in retest_requests],
        total=len(retest_requests),
    )


@router.get("/retest-requests/{request_id}", response_model=RetestRequestResponse)
async def get_retest_request(
    request_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> RetestRequestResponse:
    """Get a specific retest request by ID."""
    retest_request = retest_service.get_retest_request(db, request_id)

    if not retest_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Retest request with ID {request_id} not found",
        )

    return _format_retest_response(retest_request)


@router.get("/retest-requests/{request_id}/pdf")
async def download_retest_pdf(
    request_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Download the retest request form as PDF."""
    try:
        pdf_content = retest_service.generate_retest_pdf(db, request_id)

        # Get the retest request for filename
        retest_request = retest_service.get_retest_request(db, request_id)
        filename = f"retest-request-{retest_request.reference_number}.pdf"

        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/retest-requests/{request_id}/daane-coc")
async def download_retest_daane_coc(
    request_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Download Daane Labs Chain of Custody (XLSX) for a retest request."""
    try:
        retest_request = retest_service.get_retest_request(db, request_id)
        if not retest_request:
            raise ValueError(f"Retest request with ID {request_id} not found")
        content, test_count = daane_coc_service.generate_coc_for_retest(db, request_id)
        filename = f"daane-coc-{retest_request.reference_number}.xlsx"
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Daane-Test-Count": str(test_count),
            "X-Daane-Test-Limit": "12",
            "X-Daane-Test-Limit-Exceeded": "true" if test_count > 12 else "false",
        }
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/retest-requests/{request_id}/daane-coc/pdf")
async def download_retest_daane_coc_pdf(
    request_id: int,
    db: DbSession,
    current_user: CurrentUser,
    special_instructions: Optional[str] = Query(default=None),
):
    """Download Daane Labs Chain of Custody (PDF) for a retest request."""
    try:
        retest_request = retest_service.get_retest_request(db, request_id)
        if not retest_request:
            raise ValueError(f"Retest request with ID {request_id} not found")
        content, test_count = daane_coc_service.generate_coc_pdf_for_retest(db, request_id, special_instructions=special_instructions)
        filename = f"daane-coc-{retest_request.reference_number}.pdf"
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Daane-Test-Count": str(test_count),
            "X-Daane-Test-Limit": "12",
            "X-Daane-Test-Limit-Exceeded": "true" if test_count > 12 else "false",
        }
        return Response(
            content=content,
            media_type="application/pdf",
            headers=headers,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/retest-requests/{request_id}/complete", response_model=RetestRequestResponse)
async def complete_retest_request(
    request_id: int,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> RetestRequestResponse:
    """
    Manually mark a retest request as completed.

    Only QC Managers and Admins can complete retest requests.
    """
    try:
        retest_request = retest_service.complete_retest(
            db=db,
            retest_request_id=request_id,
            user_id=current_user.id,
        )
        return _format_retest_response(retest_request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/test-results/{test_result_id}/retest-history", response_model=List[RetestOriginalValue])
async def get_test_result_retest_history(
    test_result_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> List[RetestOriginalValue]:
    """Get retest history for a specific test result."""
    retest_items = retest_service.get_retest_items_for_test_result(db, test_result_id)

    return [
        RetestOriginalValue(
            test_result_id=item.test_result_id,
            original_value=item.original_value,
            retest_reference=item.retest_request.reference_number,
            retest_status=item.retest_request.status,
        )
        for item in retest_items
    ]
