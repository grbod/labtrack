"""Tests for database models."""

import pytest
from datetime import date, datetime

from app.models import Product, Lot, User, TestResult, Sublot
from app.models.enums import UserRole, LotType, LotStatus, TestResultStatus


class TestProductModel:
    """Test Product model."""

    def test_create_product(self, test_db):
        """Test creating a product."""
        product = Product(
            brand="Acme",
            product_name="Protein Powder",
            flavor="Chocolate",
            size="2 lb",
            display_name="Acme Protein Powder - Chocolate (2 lb)",
        )
        test_db.add(product)
        test_db.commit()

        assert product.id is not None
        assert product.brand == "Acme"
        assert product.product_name == "Protein Powder"
        assert product.created_at is not None

    def test_product_repr(self, sample_product):
        """Test product string representation."""
        assert "Test Brand" in repr(sample_product)
        assert "Test Product" in repr(sample_product)


class TestLotModel:
    """Test Lot model."""

    def test_create_lot(self, test_db):
        """Test creating a lot."""
        lot = Lot(
            lot_number="ABC123",
            lot_type=LotType.STANDARD,
            reference_number="241101-001",
            mfg_date=date.today(),
            exp_date=date(2027, 1, 1),
            status=LotStatus.AWAITING_RESULTS,
        )
        test_db.add(lot)
        test_db.commit()

        assert lot.id is not None
        assert lot.lot_number == "ABC123"
        assert lot.generate_coa is True  # Default value

    def test_lot_status_transition(self, sample_lot, test_db):
        """Test lot status transitions."""
        # Valid transition
        sample_lot.update_status(LotStatus.UNDER_REVIEW)
        test_db.commit()
        assert sample_lot.status == LotStatus.UNDER_REVIEW

        # Invalid transition (can't go back to awaiting_results)
        with pytest.raises(ValueError):
            sample_lot.update_status(LotStatus.AWAITING_RESULTS)

    def test_parent_lot_sublots(self, test_db, sample_product):
        """Test parent lot with sublots."""
        parent = Lot(
            lot_number="PARENT123",
            lot_type=LotType.PARENT_LOT,
            reference_number="241101-002",
        )
        test_db.add(parent)
        test_db.commit()

        # Create sublots
        for i in range(3):
            sublot = Sublot(
                parent_lot_id=parent.id,
                sublot_number=f"PARENT123-{i+1}",
                production_date=date.today(),
                quantity_lbs=2000.0,
            )
            test_db.add(sublot)

        test_db.commit()

        assert len(parent.sublots) == 3
        assert parent.sublots[0].sublot_number == "PARENT123-1"


class TestUserModel:
    """Test User model."""

    def test_create_user(self, test_db):
        """Test creating a user."""
        user = User(
            username="johndoe", email="john@example.com", role=UserRole.LAB_TECH
        )
        user.set_password("securepass123")
        test_db.add(user)
        test_db.commit()

        assert user.id is not None
        assert user.check_password("securepass123")
        assert not user.check_password("wrongpass")

    def test_user_permissions(self, sample_user):
        """Test user permission checking."""
        # QC Manager can approve
        assert sample_user.can_approve

        # Create lab tech user
        lab_tech = User(
            username="labtech", email="lab@example.com", role=UserRole.LAB_TECH
        )
        assert not lab_tech.can_approve

    def test_user_deactivation(self, sample_user, test_db):
        """Test user deactivation."""
        sample_user.deactivate()
        test_db.commit()

        assert not sample_user.active
        assert not sample_user.check_password("testpass123")


class TestTestResultModel:
    """Test TestResult model."""

    def test_create_test_result(self, test_db, sample_lot):
        """Test creating a test result."""
        result = TestResult(
            lot_id=sample_lot.id,
            test_type="Salmonella",
            result_value="Negative",
            unit="",
            test_date=date.today(),
            confidence_score=0.99,
            status=TestResultStatus.DRAFT,
        )
        test_db.add(result)
        test_db.commit()

        assert result.id is not None
        assert result.lot_id == sample_lot.id
        assert result.can_transition_to(TestResultStatus.APPROVED)

    def test_test_result_approval(self, test_db, sample_test_results):
        """Test test result approval workflow."""
        draft_result = next(
            r for r in sample_test_results if r.status == TestResultStatus.DRAFT
        )

        # Draft -> Approved
        draft_result.status = TestResultStatus.APPROVED
        draft_result.approved_by_id = 1  # User ID
        draft_result.approved_at = datetime.now()
        test_db.commit()

        assert draft_result.status == TestResultStatus.APPROVED

        # Can go back to draft (admin override)
        assert draft_result.can_transition_to(TestResultStatus.DRAFT)

    def test_test_category(self, sample_test_results):
        """Test test result categorization."""
        for result in sample_test_results:
            if result.test_type == "Total Plate Count":
                assert result.test_category == "Microbiological"
            elif result.test_type == "Lead":
                assert result.test_category == "Heavy Metals"
