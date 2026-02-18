"""COA Release management endpoints."""

from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import joinedload

from app.dependencies import DbSession, CurrentUser, QCManagerOrAdmin
from app.config import settings
from app.services.audit_service import AuditService
from app.models.enums import AuditAction
from app.models.coa_release import COARelease
from app.models.lot import Lot
from app.services.coa_generation_service import coa_generation_service
from app.services.release_service import ReleaseService
from app.services.lab_info_service import lab_info_service
from app.schemas.release import (
    COAReleaseResponse,
    COAReleaseWithSourcePdfs,
    LotInRelease,
    ProductInRelease,
    CustomerInRelease,
    ReleaseQueueItem,
    ReleaseQueueResponse,
    DraftSaveRequest,
    SendBackRequest,
    EmailSendRequest,
    EmailHistoryResponse,
    ApproveReleaseResponse,
    ReleaseDetailsByLotProduct,
    ApproveByLotProductRequest,
    ApproveByLotProductResponse,
    COAPreviewData,
    COATestResult,
)

router = APIRouter()
release_service = ReleaseService()
audit_service = AuditService()


def _get_coa_pdf_response(
    db: DbSession,
    release_id: int,
    inline: bool = True,
) -> FileResponse:
    """
    Helper to get COA PDF as FileResponse.

    Args:
        db: Database session
        release_id: ID of the COARelease
        inline: If True, display inline (preview). If False, force download.

    Returns:
        FileResponse with the PDF
    """
    # Verify the release exists
    coa_release = (
        db.query(COARelease)
        .options(joinedload(COARelease.lot))
        .filter(COARelease.id == release_id)
        .first()
    )

    if not coa_release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="COA Release not found",
        )

    try:
        # Get or generate the PDF (returns storage key, not full path)
        storage_key = coa_generation_service.get_or_generate_pdf(db, release_id)

        # Get full path by prepending upload_path
        full_path = settings.upload_path / storage_key

        # Verify file exists
        if not full_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PDF file generation failed",
            )

        # Return PDF with appropriate disposition
        disposition = "inline" if inline else "attachment"
        filename = f"COA_{coa_release.lot.lot_number}.pdf"

        return FileResponse(
            path=str(full_path),
            media_type="application/pdf",
            filename=filename,
            headers={
                "Content-Disposition": f"{disposition}; filename=\"{filename}\""
            }
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception as e:
        action = "generate" if inline else "download"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to {action} COA PDF: {str(e)}",
        )


@router.get("/{release_id}/preview")
async def preview_coa(
    release_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    """Generate and return COA PDF for inline preview."""
    return _get_coa_pdf_response(db, release_id, inline=True)


@router.get("/{release_id}/download")
async def download_coa(
    release_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    """Download the COA PDF as an attachment."""
    return _get_coa_pdf_response(db, release_id, inline=False)


@router.get("/{release_id}/preview-html", response_class=HTMLResponse)
async def preview_coa_html(
    release_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> HTMLResponse:
    """
    Return COA as HTML for browser preview.

    This is useful for previewing the COA without generating a PDF.
    """
    # Verify the release exists
    coa_release = db.query(COARelease).filter(COARelease.id == release_id).first()

    if not coa_release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="COA Release not found",
        )

    try:
        html_content = coa_generation_service.render_html_preview(db, release_id)
        return HTMLResponse(content=html_content)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to render COA preview: {str(e)}",
        )


@router.get("/{release_id}/data")
async def get_coa_data(
    release_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """
    Get COA data without generating PDF.

    Returns the data that would be used for COA generation.
    Useful for frontend preview rendering.
    """
    # Verify the release exists
    coa_release = db.query(COARelease).filter(COARelease.id == release_id).first()

    if not coa_release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="COA Release not found",
        )

    try:
        data = coa_generation_service.get_preview_data(db, release_id)
        return {"status": "success", "data": data}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get COA data: {str(e)}",
        )


