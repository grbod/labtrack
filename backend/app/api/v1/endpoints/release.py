"""COA Release management endpoints."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import joinedload

from app.config import settings
from app.dependencies import AdminUser, CurrentUser, DbSession, QCManagerOrAdmin
from app.models.coa_release import COARelease
from app.models.coa_snapshot import COASnapshot
from app.models.enums import AuditAction, COAReleaseStatus
from app.models.lot import Lot
from app.schemas.release import (
    ApproveByLotProductRequest,
    ApproveByLotProductResponse,
    ApproveReleaseResponse,
    COANotTestedRow,
    COAPreviewData,
    COAReleaseResponse,
    COAReleaseWithSourcePdfs,
    COATestResult,
    CustomerInRelease,
    DraftSaveRequest,
    EmailHistoryResponse,
    EmailSendRequest,
    LotInRelease,
    ProductInRelease,
    ReleaseDetailsByLotProduct,
    ReleaseGateStatus,
    ReleaseQueueItem,
    ReleaseQueueResponse,
    SendBackRequest,
    SensoryAttestRequest,
    VoidReleaseRequest,
)
from app.services.audit_service import AuditService
from app.services.coa_generation_service import coa_generation_service
from app.services.lab_info_service import lab_info_service
from app.services.release_service import ReleaseService

router = APIRouter()
release_service = ReleaseService()
audit_service = AuditService()


def _normalize_pdf_storage_key(filename: str) -> str:
    """
    Normalize PDF identifiers into a storage key.

    Handles legacy values such as bare filenames or filesystem-like paths by
    converting them to `pdfs/<name>.pdf` keys.
    """
    key = filename.lstrip("/\\")
    marker = "pdfs/"
    if marker in key:
        return key[key.index(marker) :]
    return f"pdfs/{key}"


def _get_pdf_from_storage(
    storage_key: str,
    *,
    response_filename: str,
    inline: bool,
    missing_detail: str = "PDF file not found in storage",
) -> Response:
    """Fetch a PDF from configured storage and return an HTTP response."""
    from app.services.storage_service import get_storage_service

    storage = get_storage_service()
    if not storage.exists(storage_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=missing_detail,
        )

    if settings.storage_backend == "r2":
        presigned_url = storage.get_presigned_url(storage_key)
        return RedirectResponse(
            url=presigned_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT
        )

    content = storage.download(storage_key)
    disposition = "inline" if inline else "attachment"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{response_filename}"'
        },
    )


def _get_coa_pdf_response(
    db: DbSession,
    release_id: int,
    inline: bool = True,
) -> Response:
    """
    Helper to get COA PDF from configured storage.

    Args:
        db: Database session
        release_id: ID of the COARelease
        inline: If True, display inline (preview). If False, force download.

    Returns:
        PDF response (local stream or R2 redirect)
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

    filename = f"COA_{coa_release.lot.lot_number}.pdf"

    # Released COAs are served exclusively from their immutable snapshot; no
    # lazy (re)generation happens for a released release.
    if coa_release.status == COAReleaseStatus.RELEASED:
        snapshot = (
            db.query(COASnapshot)
            .filter(
                COASnapshot.coa_release_id == coa_release.id,
                COASnapshot.voided.is_(False),
            )
            .first()
        )
        if snapshot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "No COA snapshot exists for this released COA (legacy record "
                    "predating snapshots). Run scripts/backfill_coa_snapshots.py "
                    "to reconstruct it."
                ),
            )
        return _get_pdf_from_storage(
            snapshot.pdf_storage_key,
            response_filename=filename,
            inline=inline,
        )

    try:
        # Pre-release: get or generate the PDF (returns storage key).
        storage_key = coa_generation_service.get_or_generate_pdf(db, release_id)

        return _get_pdf_from_storage(
            storage_key,
            response_filename=filename,
            inline=inline,
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
) -> Response:
    """Generate and return COA PDF for inline preview."""
    return _get_coa_pdf_response(db, release_id, inline=True)


