"""Lab test alias review endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DbSession, QCManagerOrAdmin
from app.models import LabTestAlias, LabTestType
from app.schemas.lab_test_alias import (
    LabTestBuiltinAliasList,
    LabTestBuiltinAliasRead,
    LabTestAliasDisableRequest,
    LabTestAliasList,
    LabTestAliasRead,
    LabTestAliasUpdate,
)
from app.services.lab_test_alias_service import LabTestAliasService, normalize_alias_key
from app.services.result_import_service import TEST_NAME_NORMALIZATION

router = APIRouter()
service = LabTestAliasService()


def _serialize(alias: LabTestAlias) -> LabTestAliasRead:
    target = alias.lab_test_type
    return LabTestAliasRead(
        id=alias.id,
        raw_phrase=alias.raw_phrase,
        normalized_key=alias.normalized_key,
        lab_name=alias.lab_name,
        lab_test_type_id=alias.lab_test_type_id,
        target_test_name=target.test_name if target else None,
        target_test_category=target.test_category if target else None,
        target_default_unit=target.default_unit if target else None,
        target_default_specification=target.default_specification if target else None,
        target_test_method=target.test_method if target else None,
        status=alias.status,
        source=alias.source,
        suggestion_count=alias.suggestion_count,
        first_seen_at=alias.first_seen_at,
        last_seen_at=alias.last_seen_at,
        last_result_import_id=alias.last_result_import_id,
        last_lot_id=alias.last_lot_id,
        last_filename=alias.last_filename,
        last_suggested_by_id=alias.last_suggested_by_id,
        approved_by_id=alias.approved_by_id,
        approved_at=alias.approved_at,
        disabled_by_id=alias.disabled_by_id,
        disabled_at=alias.disabled_at,
        disable_reason=alias.disable_reason,
        created_at=alias.created_at,
        updated_at=alias.updated_at,
    )


@router.get("", response_model=LabTestAliasList)
async def list_lab_test_aliases(
    db: DbSession,
    current_user: QCManagerOrAdmin,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    search: Optional[str] = None,
    lab_name: Optional[str] = None,
) -> LabTestAliasList:
    items, total = service.list_aliases(db, page, page_size, status, search, lab_name)
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return LabTestAliasList(
        items=[_serialize(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/builtins", response_model=LabTestBuiltinAliasList)
async def list_builtin_lab_test_aliases(
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> LabTestBuiltinAliasList:
    target_names = sorted(set(TEST_NAME_NORMALIZATION.values()))
    targets = {
        lab_type.test_name: lab_type
        for lab_type in db.query(LabTestType)
        .filter(LabTestType.test_name.in_(target_names))
        .all()
    }
    items = []
    for raw_phrase, target_name in sorted(TEST_NAME_NORMALIZATION.items()):
        target = targets.get(target_name)
        items.append(
            LabTestBuiltinAliasRead(
                raw_phrase=raw_phrase,
                normalized_key=normalize_alias_key(raw_phrase),
                lab_test_type_id=target.id if target else None,
                target_test_name=target_name,
                target_test_category=target.test_category if target else None,
                target_default_unit=target.default_unit if target else None,
                target_default_specification=(
                    target.default_specification if target else None
                ),
                target_test_method=target.test_method if target else None,
            )
        )
    return LabTestBuiltinAliasList(items=items, total=len(items))


@router.patch("/{alias_id}", response_model=LabTestAliasRead)
async def update_lab_test_alias(
    alias_id: int,
    payload: LabTestAliasUpdate,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> LabTestAliasRead:
    alias = service.get(db, alias_id)
    if not alias:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alias not found"
        )
    try:
        return _serialize(
            service.update_alias(
                db, alias, payload.model_dump(exclude_unset=True), current_user.id
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{alias_id}/approve", response_model=LabTestAliasRead)
async def approve_lab_test_alias(
    alias_id: int,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> LabTestAliasRead:
    alias = service.get(db, alias_id)
    if not alias:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alias not found"
        )
    try:
        return _serialize(service.approve_alias(db, alias, current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/{alias_id}", response_model=LabTestAliasRead)
async def disable_lab_test_alias(
    alias_id: int,
    payload: LabTestAliasDisableRequest,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> LabTestAliasRead:
    alias = service.get(db, alias_id)
    if not alias:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alias not found"
        )
    return _serialize(service.disable_alias(db, alias, current_user.id, payload.reason))