@router.post("/{release_id}/regenerate")
async def regenerate_coa(
    release_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """
    Force regeneration of the COA PDF.

    This will always generate a new PDF, even if one exists.
    """
    # Verify the release exists
    coa_release = db.query(COARelease).filter(COARelease.id == release_id).first()

    if not coa_release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="COA Release not found",
        )

    try:
        pdf_path = coa_generation_service.generate(db, release_id)
        return {
            "status": "success",
            "message": "COA PDF regenerated successfully",
            "file_path": pdf_path,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate COA PDF: {str(e)}",
        )


# ============================================================================
# Release Queue and Workflow Endpoints
# ============================================================================

@router.get("/queue", response_model=ReleaseQueueResponse)
async def get_release_queue(
    db: DbSession,
    current_user: CurrentUser,
) -> ReleaseQueueResponse:
    """
    Get release queue - lots with awaiting_release status, one item per product.

    Returns Lot+Product pairs for lots with AWAITING_RELEASE status,
    ordered by created_at desc.
    """
    from app.models import Lot, LotProduct, Product
    from app.models.enums import LotStatus

    # Query lots with awaiting_release status, joined with products
    results = (
        db.query(Lot, LotProduct, Product)
        .join(LotProduct, Lot.id == LotProduct.lot_id)
        .join(Product, LotProduct.product_id == Product.id)
        .filter(Lot.status == LotStatus.AWAITING_RELEASE)
        .order_by(Lot.created_at.desc())
        .all()
    )

    items = []
    for lot, lot_product, product in results:
        items.append(
            ReleaseQueueItem(
                lot_id=lot.id,
                product_id=product.id,
                reference_number=lot.reference_number,
                lot_number=lot.lot_number,
                product_name=product.product_name,
                brand=product.brand,
                flavor=product.flavor,
                size=product.size,
                created_at=lot.created_at,
            )
        )

    return ReleaseQueueResponse(items=items, total=len(items))


# ============================================================================
# Lot+Product Release Endpoints
# ============================================================================

@router.get("/{lot_id}/{product_id}", response_model=ReleaseDetailsByLotProduct)
async def get_release_details_by_lot_product(
    lot_id: int,
    product_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ReleaseDetailsByLotProduct:
    """
    Get release details for a specific lot+product pair.

    Returns lot, product, source PDFs, and existing COARelease if any.
    Used by the Release page to display details before final approval.
    """
    from app.models import LotProduct, Product

    # Get lot
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    # Get product
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Verify lot-product association
    lot_product = db.query(LotProduct).filter(
        LotProduct.lot_id == lot_id,
        LotProduct.product_id == product_id
    ).first()
    if not lot_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not associated with this lot",
        )

    # Get source PDFs from test results
    source_pdfs = release_service.get_source_pdfs(db, lot_id)

    # Check for existing COARelease
    existing_release = (
        db.query(COARelease)
        .options(
            joinedload(COARelease.lot),
            joinedload(COARelease.product),
            joinedload(COARelease.customer),
            joinedload(COARelease.released_by),
        )
        .filter(
            COARelease.lot_id == lot_id,
            COARelease.product_id == product_id
        )
        .first()
    )

    # Determine status
    from app.models.enums import COAReleaseStatus
    if existing_release:
        status = "released" if existing_release.status == COAReleaseStatus.RELEASED else "awaiting_release"
    else:
        status = "awaiting_release"

    return ReleaseDetailsByLotProduct(
        lot_id=lot_id,
        product_id=product_id,
        status=status,
        customer_id=existing_release.customer_id if existing_release else None,
        notes=existing_release.notes if existing_release else None,
        released_at=existing_release.released_at if existing_release else None,
        draft_data=existing_release.draft_data if existing_release else None,
        lot=LotInRelease.model_validate(lot),
        product=ProductInRelease.model_validate(product),
        source_pdfs=source_pdfs,
        customer=CustomerInRelease.model_validate(existing_release.customer) if existing_release and existing_release.customer else None,
    )


