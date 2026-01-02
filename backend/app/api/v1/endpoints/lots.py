"""Lot management endpoints."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func

from app.dependencies import DbSession, CurrentUser, QCManagerOrAdmin
from app.models import Lot, LotProduct, Product, Sublot
from app.models.enums import LotType, LotStatus
from app.schemas.lot import (
    LotCreate,
    LotUpdate,
    LotResponse,
    LotWithProductsResponse,
    LotListResponse,
    ProductInLot,
    SublotCreate,
    SublotResponse,
    LotStatusUpdate,
)

router = APIRouter()


def generate_reference_number(db) -> str:
    """Generate a unique reference number in format YYMMDD-XXX."""
    today = date.today()
    prefix = today.strftime("%y%m%d")

    # Find highest sequence for today
    max_ref = (
        db.query(Lot.reference_number)
        .filter(Lot.reference_number.like(f"{prefix}-%"))
        .order_by(Lot.reference_number.desc())
        .first()
    )

    if max_ref:
        try:
            seq = int(max_ref[0].split("-")[1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1

    return f"{prefix}-{seq:03d}"


@router.get("", response_model=LotListResponse)
async def list_lots(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    status_filter: Optional[LotStatus] = Query(None, alias="status"),
    lot_type: Optional[LotType] = None,
) -> LotListResponse:
    """List all lots with pagination and filtering."""
    query = db.query(Lot)

    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Lot.lot_number.ilike(search_term))
            | (Lot.reference_number.ilike(search_term))
        )

    if status_filter:
        query = query.filter(Lot.status == status_filter)

    if lot_type:
        query = query.filter(Lot.lot_type == lot_type)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    lots = (
        query.order_by(Lot.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return LotListResponse(
        items=[LotResponse.model_validate(lot) for lot in lots],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/status-counts")
async def get_status_counts(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Get count of lots by status."""
    counts = (
        db.query(Lot.status, func.count(Lot.id))
        .group_by(Lot.status)
        .all()
    )
    return {status.value: count for status, count in counts}


@router.get("/{lot_id}", response_model=LotWithProductsResponse)
async def get_lot(
    lot_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> LotWithProductsResponse:
    """Get a lot by ID with associated products."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    response = LotWithProductsResponse.model_validate(lot)
    response.products = [
        ProductInLot(
            id=lp.product.id,
            display_name=lp.product.display_name,
            brand=lp.product.brand,
            percentage=lp.percentage,
        )
        for lp in lot.lot_products
        if lp.product
    ]

    return response


@router.post("", response_model=LotResponse, status_code=status.HTTP_201_CREATED)
async def create_lot(
    lot_in: LotCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> LotResponse:
    """Create a new lot."""
    # Check for duplicate lot number
    existing = db.query(Lot).filter(Lot.lot_number == lot_in.lot_number.upper()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lot with this lot number already exists",
        )

    # Generate reference number if not provided
    reference_number = lot_in.reference_number or generate_reference_number(db)

    # Verify reference number is unique
    existing_ref = db.query(Lot).filter(Lot.reference_number == reference_number.upper()).first()
    if existing_ref:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reference number already exists",
        )

    # Validate products exist
    if lot_in.products:
        product_ids = [p.product_id for p in lot_in.products]
        products = db.query(Product).filter(Product.id.in_(product_ids)).all()
        if len(products) != len(product_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more products not found",
            )

    # Create lot
    lot = Lot(
        lot_number=lot_in.lot_number.upper(),
        lot_type=lot_in.lot_type,
        reference_number=reference_number.upper(),
        mfg_date=lot_in.mfg_date,
        exp_date=lot_in.exp_date,
        status=LotStatus.PENDING,
        generate_coa=lot_in.generate_coa,
    )
    db.add(lot)
    db.flush()  # Get the lot ID

    # Add product associations
    for product_ref in lot_in.products:
        lot_product = LotProduct(
            lot_id=lot.id,
            product_id=product_ref.product_id,
            percentage=product_ref.percentage,
        )
        db.add(lot_product)

    db.commit()
    db.refresh(lot)

    return LotResponse.model_validate(lot)


@router.patch("/{lot_id}", response_model=LotResponse)
async def update_lot(
    lot_id: int,
    lot_in: LotUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> LotResponse:
    """Update a lot."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    # Check lot number uniqueness if updating
    update_data = lot_in.model_dump(exclude_unset=True)
    if "lot_number" in update_data:
        existing = (
            db.query(Lot)
            .filter(
                Lot.lot_number == update_data["lot_number"].upper(),
                Lot.id != lot_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lot with this lot number already exists",
            )
        update_data["lot_number"] = update_data["lot_number"].upper()

    # Update fields
    for field, value in update_data.items():
        setattr(lot, field, value)

    db.commit()
    db.refresh(lot)

    return LotResponse.model_validate(lot)


@router.patch("/{lot_id}/status", response_model=LotResponse)
async def update_lot_status(
    lot_id: int,
    status_update: LotStatusUpdate,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> LotResponse:
    """Update lot status (QC Manager or Admin only)."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    try:
        lot.update_status(status_update.status)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    db.commit()
    db.refresh(lot)

    return LotResponse.model_validate(lot)


@router.delete("/{lot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lot(
    lot_id: int,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> None:
    """Delete a lot (QC Manager or Admin only)."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    # Only allow deletion of pending lots
    if lot.status != LotStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete lots in pending status",
        )

    db.delete(lot)
    db.commit()


# Sublot endpoints
@router.get("/{lot_id}/sublots", response_model=list[SublotResponse])
async def list_sublots(
    lot_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[SublotResponse]:
    """List sublots for a parent lot."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    if lot.lot_type != LotType.PARENT_LOT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only parent lots can have sublots",
        )

    return [SublotResponse.model_validate(s) for s in lot.sublots]


@router.post("/{lot_id}/sublots", response_model=SublotResponse, status_code=status.HTTP_201_CREATED)
async def create_sublot(
    lot_id: int,
    sublot_in: SublotCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> SublotResponse:
    """Create a sublot for a parent lot."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    if lot.lot_type != LotType.PARENT_LOT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only parent lots can have sublots",
        )

    # Check for duplicate sublot number
    existing = db.query(Sublot).filter(Sublot.sublot_number == sublot_in.sublot_number.upper()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sublot number already exists",
        )

    sublot = Sublot(
        parent_lot_id=lot_id,
        sublot_number=sublot_in.sublot_number.upper(),
        production_date=sublot_in.production_date,
        quantity_lbs=sublot_in.quantity_lbs,
    )
    db.add(sublot)
    db.commit()
    db.refresh(sublot)

    return SublotResponse.model_validate(sublot)
