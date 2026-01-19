"""Audit trail management endpoints."""

from typing import Optional, List

from fastapi import APIRouter, HTTPException, status

from app.dependencies import DbSession, CurrentUser
from app.services.audit_service import AuditService
from app.schemas.audit import (
    AuditLogResponse,
    AuditHistoryResponse,
    LotAuditHistoryResponse,
)

router = APIRouter()
audit_service = AuditService()


@router.get("/{table_name}/{record_id}", response_model=AuditHistoryResponse)
async def get_record_audit_history(
    table_name: str,
    record_id: int,
    db: DbSession,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> AuditHistoryResponse:
    """
    Get complete audit history for a specific record.

    Args:
        table_name: Name of the table (e.g., 'lots', 'test_results')
        record_id: ID of the record
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return

    Returns:
        Paginated audit history with changes, users, and timestamps
    """
    history = audit_service.get_record_history(
        db=db,
        table_name=table_name.lower(),
        record_id=record_id,
        skip=skip,
        limit=limit,
    )

    # Convert to response format
    items = [
        AuditLogResponse(
            id=entry["id"],
            action=entry["action"],
            timestamp=entry["timestamp"],
            user_id=entry.get("user_id"),
            username=entry.get("user"),
            old_values=entry.get("old_values"),
            new_values=entry.get("new_values"),
            changes=entry.get("changes", {}),
            reason=entry.get("reason"),
            ip_address=entry.get("ip_address"),
            table_name=table_name.lower(),
            record_id=record_id,
        )
        for entry in history
    ]

    return AuditHistoryResponse(
        items=items,
        total=len(items),  # TODO: Add proper count query
        table_name=table_name.lower(),
        record_id=record_id,
    )


@router.get("/lots/{lot_id}/complete", response_model=LotAuditHistoryResponse)
async def get_lot_complete_audit_history(
    lot_id: int,
    db: DbSession,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 200,
) -> LotAuditHistoryResponse:
    """
    Get complete audit history for a lot including related records.

    This includes audit entries for:
    - The lot itself
    - Test results associated with the lot
    - COA releases for the lot

    Args:
        lot_id: ID of the lot
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return

    Returns:
        Combined audit history from all related tables
    """
    all_items: List[AuditLogResponse] = []
    tables_included = []

    # Get lot audit history
    lot_history = audit_service.get_record_history(
        db=db,
        table_name="lots",
        record_id=lot_id,
        skip=0,
        limit=limit,
    )
    if lot_history:
        tables_included.append("lots")
        for entry in lot_history:
            all_items.append(
                AuditLogResponse(
                    id=entry["id"],
                    action=entry["action"],
                    timestamp=entry["timestamp"],
                    user_id=entry.get("user_id"),
                    username=entry.get("user"),
                    old_values=entry.get("old_values"),
                    new_values=entry.get("new_values"),
                    changes=entry.get("changes", {}),
                    reason=entry.get("reason"),
                    ip_address=entry.get("ip_address"),
                    table_name="lots",
                    record_id=lot_id,
                )
            )

    # Get test results audit history for this lot
    from app.models.test_result import TestResult

    test_results = db.query(TestResult.id).filter(TestResult.lot_id == lot_id).all()
    test_result_ids = [tr.id for tr in test_results]

    if test_result_ids:
        tables_included.append("test_results")
        for tr_id in test_result_ids:
            tr_history = audit_service.get_record_history(
                db=db,
                table_name="test_results",
                record_id=tr_id,
                skip=0,
                limit=50,  # Limit per test result
            )
            for entry in tr_history:
                all_items.append(
                    AuditLogResponse(
                        id=entry["id"],
                        action=entry["action"],
                        timestamp=entry["timestamp"],
                        user_id=entry.get("user_id"),
                        username=entry.get("user"),
                        old_values=entry.get("old_values"),
                        new_values=entry.get("new_values"),
                        changes=entry.get("changes", {}),
                        reason=entry.get("reason"),
                        ip_address=entry.get("ip_address"),
                        table_name="test_results",
                        record_id=tr_id,
                    )
                )

    # Get COA release audit history for this lot
    from app.models.coa_release import COARelease

    coa_releases = db.query(COARelease.id).filter(COARelease.lot_id == lot_id).all()
    coa_release_ids = [cr.id for cr in coa_releases]

    if coa_release_ids:
        tables_included.append("coa_releases")
        for cr_id in coa_release_ids:
            cr_history = audit_service.get_record_history(
                db=db,
                table_name="coa_releases",
                record_id=cr_id,
                skip=0,
                limit=50,
            )
            for entry in cr_history:
                all_items.append(
                    AuditLogResponse(
                        id=entry["id"],
                        action=entry["action"],
                        timestamp=entry["timestamp"],
                        user_id=entry.get("user_id"),
                        username=entry.get("user"),
                        old_values=entry.get("old_values"),
                        new_values=entry.get("new_values"),
                        changes=entry.get("changes", {}),
                        reason=entry.get("reason"),
                        ip_address=entry.get("ip_address"),
                        table_name="coa_releases",
                        record_id=cr_id,
                    )
                )

    # Sort all items by timestamp descending
    all_items.sort(key=lambda x: x.timestamp, reverse=True)

    # Apply pagination
    paginated_items = all_items[skip : skip + limit]

    return LotAuditHistoryResponse(
        items=paginated_items,
        total=len(all_items),
        lot_id=lot_id,
        tables_included=tables_included,
    )
