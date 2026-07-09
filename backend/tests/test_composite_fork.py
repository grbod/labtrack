"""D7 tests: composite gate semantics + the re-sample SPAWN (fork) mechanism.

Covers:
  * composite union completeness blocks ALL members;
  * per-SKU verdict split (one shared result passes one member, fails another);
  * a forked member satisfies the composite (union excludes it, composite can
    release);
  * fork naming B, C + uniqueness;
  * inheritance copies only PASS verdicts, with a provenance note;
  * failing/implicated analytes are NOT inherited;
  * supersede link set when a fork's release is issued over a RELEASED source;
  * sibling void (decision 24).

Runs with the workflow enforcement guard at its default (True).
"""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import (
    COARelease,
    LabTestType,
    Lot,
    LotProduct,
    Product,
    ProductTestSpecification,
    TestResult,
    User,
)
from app.models.enums import (
    COAReleaseStatus,
    LotStatus,
    LotType,
    TestResultStatus,
    UserRole,
)
from app.services.lot_fork_service import ForkError, fork_lot

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


# --- builders --------------------------------------------------------------
def _make_user(db, username, role):
    user = User(
        username=username,
        email=f"{username}@example.com",
        role=role,
        active=True,
        full_name=f"{username} Name",
        title="Quality Control",
        signature_path="signatures/sig.png",
    )
    user.set_password("testpass123")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def qc_user(test_db):
    return _make_user(test_db, "qcmanager", UserRole.QC_MANAGER)


@pytest.fixture
def admin_user(test_db):
    return _make_user(test_db, "admin", UserRole.ADMIN)


def _lab_type(db, name, category, unit=""):
    lt = LabTestType(test_name=name, test_category=category, default_unit=unit)
    db.add(lt)
    db.flush()
    return lt


def _product(db, brand, name, flavor):
    p = Product(
        brand=brand,
        product_name=name,
        flavor=flavor,
        display_name=f"{brand} {name} - {flavor}",
    )
    db.add(p)
    db.flush()
    return p


def _spec(db, product_id, lab_type, specification, required=True):
    s = ProductTestSpecification(
        product_id=product_id,
        lab_test_type_id=lab_type.id,
        specification=specification,
        is_required=required,
    )
    db.add(s)
    db.flush()
    return s


def _result(
    db,
    lot_id,
    lab_type,
    value,
    *,
    status=TestResultStatus.APPROVED,
    specification=None,
    unit="",
):
    r = TestResult(
        lot_id=lot_id,
        test_type=lab_type.test_name,
        result_value=value,
        unit=unit,
        specification=specification,
        lab_test_type_id=lab_type.id,
        status=status,
    )
    db.add(r)
    db.flush()
    return r


def _composite(
    db, product_ids, *, batch_numbers=None, status=LotStatus.AWAITING_RELEASE
):
    lot = Lot(
        lot_number="C040726LOT",
        reference_number="C040726",
        lot_type=LotType.MULTI_SKU_COMPOSITE,
        status=status,
        mfg_date=date(2026, 4, 7),
        exp_date=date(2027, 12, 31),
    )
    db.add(lot)
    db.flush()
    for i, pid in enumerate(product_ids):
        bn = batch_numbers[i] if batch_numbers else None
        db.add(LotProduct(lot_id=lot.id, product_id=pid, batch_number=bn))
    db.commit()
    return lot


def _client(user):
    app.dependency_overrides[get_db] = override_get_db

    async def _cu():
        return user

    app.dependency_overrides[get_current_user] = _cu
    return TestClient(app)


# ---------------------------------------------------------------------------
# A. Composite gate semantics
# ---------------------------------------------------------------------------
def test_union_missing_blocks_every_member(test_db, qc_user):
    """A test only sibling B requires, absent from shared results, blocks A too."""
    tpc = _lab_type(test_db, "Total Plate Count", "Microbiological", "CFU/g")
    ars = _lab_type(test_db, "Arsenic", "Heavy Metals", "ppm")
    a = _product(test_db, "BrandA", "Prod A", "Vanilla")
    b = _product(test_db, "BrandB", "Prod B", "Choc")
    _spec(test_db, a.id, tpc, "< 10000")
    _spec(test_db, b.id, tpc, "< 100000")
    _spec(test_db, b.id, ars, "< 1.0")  # only B requires Arsenic
    test_db.commit()
    lot = _composite(test_db, [a.id, b.id])
    # Shared results cover TPC but NOT Arsenic.
    _result(test_db, lot.id, tpc, "5000")
    test_db.commit()

    client = _client(qc_user)
    # Product A does not itself require Arsenic, yet is blocked by the union.
    gate_a = client.get(f"/api/v1/release/{lot.id}/{a.id}/gate").json()
    assert gate_a["is_composite"] is True
    assert "Arsenic" in gate_a["union_missing_tests"]
    assert gate_a["can_release"] is False

    gate_b = client.get(f"/api/v1/release/{lot.id}/{b.id}/gate").json()
    assert "Arsenic" in gate_b["union_missing_tests"]
    assert gate_b["can_release"] is False