@router.post("/{lot_id}/{product_id}/approve", response_model=ApproveByLotProductResponse)
async def approve_release_by_lot_product(
    lot_id: int,
    product_id: int,
    db: DbSession,
    current_user: QCManagerOrAdmin,
    request: ApproveByLotProductRequest = None,
) -> ApproveByLotProductResponse:
    """
    Approve and release a COA for a specific lot+product pair.

    Creates or updates a COARelease record and generates the PDF.
    Requires QC Manager or Admin role.

    If all products for the lot are released, updates lot status to RELEASED.
    """
    from datetime import datetime
    from app.models import LotProduct, Product
    from app.models.enums import LotStatus, COAReleaseStatus

    # Default request if not provided
    if request is None:
        request = ApproveByLotProductRequest()

    # Validate user profile before release
    if not current_user.signature_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot release: Please upload your signature in User Profile settings",
        )

    if not current_user.full_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot release: Your profile is missing a full name",
        )

    if not current_user.title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot release: Your profile is missing a title",
        )

    # Validate lot exists and is in awaiting_release status
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    if lot.status != LotStatus.AWAITING_RELEASE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lot must be in 'awaiting_release' status. Current status: {lot.status.value}",
        )

    # Capture old lot status for audit
    old_lot_status = lot.status.value

    # Validate product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Verify lot-product association
    lot_product = db.query(LotProduct).filter(
        LotProduct.lot_id == lot_id,
        LotProduct.product_id == product_id
    ).first()
    if not lot_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not associated with this lot",
        )

    # Check for existing COARelease or create new one
    coa_release = (
        db.query(COARelease)
        .filter(
            COARelease.lot_id == lot_id,
            COARelease.product_id == product_id
        )
        .first()
    )

    # Capture old COA values for audit
    old_coa_status = coa_release.status.value if coa_release else None

    if coa_release:
        # Update existing release if not already released
        if coa_release.status == COAReleaseStatus.RELEASED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This COA has already been released",
            )
        # Update with request data
        coa_release.customer_id = request.customer_id
        coa_release.notes = request.notes
    else:
        # Create new COARelease record
        coa_release = COARelease(
            lot_id=lot_id,
            product_id=product_id,
            customer_id=request.customer_id,
            notes=request.notes,
            status=COAReleaseStatus.AWAITING_RELEASE,
        )
        db.add(coa_release)
        db.flush()

    # Mark as released
    coa_release.status = COAReleaseStatus.RELEASED
    coa_release.released_at = datetime.utcnow()
    coa_release.released_by_id = current_user.id

    # Generate COA PDF
    try:
        pdf_path = coa_generation_service.generate(db, coa_release.id)
        coa_release.coa_file_path = pdf_path
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate COA PDF: {str(e)}",
        )

    # Check if all products for this lot are released
    all_lot_products = (
        db.query(LotProduct)
        .filter(LotProduct.lot_id == lot_id)
        .all()
    )

    all_product_ids = {lp.product_id for lp in all_lot_products}

    released_releases = (
        db.query(COARelease)
        .filter(
            COARelease.lot_id == lot_id,
            COARelease.status == COAReleaseStatus.RELEASED
        )
        .all()
    )
    released_product_ids = {r.product_id for r in released_releases}

    all_products_released = all_product_ids == released_product_ids

    # Update lot status to RELEASED if all products are released
    if all_products_released:
        lot.status = LotStatus.RELEASED

    # Log COARelease status change to audit trail
    audit_service.log_action(
        db=db,
        table_name="coa_releases",
        record_id=coa_release.id,
        action=AuditAction.UPDATE,
        user_id=current_user.id,
        old_values={"status": old_coa_status} if old_coa_status else None,
        new_values={"status": coa_release.status.value},
        reason=f"COA released for {product.product_name}",
    )

    # Log lot status change to RELEASED if applicable
    if all_products_released:
        audit_service.log_action(
            db=db,
            table_name="lots",
            record_id=lot_id,
            action=AuditAction.APPROVE,
            user_id=current_user.id,
            old_values={"status": old_lot_status},
            new_values={"status": lot.status.value},
            reason="All products released - COA approved",
        )

    db.commit()
    db.refresh(coa_release)
    db.refresh(lot)

    return ApproveByLotProductResponse(
        status="released",
        coa_release_id=coa_release.id,
        lot_status=lot.status,
        all_products_released=all_products_released,
    )


