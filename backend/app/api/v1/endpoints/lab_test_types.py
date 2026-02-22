"""Lab Test Type management endpoints."""

from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func

from app.dependencies import DbSession, CurrentUser, AdminUser
from app.models import LabTestType
from app.schemas.lab_test_type import (
    LabTestTypeCreate,
    LabTestTypeUpdate,
    LabTestTypeResponse,
    LabTestTypeListResponse,
    LabTestTypeCategoryCount,
    LabTestTypeBulkImportRow,
    LabTestTypeBulkImportResult,
)
from app.schemas.product import ArchiveRequest

router = APIRouter()


@router.get("", response_model=LabTestTypeListResponse)
async def list_lab_test_types(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: Optional[str] = None,
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> LabTestTypeListResponse:
    """List all lab test types with pagination and filtering."""
    query = db.query(LabTestType)

    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (LabTestType.test_name.ilike(search_term))
            | (LabTestType.description.ilike(search_term))
            | (LabTestType.test_method.ilike(search_term))
            | (LabTestType.abbreviations.ilike(search_term))
        )

    if category:
        query = query.filter(LabTestType.test_category == category)

    if is_active is not None:
        query = query.filter(LabTestType.is_active == is_active)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    test_types = (
        query.order_by(LabTestType.test_category, LabTestType.test_name)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return LabTestTypeListResponse(
        items=[LabTestTypeResponse.model_validate(t) for t in test_types],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/categories", response_model=list[LabTestTypeCategoryCount])
async def list_categories(
    db: DbSession,
    current_user: CurrentUser,
) -> list[LabTestTypeCategoryCount]:
    """Get list of categories with test type counts."""
    categories = (
        db.query(LabTestType.test_category, func.count(LabTestType.id))
        .filter(LabTestType.is_active == True)
        .group_by(LabTestType.test_category)
        .order_by(LabTestType.test_category)
        .all()
    )
    return [
        LabTestTypeCategoryCount(category=c[0], count=c[1]) for c in categories
    ]


@router.get("/{test_type_id}", response_model=LabTestTypeResponse)
async def get_lab_test_type(
    test_type_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> LabTestTypeResponse:
    """Get a lab test type by ID."""
    test_type = db.query(LabTestType).filter(LabTestType.id == test_type_id).first()
    if not test_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab test type not found",
        )

    return LabTestTypeResponse.model_validate(test_type)


@router.post("", response_model=LabTestTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_lab_test_type(
    test_type_in: LabTestTypeCreate,
    db: DbSession,
    current_user: AdminUser,
) -> LabTestTypeResponse:
    """Create a new lab test type (admin only)."""
    # Check for duplicate test name
    existing = (
        db.query(LabTestType)
        .filter(LabTestType.test_name == test_type_in.test_name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lab test type with this name already exists",
        )

    test_type = LabTestType(
        test_name=test_type_in.test_name,
        test_category=test_type_in.test_category,
        default_unit=test_type_in.default_unit,
        description=test_type_in.description,
        test_method=test_type_in.test_method,
        abbreviations=test_type_in.abbreviations,
        default_specification=test_type_in.default_specification,
        is_active=True,
    )
    db.add(test_type)
    db.commit()
    db.refresh(test_type)

    return LabTestTypeResponse.model_validate(test_type)


@router.patch("/{test_type_id}", response_model=LabTestTypeResponse)
async def update_lab_test_type(
    test_type_id: int,
    test_type_in: LabTestTypeUpdate,
    db: DbSession,
    current_user: AdminUser,
) -> LabTestTypeResponse:
    """Update a lab test type (admin only)."""
    test_type = db.query(LabTestType).filter(LabTestType.id == test_type_id).first()
    if not test_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab test type not found",
        )

    # Check test name uniqueness if updating
    update_data = test_type_in.model_dump(exclude_unset=True)
    if "test_name" in update_data:
        existing = (
            db.query(LabTestType)
            .filter(
                LabTestType.test_name == update_data["test_name"],
                LabTestType.id != test_type_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lab test type with this name already exists",
            )

    # Update fields
    for field, value in update_data.items():
        setattr(test_type, field, value)

    db.commit()
    db.refresh(test_type)

    return LabTestTypeResponse.model_validate(test_type)


@router.delete("/{test_type_id}", response_model=LabTestTypeResponse)
async def archive_lab_test_type(
    test_type_id: int,
    archive_request: ArchiveRequest,
    db: DbSession,
    current_user: AdminUser,
) -> LabTestTypeResponse:
    """Archive a lab test type (soft delete, admin only). Requires a reason."""
    test_type = db.query(LabTestType).filter(LabTestType.id == test_type_id).first()
    if not test_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab test type not found",
        )

    if not test_type.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lab test type is already archived",
        )

    # Check if test type is in use - warn but allow archiving
    # (archived tests won't be available for new products but existing specs remain)

    # Archive (soft delete)
    test_type.archive(user_id=current_user.id, reason=archive_request.reason)
    db.commit()
    db.refresh(test_type)

    return LabTestTypeResponse.model_validate(test_type)


@router.post("/{test_type_id}/restore", response_model=LabTestTypeResponse)
async def restore_lab_test_type(
    test_type_id: int,
    db: DbSession,
    current_user: AdminUser,
) -> LabTestTypeResponse:
    """Restore an archived lab test type (admin only)."""
    test_type = db.query(LabTestType).filter(LabTestType.id == test_type_id).first()
    if not test_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab test type not found",
        )

    if test_type.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lab test type is not archived",
        )

    # Restore
    test_type.restore()
    db.commit()
    db.refresh(test_type)

    return LabTestTypeResponse.model_validate(test_type)


