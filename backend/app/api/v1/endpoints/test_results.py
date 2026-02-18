"""Test Result management endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DbSession, CurrentUser, QCManagerOrAdmin
from app.models import TestResult, Lot, User
from app.models.enums import TestResultStatus, AuditAction, RetestStatus
from app.models.retest_request import RetestRequest, RetestItem
from app.services.lot_service import LotService
from app.services.audit_service import AuditService
from app.services.retest_service import retest_service
from app.schemas.test_result import (
    TestResultCreate,
    TestResultUpdate,
    TestResultResponse,
    TestResultWithLotResponse,
    TestResultListResponse,
    TestResultBulkCreate,
    TestResultApproval,
    TestResultBulkApproval,
)

router = APIRouter()


@router.get("", response_model=TestResultListResponse)
async def list_test_results(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    lot_id: Optional[int] = None,
    status_filter: Optional[TestResultStatus] = Query(None, alias="status"),
    test_type: Optional[str] = None,
    needs_review: Optional[bool] = None,
) -> TestResultListResponse:
    """List all test results with pagination and filtering."""
    query = db.query(TestResult)

    # Apply filters
    if lot_id:
        query = query.filter(TestResult.lot_id == lot_id)

    if status_filter:
        query = query.filter(TestResult.status == status_filter)

    if test_type:
        query = query.filter(TestResult.test_type.ilike(f"%{test_type}%"))

    if needs_review is True:
        query = query.filter(
            TestResult.status == TestResultStatus.DRAFT,
            (TestResult.confidence_score < 0.7) | (TestResult.confidence_score.is_(None))
        )

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    results = (
        query.order_by(TestResult.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return TestResultListResponse(
        items=[TestResultResponse.model_validate(r) for r in results],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/pending-review")
async def get_pending_review_count(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Get count of test results pending review."""
    count = (
        db.query(TestResult)
        .filter(TestResult.status == TestResultStatus.DRAFT)
        .count()
    )
    return {"pending_count": count}


@router.get("/{result_id}", response_model=TestResultWithLotResponse)
async def get_test_result(
    result_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> TestResultWithLotResponse:
    """Get a test result by ID with lot information."""
    result = db.query(TestResult).filter(TestResult.id == result_id).first()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test result not found",
        )

    response = TestResultWithLotResponse.model_validate(result)
    if result.lot:
        response.lot_number = result.lot.lot_number
        response.lot_reference = result.lot.reference_number

    return response


