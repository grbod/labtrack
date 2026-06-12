"""Tests for COC PDF archiving and re-download endpoint."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import Lot, LotProduct, Product, User
from app.models.enums import LotStatus, LotType, UserRole
from app.services import storage_service as storage_module
from app.services.local_storage import LocalStorageService

# Isolated in-memory DB for this test module
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
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
def temp_storage(tmp_path, monkeypatch):
    """Point the storage singleton at a temp dir, isolated per test."""
    storage_module.reset_storage_service()
    local = LocalStorageService(base_path=tmp_path / "storage")
    monkeypatch.setattr(storage_module, "get_storage_service", lambda: local)
    yield local
    storage_module.reset_storage_service()


@pytest.fixture
def admin_user(test_db):
    user = User(
        username="admin", email="admin@example.com", role=UserRole.ADMIN, active=True
    )
    user.set_password("adminpass123")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def client(test_db, admin_user):
    app.dependency_overrides[get_db] = override_get_db

    async def override_get_current_user():
        return admin_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def test_product(test_db):
    product = Product(
        brand="Test Brand",
        product_name="Test Product",
        flavor="Vanilla",
        size="20 serving",
        display_name="Test Brand Test Product - Vanilla (20 serving)",
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


def _make_lot(test_db, product, *, reference_number="241101-001", status=LotStatus.AWAITING_RESULTS):
    lot = Lot(
        lot_number="TEST123",
        lot_type=LotType.STANDARD,
        reference_number=reference_number,
        mfg_date=date(2024, 11, 1),
        exp_date=date(2027, 11, 1),
        status=status,
        generate_coa=True,
    )
    test_db.add(lot)
    test_db.commit()
    test_db.add(LotProduct(lot_id=lot.id, product_id=product.id))
    test_db.commit()
    test_db.refresh(lot)
    return lot


@pytest.fixture
def active_lot(test_db, test_product):
    return _make_lot(test_db, test_product)


def test_coc_pdf_generation_archives(client, test_db, active_lot):
    resp = client.get(f"/api/v1/lots/{active_lot.id}/daane-coc/pdf")
    assert resp.status_code == 200

    test_db.refresh(active_lot)
    assert active_lot.coc_storage_key


def test_coc_pdf_regeneration_overwrites_archive(client, test_db, active_lot, temp_storage):
    r1 = client.get(f"/api/v1/lots/{active_lot.id}/daane-coc/pdf")
    assert r1.status_code == 200

    r2 = client.get(
        f"/api/v1/lots/{active_lot.id}/daane-coc/pdf",
        params={"special_instructions": "SECOND GENERATION DIFFERENT NOTE"},
    )
    assert r2.status_code == 200

    test_db.refresh(active_lot)
    assert active_lot.coc_storage_key

    archived = temp_storage.download(active_lot.coc_storage_key)
    assert archived == r2.content


def test_coc_archive_download_serves_archived_bytes(client, test_db, active_lot):
    gen = client.get(f"/api/v1/lots/{active_lot.id}/daane-coc/pdf")
    assert gen.status_code == 200

    arch = client.get(f"/api/v1/lots/{active_lot.id}/coc-archive")
    assert arch.status_code == 200
    assert arch.content == gen.content
    assert (
        arch.headers["content-disposition"]
        == f'attachment; filename="daane-coc-{active_lot.reference_number}.pdf"'
    )


def test_coc_archive_fallback_generates_for_active_lot(client, test_db, active_lot):
    # No prior explicit generation
    test_db.refresh(active_lot)
    assert not active_lot.coc_storage_key

    resp = client.get(f"/api/v1/lots/{active_lot.id}/coc-archive")
    assert resp.status_code == 200

    test_db.refresh(active_lot)
    assert active_lot.coc_storage_key


def test_coc_archive_404_for_terminal_lot_without_archive(client, test_db, test_product):
    lot = _make_lot(
        test_db,
        test_product,
        reference_number="241101-002",
        status=LotStatus.RELEASED,
    )
    assert not lot.coc_storage_key

    resp = client.get(f"/api/v1/lots/{lot.id}/coc-archive")
    assert resp.status_code == 404


def test_coc_archive_404_unknown_lot(client):
    resp = client.get("/api/v1/lots/999999/coc-archive")
    assert resp.status_code == 404
