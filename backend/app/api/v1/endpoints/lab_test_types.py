"""Lab Test Type management endpoints."""

from typing import Optional

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
)

router = APIRouter()


@router.get("", response_model=LabTestTypeListResponse)
async def list_lab_test_types(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
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


@router.delete("/{test_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lab_test_type(
    test_type_id: int,
    db: DbSession,
    current_user: AdminUser,
) -> None:
    """Delete a lab test type (admin only). Soft delete by setting is_active=False."""
    test_type = db.query(LabTestType).filter(LabTestType.id == test_type_id).first()
    if not test_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab test type not found",
        )

    # Check if test type is in use
    if test_type.product_specifications:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete - test type is used by {len(test_type.product_specifications)} products",
        )

    # Soft delete
    test_type.is_active = False
    db.commit()