@router.get("/{lot_id}/{product_id}/preview")
async def preview_coa_by_lot_product(
    lot_id: int,
    product_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    """
    Generate and return COA PDF preview for a lot+product pair.
    Works whether or not a COARelease record exists yet.
    """
    from app.models import LotProduct, Product

    # Verify lot exists
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    # Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Verify lot-product association
    lot_product = db.query(LotProduct).filter(
        LotProduct.lot_id == lot_id,
        LotProduct.product_id == product_id
    ).first()
    if not lot_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not associated with this lot",
        )

    try:
        from app.services.storage_service import get_storage_service

        # Check if COARelease exists with a valid file
        existing_release = (
            db.query(COARelease)
            .filter(
                COARelease.lot_id == lot_id,
                COARelease.product_id == product_id
            )
            .first()
        )

        if existing_release and existing_release.coa_file_path:
            storage = get_storage_service()
            if storage.exists(existing_release.coa_file_path):
                full_path = settings.upload_path / existing_release.coa_file_path
                return FileResponse(
                    path=str(full_path),
                    media_type="application/pdf",
                    filename=f"COA_{lot.lot_number}.pdf",
                    headers={
                        "Content-Disposition": f"inline; filename=\"COA_{lot.lot_number}.pdf\""
                    }
                )

        # Generate preview PDF on-the-fly (returns storage key)
        storage_key = coa_generation_service.generate_preview(db, lot_id, product_id)
        full_path = settings.upload_path / storage_key

        return FileResponse(
            path=str(full_path),
            media_type="application/pdf",
            filename=f"COA_{lot.lot_number}_preview.pdf",
            headers={
                "Content-Disposition": f"inline; filename=\"COA_{lot.lot_number}_preview.pdf\""
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate COA preview: {str(e)}",
        )


@router.get("/{lot_id}/{product_id}/download")
async def download_coa_by_lot_product(
    lot_id: int,
    product_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    """
    Download COA PDF for a lot+product pair.
    Only works if a COARelease exists and has been released.
    """
    from app.models.enums import COAReleaseStatus
    from app.services.storage_service import get_storage_service

    # Get the COARelease
    coa_release = (
        db.query(COARelease)
        .options(joinedload(COARelease.lot))
        .filter(
            COARelease.lot_id == lot_id,
            COARelease.product_id == product_id,
            COARelease.status == COAReleaseStatus.RELEASED
        )
        .first()
    )

    if not coa_release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Released COA not found for this lot+product",
        )

    if not coa_release.coa_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="COA PDF file path not set",
        )

    # Use storage service to check if file exists
    storage = get_storage_service()
    if not storage.exists(coa_release.coa_file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="COA PDF file not found in storage",
        )

    # Get full path by prepending upload_path
    full_path = settings.upload_path / coa_release.coa_file_path

    return FileResponse(
        path=str(full_path),
        media_type="application/pdf",
        filename=f"COA_{coa_release.lot.lot_number}.pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"COA_{coa_release.lot.lot_number}.pdf\""
        }
    )


@router.post("/{lot_id}/{product_id}/regenerate")
async def regenerate_coa_by_lot_product(
    lot_id: int,
    product_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """
    Force regeneration of the COA PDF for a lot+product pair.

    This will regenerate the PDF with current data, even if one already exists.
    Useful for fixing PDFs that were generated with incomplete data.
    """
    from app.models.enums import COAReleaseStatus

    # Get the COARelease
    coa_release = (
        db.query(COARelease)
        .filter(
            COARelease.lot_id == lot_id,
            COARelease.product_id == product_id,
            COARelease.status == COAReleaseStatus.RELEASED
        )
        .first()
    )

    if not coa_release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Released COA not found for this lot+product",
        )

    try:
        pdf_path = coa_generation_service.generate(db, coa_release.id)
        coa_release.coa_file_path = pdf_path
        db.commit()
        return {
            "status": "success",
            "message": "COA PDF regenerated successfully",
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate COA PDF: {str(e)}",
        )


