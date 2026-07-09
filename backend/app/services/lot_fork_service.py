"""Re-sample SPAWN mechanism.

``fork_lot`` individualizes a single product out of a source lot (typically a
composite member) into a fresh STANDARD lot for supplementary testing. It:

  * names the new lot ``<base><next-free-letter>`` (B, C, ...), where ``base``
    is the composite component lot number (``lot_products.batch_number``) for a
    composite member, else the source lot's own ``lot_number``;
  * generates a new lab reference number;
  * inherits the source lot's results that PASS this product's specs (per the
    canonical spec engine) as APPROVED results carrying a provenance note, and
    leaves everything else to be re-tested;
  * recomputes the new lot's status through the canonical workflow;
  * marks the source composite member's un-issued release as FORKED so the
    composite gate treats it as satisfied.

The caller owns the transaction (commit/rollback).
"""

from __future__ import annotations

import string
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.coa_release import COARelease
from app.models.enums import (
    AuditAction,
    COAReleaseStatus,
    LotStatus,
    LotType,
    TestResultStatus,
)
from app.models.lot import Lot, LotProduct
from app.models.product import Product
from app.models.test_result import TestResult
from app.services.audit_service import AuditService
from app.services.lot_service import LotService
from app.utils.logger import logger

audit_service = AuditService()


class ForkError(ValueError):
    """Raised when a lot cannot be forked (bad product/lot, no free suffix)."""


def _next_forked_lot_number(db: Session, base: str) -> str:
    """Return ``<root><letter>`` for the first free letter B..Z.

    ``root`` is ``base`` with any single trailing A-Z letter stripped, so
    forking ``260920007`` yields ``260920007B`` and forking that fork yields
    ``260920007C``. Uniqueness is validated against ``lots.lot_number`` (stored
    upper-cased by the model validator).
    """
    root = (base or "").strip().upper()
    if root and root[-1] in string.ascii_uppercase:
        root = root[:-1]
    if not root:
        raise ForkError("Cannot derive a fork lot number from an empty base")

    for letter in string.ascii_uppercase[1:]:  # B, C, ... Z
        candidate = f"{root}{letter}"
        exists = (
            db.query(Lot.id).filter(Lot.lot_number == candidate).first() is not None
        )
        if not exists:
            return candidate
    raise ForkError(f"No free fork suffix available for base '{root}'")


def _resolve_spec_text(
    product_specs: dict, product_specs_by_name: dict, result: TestResult
) -> Optional[str]:
    """Resolve the spec text to evaluate a source result against THIS product."""
    spec = None
    if result.lab_test_type_id is not None:
        spec = product_specs.get(result.lab_test_type_id)
    if spec is None:
        spec = product_specs_by_name.get((result.test_type or "").strip().casefold())
    if spec is not None:
        return spec.specification
    # Fall back to the spec saved on the result itself (never fabricated).
    return result.specification


def _result_passes_product(spec_text: Optional[str], result: TestResult) -> bool:
    """True only when the spec engine returns a definite PASS for this product.

    FAIL / INDETERMINATE / NO_SPEC results are NOT inherited — the analytes
    implicated in a rejection must be re-tested on the fork.
    """
    if not spec_text:
        return False
    try:
        from app.specs import VerdictKind, evaluate

        verdict = evaluate(spec_text, result.result_value, result_unit=result.unit)
        kind = getattr(verdict, "kind", verdict)
        return kind == VerdictKind.PASS
    except Exception:
        # Engine unavailable or blew up → do not inherit (safe default).
        return False


