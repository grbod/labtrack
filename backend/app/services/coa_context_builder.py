"""Canonical COA context builder.

Single source of truth for the data that renders a Certificate of Analysis.
Feeds three consumers:

1. the on-screen preview endpoint (``release.py`` preview-data),
2. the ReportLab PDF renderer (``coa_generation_service.py``),
3. (next wave) immutable COA snapshots.

``build_context(db, lot_id, product_id, *, release=None) -> COAContext`` returns
a fully JSON-serialisable Pydantic model. Nothing here fabricates acceptance
criteria: a test with no product specification renders ``spec_text=None``
(``"—"``) with a NO_SPEC verdict.

Verdicts are computed by the specification engine (``app.specs.evaluate``),
which is built in parallel. If that module is not yet importable this builder
falls back to a local ``_fallback_verdict`` that returns a PENDING_ENGINE
(INDETERMINATE-equivalent) verdict so this branch stands alone.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.models.coa_release import COARelease
from app.models.enums import COAReleaseStatus
from app.models.lab_test_type import LabTestType
from app.models.lot import Lot, LotProduct
from app.models.product import Product
from app.models.product_test_spec import ProductTestSpecification
from app.models.test_result import TestResult
from app.services.coa_category_order_service import coa_category_order_service
from app.services.lab_info_service import lab_info_service

# Bumped whenever the COAContext shape changes. Snapshots store this so future
# renderers can branch on it if the schema ever diverges.
CONTEXT_SCHEMA_VERSION = 1

# Template identifier persisted alongside the context for the same reason.
TEMPLATE_VERSION = "coa-standard-v1"

# Categories that are sensory/organoleptic and therefore excluded from the
# "Not Tested" panel — a missing taste/odor observation is not a lab gap.
_SENSORY_CATEGORY_TOKENS = ("organoleptic", "sensory")

# ---------------------------------------------------------------------------
# Spec-engine integration (built in parallel — guard the import).
# ---------------------------------------------------------------------------
try:  # pragma: no cover - exercised by whichever branch lands first
    from app.specs import VerdictKind as _VerdictKind  # type: ignore
    from app.specs import evaluate as _spec_evaluate  # type: ignore

    _HAS_SPEC_ENGINE = True
except (
    Exception
):  # ImportError today; broad guard so a half-built module can't crash us
    _spec_evaluate = None  # type: ignore
    _VerdictKind = None  # type: ignore
    _HAS_SPEC_ENGINE = False


# Verdict kind constants used by the display policy. These are plain strings so
# the builder does not depend on the parallel engine's enum identity — the
# engine's verdict kind is normalised to its ``.name`` (uppercased) before use.
VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_NO_SPEC = "NO_SPEC"
VERDICT_INDETERMINATE = "INDETERMINATE"
# Fallback marker when the spec engine is not available. Treated exactly like
# INDETERMINATE by the display policy.
VERDICT_PENDING_ENGINE = "PENDING_ENGINE"


class _Verdict(BaseModel):
    kind: str
    reason: str


def _fallback_verdict(
    spec_text: Optional[str], result_value: Optional[str]
) -> _Verdict:
    """Standalone verdict used when ``app.specs`` is unavailable.

    TODO(spec-engine): delete once ``app.specs.evaluate`` is guaranteed present.
    Never returns PASS/FAIL — an unavailable engine must not decide compliance.
    """
    if not spec_text:
        return _Verdict(kind=VERDICT_NO_SPEC, reason="no specification on file")
    return _Verdict(
        kind=VERDICT_PENDING_ENGINE,
        reason="spec engine unavailable; verdict deferred to human release decision",
    )


def _compute_verdict(
    spec_text: Optional[str], result_value: Optional[str], unit: Optional[str]
) -> _Verdict:
    """Compute a verdict for a result against a spec, via the engine or fallback."""
    if not spec_text:
        return _Verdict(kind=VERDICT_NO_SPEC, reason="no specification on file")
    if not _HAS_SPEC_ENGINE:
        return _fallback_verdict(spec_text, result_value)
    try:
        verdict = _spec_evaluate(spec_text, result_value, result_unit=unit)
        kind = getattr(verdict, "kind", None)
        kind_str = getattr(kind, "name", str(kind)).upper()
        reason = getattr(verdict, "reason", "") or ""
        return _Verdict(kind=kind_str, reason=str(reason))
    except Exception as exc:  # engine present but blew up on this input
        return _Verdict(
            kind=VERDICT_INDETERMINATE,
            reason=f"spec engine error: {exc}",
        )


def _status_display(verdict_kind: str, has_spec: bool, is_released: bool) -> str:
    """Map a verdict to the on-certificate status string.

    User-approved policy:
      * PASS  -> "Pass"
      * FAIL  -> "Fail"
      * NO_SPEC / no spec -> "—"
      * INDETERMINATE / JUDGMENT / PENDING_ENGINE ->
            "Pass" when the release is RELEASED (a human verified it at release),
            "—" otherwise.
    """
    if not has_spec or verdict_kind == VERDICT_NO_SPEC:
        return "—"
    if verdict_kind == VERDICT_PASS:
        return "Pass"
    if verdict_kind == VERDICT_FAIL:
        return "Fail"
    # INDETERMINATE, JUDGMENT, PENDING_ENGINE, or anything unrecognised.
    return "Pass" if is_released else "—"


# ---------------------------------------------------------------------------
# COAContext schema
# ---------------------------------------------------------------------------
class LabBlock(BaseModel):
    company_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    # URL for the browser preview (``/uploads/...``) and the relative storage
    # key the PDF renderer resolves to a filesystem path.
    logo_url: Optional[str] = None
    logo_path: Optional[str] = None


class DocumentBlock(BaseModel):
    # Stable identity for now: "COA-{reference_number}". Superseded by an issued
    # serial in the snapshot wave (section C).
    document_id: str
    # Human-facing "Generated:" date. now() for live previews, release date once
    # released.
    generated_date: str
    # Release/issue date (None until released).
    release_date: Optional[str] = None
    template_version: str = TEMPLATE_VERSION
    schema_version: int = CONTEXT_SCHEMA_VERSION
    # Printed deviation note when a release gate override was applied.
    deviation_note: Optional[str] = None


class ProductBlock(BaseModel):
    product_id: int
    product_name: str
    brand: Optional[str] = None


class LotBlock(BaseModel):
    lot_number: str
    reference_number: str
    lot_type: Optional[str] = None
    mfg_date: Optional[str] = None
    exp_date: Optional[str] = None
    # Composite component batch number for this product, when the lot is a
    # multi-SKU composite and the association records one.
    component_batch_number: Optional[str] = None


class CustomerBlock(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None


class ApproverBlock(BaseModel):
    """The person who released the COA — sourced ONLY from the release record.

    Never the current viewer. Absent for pre-release previews, in which case the
    signature block renders empty with the (empty) name line only.
    """

    name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    signature_path: Optional[str] = None
    signature_url: Optional[str] = None


class TestRow(BaseModel):
    id: int
    name: str
    method: Optional[str] = None
    result_value: str
    unit: Optional[str] = None
    spec_text: Optional[str] = None
    category: str = "Other"
    order_index: int = 0
    verdict: str = VERDICT_NO_SPEC
    verdict_reason: str = ""
    status_display: str = "—"


class NotTestedRow(BaseModel):
    name: str
    method: Optional[str] = None
    spec_text: Optional[str] = None
    category: str = "Other"
    order_index: int = 0
    status_display: str = "Not Tested"


class COAContext(BaseModel):
    """Fully JSON-serialisable render context for a COA."""

    schema_version: int = CONTEXT_SCHEMA_VERSION
    source: str = "live"  # "live" now; "snapshot" once section C lands
    is_released: bool = False

    lab: LabBlock
    document: DocumentBlock
    product: ProductBlock
    lot: LotBlock
    customer: Optional[CustomerBlock] = None
    approver: ApproverBlock

    test_rows: List[TestRow] = []
    not_tested_rows: List[NotTestedRow] = []
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------
def _fmt_date(value) -> Optional[str]:
    return value.strftime("%B %d, %Y") if value else None


def _is_sensory(category: Optional[str]) -> bool:
    if not category:
        return False
    lowered = category.lower()
    return any(tok in lowered for tok in _SENSORY_CATEGORY_TOKENS)


def build_context(
    db: Session,
    lot_id: int,
    product_id: int,
    *,
    release: Optional[COARelease] = None,
) -> COAContext:
    """Build the canonical COA render context for a (lot, product) pair.

    Args:
        db: database session.
        lot_id: the lot.
        product_id: the product the COA is for (one per COA, even on composites).
        release: the COARelease record for this pair, when one exists. Its
            approver and dates are authoritative; a RELEASED status also drives
            the verdict display policy. ``None`` for a pure pre-release preview.

    Raises:
        ValueError: if the lot or product does not exist.
    """
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise ValueError(f"Lot with id {lot_id} not found")

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise ValueError(f"Product with id {product_id} not found")

    is_released = bool(release and release.status == COAReleaseStatus.RELEASED)

    # Sensory rows attested by QC on this release print "Pass" regardless of the
    # (JUDGMENT/INDETERMINATE) machine verdict — a human signed off on them.
    attested_sensory_ids: set = set()
    if release is not None and getattr(release, "id", None) is not None:
        from app.models.release_sensory_attest import ReleaseSensoryAttest

        attested_sensory_ids = {
            a.lab_test_type_id
            for a in db.query(ReleaseSensoryAttest)
            .filter(ReleaseSensoryAttest.release_id == release.id)
            .all()
        }

    # --- test results ---
    # Every test performed on the lot (print-all policy), then split:
    #   * ``coa_results`` (include_on_coa) become the rendered rows;
    #   * ``all_results`` drive completeness (a test we ran but excluded from the
    #     certificate must not resurface as "Not Tested").
    all_results: List[TestResult] = (
        db.query(TestResult).filter(TestResult.lot_id == lot_id).all()
    )
    coa_results = [r for r in all_results if getattr(r, "include_on_coa", True)]
    test_results = coa_results

    # category lookup from LabTestType, keyed by test name (case-insensitive)
    all_test_types = db.query(LabTestType).all()
    category_by_name = {lt.test_name.lower(): lt.test_category for lt in all_test_types}

    def category_for(test_type: str) -> str:
        return category_by_name.get((test_type or "").lower(), "Other")

    # product specs: test name -> specification text (never fabricated)
    product_specs: List[ProductTestSpecification] = (
        db.query(ProductTestSpecification)
        .options(joinedload(ProductTestSpecification.lab_test_type))
        .filter(ProductTestSpecification.product_id == product_id)
        .all()
    )
    spec_by_name = {}
    for spec in product_specs:
        name = spec.test_name
        if name:
            spec_by_name[name.lower()] = spec.specification

    # category display order
    category_order = coa_category_order_service.get_ordered_categories(db)

    def cat_index(category: str) -> int:
        try:
            return category_order.index(category)
        except ValueError:
            return len(category_order)

    def sort_key_result(result: TestResult) -> tuple:
        category = category_for(result.test_type)
        return (cat_index(category), category, (result.test_type or "").lower())

    test_results.sort(key=sort_key_result)

    test_rows: List[TestRow] = []
    for order_index, result in enumerate(test_results):
        category = category_for(result.test_type)
        # Spec resolution order: the spec saved with the result, else the
        # product's spec for this test. NEVER a fabricated default.
        spec_text = result.specification or spec_by_name.get(
            (result.test_type or "").lower()
        )
        has_spec = bool(spec_text)
        verdict = _compute_verdict(spec_text, result.result_value, result.unit)
        status = _status_display(verdict.kind, has_spec, is_released)
        # A QC-attested sensory row prints "Pass".
        if _is_sensory(category) and result.lab_test_type_id in attested_sensory_ids:
            status = "Pass"
        test_rows.append(
            TestRow(
                id=result.id,
                name=result.test_type,
                method=result.method,
                result_value=result.result_value or "N/D",
                unit=result.unit or None,
                spec_text=spec_text,
                category=category,
                order_index=order_index,
                verdict=verdict.kind,
                verdict_reason=verdict.reason,
                status_display=status,
            )
        )

    # --- not-tested rows: required panel minus any result present ---
    covered = {(r.test_type or "").lower() for r in all_results}
    missing_specs = []
    for spec in product_specs:
        if not spec.is_required:
            continue
        name = spec.test_name
        if not name:
            continue
        category = spec.test_category or "Other"
        if _is_sensory(category):
            continue
        if name.lower() in covered:
            continue
        missing_specs.append(spec)

    missing_specs.sort(
        key=lambda s: (
            cat_index(s.test_category or "Other"),
            s.test_category or "Other",
            (s.test_name or "").lower(),
        )
    )
    not_tested_rows: List[NotTestedRow] = []
    for order_index, spec in enumerate(missing_specs):
        method = spec.lab_test_type.test_method if spec.lab_test_type else None
        not_tested_rows.append(
            NotTestedRow(
                name=spec.test_name,
                method=method,
                spec_text=spec.specification,
                category=spec.test_category or "Other",
                order_index=order_index,
            )
        )

    # --- lab block ---
    lab_info = lab_info_service.get_or_create_default(db)
    lab_block = LabBlock(
        company_name=lab_info.company_name,
        address=lab_info.full_address,
        phone=lab_info.phone,
        email=lab_info.email,
        logo_url=lab_info_service.get_logo_url(lab_info.logo_path),
        logo_path=lab_info.logo_path,
    )

    # --- approver block: strictly from the release record ---
    approver_block = ApproverBlock()
    notes = None
    generated_date = datetime.now().strftime("%B %d, %Y")
    release_date = None
    deviation_note = None
    customer_block = None
    if release is not None:
        # notes: prefer draft_data notes (in-progress edits) over the persisted note
        notes = release.notes
        if release.draft_data and isinstance(release.draft_data, dict):
            notes = release.draft_data.get("notes") or notes

        deviation_note = getattr(release, "deviation_note", None)

        approver = release.released_by
        if approver is None and release.released_by_id:
            from app.models import User

            approver = db.query(User).filter(User.id == release.released_by_id).first()
        if approver is not None:
            approver_block = ApproverBlock(
                name=approver.full_name or approver.username,
                title=approver.title,
                email=approver.email,
                phone=approver.phone,
                signature_path=approver.signature_path,
                signature_url=(
                    f"/uploads/{approver.signature_path}"
                    if approver.signature_path
                    else None
                ),
            )

        if release.released_at:
            release_date = release.released_at.strftime("%B %d, %Y")
            if is_released:
                # Frozen "generated" date for a released COA is the release date.
                generated_date = release_date

        if release.customer is not None:
            customer_block = CustomerBlock(
                company_name=release.customer.company_name,
                contact_name=getattr(release.customer, "contact_name", None),
                email=getattr(release.customer, "email", None),
            )

    # --- composite component batch number (best-effort; column may not exist) ---
    component_batch_number = None
    lot_product = (
        db.query(LotProduct)
        .filter(LotProduct.lot_id == lot_id, LotProduct.product_id == product_id)
        .first()
    )
    if lot_product is not None:
        component_batch_number = getattr(lot_product, "batch_number", None)

    document_block = DocumentBlock(
        document_id=f"COA-{lot.reference_number}",
        generated_date=generated_date,
        release_date=release_date,
        deviation_note=deviation_note,
    )

    return COAContext(
        is_released=is_released,
        lab=lab_block,
        document=document_block,
        product=ProductBlock(
            product_id=product.id,
            product_name=product.display_name or product.product_name,
            brand=product.brand,
        ),
        lot=LotBlock(
            lot_number=lot.lot_number,
            reference_number=lot.reference_number,
            lot_type=lot.lot_type.value if lot.lot_type else None,
            mfg_date=_fmt_date(lot.mfg_date),
            exp_date=_fmt_date(lot.exp_date),
            component_batch_number=component_batch_number,
        ),
        customer=customer_block,
        approver=approver_block,
        test_rows=test_rows,
        not_tested_rows=not_tested_rows,
        notes=notes,
    )