@router.get("/{lot_id}/{product_id}/preview-data", response_model=COAPreviewData)
async def get_preview_data_by_lot_product(
    lot_id: int,
    product_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> COAPreviewData:
    """
    Get COA preview data for frontend rendering.
    Returns all data needed to render a WYSIWYG COA preview.
    """
    from datetime import datetime
    from app.models import LotProduct, Product
    from app.models.test_result import TestResult

    # Verify lot exists
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    # Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Verify lot-product association
    lot_product = db.query(LotProduct).filter(
        LotProduct.lot_id == lot_id,
        LotProduct.product_id == product_id
    ).first()
    if not lot_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not associated with this lot",
        )

    # Get all test results for this lot that have values (no ordering in SQL, we'll sort in Python)
    test_results = (
        db.query(TestResult)
        .filter(
            TestResult.lot_id == lot_id,
            TestResult.result_value.isnot(None),
            TestResult.result_value != "",
        )
        .all()
    )

    # Get category order configuration and sort tests
    from app.services.coa_category_order_service import coa_category_order_service
    from app.models.lab_test_type import LabTestType

    category_order = coa_category_order_service.get_ordered_categories(db)

    # Build a lookup for test_type -> category from LabTestType
    test_type_names = [r.test_type for r in test_results]
    lab_test_types = (
        db.query(LabTestType)
        .filter(LabTestType.test_name.in_(test_type_names))
        .all()
    ) if test_type_names else []
    category_lookup = {lt.test_name.lower(): lt.test_category for lt in lab_test_types}

    def get_category(test_type: str) -> str:
        """Get category for a test type, defaulting to 'Other' if not found."""
        return category_lookup.get(test_type.lower(), "Other")

    def sort_key(result: TestResult) -> tuple:
        """Sort key: category order index, then category name, then test name alphabetically."""
        category = get_category(result.test_type)
        try:
            cat_index = category_order.index(category)
        except ValueError:
            cat_index = len(category_order)  # Unconfigured categories at end
        return (cat_index, category, result.test_type.lower())

    # Sort test results by category order, then alphabetically within category
    test_results.sort(key=sort_key)

    # Get product test specifications for fallback
    from app.models.product_test_spec import ProductTestSpecification
    product_specs = (
        db.query(ProductTestSpecification)
        .filter(ProductTestSpecification.product_id == product_id)
        .all()
    )
    # Build lookup dict by test name (case-insensitive)
    spec_lookup = {spec.test_name.lower(): spec.specification for spec in product_specs}

    # Format test results
    tests = []
    for result in test_results:
        # Try to get specification from:
        # 1. TestResult.specification (what was entered/saved with the result)
        # 2. ProductTestSpec (product's default specification for this test type)
        # 3. Default fallback
        specification = result.specification
        if not specification:
            # Look up from product specs
            specification = spec_lookup.get(result.test_type.lower())
        if not specification:
            specification = "Within limits"

        tests.append(COATestResult(
            name=result.test_type,
            result=result.result_value or "N/D",
            unit=result.unit,
            specification=specification,
            status="Pass",  # All approved results are considered passing
        ))

    # Check for existing COARelease to get notes and release info
    from sqlalchemy.orm import joinedload

    coa_release = (
        db.query(COARelease)
        .options(joinedload(COARelease.released_by))
        .filter(
            COARelease.lot_id == lot_id,
            COARelease.product_id == product_id
        )
        .first()
    )

    notes = None
    released_by = None
    released_by_title = None
    released_by_email = None
    released_at = None
    if coa_release:
        notes = coa_release.notes
        if coa_release.draft_data:
            notes = coa_release.draft_data.get("notes") or notes
        if coa_release.released_by:
            released_by = coa_release.released_by.full_name or coa_release.released_by.username
            released_by_title = coa_release.released_by.title
            released_by_email = coa_release.released_by.email
        if coa_release.released_at:
            released_at = coa_release.released_at.strftime("%B %d, %Y")

    # Get lab info from database
    lab_info = lab_info_service.get_or_create_default(db)

    # Build signature URL - use released_by user's signature if released, else current user's
    signature_url = None
    if coa_release and coa_release.released_by and coa_release.released_by.signature_path:
        signature_url = f"/uploads/{coa_release.released_by.signature_path}"
    elif current_user.signature_path:
        signature_url = f"/uploads/{current_user.signature_path}"

    return COAPreviewData(
        # Company info from database
        company_name=lab_info.company_name,
        company_address=lab_info.full_address,
        company_phone=lab_info.phone,
        company_email=lab_info.email,
        company_logo_url=lab_info_service.get_logo_url(lab_info.logo_path),

        # Product info
        product_name=product.display_name,
        brand=product.brand,

        # Lot info
        lot_number=lot.lot_number,
        reference_number=lot.reference_number,
        mfg_date=lot.mfg_date.strftime("%B %d, %Y") if lot.mfg_date else None,
        exp_date=lot.exp_date.strftime("%B %d, %Y") if lot.exp_date else None,

        # Test results
        tests=tests,

        # Notes
        notes=notes,

        # Generation info
        generated_date=datetime.now().strftime("%B %d, %Y"),
        released_by=released_by,
        released_by_title=released_by_title,
        released_by_email=released_by_email or "(Preview)",
        signature_url=signature_url,
        released_at=released_at,
    )


