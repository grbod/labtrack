"""Extended service tests for better coverage."""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.models import (
    User, Product, Lot, LotProduct, TestResult,
    AuditLog, ParsingQueue, LabTestType
)
from app.models.enums import (
    UserRole, LotType, LotStatus, TestResultStatus,
    ParsingStatus, AuditAction
)
from app.services import (
    UserService, AuditService, LotService,
    ProductService, ApprovalService
)
from app.services.sample_service import SampleService


# =============================================================================
# USER SERVICE EXTENDED TESTS
# =============================================================================

class TestUserServiceExtended:
    """Extended tests for UserService."""

    def test_get_user_by_username(self, test_db, sample_user):
        """Test getting user by username."""
        service = UserService()
        user = service.get_by_username(test_db, sample_user.username)
        assert user is not None
        assert user.username == sample_user.username

    def test_get_user_by_email(self, test_db, sample_user):
        """Test getting user by email."""
        service = UserService()
        user = service.get_by_email(test_db, sample_user.email)
        assert user is not None
        assert user.email == sample_user.email

    def test_get_users_by_role(self, test_db, sample_user):
        """Test getting users by role."""
        service = UserService()
        users = service.get_users_by_role(test_db, sample_user.role)
        assert len(users) >= 1
        assert all(u.role == sample_user.role for u in users)

    def test_deactivate_user(self, test_db, sample_user):
        """Test deactivating a user."""
        service = UserService()

        # Create admin to perform deactivation
        admin = service.create_user(
            test_db,
            username="admin_deact",
            email="admin_deact@example.com",
            password="adminpass",
            role=UserRole.ADMIN
        )

        result = service.deactivate_user(test_db, sample_user.id, admin.id, reason="Testing")
        assert result is not None

        test_db.refresh(sample_user)
        assert sample_user.active is False

    def test_reactivate_user(self, test_db):
        """Test reactivating a user."""
        service = UserService()

        # Create and deactivate a user
        user = service.create_user(
            test_db,
            username="inactive_user",
            email="inactive@example.com",
            password="pass123",
            role=UserRole.LAB_TECH
        )
        user.active = False
        test_db.commit()

        # Create admin
        admin = service.create_user(
            test_db,
            username="admin_react",
            email="admin_react@example.com",
            password="adminpass",
            role=UserRole.ADMIN
        )

        result = service.reactivate_user(test_db, user.id, admin.id, reason="Testing")
        assert result is not None

        test_db.refresh(user)
        assert user.active is True

    def test_change_password(self, test_db, sample_user):
        """Test changing user password."""
        service = UserService()

        old_hash = sample_user.password_hash
        result = service.change_password(
            test_db,
            sample_user.id,
            old_password="testpass123",
            new_password="newpassword123"
        )

        # Result could be bool or user object depending on implementation
        assert result is not None
        test_db.refresh(sample_user)
        assert sample_user.password_hash != old_hash

    def test_authenticate_inactive_user(self, test_db):
        """Test authentication fails for inactive user."""
        service = UserService()

        user = service.create_user(
            test_db,
            username="inactive",
            email="inactive2@example.com",
            password="pass123",
            role=UserRole.LAB_TECH
        )
        user.active = False
        test_db.commit()

        result = service.authenticate(test_db, "inactive", "pass123")
        assert result is None


# =============================================================================
# AUDIT SERVICE EXTENDED TESTS
# =============================================================================

class TestAuditServiceExtended:
    """Extended tests for AuditService."""

    def test_log_insert_action(self, test_db, sample_user):
        """Test logging insert action."""
        service = AuditService()

        log = service.log_action(
            test_db,
            table_name="products",
            record_id=1,
            action=AuditAction.INSERT,
            user_id=sample_user.id,
            new_values={"brand": "New Brand", "product_name": "New Product"}
        )

        assert log is not None
        assert log.action == AuditAction.INSERT
        assert log.table_name == "products"

    def test_log_delete_action(self, test_db, sample_user):
        """Test logging delete action."""
        service = AuditService()

        log = service.log_action(
            test_db,
            table_name="lots",
            record_id=5,
            action=AuditAction.DELETE,
            user_id=sample_user.id,
            old_values={"lot_number": "LOT123", "status": "pending"},
            reason="Test deletion"  # Reason required for delete
        )

        assert log is not None
        assert log.action == AuditAction.DELETE

    def test_get_record_history(self, test_db, sample_user):
        """Test getting history for a specific record."""
        service = AuditService()

        # Create activity for a record using the model directly
        from app.models.audit import AuditLog
        AuditLog.log_change(
            session=test_db,
            table_name="products",
            record_id=100,
            action=AuditAction.INSERT,
            user=sample_user.id
        )
        test_db.commit()

        history = service.get_record_history(test_db, "products", 100)
        assert len(history) >= 1