@router.get("/archived", response_model=LabTestTypeListResponse)
async def list_archived_lab_test_types(
    db: DbSession,
    current_user: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: Optional[str] = None,
) -> LabTestTypeListResponse:
    """List archived lab test types (admin only)."""
    query = db.query(LabTestType).filter(LabTestType.is_active == False)

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (LabTestType.test_name.ilike(search_term))
            | (LabTestType.description.ilike(search_term))
            | (LabTestType.test_method.ilike(search_term))
        )

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    test_types = (
        query.order_by(LabTestType.archived_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return LabTestTypeListResponse(
        items=[LabTestTypeResponse.model_validate(t) for t in test_types],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/bulk-import", response_model=LabTestTypeBulkImportResult)
async def bulk_import_lab_test_types(
    rows: List[LabTestTypeBulkImportRow],
    db: DbSession,
    current_user: AdminUser,
) -> LabTestTypeBulkImportResult:
    """Bulk import lab test types (admin only)."""
    total_rows = len(rows)
    imported = 0
    skipped = 0
    errors = []

    # Get existing test names for duplicate detection
    existing_names = {
        t.test_name.lower() for t in db.query(LabTestType.test_name).all()
    }

    for idx, row in enumerate(rows, start=1):
        try:
            # Validate required fields
            if not row.test_name or not row.test_category:
                errors.append(f"Row {idx}: Missing required fields")
                skipped += 1
                continue

            # Check duplicates
            if row.test_name.lower() in existing_names:
                errors.append(f"Row {idx}: Test '{row.test_name}' already exists")
                skipped += 1
                continue

            # Create lab test type
            test_type = LabTestType(
                test_name=row.test_name,
                test_category=row.test_category,
                default_unit=row.default_unit,
                description=row.description,
                test_method=row.test_method,
                abbreviations=row.abbreviations,
                default_specification=row.default_specification,
                is_active=True,
            )
            db.add(test_type)
            existing_names.add(row.test_name.lower())
            imported += 1

        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")
            skipped += 1

    if imported > 0:
        db.commit()

    return LabTestTypeBulkImportResult(
        total_rows=total_rows,
        imported=imported,
        skipped=skipped,
        errors=errors,
    )