@router.get("/{lot_id}/{product_id}/source-pdfs/{filename}")
async def get_source_pdf_by_lot_product(
    lot_id: int,
    product_id: int,
    filename: str,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    """
    Get a source PDF file for a lot+product pair.
    """
    from app.models import LotProduct

    # Verify lot exists and lot-product association
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    lot_product = db.query(LotProduct).filter(
        LotProduct.lot_id == lot_id,
        LotProduct.product_id == product_id
    ).first()
    if not lot_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not associated with this lot",
        )

    # Get source PDFs
    source_pdfs = release_service.get_source_pdfs(db, lot_id)
    if filename not in source_pdfs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source PDF not found",
        )

    # Build the file path
    pdf_path = Path(settings.upload_path) / "pdfs" / filename
    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source PDF file not found on disk",
        )

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=filename,
        headers={
            "Content-Disposition": f"inline; filename=\"{filename}\""
        }
    )


@router.put("/{lot_id}/{product_id}/draft", response_model=ReleaseDetailsByLotProduct)
async def save_draft_by_lot_product(
    lot_id: int,
    product_id: int,
    request: DraftSaveRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ReleaseDetailsByLotProduct:
    """
    Save draft data (customer_id, notes, mfg_date, exp_date) for a lot+product pair.
    Creates or updates a draft COARelease record.
    Also updates Lot dates if provided.
    """
    from app.models import LotProduct, Product
    from app.models.enums import COAReleaseStatus

    # Verify lot-product association
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    lot_product = db.query(LotProduct).filter(
        LotProduct.lot_id == lot_id,
        LotProduct.product_id == product_id
    ).first()
    if not lot_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not associated with this lot",
        )

    # Capture old lot values for audit
    old_mfg_date = lot.mfg_date.isoformat() if lot.mfg_date else None
    old_exp_date = lot.exp_date.isoformat() if lot.exp_date else None

    # Track lot date changes
    lot_changes_old = {}
    lot_changes_new = {}

    # Update Lot dates if provided
    if request.mfg_date is not None and request.mfg_date != lot.mfg_date:
        lot_changes_old["mfg_date"] = old_mfg_date
        lot_changes_new["mfg_date"] = request.mfg_date.isoformat()
        lot.mfg_date = request.mfg_date
    if request.exp_date is not None and request.exp_date != lot.exp_date:
        lot_changes_old["exp_date"] = old_exp_date
        lot_changes_new["exp_date"] = request.exp_date.isoformat()
        lot.exp_date = request.exp_date

    # Get or create COARelease
    coa_release = (
        db.query(COARelease)
        .filter(
            COARelease.lot_id == lot_id,
            COARelease.product_id == product_id
        )
        .first()
    )

    # Capture old draft values for audit
    old_customer_id = None
    old_notes = None
    if coa_release and coa_release.draft_data:
        old_customer_id = coa_release.draft_data.get("customer_id")
        old_notes = coa_release.draft_data.get("notes")

    if coa_release:
        # Update existing
        coa_release.draft_data = {
            "customer_id": request.customer_id,
            "notes": request.notes,
        }
    else:
        # Create new draft COARelease
        coa_release = COARelease(
            lot_id=lot_id,
            product_id=product_id,
            status=COAReleaseStatus.AWAITING_RELEASE,
            draft_data={
                "customer_id": request.customer_id,
                "notes": request.notes,
            }
        )
        db.add(coa_release)
        db.flush()  # Get the ID for audit logging

    # Log lot date changes if any
    if lot_changes_new:
        audit_service.log_action(
            db=db,
            table_name="lots",
            record_id=lot_id,
            action=AuditAction.UPDATE,
            user_id=current_user.id,
            old_values=lot_changes_old,
            new_values=lot_changes_new,
            reason="Release draft: dates updated",
        )

    # Log draft data changes (customer, notes)
    draft_changes_old = {}
    draft_changes_new = {}

    if request.customer_id != old_customer_id:
        draft_changes_old["customer_id"] = old_customer_id
        draft_changes_new["customer_id"] = request.customer_id

    if request.notes != old_notes:
        draft_changes_old["notes"] = old_notes
        draft_changes_new["notes"] = request.notes

    if draft_changes_new:
        audit_service.log_action(
            db=db,
            table_name="coa_releases",
            record_id=coa_release.id,
            action=AuditAction.UPDATE,
            user_id=current_user.id,
            old_values=draft_changes_old if any(v is not None for v in draft_changes_old.values()) else None,
            new_values=draft_changes_new,
            reason="Release draft: details updated",
        )

    db.commit()
    db.refresh(lot)  # Refresh to get updated dates

    # Return updated details
    source_pdfs = release_service.get_source_pdfs(db, lot_id)

    return ReleaseDetailsByLotProduct(
        lot_id=lot_id,
        product_id=product_id,
        status="awaiting_release",
        customer_id=coa_release.draft_data.get("customer_id") if coa_release.draft_data else None,
        notes=coa_release.draft_data.get("notes") if coa_release.draft_data else None,
        draft_data=coa_release.draft_data,
        lot=LotInRelease.model_validate(lot),
        product=ProductInRelease.model_validate(product),
        source_pdfs=source_pdfs,
    )