@router.get("/{release_id}/download")
async def download_coa(
    release_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
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
    lot_product = (
        db.query(LotProduct)
        .filter(LotProduct.lot_id == lot_id, LotProduct.product_id == product_id)
        .first()
    )
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
        .filter(COARelease.lot_id == lot_id, COARelease.product_id == product_id)
        .first()
    )

    # Determine status
    from app.models.enums import COAReleaseStatus

    if existing_release:
        status = (
            "released"
            if existing_release.status == COAReleaseStatus.RELEASED
            else "awaiting_release"
        )
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
        customer=(
            CustomerInRelease.model_validate(existing_release.customer)
            if existing_release and existing_release.customer
            else None
        ),
    )


@router.post(
    "/{lot_id}/{product_id}/approve", response_model=ApproveByLotProductResponse
)
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
    from app.models.enums import COAReleaseStatus, LotStatus

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

    # Validate product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Verify lot-product association
    lot_product = (
        db.query(LotProduct)
        .filter(LotProduct.lot_id == lot_id, LotProduct.product_id == product_id)
        .first()
    )
    if not lot_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not associated with this lot",
        )

    # Check for existing COARelease or create new one
    coa_release = (
        db.query(COARelease)
        .filter(COARelease.lot_id == lot_id, COARelease.product_id == product_id)
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

    # --- Release gate -----------------------------------------------------
    from app.services.release_gate_service import compute_gate
    from app.workflow.lot_workflow_service import (
        LotWorkflowService,
        WorkflowTransitionError,
    )

    override = bool(getattr(request, "override", False))
    override_reason = (getattr(request, "override_reason", None) or "").strip() or None

    if override and not override_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Override requires a reason (it prints on the COA as a deviation).",
        )

    gate = compute_gate(db, lot_id, product_id, release=coa_release)
    if not gate.can_release and not override:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "GATE_BLOCKED",
                "reason": "; ".join(gate.blocking_reasons)
                or "Release gate not satisfied",
                "missing_tests": gate.missing_tests,
                "failing_tests": [t.name for t in gate.failing_tests],
            },
        )

    # Mark as released
    coa_release.status = COAReleaseStatus.RELEASED
    coa_release.released_at = datetime.utcnow()
    coa_release.released_by_id = current_user.id
    if override:
        coa_release.deviation_note = override_reason
    db.flush()

    # Create the immutable snapshot (renders + freezes the PDF into storage).
    # Part of THIS transaction: any failure raises before commit so the whole
    # release rolls back. Released COAs are served from the snapshot, so no lazy
    # PDF generation happens for released releases anymore.
    from app.services.coa_snapshot_service import coa_snapshot_service

    # A prior release cycle for this pair (voided) makes this a re-release.
    prior_snapshot = (
        db.query(COASnapshot)
        .filter(COASnapshot.coa_release_id == coa_release.id)
        .order_by(COASnapshot.revision.desc())
        .first()
    )
    try:
        snapshot = coa_snapshot_service.create_snapshot(db, coa_release)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create COA snapshot: {str(e)}",
        )
    if prior_snapshot is not None and prior_snapshot.voided:
        snapshot.revision = prior_snapshot.revision + 1
        snapshot.supersedes_id = prior_snapshot.id
        db.flush()
    coa_release.coa_file_path = snapshot.pdf_storage_key

    # Check if all products for this lot are released
    all_lot_products = db.query(LotProduct).filter(LotProduct.lot_id == lot_id).all()

    all_product_ids = {lp.product_id for lp in all_lot_products}

    released_releases = (
        db.query(COARelease)
        .filter(
            COARelease.lot_id == lot_id, COARelease.status == COAReleaseStatus.RELEASED
        )
        .all()
    )
    released_product_ids = {r.product_id for r in released_releases}

    all_products_released = all_product_ids == released_product_ids

    # Log COARelease status change to audit trail
    audit_service.log_action(
        db=db,
        table_name="coa_releases",
        record_id=coa_release.id,
        action=AuditAction.OVERRIDE if override else AuditAction.UPDATE,
        user_id=current_user.id,
        old_values={"status": old_coa_status} if old_coa_status else None,
        new_values={"status": coa_release.status.value},
        reason=(
            f"COA released for {product.product_name} (override: {override_reason})"
            if override
            else f"COA released for {product.product_name}"
        ),
    )

    # Move the lot to RELEASED once every product is released. The canonical
    # transition re-validates role / machine-fails (override honoured).
    if all_products_released:
        try:
            LotWorkflowService().transition(
                db,
                lot,
                LotStatus.RELEASED,
                current_user,
                reason=override_reason or "All products released - COA approved",
                override=override,
                trigger="manual",
            )
        except WorkflowTransitionError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": exc.code,
                    "reason": exc.reason,
                    "missing_tests": gate.missing_tests,
                    "failing_tests": [t.name for t in gate.failing_tests],
                },
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


