"""Tests for service classes."""

import pytest
from datetime import date, datetime

from app.services import (
    ProductService,
    LotService,
    SampleService,
    UserService,
    ApprovalService,
    AuditService,
)
from app.models.enums import UserRole, LotType, LotStatus, TestResultStatus


class TestProductService:
    """Test ProductService."""

    def test_create_product(self, test_db):
        """Test creating a product through service."""
        service = ProductService()

        product = service.create(
            test_db,
            obj_in={
                "brand": "TestBrand",
                "product_name": "TestProduct",
                "flavor": "Berry",
                "size": "1 kg",
                "display_name": "TestBrand TestProduct - Berry (1 kg)",
            },
        )

        assert product.id is not None
        assert product.brand == "TestBrand"

    def test_find_product(self, test_db, sample_product):
        """Test finding products."""
        service = ProductService()

        # Find by brand and name
        product = service.find_by_brand_and_name(
            test_db,
            sample_product.brand,
            sample_product.product_name,
            sample_product.flavor,
            sample_product.size,
        )
        assert product is not None
        assert product.id == sample_product.id

        # Search products
        results = service.search_products(test_db, search_term="Test")
        assert len(results) == 1

    def test_duplicate_product_prevention(self, test_db, sample_product):
        """Test that duplicate products are prevented."""
        service = ProductService()

        with pytest.raises(ValueError):
            service.create(
                test_db,
                obj_in={
                    "brand": sample_product.brand,
                    "product_name": sample_product.product_name,
                    "flavor": sample_product.flavor,
                    "size": sample_product.size,
                    "display_name": sample_product.display_name,
                },
            )


class TestLotService:
    """Test LotService."""

    def test_create_lot_with_reference(self, test_db, sample_product):
        """Test creating a lot with auto-generated reference."""
        service = LotService()

        lot = service.create_lot(
            test_db,
            lot_data={
                "lot_number": "NEW123",
                "lot_type": LotType.STANDARD,
                "mfg_date": date.today(),
                "exp_date": date(2027, 1, 1),
            },
            product_ids=[sample_product.id],
        )

        assert lot.reference_number is not None
        assert lot.reference_number.startswith(datetime.now().strftime("%y%m%d"))
        assert len(lot.lot_products) == 1

    def test_create_sublots(self, test_db, sample_product):
        """Test creating sublots under parent."""
        service = LotService()

        # Create parent lot
        parent = service.create_lot(
            test_db,
            lot_data={
                "lot_number": "PARENT456",
                "lot_type": LotType.PARENT_LOT,
                "mfg_date": date.today(),
                "exp_date": date(2027, 1, 1),
            },
            product_ids=[sample_product.id],
        )

        # Create sublots manually since create_sublots method doesn't exist
        sublots = []
        for i in range(3):
            sublot = service.create_sublot(
                test_db, 
                parent_lot_id=parent.id,
                sublot_data={
                    "sublot_number": f"PARENT456-{i+1}",
                    "production_date": date.today(),
                    "quantity_lbs": 1000.0
                }
            )
            sublots.append(sublot)

        assert len(sublots) == 3
        assert sublots[0].sublot_number == "PARENT456-1"
        assert sublots[0].quantity_lbs == 1000.0

    def test_update_lot_status(self, test_db, sample_lot):
        """Test updating lot status."""
        service = LotService()

        updated = service.update_lot_status(test_db, sample_lot.id, LotStatus.TESTED)

        assert updated.status == LotStatus.TESTED

    def test_get_expiring_lots(self, test_db, sample_lot):
        """Test getting expiring lots."""
        service = LotService()

        # Sample lot expires in ~3 years, so shouldn't show up
        expiring = service.get_expiring_lots(test_db, days_ahead=30)
        assert len(expiring) == 0

        # But should show up for longer period
        expiring = service.get_expiring_lots(test_db, days_ahead=1200)
        assert len(expiring) == 1