def fork_lot(
    db: Session,
    source_lot_id: int,
    product_id: int,
    actor,
) -> Lot:
    """Fork ``product_id`` out of ``source_lot_id`` into a fresh STANDARD lot."""
    lot_service = LotService()
    actor_id = getattr(actor, "id", None)

    source = db.query(Lot).filter(Lot.id == source_lot_id).first()
    if source is None:
        raise ForkError(f"Source lot {source_lot_id} not found")

    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise ForkError(f"Product {product_id} not found")

    source_lot_product = (
        db.query(LotProduct)
        .filter(
            LotProduct.lot_id == source_lot_id,
            LotProduct.product_id == product_id,
        )
        .first()
    )
    if source_lot_product is None:
        raise ForkError("Product is not associated with the source lot")

    is_composite = source.lot_type == LotType.MULTI_SKU_COMPOSITE

    # --- new lot number: component lot (composite) else the source lot number.
    if is_composite and (source_lot_product.batch_number or "").strip():
        base = source_lot_product.batch_number
    else:
        base = source.lot_number
    new_lot_number = _next_forked_lot_number(db, base)

    if is_composite:
        fork_context = f"composite {source.reference_number}"
    else:
        fork_context = f"lot {source.lot_number}"

    # --- create the STANDARD fork lot (default status AWAITING_RESULTS).
    new_lot = Lot(
        lot_number=new_lot_number,
        lot_type=LotType.STANDARD,
        reference_number=lot_service.generate_reference_number(db),
        mfg_date=source.mfg_date,
        exp_date=source.exp_date,
        status=LotStatus.AWAITING_RESULTS,
        generate_coa=True,
        forked_from_lot_id=source.id,
        fork_context=fork_context,
    )
    db.add(new_lot)
    db.flush()

    db.add(LotProduct(lot_id=new_lot.id, product_id=product_id))

    # --- inherit passing results (panel = the SKU's full required panel, which
    # is defined by the product's specifications).
    product_specs = {
        s.lab_test_type_id: s
        for s in product.test_specifications
        if s.lab_test_type_id is not None
    }
    product_specs_by_name = {
        (s.test_name or "").strip().casefold(): s
        for s in product.test_specifications
        if s.test_name
    }

    source_results = (
        db.query(TestResult).filter(TestResult.lot_id == source_lot_id).all()
    )
    if is_composite:
        tested_when = source.mfg_date.strftime("%Y-%m-%d") if source.mfg_date else None
    inherited_count = 0
    for result in source_results:
        spec_text = _resolve_spec_text(product_specs, product_specs_by_name, result)
        if not _result_passes_product(spec_text, result):
            continue
        if is_composite:
            when = (
                result.test_date.strftime("%Y-%m-%d")
                if result.test_date
                else tested_when
            )
            provenance = f"Tested as composite {source.reference_number}"
            if when:
                provenance = f"{provenance}, {when}"
        else:
            provenance = f"Tested as {source.lot_number}"

        db.add(
            TestResult(
                lot_id=new_lot.id,
                test_type=result.test_type,
                result_value=result.result_value,
                unit=result.unit,
                test_date=result.test_date,
                method=result.method,
                specification=result.specification,
                lab_test_type_id=result.lab_test_type_id,
                include_on_coa=result.include_on_coa,
                pdf_source=result.pdf_source,
                confidence_score=result.confidence_score,
                status=TestResultStatus.APPROVED,
                approved_by_id=actor_id,
                approved_at=datetime.utcnow(),
                created_by_id=actor_id,
                provenance_note=provenance,
            )
        )
        inherited_count += 1
    db.flush()

    # --- recompute the fork's status through the canonical workflow.
    calculation = lot_service.calculate_lot_status(db, new_lot)
    lot_service._apply_lot_status_calculation(
        db, calculation, user_id=actor_id, reason_prefix="Fork inheritance"
    )

    # --- mark the source composite member's UN-ISSUED release as FORKED so the
    # composite gate treats that member as satisfied/absent.
    source_release = (
        db.query(COARelease)
        .filter(
            COARelease.lot_id == source_lot_id,
            COARelease.product_id == product_id,
        )
        .first()
    )
    if (
        source_release is not None
        and source_release.status == COAReleaseStatus.AWAITING_RELEASE
    ):
        source_release.status = COAReleaseStatus.FORKED
        marker = f"[Forked to {new_lot.reference_number} / {new_lot.lot_number}]"
        source_release.notes = (
            f"{source_release.notes}\n{marker}" if source_release.notes else marker
        )
        audit_service.log_action(
            db=db,
            table_name="coa_releases",
            record_id=source_release.id,
            action=AuditAction.UPDATE,
            user_id=actor_id,
            old_values={"status": COAReleaseStatus.AWAITING_RELEASE.value},
            new_values={"status": COAReleaseStatus.FORKED.value},
            reason=f"Composite member forked to {new_lot.reference_number}",
        )

    audit_service.log_action(
        db=db,
        table_name="lots",
        record_id=new_lot.id,
        action=AuditAction.INSERT,
        user_id=actor_id,
        new_values={
            "lot_number": new_lot.lot_number,
            "reference_number": new_lot.reference_number,
            "forked_from_lot_id": source.id,
            "fork_context": fork_context,
            "inherited_results": inherited_count,
        },
        reason=f"Forked from lot {source.lot_number} ({fork_context})",
    )

    logger.info(
        "Forked product {} from lot {} into new lot {} ({} results inherited)",
        product_id,
        source.lot_number,
        new_lot.lot_number,
        inherited_count,
    )
    return new_lot
