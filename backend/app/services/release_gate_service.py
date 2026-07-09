"""Release gate computation.

Single source of truth for the green/amber/red gate the Release page renders
and the approve endpoint enforces. Reuses the canonical COA context builder for
per-test verdicts so the gate and the certificate never disagree.

Red (blocking) items:
  * ``missing_tests`` - required non-sensory lab tests with no result
    (exempt for legacy-import lots),
  * ``failing_tests`` - results the spec engine marks FAIL,
  * unattested sensory rows (exempt for legacy-import lots),
  * results not all approved.

Amber (non-blocking) items:
  * ``indeterminate_tests`` - INDETERMINATE verdicts (the human release
    decision resolves these).
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.coa_release import COARelease
from app.models.enums import COAReleaseStatus, LotType, TestResultStatus
from app.models.product_test_spec import ProductTestSpecification
from app.models.release_sensory_attest import ReleaseSensoryAttest
from app.models.test_result import TestResult
from app.schemas.release import (
    GateSensoryRow,
    GateTestRef,
    ReleaseGateStatus,
)
from app.services.coa_context_builder import (
    VERDICT_FAIL,
    VERDICT_INDETERMINATE,
    VERDICT_PENDING_ENGINE,
    _is_sensory,
    build_context,
)
from app.workflow.lot_workflow_service import _is_legacy_import


def _required_sensory_specs(
    db: Session, product_id: int
) -> List[ProductTestSpecification]:
    specs = (
        db.query(ProductTestSpecification)
        .options(joinedload(ProductTestSpecification.lab_test_type))
        .filter(ProductTestSpecification.product_id == product_id)
        .all()
    )
    out: List[ProductTestSpecification] = []
    seen: set[int] = set()
    for spec in specs:
        if not spec.is_required or not spec.lab_test_type_id:
            continue
        category = spec.test_category or (
            spec.lab_test_type.test_category if spec.lab_test_type else None
        )
        if not _is_sensory(category):
            continue
        if spec.lab_test_type_id in seen:
            continue
        seen.add(spec.lab_test_type_id)
        out.append(spec)
    return out


def _norm(value: Optional[str]) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _composite_union_missing_tests(db: Session, lot) -> List[str]:
    """Union of every non-forked member's required non-sensory lab panel that the
    lot's shared results do not yet cover.

    A composite's members share one set of lab results, so a test any member
    requires but that is absent from the shared results blocks the whole
    composite. Members whose release is FORKED have left the composite and are
    excluded from the union.
    """
    forked_product_ids = {
        r.product_id
        for r in db.query(COARelease)
        .filter(
            COARelease.lot_id == lot.id,
            COARelease.status == COAReleaseStatus.FORKED,
        )
        .all()
    }

    results = db.query(TestResult).filter(TestResult.lot_id == lot.id).all()
    covered = {
        _norm(r.test_type)
        for r in results
        if r.result_value is not None and str(r.result_value).strip() != ""
    }

    missing: List[str] = []
    seen: set[str] = set()
    for lot_product in lot.lot_products:
        if lot_product.product_id in forked_product_ids:
            continue
        product = lot_product.product
        if product is None:
            continue
        for spec in product.test_specifications:
            if not spec.is_required or not spec.lab_test_type_id:
                continue
            category = spec.test_category or (
                spec.lab_test_type.test_category if spec.lab_test_type else None
            )
            if _is_sensory(category):
                continue
            name = spec.test_name
            if not name or _norm(name) in covered:
                continue
            if _norm(name) in seen:
                continue
            seen.add(_norm(name))
            missing.append(name)
    return missing


def compute_gate(
    db: Session,
    lot_id: int,
    product_id: int,
    *,
    release: Optional[COARelease] = None,
) -> ReleaseGateStatus:
    """Compute the release gate for a (lot, product) pair."""
    from app.models.lot import Lot

    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    is_legacy = _is_legacy_import(lot) if lot else False
    is_composite = bool(lot and lot.lot_type == LotType.MULTI_SKU_COMPOSITE)

    context = build_context(db, lot_id, product_id, release=release)

    missing_tests = [row.name for row in context.not_tested_rows]
    failing_tests = [
        GateTestRef(
            name=row.name, result_value=row.result_value, spec_text=row.spec_text
        )
        for row in context.test_rows
        if row.verdict == VERDICT_FAIL
    ]
    indeterminate_tests = [
        GateTestRef(
            name=row.name, result_value=row.result_value, spec_text=row.spec_text
        )
        for row in context.test_rows
        if row.verdict in (VERDICT_INDETERMINATE, VERDICT_PENDING_ENGINE)
    ]

    # Sensory attest checklist for this release
    attested_ids: set[int] = set()
    if release is not None and release.id is not None:
        attested_ids = {
            a.lab_test_type_id
            for a in db.query(ReleaseSensoryAttest)
            .filter(ReleaseSensoryAttest.release_id == release.id)
            .all()
        }
    sensory_rows: List[GateSensoryRow] = []
    for spec in _required_sensory_specs(db, product_id):
        sensory_rows.append(
            GateSensoryRow(
                lab_test_type_id=spec.lab_test_type_id,
                name=spec.test_name or "",
                spec_text=spec.specification,
                attested=spec.lab_test_type_id in attested_ids,
            )
        )
    sensory_all_attested = all(r.attested for r in sensory_rows)

    # Results approval state (mirrors the state-machine submit check)
    results = db.query(TestResult).filter(TestResult.lot_id == lot_id).all()
    results_all_approved = (
        all(r.status == TestResultStatus.APPROVED for r in results) if results else True
    )

    # Composite completeness: the union of ALL (non-forked) members' required
    # panels must be covered by the shared results. A missing union test blocks
    # EVERY member (this one included), even tests this product does not itself
    # require.
    union_missing_tests: List[str] = []
    if is_composite and not is_legacy:
        union_missing_tests = _composite_union_missing_tests(db, lot)

    blocking: List[str] = []
    if union_missing_tests:
        blocking.append(
            "Composite incomplete — missing shared tests: "
            + ", ".join(union_missing_tests)
        )
    if missing_tests and not is_legacy:
        blocking.append("Missing required tests: " + ", ".join(missing_tests))
    if failing_tests:
        blocking.append("Failing results: " + ", ".join(t.name for t in failing_tests))
    if sensory_rows and not sensory_all_attested and not is_legacy:
        pending = [r.name for r in sensory_rows if not r.attested]
        blocking.append("Sensory attestation required: " + ", ".join(pending))
    if not results_all_approved:
        blocking.append("Not all test results are approved")

    can_release = not blocking

    prior_recipients, prior_date = _prior_email_notice(db, release)

    return ReleaseGateStatus(
        lot_id=lot_id,
        product_id=product_id,
        is_legacy_import=is_legacy,
        is_composite=is_composite,
        results_all_approved=results_all_approved,
        missing_tests=missing_tests if not is_legacy else [],
        union_missing_tests=union_missing_tests,
        failing_tests=failing_tests,
        indeterminate_tests=indeterminate_tests,
        sensory_rows=sensory_rows,
        sensory_all_attested=sensory_all_attested,
        blocking_reasons=blocking,
        can_release=can_release,
        prior_email_recipients=prior_recipients,
        prior_email_date=prior_date,
    )


def _prior_email_notice(db: Session, release: Optional[COARelease]):
    """Return (recipients, date) when a prior voided release had email history."""
    if release is None or release.id is None:
        return [], None
    if getattr(release, "voided_at", None) is None:
        return [], None
    from app.models.email_history import EmailHistory

    emails = (
        db.query(EmailHistory)
        .filter(EmailHistory.coa_release_id == release.id)
        .order_by(EmailHistory.sent_at.desc())
        .all()
    )
    if not emails:
        return [], None
    recipients = sorted({e.recipient_email for e in emails if e.recipient_email})
    return recipients, emails[0].sent_at
