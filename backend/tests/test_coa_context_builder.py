"""Tests for the canonical COA context builder (coa_context_builder.build_context).

Covers:
  * standard lot: rows carry method + unit; spec resolution never fabricates.
  * verdict display policy: INDETERMINATE renders "Pass" only when RELEASED.
  * NO_SPEC rows show spec None and status "—".
  * not_tested computation from the required panel, excluding sensory tests.
  * composite lot: per-product context with component batch numbers.
"""

from datetime import date, datetime

import pytest

from app.models import (
    Lot,
    LotProduct,
    LotType,
    Product,
    TestResult,
    TestResultStatus,
    UserRole,
)
from app.models.coa_release import COARelease
from app.models.enums import COAReleaseStatus
from app.models.lab_test_type import LabTestType
from app.models.product_test_spec import ProductTestSpecification
from app.services.coa_context_builder import (
    VERDICT_NO_SPEC,
    build_context,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def lab_test_types(test_db):
    types = [
        LabTestType(
            test_name="Total Plate Count",
            test_category="Microbiological",
            default_unit="CFU/g",
            test_method="AOAC 990.12",
            is_active=True,
        ),
        LabTestType(
            test_name="Escherichia coli",
            test_category="Microbiological",
            default_unit="CFU/g",
            test_method="AOAC 991.14",
            is_active=True,
        ),
        LabTestType(
            test_name="Lead",
            test_category="Heavy Metals",
            default_unit="ppm",
            test_method="USP <2232>",
            is_active=True,
        ),
        LabTestType(
            test_name="Appearance",
            test_category="Organoleptic",
            default_unit=None,
            test_method=None,
            is_active=True,
        ),
    ]
    for t in types:
        test_db.add(t)
    test_db.commit()
    return {t.test_name: t for t in types}


@pytest.fixture
def product(test_db):
    p = Product(
        brand="Test Brand",
        product_name="Test Product",
        flavor="Vanilla",
        size="20 serving",
        display_name="Test Brand Test Product - Vanilla (20 serving)",
    )
    test_db.add(p)
    test_db.commit()
    return p


@pytest.fixture
def product_specs(test_db, product, lab_test_types):
    """Required panel: TPC, E. coli, Lead, plus a sensory (Appearance)."""
    specs = [
        ProductTestSpecification(
            product_id=product.id,
            lab_test_type_id=lab_test_types["Total Plate Count"].id,
            specification="< 10000",
            is_required=True,
        ),
        ProductTestSpecification(
            product_id=product.id,
            lab_test_type_id=lab_test_types["Escherichia coli"].id,
            specification="Negative",
            is_required=True,
        ),
        ProductTestSpecification(
            product_id=product.id,
            lab_test_type_id=lab_test_types["Lead"].id,
            specification="< 0.5",
            is_required=True,
        ),
        ProductTestSpecification(
            product_id=product.id,
            lab_test_type_id=lab_test_types["Appearance"].id,
            specification="Conforms",
            is_required=True,
        ),
    ]
    for s in specs:
        test_db.add(s)
    test_db.commit()
    return specs


@pytest.fixture
def standard_lot(test_db, product):
    lot = Lot(
        lot_number="LOT-STD-1",
        lot_type=LotType.STANDARD,
        reference_number="260101-001",
        mfg_date=date(2026, 1, 1),
        exp_date=date(2028, 1, 1),
    )
    test_db.add(lot)
    test_db.commit()
    test_db.add(LotProduct(lot_id=lot.id, product_id=product.id))
    test_db.commit()
    return lot


def _add_result(
    test_db,
    lot_id,
    test_type,
    value,
    unit,
    method=None,
    spec=None,
    status=TestResultStatus.APPROVED,
):
    r = TestResult(
        lot_id=lot_id,
        test_type=test_type,
        result_value=value,
        unit=unit,
        method=method,
        specification=spec,
        status=status,
    )
    test_db.add(r)
    test_db.commit()
    return r


@pytest.fixture
def qc_user(test_db):
    from app.services.user_service import UserService

    return UserService().create_user(
        test_db,
        username="qc",
        email="qc@example.com",
        password="secret123",
        role=UserRole.QC_MANAGER,
    )


# ---------------------------------------------------------------------------
# Standard lot: rows, method, unit, spec resolution
# ---------------------------------------------------------------------------
def test_standard_lot_rows_carry_method_and_unit(
    test_db, standard_lot, product, lab_test_types
):
    _add_result(
        test_db,
        standard_lot.id,
        "Total Plate Count",
        "< 10",
        "CFU/g",
        method="AOAC 990.12",
    )
    _add_result(test_db, standard_lot.id, "Lead", "0.05", "ppm", method="USP <2232>")

    ctx = build_context(test_db, standard_lot.id, product.id)

    assert ctx.schema_version == 1
    assert ctx.document.document_id == "COA-260101-001"
    names = {r.name: r for r in ctx.test_rows}
    assert names["Total Plate Count"].method == "AOAC 990.12"
    assert names["Total Plate Count"].unit == "CFU/g"
    assert names["Lead"].unit == "ppm"


def test_no_fabricated_specs(test_db, standard_lot, product, lab_test_types):
    # No product specs and no result-level spec -> spec_text is None (never "Within limits").
    _add_result(test_db, standard_lot.id, "Total Plate Count", "< 10", "CFU/g")

    ctx = build_context(test_db, standard_lot.id, product.id)
    row = ctx.test_rows[0]
    assert row.spec_text is None
    assert row.verdict == VERDICT_NO_SPEC
    assert row.status_display == "—"


def test_result_level_spec_used_when_present(
    test_db, standard_lot, product, lab_test_types
):
    _add_result(test_db, standard_lot.id, "Lead", "0.05", "ppm", spec="< 0.5")
    ctx = build_context(test_db, standard_lot.id, product.id)
    assert ctx.test_rows[0].spec_text == "< 0.5"


def test_product_spec_used_as_fallback(test_db, standard_lot, product, product_specs):
    _add_result(test_db, standard_lot.id, "Lead", "0.05", "ppm")  # no result-level spec
    ctx = build_context(test_db, standard_lot.id, product.id)
    lead = next(r for r in ctx.test_rows if r.name == "Lead")
    assert lead.spec_text == "< 0.5"  # from ProductTestSpecification


# ---------------------------------------------------------------------------
# Verdict display policy (released vs not)
# ---------------------------------------------------------------------------
def test_indeterminate_row_dash_when_not_released(
    test_db, standard_lot, product, product_specs
):
    # With the parallel spec engine absent, a spec'd row is PENDING_ENGINE
    # (INDETERMINATE-equivalent) -> "—" when not released.
    _add_result(test_db, standard_lot.id, "Lead", "0.05", "ppm")
    ctx = build_context(test_db, standard_lot.id, product.id)
    lead = next(r for r in ctx.test_rows if r.name == "Lead")
    assert lead.status_display == "—"
    assert not ctx.is_released


def test_indeterminate_row_pass_when_released(
    test_db, standard_lot, product, product_specs, qc_user
):
    _add_result(test_db, standard_lot.id, "Lead", "0.05", "ppm")
    release = COARelease(
        lot_id=standard_lot.id,
        product_id=product.id,
        status=COAReleaseStatus.RELEASED,
        released_at=datetime(2026, 2, 1, 12, 0, 0),
        released_by_id=qc_user.id,
    )
    test_db.add(release)
    test_db.commit()

    ctx = build_context(test_db, standard_lot.id, product.id, release=release)
    lead = next(r for r in ctx.test_rows if r.name == "Lead")
    assert ctx.is_released
    assert lead.status_display == "Pass"  # human verified at release
    # Released COA freezes generated_date to the release date.
    assert ctx.document.release_date == "February 01, 2026"
    assert ctx.document.generated_date == "February 01, 2026"


def test_no_spec_row_dash_even_when_released(test_db, standard_lot, product, qc_user):
    # A row with no spec is NO_SPEC and must stay "—" regardless of release state.
    _add_result(test_db, standard_lot.id, "Total Plate Count", "< 10", "CFU/g")
    release = COARelease(
        lot_id=standard_lot.id,
        product_id=product.id,
        status=COAReleaseStatus.RELEASED,
        released_at=datetime(2026, 2, 1),
        released_by_id=qc_user.id,
    )
    test_db.add(release)
    test_db.commit()
    ctx = build_context(test_db, standard_lot.id, product.id, release=release)
    row = ctx.test_rows[0]
    assert row.spec_text is None
    assert row.status_display == "—"


# ---------------------------------------------------------------------------
# Not-tested computation
# ---------------------------------------------------------------------------
def test_not_tested_excludes_sensory_and_lists_missing(
    test_db, standard_lot, product, product_specs
):
    # Required panel = TPC, E. coli, Lead, Appearance(sensory). Provide only TPC.
    _add_result(test_db, standard_lot.id, "Total Plate Count", "< 10", "CFU/g")

    ctx = build_context(test_db, standard_lot.id, product.id)
    missing = {r.name for r in ctx.not_tested_rows}
    # E. coli and Lead are missing; Appearance is sensory and excluded; TPC present.
    assert missing == {"Escherichia coli", "Lead"}
    for r in ctx.not_tested_rows:
        assert r.status_display == "Not Tested"
        assert r.spec_text is not None  # panel specs are real, not fabricated


def test_present_test_not_in_not_tested_even_if_no_value(
    test_db, standard_lot, product, product_specs
):
    # A present-but-empty result still counts as "tested" (no duplicate Not-Tested row).
    _add_result(test_db, standard_lot.id, "Lead", "", "ppm")
    ctx = build_context(test_db, standard_lot.id, product.id)
    assert "Lead" not in {r.name for r in ctx.not_tested_rows}


def test_optional_tests_not_in_not_tested(
    test_db, standard_lot, product, lab_test_types
):
    test_db.add(
        ProductTestSpecification(
            product_id=product.id,
            lab_test_type_id=lab_test_types["Lead"].id,
            specification="< 0.5",
            is_required=False,
        )
    )
    test_db.commit()
    ctx = build_context(test_db, standard_lot.id, product.id)
    assert ctx.not_tested_rows == []


# ---------------------------------------------------------------------------
# include_on_coa
# ---------------------------------------------------------------------------
def test_internal_results_excluded_from_rows_but_count_as_tested(
    test_db, standard_lot, product, product_specs
):
    r = _add_result(test_db, standard_lot.id, "Lead", "0.05", "ppm")
    r.include_on_coa = False
    test_db.commit()

    ctx = build_context(test_db, standard_lot.id, product.id)
    # Excluded from rendered rows...
    assert "Lead" not in {row.name for row in ctx.test_rows}
    # ...but not surfaced as Not Tested (we did run it).
    assert "Lead" not in {row.name for row in ctx.not_tested_rows}


# ---------------------------------------------------------------------------
# Approver comes only from the release record
# ---------------------------------------------------------------------------
def test_approver_absent_without_release(test_db, standard_lot, product):
    _add_result(test_db, standard_lot.id, "Total Plate Count", "< 10", "CFU/g")
    ctx = build_context(test_db, standard_lot.id, product.id)
    assert ctx.approver.name is None
    assert ctx.approver.signature_url is None


def test_approver_from_release(test_db, standard_lot, product, qc_user):
    qc_user.full_name = "Jane QC"
    qc_user.title = "QC Manager"
    qc_user.signature_path = "signatures/jane.png"
    test_db.commit()
    release = COARelease(
        lot_id=standard_lot.id,
        product_id=product.id,
        status=COAReleaseStatus.RELEASED,
        released_at=datetime(2026, 2, 1),
        released_by_id=qc_user.id,
    )
    test_db.add(release)
    test_db.commit()
    ctx = build_context(test_db, standard_lot.id, product.id, release=release)
    assert ctx.approver.name == "Jane QC"
    assert ctx.approver.title == "QC Manager"
    assert ctx.approver.signature_url == "/uploads/signatures/jane.png"


# ---------------------------------------------------------------------------
# Composite lot with per-product context
# ---------------------------------------------------------------------------
def test_composite_lot_per_product(test_db):
    p1 = Product(brand="B", product_name="P1", display_name="B P1")
    p2 = Product(brand="B", product_name="P2", display_name="B P2")
    test_db.add_all([p1, p2])
    test_db.commit()

    lot = Lot(
        lot_number="C-260101-009",
        lot_type=LotType.MULTI_SKU_COMPOSITE,
        reference_number="C260101-009",
        mfg_date=date(2026, 1, 1),
        exp_date=date(2028, 1, 1),
    )
    test_db.add(lot)
    test_db.commit()
    test_db.add_all(
        [
            LotProduct(lot_id=lot.id, product_id=p1.id),
            LotProduct(lot_id=lot.id, product_id=p2.id),
        ]
    )
    test_db.commit()

    _add_result(test_db, lot.id, "Total Plate Count", "< 10", "CFU/g")

    ctx1 = build_context(test_db, lot.id, p1.id)
    ctx2 = build_context(test_db, lot.id, p2.id)
    assert ctx1.product.product_id == p1.id
    assert ctx2.product.product_id == p2.id
    assert ctx1.lot.lot_type == "multi_sku_composite"
    # Both COAs reference the same composite lot / document identity.
    assert ctx1.document.document_id == ctx2.document.document_id == "COA-C260101-009"


def test_context_is_json_serialisable(test_db, standard_lot, product, product_specs):
    _add_result(test_db, standard_lot.id, "Lead", "0.05", "ppm")
    ctx = build_context(test_db, standard_lot.id, product.id)
    # Round-trips through JSON without error.
    dumped = ctx.model_dump_json()
    assert '"schema_version":1' in dumped.replace(" ", "")