@router.get("/{lot_id}/{product_id}/gate", response_model=ReleaseGateStatus)
async def get_release_gate(
    lot_id: int,
    product_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ReleaseGateStatus:
    """Green/amber/red release gate for a (lot, product) pair.

    Exposes required-test completeness, per-test verdicts, the sensory attest
    checklist, the legacy-import exemption state, and the prior-email notice for
    a re-release after a void.
    """
    from app.services.release_gate_service import compute_gate

    release = (
        db.query(COARelease)
        .filter(COARelease.lot_id == lot_id, COARelease.product_id == product_id)
        .first()
    )
    try:
        return compute_gate(db, lot_id, product_id, release=release)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{lot_id}/{product_id}/attest", response_model=ReleaseGateStatus)
async def attest_sensory_rows(
    lot_id: int,
    product_id: int,
    request: SensoryAttestRequest,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> ReleaseGateStatus:
    """Attest sensory/organoleptic rows for a release (QC Manager or Admin)."""
    from datetime import datetime

    from app.models.release_sensory_attest import ReleaseSensoryAttest
    from app.services.release_gate_service import compute_gate

    # Find or create the release row so attests can hang off it.
    release = (
        db.query(COARelease)
        .filter(COARelease.lot_id == lot_id, COARelease.product_id == product_id)
        .first()
    )
    if release is None:
        release = COARelease(
            lot_id=lot_id,
            product_id=product_id,
            status=COAReleaseStatus.AWAITING_RELEASE,
        )
        db.add(release)
        db.flush()

    if release.status == COAReleaseStatus.RELEASED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot attest a released COA",
        )

    existing = {
        a.lab_test_type_id
        for a in db.query(ReleaseSensoryAttest)
        .filter(ReleaseSensoryAttest.release_id == release.id)
        .all()
    }
    for lab_test_type_id in request.lab_test_type_ids:
        if lab_test_type_id in existing:
            continue
        db.add(
            ReleaseSensoryAttest(
                release_id=release.id,
                lab_test_type_id=lab_test_type_id,
                attested_by_id=current_user.id,
                attested_at=datetime.utcnow(),
            )
        )
        audit_service.log_action(
            db=db,
            table_name="release_sensory_attests",
            record_id=release.id,
            action=AuditAction.APPROVE,
            user_id=current_user.id,
            new_values={"lab_test_type_id": lab_test_type_id},
            reason="Sensory row attested",
        )

    db.commit()
    db.refresh(release)
    return compute_gate(db, lot_id, product_id, release=release)


@router.post("/{release_id}/void", response_model=ReleaseDetailsByLotProduct)
async def void_release(
    release_id: int,
    request: VoidReleaseRequest,
    db: DbSession,
    current_user: AdminUser,
) -> ReleaseDetailsByLotProduct:
    """Void a released COA and return the lot to the release queue (Admin only)."""
    from datetime import datetime

    from app.models import Product
    from app.models.enums import LotStatus
    from app.workflow.lot_workflow_service import (
        LotWorkflowService,
        WorkflowTransitionError,
    )

    reason = (request.reason or "").strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A reason is required to void a release",
        )

    release = db.query(COARelease).filter(COARelease.id == release_id).first()
    if not release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Release not found"
        )
    if release.status != COAReleaseStatus.RELEASED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only a released COA can be voided",
        )

    lot = db.query(Lot).filter(Lot.id == release.lot_id).first()

    # Return the lot to the queue via the canonical VOID path (admin + reason).
    if lot is not None and lot.status == LotStatus.RELEASED:
        try:
            LotWorkflowService().transition(
                db,
                lot,
                LotStatus.AWAITING_RELEASE,
                current_user,
                reason=f"Voided release: {reason}",
                trigger="manual",
            )
        except WorkflowTransitionError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": exc.code, "reason": exc.reason},
            )

    # Void the immutable snapshot (kept for history; display watermarks it).
    from app.services.coa_snapshot_service import coa_snapshot_service

    snapshot = (
        db.query(COASnapshot)
        .filter(
            COASnapshot.coa_release_id == release.id,
            COASnapshot.voided.is_(False),
        )
        .first()
    )
    if snapshot is not None:
        coa_snapshot_service.void_snapshot(db, snapshot, reason)

    # Reset the release back to a pending-equivalent state, keeping the void
    # trail (voided_at drives the re-release "prior email" notice).
    old_coa_status = release.status.value
    release.status = COAReleaseStatus.AWAITING_RELEASE
    release.voided_note = reason
    release.voided_at = datetime.utcnow()
    release.voided_by_id = current_user.id
    release.released_at = None
    release.released_by_id = None
    release.coa_file_path = None

    audit_service.log_action(
        db=db,
        table_name="coa_releases",
        record_id=release.id,
        action=AuditAction.VOID,
        user_id=current_user.id,
        old_values={"status": old_coa_status},
        new_values={"status": release.status.value},
        reason=f"Release voided: {reason}",
    )

    db.commit()
    db.refresh(release)

    product = db.query(Product).filter(Product.id == release.product_id).first()
    source_pdfs = release_service.get_source_pdfs(db, release.lot_id)
    return ReleaseDetailsByLotProduct(
        lot_id=release.lot_id,
        product_id=release.product_id,
        status="awaiting_release",
        customer_id=release.customer_id,
        notes=release.notes,
        released_at=None,
        draft_data=release.draft_data,
        lot=LotInRelease.model_validate(lot),
        product=ProductInRelease.model_validate(product),
        source_pdfs=source_pdfs,
        customer=(
            CustomerInRelease.model_validate(release.customer)
            if release.customer
            else None
        ),
    )