@router.post("/{lot_id}/{product_id}/email", response_model=EmailHistoryResponse)
async def send_email_by_lot_product(
    lot_id: int,
    product_id: int,
    request: EmailSendRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> EmailHistoryResponse:
    """
    Log an email sent for a lot+product's COARelease.
    Only works after the COA has been released.
    """
    from app.models.enums import COAReleaseStatus
    from app.models.email_history import EmailHistory
    from datetime import datetime

    # Get the released COARelease
    coa_release = (
        db.query(COARelease)
        .filter(
            COARelease.lot_id == lot_id,
            COARelease.product_id == product_id,
            COARelease.status == COAReleaseStatus.RELEASED
        )
        .first()
    )

    if not coa_release:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="COA must be released before sending email",
        )

    # Create email history record
    email_history = EmailHistory(
        coa_release_id=coa_release.id,
        recipient_email=request.recipient_email,
        sent_at=datetime.utcnow(),
        sent_by_id=current_user.id,
    )
    db.add(email_history)
    db.commit()
    db.refresh(email_history)

    return EmailHistoryResponse(
        id=email_history.id,
        recipient_email=email_history.recipient_email,
        sent_at=email_history.sent_at,
        sent_by=current_user.username,
    )


@router.get("/{lot_id}/{product_id}/emails", response_model=List[EmailHistoryResponse])
async def get_email_history_by_lot_product(
    lot_id: int,
    product_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> List[EmailHistoryResponse]:
    """
    Get email history for a lot+product's COARelease.
    """
    from app.models.email_history import EmailHistory
    from app.models import User

    # Get the COARelease
    coa_release = (
        db.query(COARelease)
        .filter(
            COARelease.lot_id == lot_id,
            COARelease.product_id == product_id
        )
        .first()
    )

    if not coa_release:
        return []

    # Get email history
    emails = (
        db.query(EmailHistory, User)
        .join(User, EmailHistory.sent_by_id == User.id)
        .filter(EmailHistory.coa_release_id == coa_release.id)
        .order_by(EmailHistory.sent_at.desc())
        .all()
    )

    return [
        EmailHistoryResponse(
            id=email.id,
            recipient_email=email.recipient_email,
            sent_at=email.sent_at,
            sent_by=user.username,
        )
        for email, user in emails
    ]


# ============================================================================
# Legacy COARelease ID-based Endpoints
# ============================================================================

@router.get("/{id}", response_model=COAReleaseWithSourcePdfs)
async def get_release(
    id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> COAReleaseWithSourcePdfs:
    """
    Get a COARelease by ID with all details including source PDFs.

    Returns the COARelease with lot, product, customer relations and
    list of source PDF filenames from associated test results.
    """
    release = release_service.get_by_id(db, id)
    if not release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="COARelease not found",
        )

    # Get source PDFs
    source_pdfs = release_service.get_source_pdfs(db, release.lot_id)

    # Build response with nested relations
    response = COAReleaseWithSourcePdfs.model_validate(release)
    response.source_pdfs = source_pdfs

    return response


@router.get("/{id}/source-pdfs/{filename}")
async def get_source_pdf(
    id: int,
    filename: str,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    """
    Serve a source PDF file.

    Downloads the PDF file from the uploads/pdfs directory.
    """
    # Verify release exists
    release = release_service.get(db, id)
    if not release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="COARelease not found",
        )

    # Verify the PDF is associated with this release's lot
    source_pdfs = release_service.get_source_pdfs(db, release.lot_id)
    if filename not in source_pdfs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF not associated with this release",
        )

    # Build file path
    pdf_path = Path(settings.upload_path) / "pdfs" / filename

    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found",
        )

    return FileResponse(
        path=str(pdf_path),
        filename=filename,
        media_type="application/pdf",
    )


