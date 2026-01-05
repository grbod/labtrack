"""Lot management endpoints."""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.dependencies import DbSession, CurrentUser, QCManagerOrAdmin
from app.models import Lot, LotProduct, Product, Sublot, ProductTestSpecification, TestResult
from app.models.enums import LotType, LotStatus
from app.schemas.lot import (
    LotCreate,
    LotUpdate,
    LotResponse,
    LotWithProductsResponse,
    LotWithProductSummaryResponse,
    LotWithProductSpecsResponse,
    LotListResponse,
    ProductInLot,
    ProductInLotWithSpecs,
    ProductSummary,
    TestSpecInProduct,
    SublotCreate,
    SublotBulkCreate,
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
    exclude_statuses: Optional[List[LotStatus]] = Query(None, alias="exclude_statuses"),
    lot_type: Optional[LotType] = None,
) -> LotListResponse:
    """List all lots with pagination, filtering, and product info."""
    # Eager load products, test specs (with lab test types), and test results to avoid N+1 queries
    query = db.query(Lot).options(
        joinedload(Lot.lot_products)
        .joinedload(LotProduct.product)
        .joinedload(Product.test_specifications)
        .joinedload(ProductTestSpecification.lab_test_type),
        joinedload(Lot.test_results),
    )

    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Lot.lot_number.ilike(search_term))
            | (Lot.reference_number.ilike(search_term))
        )

    if status_filter:
        query = query.filter(Lot.status == status_filter)

    if exclude_statuses:
        query = query.filter(Lot.status.notin_(exclude_statuses))

    if lot_type:
        query = query.filter(Lot.lot_type == lot_type)

    # Get total count (separate query without joins for accurate count)
    count_query = db.query(func.count(Lot.id))
    if search:
        search_term = f"%{search}%"
        count_query = count_query.filter(
            (Lot.lot_number.ilike(search_term))
            | (Lot.reference_number.ilike(search_term))
        )
    if status_filter:
        count_query = count_query.filter(Lot.status == status_filter)
    if exclude_statuses:
        count_query = count_query.filter(Lot.status.notin_(exclude_statuses))
    if lot_type:
        count_query = count_query.filter(Lot.lot_type == lot_type)
    total = count_query.scalar()

    # Apply pagination
    offset = (page - 1) * page_size
    lots = (
        query.order_by(Lot.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    # Build response with product summaries and test counts
    items = []
    for lot in lots:
        lot_response = LotWithProductSummaryResponse.model_validate(lot)
        lot_response.products = [
            ProductSummary(
                id=lp.product.id,
                brand=lp.product.brand,
                product_name=lp.product.product_name,
                flavor=lp.product.flavor,
                size=lp.product.size,
                percentage=lp.percentage,
            )
            for lp in lot.lot_products
            if lp.product
        ]

        # Calculate test counts
        # tests_total: sum of test specifications across all products in the lot
        tests_total = sum(
            len(lp.product.test_specifications)
            for lp in lot.lot_products
            if lp.product
        )

        # Build a map of test_name -> spec for failure checking
        spec_by_test_name = {}
        for lp in lot.lot_products:
            if lp.product:
                for spec in lp.product.test_specifications:
                    if spec.lab_test_type:
                        spec_by_test_name[spec.lab_test_type.test_name] = spec

        # tests_entered: count of test results with a value entered
        # tests_failed: count of test results that failed their specification
        tests_entered = 0
        tests_failed = 0
        for tr in lot.test_results:
            if tr.result_value is not None and tr.result_value.strip() != "":
                tests_entered += 1
                # Check if this test fails its specification
                spec = spec_by_test_name.get(tr.test_type)
                if spec and not spec.matches_result(tr.result_value):
                    tests_failed += 1

        lot_response.tests_total = tests_total
        lot_response.tests_entered = tests_entered
        lot_response.tests_failed = tests_failed

        items.append(lot_response)

    return LotListResponse(
        items=items,
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


@router.get("/{lot_id}/with-specs", response_model=LotWithProductSpecsResponse)
async def get_lot_with_specs(
    lot_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> LotWithProductSpecsResponse:
    """
    Get a lot by ID with products and their test specifications.
    Used by the Sample Modal to display inherited tests.
    """
    # Eager load products with test specifications and lab test types
    lot = (
        db.query(Lot)
        .options(
            joinedload(Lot.lot_products)
            .joinedload(LotProduct.product)
            .joinedload(Product.test_specifications)
            .joinedload(ProductTestSpecification.lab_test_type)
        )
        .filter(Lot.id == lot_id)
        .first()
    )

    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    # Build response with products and their test specs
    products_with_specs = []
    for lp in lot.lot_products:
        if not lp.product:
            continue

        product = lp.product
        test_specs = []

        for spec in product.test_specifications:
            # Get lab test type info
            lab_test = spec.lab_test_type
            test_specs.append(
                TestSpecInProduct(
                    id=spec.id,
                    lab_test_type_id=spec.lab_test_type_id,
                    test_name=lab_test.test_name if lab_test else "Unknown",
                    test_category=lab_test.test_category if lab_test else None,
                    test_method=lab_test.test_method if lab_test else None,
                    test_unit=lab_test.default_unit if lab_test else None,
                    specification=spec.specification,
                    is_required=spec.is_required,
                )
            )

        products_with_specs.append(
            ProductInLotWithSpecs(
                id=product.id,
                brand=product.brand,
                product_name=product.product_name,
                flavor=product.flavor,
                size=product.size,
                display_name=product.display_name,
                percentage=lp.percentage,
                test_specifications=test_specs,
            )
        )

    response = LotWithProductSpecsResponse.model_validate(lot)
    response.products = products_with_specs

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
        status=LotStatus.AWAITING_RESULTS,
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


@router.post("/{lot_id}/submit-for-review", response_model=LotResponse)
async def submit_for_review(
    lot_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> LotResponse:
    """Submit a lot for QC review (moves from under_review to awaiting_release)."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    # Must be in under_review status to submit
    if lot.status != LotStatus.UNDER_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit for review from status '{lot.status.value}'. Must be 'under_review'.",
        )

    lot.status = LotStatus.AWAITING_RELEASE
    db.commit()
    db.refresh(lot)

    return LotResponse.model_validate(lot)


@router.post("/{lot_id}/resubmit", response_model=LotResponse)
async def resubmit_lot(
    lot_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> LotResponse:
    """Resubmit a rejected lot for review."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    # Must be rejected to resubmit
    if lot.status != LotStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resubmit from status '{lot.status.value}'. Must be 'rejected'.",
        )

    # Clear rejection reason and move back to awaiting_release
    lot.rejection_reason = None
    lot.status = LotStatus.AWAITING_RELEASE
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

    # Handle rejection - require reason
    if status_update.status == LotStatus.REJECTED:
        if not status_update.rejection_reason or not status_update.rejection_reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rejection reason is required when rejecting a lot",
            )
        lot.rejection_reason = status_update.rejection_reason.strip()
    elif status_update.status == LotStatus.APPROVED:
        # Clear any previous rejection reason when approving (unless it's a QC override note)
        if lot.rejection_reason and not lot.rejection_reason.startswith("[QC Override]"):
            lot.rejection_reason = None

    try:
        lot.update_status(
            status_update.status,
            rejection_reason=status_update.rejection_reason,
            override_reason=status_update.override_reason,
        )
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

    # Only allow deletion of awaiting_results lots
    if lot.status != LotStatus.AWAITING_RESULTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete lots in awaiting_results status",
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


@router.post("/{lot_id}/sublots/bulk", response_model=list[SublotResponse], status_code=status.HTTP_201_CREATED)
async def create_sublots_bulk(
    lot_id: int,
    sublots_in: SublotBulkCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> list[SublotResponse]:
    """Create multiple sublots for a parent lot in bulk."""
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

    # Check for duplicate sublot numbers
    sublot_numbers = [s.sublot_number.upper() for s in sublots_in.sublots]
    existing = db.query(Sublot).filter(Sublot.sublot_number.in_(sublot_numbers)).all()
    if existing:
        existing_numbers = [s.sublot_number for s in existing]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sublot numbers already exist: {', '.join(existing_numbers)}",
        )

    # Create all sublots
    created_sublots = []
    for sublot_in in sublots_in.sublots:
        sublot = Sublot(
            parent_lot_id=lot_id,
            sublot_number=sublot_in.sublot_number.upper(),
            production_date=sublot_in.production_date,
            quantity_lbs=sublot_in.quantity_lbs,
        )
        db.add(sublot)
        created_sublots.append(sublot)

    db.commit()

    # Refresh all sublots to get IDs
    for sublot in created_sublots:
        db.refresh(sublot)

    return [SublotResponse.model_validate(s) for s in created_sublots]