@router.get("/{lot_id}/{product_id}/preview")
async def preview_coa_by_lot_product(
    lot_id: int,
    product_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
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
    lot_product = (
        db.query(LotProduct)
        .filter(LotProduct.lot_id == lot_id, LotProduct.product_id == product_id)
        .first()
    )
    if not lot_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not associated with this lot",
        )

    existing_release = (
        db.query(COARelease)
        .filter(COARelease.lot_id == lot_id, COARelease.product_id == product_id)
        .first()
    )

    # A released COA is served from its frozen snapshot PDF (never regenerated).
    if existing_release and existing_release.status == COAReleaseStatus.RELEASED:
        snapshot = (
            db.query(COASnapshot)
            .filter(
                COASnapshot.coa_release_id == existing_release.id,
                COASnapshot.voided.is_(False),
            )
            .first()
        )
        if snapshot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "No COA snapshot exists for this released COA (legacy record "
                    "predating snapshots). Run scripts/backfill_coa_snapshots.py "
                    "to reconstruct it."
                ),
            )
        return _get_pdf_from_storage(
            snapshot.pdf_storage_key,
            response_filename=f"COA_{lot.lot_number}.pdf",
            inline=True,
        )

    # Pre-release: generate a live preview PDF on the fly.
    try:
        storage_key = coa_generation_service.generate_preview(db, lot_id, product_id)
        return _get_pdf_from_storage(
            storage_key,
            response_filename=f"COA_{lot.lot_number}_preview.pdf",
            inline=True,
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
) -> Response:
    """
    Download COA PDF for a lot+product pair.
    Only works if a COARelease exists and has been released.
    """
    from app.models.enums import COAReleaseStatus

    # Get the COARelease
    coa_release = (
        db.query(COARelease)
        .options(joinedload(COARelease.lot))
        .filter(
            COARelease.lot_id == lot_id,
            COARelease.product_id == product_id,
            COARelease.status == COAReleaseStatus.RELEASED,
        )
        .first()
    )

    if not coa_release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Released COA not found for this lot+product",
        )

    # Released COAs are served exclusively from their immutable snapshot.
    snapshot = (
        db.query(COASnapshot)
        .filter(
            COASnapshot.coa_release_id == coa_release.id,
            COASnapshot.voided.is_(False),
        )
        .first()
    )
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No COA snapshot exists for this released COA (legacy record "
                "predating snapshots). Run scripts/backfill_coa_snapshots.py to "
                "reconstruct it."
            ),
        )

    return _get_pdf_from_storage(
        snapshot.pdf_storage_key,
        response_filename=f"COA_{coa_release.lot.lot_number}.pdf",
        inline=False,
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
            COARelease.status == COAReleaseStatus.RELEASED,
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


def _context_to_preview_data(context, snapshot=None) -> COAPreviewData:
    """Serialise a canonical ``COAContext`` into the frontend preview shape.

    When ``snapshot`` is provided the payload is flagged with its provenance so
    the frontend can render "Reconstructed" / "Voided" badges.
    """
    tests = [
        COATestResult(
            id=row.id,
            name=row.name,
            method=row.method,
            result=row.result_value,
            unit=row.unit,
            specification=row.spec_text,  # None -> render "—"; never fabricated
            status=row.status_display,
            verdict=row.verdict,
        )
        for row in context.test_rows
    ]
    not_tested = [
        COANotTestedRow(
            name=row.name,
            method=row.method,
            specification=row.spec_text,
            status=row.status_display,
        )
        for row in context.not_tested_rows
    ]

    return COAPreviewData(
        # Company / lab info
        company_name=context.lab.company_name,
        company_address=context.lab.address,
        company_phone=context.lab.phone,
        company_email=context.lab.email,
        company_logo_url=context.lab.logo_url,
        # Product info
        product_name=context.product.product_name,
        brand=context.product.brand or "",
        # Lot info
        lot_number=context.lot.lot_number,
        reference_number=context.lot.reference_number,
        mfg_date=context.lot.mfg_date,
        exp_date=context.lot.exp_date,
        # Test results
        tests=tests,
        not_tested=not_tested,
        # Document identity + deviation note
        document_id=context.document.document_id,
        deviation_note=context.document.deviation_note,
        # Notes
        notes=context.notes,
        # Generation / approver info (approver strictly from the release record)
        generated_date=context.document.generated_date,
        released_by=context.approver.name,
        released_by_title=context.approver.title,
        released_by_email=context.approver.email or "(Preview)",
        signature_url=context.approver.signature_url,
        released_at=context.document.release_date,
        # Snapshot provenance
        source=context.source,
        reconstructed=bool(snapshot.reconstructed) if snapshot else False,
        voided=bool(snapshot.voided) if snapshot else False,
        revision=snapshot.revision if snapshot else None,
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

    Delegates to the canonical ``coa_context_builder`` — the single source of
    truth shared with the PDF renderer — then serialises the resulting
    ``COAContext`` into the ``COAPreviewData`` shape the frontend consumes.
    """
    from sqlalchemy.orm import joinedload

    from app.models import LotProduct, Product
    from app.services.coa_context_builder import build_context

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
    lot_product = (
        db.query(LotProduct)
        .filter(LotProduct.lot_id == lot_id, LotProduct.product_id == product_id)
        .first()
    )
    if not lot_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not associated with this lot",
        )

    # Existing release (if any) supplies the approver, notes, dates, and — when
    # RELEASED — drives the verdict display policy. The approver comes ONLY from
    # this record; the current viewer is never used as a signature fallback.
    coa_release = (
        db.query(COARelease)
        .options(joinedload(COARelease.released_by), joinedload(COARelease.customer))
        .filter(COARelease.lot_id == lot_id, COARelease.product_id == product_id)
        .first()
    )

    # A released COA is served from its immutable snapshot — frozen at release
    # time, unaffected by later edits to the lot/product/results.
    if coa_release and coa_release.status == COAReleaseStatus.RELEASED:
        from app.services.coa_snapshot_service import coa_snapshot_service

        snapshot = (
            db.query(COASnapshot)
            .filter(
                COASnapshot.coa_release_id == coa_release.id,
                COASnapshot.voided.is_(False),
            )
            .first()
        )
        if snapshot is not None:
            frozen = coa_snapshot_service.get_snapshot_context(db, coa_release.id)
            return _context_to_preview_data(frozen, snapshot=snapshot)

    context = build_context(db, lot_id, product_id, release=coa_release)
    return _context_to_preview_data(context)


@router.get("/{lot_id}/{product_id}/source-pdfs/{filename:path}")
async def get_source_pdf_by_lot_product(
    lot_id: int,
    product_id: int,
    filename: str,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    """
    Get a source PDF file for a lot+product pair from configured storage.
    """
    from app.models import LotProduct

    # Verify lot exists and lot-product association
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot not found",
        )

    lot_product = (
        db.query(LotProduct)
        .filter(LotProduct.lot_id == lot_id, LotProduct.product_id == product_id)
        .first()
    )
    if not lot_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not associated with this lot",
        )

    # Get source PDFs
    source_pdfs = release_service.get_source_pdfs(db, lot_id)
    normalized_sources = {_normalize_pdf_storage_key(src) for src in source_pdfs}
    storage_key = _normalize_pdf_storage_key(filename)
    if storage_key not in normalized_sources:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source PDF not found",
        )

    response_filename = storage_key.rsplit("/", 1)[-1]
    return _get_pdf_from_storage(
        storage_key,
        response_filename=response_filename,
        inline=True,
        missing_detail=f"Source PDF file '{filename}' not found in storage",
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

    lot_product = (
        db.query(LotProduct)
        .filter(LotProduct.lot_id == lot_id, LotProduct.product_id == product_id)
        .first()
    )
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
        .filter(COARelease.lot_id == lot_id, COARelease.product_id == product_id)
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
            },
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
            old_values=(
                draft_changes_old
                if any(v is not None for v in draft_changes_old.values())
                else None
            ),
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
        customer_id=(
            coa_release.draft_data.get("customer_id")
            if coa_release.draft_data
            else None
        ),
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
    from datetime import datetime

    from app.models.email_history import EmailHistory
    from app.models.enums import COAReleaseStatus

    # Get the released COARelease
    coa_release = (
        db.query(COARelease)
        .filter(
            COARelease.lot_id == lot_id,
            COARelease.product_id == product_id,
            COARelease.status == COAReleaseStatus.RELEASED,
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
    from app.models import User
    from app.models.email_history import EmailHistory

    # Get the COARelease
    coa_release = (
        db.query(COARelease)
        .filter(COARelease.lot_id == lot_id, COARelease.product_id == product_id)
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


@router.get("/{id}/source-pdfs/{filename:path}")
async def get_source_pdf(
    id: int,
    filename: str,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    """
    Serve a source PDF file.

    Reads from configured storage (R2 or local filesystem).
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
    normalized_sources = {_normalize_pdf_storage_key(src) for src in source_pdfs}
    storage_key = _normalize_pdf_storage_key(filename)
    if storage_key not in normalized_sources:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF not associated with this release",
        )

    response_filename = storage_key.rsplit("/", 1)[-1]
    return _get_pdf_from_storage(
        storage_key,
        response_filename=response_filename,
        inline=True,
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