class TestUserService:
    """Test UserService."""

    def test_create_user(self, test_db):
        """Test creating a user."""
        service = UserService()

        user = service.create_user(
            test_db,
            username="newuser",
            email="new@example.com",
            password="password123",
            role=UserRole.LAB_TECH,
        )

        assert user.id is not None
        assert user.username == "newuser"
        assert user.password_hash is not None  # User service sets password internally

    def test_authenticate_user(self, test_db, sample_user):
        """Test user authentication."""
        service = UserService()

        # Valid credentials
        user = service.authenticate(test_db, "testuser", "testpass123")
        assert user is not None
        assert user.id == sample_user.id

        # Invalid password
        user = service.authenticate(test_db, "testuser", "wrongpass")
        assert user is None

        # Invalid username
        user = service.authenticate(test_db, "wronguser", "testpass123")
        assert user is None

    def test_update_user_role(self, test_db, sample_user):
        """Test updating user role."""
        service = UserService()

        updated = service.update_user_role(test_db, sample_user.id, UserRole.ADMIN, updated_by_user_id=1)

        assert updated.role == UserRole.ADMIN


class TestApprovalService:
    """Test ApprovalService."""

    def test_approve_test_result(self, test_db, sample_test_results, sample_user):
        """Test approving a test result."""
        service = ApprovalService()

        # Get draft result
        draft_result = next(
            r for r in sample_test_results if r.status == TestResultStatus.DRAFT
        )

        # Approve it
        approved = service.approve_test_result(test_db, draft_result.id, sample_user.id)

        assert approved.status == TestResultStatus.APPROVED
        assert approved.approved_by_id == sample_user.id
        assert approved.approved_at is not None

    def test_reject_test_result(self, test_db, sample_test_results, sample_user):
        """Test rejecting a test result."""
        service = ApprovalService()

        draft_result = next(
            r for r in sample_test_results if r.status == TestResultStatus.DRAFT
        )

        # Reject it
        rejected = service.reject_test_result(
            test_db, draft_result.id, sample_user.id, reason="Values out of range"
        )

        assert rejected.status == TestResultStatus.DRAFT  # Stays in draft
        # Check approval history would show rejection

    def test_bulk_approve(self, test_db, sample_lot, sample_user):
        """Test bulk approval of test results."""
        service = ApprovalService()

        # Create multiple draft results
        from app.models import TestResult

        result_ids = []
        for i in range(3):
            result = TestResult(
                lot_id=sample_lot.id,
                test_type=f"Test {i}",
                result_value="Pass",
                status=TestResultStatus.DRAFT,
            )
            test_db.add(result)
            test_db.flush()
            result_ids.append(result.id)

        test_db.commit()

        # Bulk approve
        approved_count = service.bulk_approve_results(test_db, result_ids, sample_user.id)
        assert approved_count == 3

        # Verify all approved
        for result_id in result_ids:
            result = (
                test_db.query(TestResult).filter(TestResult.id == result_id).first()
            )
            assert result.status == TestResultStatus.APPROVED

    def test_lot_auto_approval(
        self, test_db, sample_lot, sample_test_results, sample_user
    ):
        """Test that lot status updates to UNDER_REVIEW when all tests approved."""
        service = ApprovalService()

        # Approve all test results
        for result in sample_test_results:
            if result.status != TestResultStatus.APPROVED:
                service.approve_test_result(test_db, result.id, sample_user.id)

        # Check lot status - should be UNDER_REVIEW awaiting manual approval
        test_db.refresh(sample_lot)
        assert sample_lot.status == LotStatus.UNDER_REVIEW


class TestAuditService:
    """Test AuditService."""

    def test_audit_logging(self, test_db, sample_product, sample_user):
        """Test that changes are logged."""
        service = AuditService()

        # Make a change
        old_name = sample_product.product_name
        sample_product.product_name = "Updated Product"

        # Log the change
        from app.models.audit import AuditLog
        from app.models.enums import AuditAction
        
        AuditLog.log_change(
            session=test_db,
            table_name="products",
            record_id=sample_product.id,
            action=AuditAction.UPDATE,
            old_values={"product_name": old_name},
            new_values={"product_name": "Updated Product"},
            user=sample_user.id,
        )

        test_db.commit()

        # Get audit history
        history = service.get_record_history(test_db, "products", sample_product.id)
        assert len(history) == 1
        assert history[0].action == "update"