def test_per_sku_verdict_split(test_db, qc_user):
    """One shared TPC result passes member A but fails member B (tighter spec)."""
    tpc = _lab_type(test_db, "Total Plate Count", "Microbiological", "CFU/g")
    a = _product(test_db, "BrandA", "Prod A", "Vanilla")
    b = _product(test_db, "BrandB", "Prod B", "Choc")
    _spec(test_db, a.id, tpc, "< 10000")  # 5000 passes
    _spec(test_db, b.id, tpc, "< 100")  # 5000 fails
    test_db.commit()
    lot = _composite(test_db, [a.id, b.id])
    # Shared result carries NO per-product spec so each member uses its own.
    _result(test_db, lot.id, tpc, "5000", specification=None)
    test_db.commit()

    client = _client(qc_user)
    gate_a = client.get(f"/api/v1/release/{lot.id}/{a.id}/gate").json()
    gate_b = client.get(f"/api/v1/release/{lot.id}/{b.id}/gate").json()

    assert gate_a["failing_tests"] == []
    assert gate_a["can_release"] is True  # A passes the shared result
    assert any(t["name"] == "Total Plate Count" for t in gate_b["failing_tests"])
    assert gate_b["can_release"] is False  # B fails the same shared result


def test_forked_member_satisfies_composite(test_db, qc_user):
    """Forking B out clears the union so A (and the composite) can release."""
    tpc = _lab_type(test_db, "Total Plate Count", "Microbiological", "CFU/g")
    ars = _lab_type(test_db, "Arsenic", "Heavy Metals", "ppm")
    a = _product(test_db, "BrandA", "Prod A", "Vanilla")
    b = _product(test_db, "BrandB", "Prod B", "Choc")
    _spec(test_db, a.id, tpc, "< 10000")
    _spec(test_db, b.id, tpc, "< 100")
    _spec(test_db, b.id, ars, "< 1.0")  # only B; Arsenic never tested
    test_db.commit()
    lot = _composite(test_db, [a.id, b.id])
    _result(test_db, lot.id, tpc, "5000")
    # B has an un-issued release so the fork can mark it FORKED.
    test_db.add(
        COARelease(
            lot_id=lot.id, product_id=b.id, status=COAReleaseStatus.AWAITING_RELEASE
        )
    )
    test_db.commit()

    client = _client(qc_user)
    # Before fork: A blocked by the union (Arsenic from B).
    assert (
        client.get(f"/api/v1/release/{lot.id}/{a.id}/gate").json()["can_release"]
        is False
    )

    # Fork B out.
    resp = client.post(f"/api/v1/lots/{lot.id}/fork", json={"product_id": b.id})
    assert resp.status_code == 201

    # B's release is now FORKED; union excludes B → A can release.
    gate_a = client.get(f"/api/v1/release/{lot.id}/{a.id}/gate").json()
    assert gate_a["union_missing_tests"] == []
    assert gate_a["can_release"] is True

    # Approving A releases the whole composite (B is FORKED = satisfied).
    approve = client.post(f"/api/v1/release/{lot.id}/{a.id}/approve", json={})
    assert approve.status_code == 200, approve.text
    body = approve.json()
    assert body["all_products_released"] is True
    assert body["lot_status"] == "released"


# ---------------------------------------------------------------------------
# B. Fork naming + inheritance
# ---------------------------------------------------------------------------
def test_fork_naming_b_then_c_and_uniqueness(test_db, qc_user):
    tpc = _lab_type(test_db, "Total Plate Count", "Microbiological", "CFU/g")
    a = _product(test_db, "BrandA", "Prod A", "Vanilla")
    _spec(test_db, a.id, tpc, "< 10000")
    test_db.commit()
    lot = _composite(test_db, [a.id], batch_numbers=["260920007"])
    _result(test_db, lot.id, tpc, "5000")
    test_db.commit()

    first = fork_lot(test_db, lot.id, a.id, qc_user)
    test_db.commit()
    assert first.lot_number == "260920007B"

    second = fork_lot(test_db, lot.id, a.id, qc_user)
    test_db.commit()
    assert second.lot_number == "260920007C"


def test_fork_inherits_only_passing_results_with_provenance(test_db, qc_user):
    tpc = _lab_type(test_db, "Total Plate Count", "Microbiological", "CFU/g")
    lead = _lab_type(test_db, "Lead", "Heavy Metals", "ppm")
    a = _product(test_db, "BrandA", "Prod A", "Vanilla")
    _spec(test_db, a.id, tpc, "< 10000")
    _spec(test_db, a.id, lead, "< 0.5")
    test_db.commit()
    lot = _composite(test_db, [a.id], batch_numbers=["260920007"])
    _result(test_db, lot.id, tpc, "5000")  # PASS for A
    _result(test_db, lot.id, lead, "1.0")  # FAIL for A (implicated)
    test_db.commit()

    fork = fork_lot(test_db, lot.id, a.id, qc_user)
    test_db.commit()

    inherited = test_db.query(TestResult).filter(TestResult.lot_id == fork.id).all()
    names = {r.test_type for r in inherited}
    assert "Total Plate Count" in names  # passing → inherited
    assert "Lead" not in names  # failing analyte → NOT inherited
    tpc_row = next(r for r in inherited if r.test_type == "Total Plate Count")
    assert tpc_row.status == TestResultStatus.APPROVED
    assert tpc_row.provenance_note is not None
    assert "composite C040726" in tpc_row.provenance_note
    assert fork.fork_context == "composite C040726"
    assert fork.forked_from_lot_id == lot.id


