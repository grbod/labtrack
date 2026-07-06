"""Tests for lab test alias review endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.database import Base
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import LabTestAlias, LabTestType, User
from app.models.enums import UserRole
from app.services.lab_test_alias_service import normalize_alias_key
from tests.test_api_endpoints import TestingSessionLocal, engine, override_get_db


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _make_user(db, role):
    user = User(
        username=f"alias_{role.value}",
        email=f"alias_{role.value}@x.com",
        role=role,
        active=True,
    )
    user.set_password("pw12345678")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _client_as(user):
    app.dependency_overrides[get_db] = override_get_db

    async def _override_user():
        return user

    app.dependency_overrides[get_current_user] = _override_user
    return TestClient(app)


def _lab_type(db, name="Total Plate Count"):
    lab_type = LabTestType(
        test_name=name,
        test_category="Microbiological",
        default_unit="CFU/g",
        test_method="AOAC 990.12",
        is_active=True,
    )
    db.add(lab_type)
    db.commit()
    db.refresh(lab_type)
    return lab_type


def _alias(db, lab_type, status="pending", raw="TPC Count"):
    alias = LabTestAlias(
        raw_phrase=raw,
        normalized_key=normalize_alias_key(raw),
        lab_name="Acme",
        lab_test_type_id=lab_type.id,
        status=status,
        source="fuzzy",
    )
    db.add(alias)
    db.commit()
    db.refresh(alias)
    return alias


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.QC_MANAGER])
def test_admin_and_qc_can_list_edit_approve_and_disable_aliases(db, role):
    lab_type = _lab_type(db)
    alias = _alias(db, lab_type)
    user = _make_user(db, role)
    client = _client_as(user)
    try:
        response = client.get("/api/v1/lab-test-aliases")
        assert response.status_code == 200
        assert response.json()["items"][0]["raw_phrase"] == "TPC Count"

        response = client.patch(
            f"/api/v1/lab-test-aliases/{alias.id}",
            json={"raw_phrase": "TPC", "lab_name": None},
        )
        assert response.status_code == 200
        assert response.json()["normalized_key"] == "tpc"

        response = client.post(f"/api/v1/lab-test-aliases/{alias.id}/approve")
        assert response.status_code == 200
        assert response.json()["status"] == "approved"

        response = client.request(
            "DELETE",
            f"/api/v1/lab-test-aliases/{alias.id}",
            json={"reason": "bad mapping"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "disabled"
        assert response.json()["disable_reason"] == "bad mapping"
    finally:
        app.dependency_overrides.clear()


def test_lab_tech_cannot_manage_aliases(db):
    lab_type = _lab_type(db)
    alias = _alias(db, lab_type)
    user = _make_user(db, UserRole.LAB_TECH)
    client = _client_as(user)
    try:
        assert client.get("/api/v1/lab-test-aliases").status_code == 403
        assert (
            client.patch(
                f"/api/v1/lab-test-aliases/{alias.id}", json={"raw_phrase": "TPC"}
            ).status_code
            == 403
        )
        assert (
            client.post(f"/api/v1/lab-test-aliases/{alias.id}/approve").status_code
            == 403
        )
        assert (
            client.request(
                "DELETE", f"/api/v1/lab-test-aliases/{alias.id}", json={}
            ).status_code
            == 403
        )
    finally:
        app.dependency_overrides.clear()


def test_approving_alias_disables_same_scope_competitors(db):
    tpc = _lab_type(db, "Total Plate Count")
    lead = _lab_type(db, "Lead")
    winner = _alias(db, tpc, raw="TPC Count")
    competitor = _alias(db, lead, raw="TPC Count")
    other_scope = LabTestAlias(
        raw_phrase="TPC Count",
        normalized_key=normalize_alias_key("TPC Count"),
        lab_name=None,
        lab_test_type_id=lead.id,
        status="pending",
        source="fuzzy",
    )
    db.add(other_scope)
    db.commit()
    user = _make_user(db, UserRole.QC_MANAGER)
    client = _client_as(user)
    try:
        response = client.post(f"/api/v1/lab-test-aliases/{winner.id}/approve")
        assert response.status_code == 200
        db.refresh(winner)
        db.refresh(competitor)
        db.refresh(other_scope)
        assert winner.status == "approved"
        assert competitor.status == "disabled"
        assert other_scope.status == "pending"
    finally:
        app.dependency_overrides.clear()