@router.post("", response_model=TestResultResponse, status_code=status.HTTP_201_CREATED)
async def create_test_result(
    result_in: TestResultCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> TestResultResponse:
    """Create a new test result."""
    # Verify lot exists
    lot = db.query(Lot).filter(Lot.id == result_in.lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    result = TestResult(
        lot_id=result_in.lot_id,
        test_type=result_in.test_type,
        result_value=result_in.result_value,
        unit=result_in.unit,
        test_date=result_in.test_date,
        pdf_source=result_in.pdf_source,
        confidence_score=result_in.confidence_score,
        specification=result_in.specification,
        method=result_in.method,
        notes=result_in.notes,
        status=TestResultStatus.DRAFT,
    )
    db.add(result)
    db.flush()  # Get the ID before commit

    # Log to audit trail
    audit_service = AuditService()
    new_values = {
        "test_type": result.test_type,
        "result_value": result.result_value,
        "unit": result.unit,
        "specification": result.specification,
        "method": result.method,
        "status": result.status.value,
    }
    audit_service.log_action(
        db=db,
        table_name="test_results",
        record_id=result.id,
        action=AuditAction.INSERT,
        user_id=current_user.id,
        old_values=None,
        new_values=new_values,
        reason=f"Test result created: {result.test_type}",
    )

    db.commit()
    db.refresh(result)

    # Auto-recalculate lot status
    lot_service = LotService()
    lot_service.recalculate_lot_status(db, result_in.lot_id, user_id=current_user.id)

    return TestResultResponse.model_validate(result)


@router.post("/bulk", response_model=list[TestResultResponse], status_code=status.HTTP_201_CREATED)
async def bulk_create_test_results(
    bulk_in: TestResultBulkCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> list[TestResultResponse]:
    """Create multiple test results for a lot."""
    # Verify lot exists
    lot = db.query(Lot).filter(Lot.id == bulk_in.lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    created_results = []
    for result_data in bulk_in.results:
        result = TestResult(
            lot_id=bulk_in.lot_id,
            test_type=result_data.test_type,
            result_value=result_data.result_value,
            unit=result_data.unit,
            test_date=result_data.test_date,
            pdf_source=bulk_in.pdf_source,
            specification=result_data.specification,
            method=result_data.method,
            notes=result_data.notes,
            status=TestResultStatus.DRAFT,
        )
        db.add(result)
        created_results.append(result)

    db.flush()  # Get IDs before commit

    # Log to audit trail for each created result
    audit_service = AuditService()
    for result in created_results:
        new_values = {
            "test_type": result.test_type,
            "result_value": result.result_value,
            "unit": result.unit,
            "specification": result.specification,
            "method": result.method,
            "status": result.status.value,
        }
        audit_service.log_action(
            db=db,
            table_name="test_results",
            record_id=result.id,
            action=AuditAction.INSERT,
            user_id=current_user.id,
            old_values=None,
            new_values=new_values,
            reason=f"Test result created (bulk): {result.test_type}",
        )

    db.commit()
    for result in created_results:
        db.refresh(result)

    # Auto-recalculate lot status
    lot_service = LotService()
    lot_service.recalculate_lot_status(db, bulk_in.lot_id, user_id=current_user.id)

    return [TestResultResponse.model_validate(r) for r in created_results]


@router.patch("/{result_id}", response_model=TestResultResponse)
async def update_test_result(
    result_id: int,
    result_in: TestResultUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> TestResultResponse:
    """Update a test result."""
    result = db.query(TestResult).filter(TestResult.id == result_id).first()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test result not found",
        )

    # Only allow editing draft results
    if result.status != TestResultStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only edit draft test results",
        )

    update_data = result_in.model_dump(exclude_unset=True)

    # Capture old values before update for audit trail
    old_values = {}
    for field in update_data.keys():
        if hasattr(result, field):
            old_val = getattr(result, field)
            if hasattr(old_val, 'isoformat'):
                old_values[field] = old_val.isoformat()
            elif hasattr(old_val, 'value'):
                old_values[field] = old_val.value
            else:
                old_values[field] = old_val

    for field, value in update_data.items():
        setattr(result, field, value)

    db.flush()

    # Capture new values for audit trail
    new_values = {}
    for field in update_data.keys():
        if hasattr(result, field):
            new_val = getattr(result, field)
            if hasattr(new_val, 'isoformat'):
                new_values[field] = new_val.isoformat()
            elif hasattr(new_val, 'value'):
                new_values[field] = new_val.value
            else:
                new_values[field] = new_val

    # Log to audit trail if there are actual changes
    if old_values != new_values:
        # Check if this test result is part of a pending retest
        pending_retest_item = (
            db.query(RetestItem)
            .join(RetestRequest)
            .filter(
                RetestItem.test_result_id == result_id,
                RetestRequest.status == RetestStatus.PENDING,
            )
            .first()
        )

        # Add retest context to audit if applicable
        audit_reason = f"Test result update: {result.test_type}"
        if pending_retest_item:
            retest_ref = pending_retest_item.retest_request.reference_number
            new_values["retest_context"] = {
                "retest_request_id": pending_retest_item.retest_request_id,
                "reference_number": retest_ref,
            }
            audit_reason = f"Retest result entry ({retest_ref}): {result.test_type}"

        audit_service = AuditService()
        audit_service.log_action(
            db=db,
            table_name="test_results",
            record_id=result.id,
            action=AuditAction.UPDATE,
            user_id=current_user.id,
            old_values=old_values,
            new_values=new_values,
            reason=audit_reason,
        )

    db.commit()
    db.refresh(result)

    # Check if this update completes any pending retests
    if 'result_value' in update_data:
        retest_service.check_and_complete_retest(db, result_id, user_id=current_user.id)

    # Auto-recalculate lot status based on test results completion
    if result.lot_id:
        lot_service = LotService()
        lot_service.recalculate_lot_status(db, result.lot_id, user_id=current_user.id)

    return TestResultResponse.model_validate(result)


@router.patch("/{result_id}/status", response_model=TestResultResponse)
async def update_test_result_status(
    result_id: int,
    approval: TestResultApproval,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> TestResultResponse:
    """Approve or reject a test result (QC Manager or Admin only)."""
    result = db.query(TestResult).filter(TestResult.id == result_id).first()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test result not found",
        )

    # Capture old values
    old_values = {
        "status": result.status.value,
        "approved_by_id": result.approved_by_id,
        "approved_at": result.approved_at.isoformat() if result.approved_at else None,
        "notes": result.notes,
    }

    if approval.status == TestResultStatus.APPROVED:
        result.status = TestResultStatus.APPROVED
        result.approved_by_id = current_user.id
        result.approved_at = datetime.utcnow()
        action_reason = f"Test result approved: {result.test_type}"
    else:
        result.status = TestResultStatus.DRAFT
        result.approved_by_id = None
        result.approved_at = None
        action_reason = f"Test result reverted to draft: {result.test_type}"

    if approval.notes:
        result.notes = f"{result.notes or ''}\n{approval.notes}".strip()

    db.flush()

    # Log the approval/rejection
    audit_service = AuditService()
    audit_service.log_action(
        db=db,
        table_name="test_results",
        record_id=result.id,
        action=AuditAction.APPROVE if approval.status == TestResultStatus.APPROVED else AuditAction.UPDATE,
        user_id=current_user.id,
        old_values=old_values,
        new_values={
            "status": result.status.value,
            "approved_by_id": result.approved_by_id,
            "approved_at": result.approved_at.isoformat() if result.approved_at else None,
            "notes": result.notes,
        },
        reason=action_reason,
    )

    db.commit()
    db.refresh(result)

    return TestResultResponse.model_validate(result)


@router.post("/bulk-approve", response_model=list[TestResultResponse])
async def bulk_approve_test_results(
    bulk_approval: TestResultBulkApproval,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> list[TestResultResponse]:
    """Bulk approve or reject test results (QC Manager or Admin only)."""
    results = (
        db.query(TestResult)
        .filter(TestResult.id.in_(bulk_approval.result_ids))
        .all()
    )

    if len(results) != len(bulk_approval.result_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more test results not found",
        )

    audit_service = AuditService()
    action_type = AuditAction.APPROVE if bulk_approval.status == TestResultStatus.APPROVED else AuditAction.UPDATE

    for result in results:
        # Capture old values
        old_values = {
            "status": result.status.value,
            "approved_by_id": result.approved_by_id,
            "approved_at": result.approved_at.isoformat() if result.approved_at else None,
        }

        if bulk_approval.status == TestResultStatus.APPROVED:
            result.status = TestResultStatus.APPROVED
            result.approved_by_id = current_user.id
            result.approved_at = datetime.utcnow()
            action_reason = f"Bulk approved: {result.test_type}"
        else:
            result.status = TestResultStatus.DRAFT
            result.approved_by_id = None
            result.approved_at = None
            action_reason = f"Bulk reverted to draft: {result.test_type}"

        # Log each result's change
        audit_service.log_action(
            db=db,
            table_name="test_results",
            record_id=result.id,
            action=action_type,
            user_id=current_user.id,
            old_values=old_values,
            new_values={
                "status": result.status.value,
                "approved_by_id": result.approved_by_id,
                "approved_at": result.approved_at.isoformat() if result.approved_at else None,
            },
            reason=action_reason,
        )

    db.commit()
    for result in results:
        db.refresh(result)

    return [TestResultResponse.model_validate(r) for r in results]


@router.delete("/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_result(
    result_id: int,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> None:
    """Delete a test result (QC Manager or Admin only)."""
    result = db.query(TestResult).filter(TestResult.id == result_id).first()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test result not found",
        )

    # Only allow deletion of draft results
    if result.status != TestResultStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete draft test results",
        )

    db.delete(result)
    db.commit()