def test_fork_requires_product_on_lot(test_db, qc_user):
    a = _product(test_db, "BrandA", "Prod A", "Vanilla")
    other = _product(test_db, "BrandX", "Other", "None")
    test_db.commit()
    lot = _composite(test_db, [a.id])
    with pytest.raises(ForkError):
        fork_lot(test_db, lot.id, other.id, qc_user)


# ---------------------------------------------------------------------------
# C. Supersede + sibling void
# ---------------------------------------------------------------------------
def test_supersede_link_set_when_fork_release_issued(test_db, qc_user):
    """Releasing a fork over a RELEASED source stamps superseded_by on the old."""
    tpc = _lab_type(test_db, "Total Plate Count", "Microbiological", "CFU/g")
    a = _product(test_db, "BrandA", "Prod A", "Vanilla")
    _spec(test_db, a.id, tpc, "< 10000")
    test_db.commit()

    # Source STANDARD lot, already RELEASED.
    source = Lot(
        lot_number="260920007",
        reference_number="260709-001",
        lot_type=LotType.STANDARD,
        status=LotStatus.RELEASED,
        mfg_date=date(2026, 4, 7),
        exp_date=date(2027, 12, 31),
    )
    test_db.add(source)
    test_db.flush()
    test_db.add(LotProduct(lot_id=source.id, product_id=a.id))
    source_release = COARelease(
        lot_id=source.id,
        product_id=a.id,
        status=COAReleaseStatus.RELEASED,
        released_at=datetime.utcnow(),
        released_by_id=qc_user.id,
    )
    test_db.add(source_release)
    test_db.commit()

    # Fork lot: a re-sample of the same product, ready to release.
    fork = Lot(
        lot_number="260920007B",
        reference_number="260709-002",
        lot_type=LotType.STANDARD,
        status=LotStatus.AWAITING_RELEASE,
        mfg_date=date(2026, 4, 7),
        exp_date=date(2027, 12, 31),
        forked_from_lot_id=source.id,
        fork_context="lot 260920007",
    )
    test_db.add(fork)
    test_db.flush()
    test_db.add(LotProduct(lot_id=fork.id, product_id=a.id))
    _result(test_db, fork.id, tpc, "4000")  # present + approved → gate passes
    test_db.commit()

    client = _client(qc_user)
    resp = client.post(f"/api/v1/release/{fork.id}/{a.id}/approve", json={})
    assert resp.status_code == 200, resp.text
    fork_release_id = resp.json()["coa_release_id"]

    test_db.refresh(source_release)
    assert source_release.superseded_by_release_id == fork_release_id


def test_sibling_void_lists_and_voids_together(test_db, admin_user):
    tpc = _lab_type(test_db, "Total Plate Count", "Microbiological", "CFU/g")
    a = _product(test_db, "BrandA", "Prod A", "Vanilla")
    b = _product(test_db, "BrandB", "Prod B", "Choc")
    _spec(test_db, a.id, tpc, "< 10000")
    _spec(test_db, b.id, tpc, "< 10000")
    test_db.commit()
    lot = _composite(test_db, [a.id, b.id], status=LotStatus.RELEASED)
    rel_a = COARelease(
        lot_id=lot.id,
        product_id=a.id,
        status=COAReleaseStatus.RELEASED,
        released_at=datetime.utcnow(),
        released_by_id=admin_user.id,
    )
    rel_b = COARelease(
        lot_id=lot.id,
        product_id=b.id,
        status=COAReleaseStatus.RELEASED,
        released_at=datetime.utcnow(),
        released_by_id=admin_user.id,
    )
    test_db.add_all([rel_a, rel_b])
    test_db.commit()

    client = _client(admin_user)
    # Siblings endpoint lists B when querying A.
    sibs = client.get(f"/api/v1/release/{rel_a.id}/siblings").json()
    assert [s["id"] for s in sibs] == [rel_b.id]

    # Void A and also void sibling B in one action.
    resp = client.post(
        f"/api/v1/release/{rel_a.id}/void",
        json={"reason": "wrong shared results", "also_void_release_ids": [rel_b.id]},
    )
    assert resp.status_code == 200, resp.text

    test_db.refresh(rel_a)
    test_db.refresh(rel_b)
    test_db.refresh(lot)
    assert rel_a.status == COAReleaseStatus.AWAITING_RELEASE
    assert rel_b.status == COAReleaseStatus.AWAITING_RELEASE
    assert rel_a.voided_at is not None and rel_b.voided_at is not None
    assert lot.status == LotStatus.AWAITING_RELEASE