@router.put("/{id}/draft", response_model=COAReleaseWithSourcePdfs)
async def save_draft(
    id: int,
    draft: DraftSaveRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> COAReleaseWithSourcePdfs:
    """
    Save draft data for a COARelease (auto-saved on blur).

    Updates customer_id and notes fields. Both fields are optional.
    """
    try:
        release = release_service.save_draft(
            db=db,
            id=id,
            customer_id=draft.customer_id,
            notes=draft.notes,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    # Reload with relations
    release = release_service.get_by_id(db, id)
    source_pdfs = release_service.get_source_pdfs(db, release.lot_id)

    response = COAReleaseWithSourcePdfs.model_validate(release)
    response.source_pdfs = source_pdfs

    return response


@router.post("/{id}/approve", response_model=ApproveReleaseResponse)
async def approve_release(
    id: int,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> ApproveReleaseResponse:
    """
    Approve a COARelease (set status=RELEASED).

    Requires QC Manager or Admin role.
    Sets released_at timestamp and released_by_id.
    """
    try:
        release = release_service.approve_release(
            db=db,
            id=id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return ApproveReleaseResponse.model_validate(release)


@router.post("/{id}/send-back", response_model=COAReleaseWithSourcePdfs)
async def send_back_release(
    id: int,
    request: SendBackRequest,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> COAReleaseWithSourcePdfs:
    """
    Send a COARelease back to Sample Tracker (QC review).

    Requires QC Manager or Admin role.
    Sets send_back_reason and updates lot status to UNDER_REVIEW.
    """
    try:
        release = release_service.send_back(
            db=db,
            id=id,
            user_id=current_user.id,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Reload with relations
    release = release_service.get_by_id(db, id)
    source_pdfs = release_service.get_source_pdfs(db, release.lot_id)

    response = COAReleaseWithSourcePdfs.model_validate(release)
    response.source_pdfs = source_pdfs

    return response


@router.post("/{id}/email", response_model=EmailHistoryResponse)
async def log_email_sent(
    id: int,
    request: EmailSendRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> EmailHistoryResponse:
    """
    Log that an email was sent for a COARelease.

    Note: This is a placeholder - no actual email is sent.
    Creates an EmailHistory record to track the email.
    """
    try:
        email_record = release_service.log_email_sent(
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

    return EmailHistoryResponse.model_validate(email_record)


@router.get("/{id}/emails", response_model=List[EmailHistoryResponse])
async def get_email_history(
    id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> List[EmailHistoryResponse]:
    """
    Get email history for a COARelease.

    Returns list of EmailHistory records, ordered by sent_at desc.
    """
    # Verify release exists
    release = release_service.get(db, id)
    if not release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="COARelease not found",
        )

    emails = release_service.get_email_history(db, id)

    return [EmailHistoryResponse.model_validate(e) for e in emails]