# =============================================================================
# APPROVAL SERVICE EXTENDED TESTS
# =============================================================================

class TestApprovalServiceExtended:
    """Extended tests for ApprovalService."""

    def test_get_pending_approvals(self, test_db, sample_lot):
        """Test getting pending approvals."""
        service = ApprovalService()

        # Create draft test results
        for i in range(3):
            result = TestResult(
                lot_id=sample_lot.id,
                test_type=f"Test{i}",
                result_value="Pass",
                status=TestResultStatus.DRAFT
            )
            test_db.add(result)
        test_db.commit()

        pending = service.get_pending_approvals(test_db)
        assert len(pending) >= 3

    def test_approve_single_result(self, test_db, sample_lot, sample_user):
        """Test approving a single result."""
        service = ApprovalService()

        result = TestResult(
            lot_id=sample_lot.id,
            test_type="SingleTest",
            result_value="Pass",
            status=TestResultStatus.DRAFT
        )
        test_db.add(result)
        test_db.commit()

        approved = service.approve_test_result(test_db, result.id, sample_user.id)
        assert approved is not None
        assert approved.status == TestResultStatus.APPROVED
        assert approved.approved_by_id == sample_user.id

    def test_reject_result(self, test_db, sample_lot, sample_user):
        """Test rejecting a test result."""
        service = ApprovalService()

        result = TestResult(
            lot_id=sample_lot.id,
            test_type="RejectTest",
            result_value="Fail",
            status=TestResultStatus.DRAFT
        )
        test_db.add(result)
        test_db.commit()

        rejected = service.reject_test_result(
            test_db,
            result.id,
            sample_user.id,
            reason="Value out of specification"
        )
        assert rejected is not None
        # Result stays in DRAFT status when rejected
        assert rejected.status == TestResultStatus.DRAFT

    def test_approval_service_exists(self, test_db):
        """Test ApprovalService can be instantiated."""
        service = ApprovalService()
        assert service is not None


# =============================================================================
# PRODUCT SERVICE EXTENDED TESTS
# =============================================================================

class TestProductServiceExtended:
    """Extended tests for ProductService."""

    def test_get_product_with_specifications(self, test_db, sample_product_with_specs):
        """Test getting product with its specifications."""
        from app.models import Product
        product = test_db.query(Product).filter(Product.id == sample_product_with_specs.id).first()

        assert product is not None
        assert len(product.test_specifications) >= 1

    def test_get_brands(self, test_db, sample_product):
        """Test getting list of brands."""
        service = ProductService()

        brands = service.get_brands(test_db)
        assert len(brands) >= 1
        assert sample_product.brand in brands

    def test_product_service_exists(self, test_db):
        """Test ProductService can be instantiated."""
        service = ProductService()
        assert service is not None


# =============================================================================
# LOT SERVICE EXTENDED TESTS
# =============================================================================

class TestLotServiceExtended:
    """Extended tests for LotService."""

    def test_get_lots_by_status(self, test_db, sample_lot):
        """Test getting lots by status."""
        service = LotService()

        lots = service.get_lots_by_status(test_db, sample_lot.status)
        assert len(lots) >= 1

    def test_get_lots_by_product(self, test_db, sample_lot, sample_product):
        """Test getting lots for a product."""
        service = LotService()

        lots = service.get_lots_by_product(test_db, sample_product.id)
        assert len(lots) >= 1

    def test_get_expiring_lots(self, test_db, sample_lot):
        """Test getting expiring lots."""
        service = LotService()

        # Get lots expiring within 365 days
        lots = service.get_expiring_lots(test_db, 365)
        assert isinstance(lots, list)


# =============================================================================
# SAMPLE SERVICE TESTS
# =============================================================================

class TestSampleService:
    """Tests for SampleService."""

    def test_sample_service_exists(self, test_db):
        """Test SampleService can be instantiated."""
        service = SampleService()
        assert service is not None
