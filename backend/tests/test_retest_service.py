"""Tests for retest service and API endpoints."""

import pytest
from datetime import date, datetime

from app.models import Lot, Product, TestResult, User, LotProduct
from app.models.retest_request import RetestRequest, RetestItem
from app.models.enums import (
    UserRole, LotType, LotStatus, TestResultStatus, RetestStatus
)
from app.services.retest_service import retest_service


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def qc_manager(test_db):
    """Create a QC Manager user."""
    from app.services.user_service import UserService

    service = UserService()
    user = service.create_user(
        test_db,
        username="qcmanager",
        email="qc@example.com",
        password="testpass123",
        role=UserRole.QC_MANAGER,
    )
    # Set full_name after creation
    user.full_name = "QC Manager"
    test_db.commit()
    return user


@pytest.fixture
def lot_with_failing_tests(test_db, sample_product, qc_manager):
    """Create a lot with some failing test results."""
    lot = Lot(
        lot_number="FAIL-001",
        lot_type=LotType.STANDARD,
        reference_number="260129-001",
        mfg_date=date(2026, 1, 15),
        exp_date=date(2028, 1, 15),
        status=LotStatus.AWAITING_RESULTS,
        generate_coa=True,
    )
    test_db.add(lot)
    test_db.commit()

    # Link product to lot
    lot_product = LotProduct(lot_id=lot.id, product_id=sample_product.id)
    test_db.add(lot_product)
    test_db.commit()

    # Create test results - some passing, some failing
    test_results = [
        TestResult(
            lot_id=lot.id,
            test_type="Total Plate Count",
            result_value="15000",  # Failing - too high
            unit="CFU/g",
            test_date=date(2026, 1, 20),
            status=TestResultStatus.APPROVED,
        ),
        TestResult(
            lot_id=lot.id,
            test_type="E. coli",
            result_value="Positive",  # Failing
            unit="",
            test_date=date(2026, 1, 20),
            status=TestResultStatus.APPROVED,
        ),
        TestResult(
            lot_id=lot.id,
            test_type="Lead",
            result_value="0.05",  # Passing
            unit="ppm",
            test_date=date(2026, 1, 20),
            status=TestResultStatus.APPROVED,
        ),
    ]

    for result in test_results:
        test_db.add(result)

    test_db.commit()
    test_db.refresh(lot)
    return lot


# =============================================================================
# GENERATE RETEST REFERENCE TESTS
# =============================================================================

class TestGenerateRetestReference:
    """Tests for generating retest reference numbers."""

    def test_first_retest_generates_r1(self, test_db, sample_lot):
        """First retest for a lot should generate -R1 reference."""
        ref, num = retest_service.generate_retest_reference(test_db, sample_lot.id)

        assert ref == f"{sample_lot.reference_number}-R1"
        assert num == 1

    def test_second_retest_generates_r2(self, test_db, sample_lot, sample_user):
        """Second retest for same lot should generate -R2 reference."""
        # Create first retest request
        first_request = RetestRequest(
            lot_id=sample_lot.id,
            reference_number=f"{sample_lot.reference_number}-R1",
            retest_number=1,
            reason="First retest",
            requested_by_id=sample_user.id,
        )
        test_db.add(first_request)
        test_db.commit()

        # Generate second reference
        ref, num = retest_service.generate_retest_reference(test_db, sample_lot.id)

        assert ref == f"{sample_lot.reference_number}-R2"
        assert num == 2

    def test_invalid_lot_raises_error(self, test_db):
        """Invalid lot ID should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            retest_service.generate_retest_reference(test_db, 99999)

        assert "not found" in str(exc_info.value)


# =============================================================================
# CREATE RETEST REQUEST TESTS
# =============================================================================

class TestCreateRetestRequest:
    """Tests for creating retest requests."""

    def test_creates_retest_request_successfully(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should create a retest request with items."""
        lot = lot_with_failing_tests
        test_result_ids = [tr.id for tr in lot.test_results[:2]]  # First two failing tests

        request = retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=test_result_ids,
            reason="Suspected lab contamination",
            user_id=qc_manager.id,
        )

        assert request.id is not None
        assert request.reference_number == f"{lot.reference_number}-R1"
        assert request.retest_number == 1
        assert request.reason == "Suspected lab contamination"
        assert request.status == RetestStatus.PENDING
        assert request.requested_by_id == qc_manager.id
        assert len(request.items) == 2

    def test_snapshots_original_values(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should snapshot original test values in retest items."""
        lot = lot_with_failing_tests
        failing_test = lot.test_results[0]  # TPC = 15000

        request = retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[failing_test.id],
            reason="Retest needed",
            user_id=qc_manager.id,
        )

        item = request.items[0]
        assert item.original_value == "15000"
        assert item.test_result_id == failing_test.id

    def test_sets_lot_has_pending_retest_flag(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should set has_pending_retest flag on lot."""
        lot = lot_with_failing_tests
        assert lot.has_pending_retest is False  # Initially false

        retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[lot.test_results[0].id],
            reason="Test reason",
            user_id=qc_manager.id,
        )

        test_db.refresh(lot)
        assert lot.has_pending_retest is True

    def test_rejects_empty_test_result_ids(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should reject request with no test result IDs."""
        with pytest.raises(ValueError) as exc_info:
            retest_service.create_retest_request(
                db=test_db,
                lot_id=lot_with_failing_tests.id,
                test_result_ids=[],
                reason="Test reason",
                user_id=qc_manager.id,
            )

        assert "At least one test result" in str(exc_info.value)

    def test_rejects_invalid_lot_id(self, test_db, qc_manager):
        """Should reject request with invalid lot ID."""
        with pytest.raises(ValueError) as exc_info:
            retest_service.create_retest_request(
                db=test_db,
                lot_id=99999,
                test_result_ids=[1],
                reason="Test reason",
                user_id=qc_manager.id,
            )

        assert "Lot with ID" in str(exc_info.value)

    def test_rejects_invalid_test_result_id(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should reject request with invalid test result ID."""
        with pytest.raises(ValueError) as exc_info:
            retest_service.create_retest_request(
                db=test_db,
                lot_id=lot_with_failing_tests.id,
                test_result_ids=[99999],
                reason="Test reason",
                user_id=qc_manager.id,
            )

        assert "Test result with ID" in str(exc_info.value)

    def test_rejects_test_result_from_different_lot(
        self, test_db, lot_with_failing_tests, sample_lot, qc_manager
    ):
        """Should reject test result that belongs to a different lot."""
        # Create a test result for sample_lot
        other_test = TestResult(
            lot_id=sample_lot.id,
            test_type="Other Test",
            result_value="100",
            unit="units",
            test_date=date(2026, 1, 20),
            status=TestResultStatus.APPROVED,
        )
        test_db.add(other_test)
        test_db.commit()

        with pytest.raises(ValueError) as exc_info:
            retest_service.create_retest_request(
                db=test_db,
                lot_id=lot_with_failing_tests.id,
                test_result_ids=[other_test.id],
                reason="Test reason",
                user_id=qc_manager.id,
            )

        assert "does not belong to lot" in str(exc_info.value)


# =============================================================================
# GET RETEST REQUESTS TESTS
# =============================================================================

class TestGetRetestRequests:
    """Tests for retrieving retest requests."""

    def test_get_retests_for_lot(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should return all retest requests for a lot."""
        lot = lot_with_failing_tests

        # Create two retest requests
        retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[lot.test_results[0].id],
            reason="First retest",
            user_id=qc_manager.id,
        )
        retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[lot.test_results[1].id],
            reason="Second retest",
            user_id=qc_manager.id,
        )

        requests = retest_service.get_retests_for_lot(test_db, lot.id)

        assert len(requests) == 2
        # Should be ordered by created_at desc
        assert requests[0].reference_number == f"{lot.reference_number}-R2"
        assert requests[1].reference_number == f"{lot.reference_number}-R1"

    def test_get_pending_retests_for_lot(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should return only pending retest requests."""
        lot = lot_with_failing_tests

        # Create a retest and complete it
        request1 = retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[lot.test_results[0].id],
            reason="First retest",
            user_id=qc_manager.id,
        )
        retest_service.complete_retest(test_db, request1.id, qc_manager.id)

        # Create another pending retest
        retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[lot.test_results[1].id],
            reason="Second retest",
            user_id=qc_manager.id,
        )

        pending = retest_service.get_pending_retests_for_lot(test_db, lot.id)

        assert len(pending) == 1
        assert pending[0].status == RetestStatus.PENDING

    def test_get_retest_request_by_id(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should retrieve a specific retest request with related data."""
        lot = lot_with_failing_tests

        request = retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[lot.test_results[0].id],
            reason="Test reason",
            user_id=qc_manager.id,
        )

        retrieved = retest_service.get_retest_request(test_db, request.id)

        assert retrieved is not None
        assert retrieved.id == request.id
        assert retrieved.lot is not None
        assert retrieved.requested_by is not None
        assert len(retrieved.items) == 1

    def test_get_nonexistent_retest_returns_none(self, test_db):
        """Should return None for nonexistent retest request."""
        result = retest_service.get_retest_request(test_db, 99999)
        assert result is None


# =============================================================================
# AUTO-COMPLETE RETEST TESTS
# =============================================================================

class TestCheckAndCompleteRetest:
    """Tests for auto-completing retests when test values change."""

    def test_auto_completes_when_all_values_updated(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should auto-complete retest when all test values are updated."""
        lot = lot_with_failing_tests
        failing_test = lot.test_results[0]  # TPC = 15000

        # Create retest request
        request = retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[failing_test.id],
            reason="Suspected false positive",
            user_id=qc_manager.id,
        )

        assert request.status == RetestStatus.PENDING

        # Update the test result value
        failing_test.result_value = "5000"  # New value (different from original)
        test_db.commit()

        # Check for completion
        completed = retest_service.check_and_complete_retest(test_db, failing_test.id)

        assert completed is not None
        assert completed.status == RetestStatus.COMPLETED
        assert completed.completed_at is not None

        # Lot flag should be cleared
        test_db.refresh(lot)
        assert lot.has_pending_retest is False

    def test_does_not_complete_when_some_values_unchanged(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should not auto-complete when some test values are unchanged."""
        lot = lot_with_failing_tests
        test1 = lot.test_results[0]
        test2 = lot.test_results[1]

        # Create retest request for both tests
        request = retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[test1.id, test2.id],
            reason="Multiple tests need retest",
            user_id=qc_manager.id,
        )

        # Update only one test result
        test1.result_value = "5000"
        test_db.commit()

        # Check for completion - should not complete
        completed = retest_service.check_and_complete_retest(test_db, test1.id)

        assert completed is None
        test_db.refresh(request)
        assert request.status == RetestStatus.PENDING

    def test_keeps_pending_flag_when_other_retests_exist(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should keep lot flag when other pending retests exist."""
        lot = lot_with_failing_tests
        test1 = lot.test_results[0]
        test2 = lot.test_results[1]

        # Create two separate retest requests
        request1 = retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[test1.id],
            reason="First retest",
            user_id=qc_manager.id,
        )
        retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[test2.id],
            reason="Second retest",
            user_id=qc_manager.id,
        )

        # Update first test - completes first retest
        test1.result_value = "New Value 1"
        test_db.commit()
        retest_service.check_and_complete_retest(test_db, test1.id)

        # Lot should still have pending retest flag (second retest still pending)
        test_db.refresh(lot)
        assert lot.has_pending_retest is True


# =============================================================================
# MANUAL COMPLETE RETEST TESTS
# =============================================================================

class TestCompleteRetest:
    """Tests for manually completing retest requests."""

    def test_manually_completes_retest(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should manually mark retest as completed."""
        lot = lot_with_failing_tests

        request = retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[lot.test_results[0].id],
            reason="Test reason",
            user_id=qc_manager.id,
        )

        completed = retest_service.complete_retest(test_db, request.id, qc_manager.id)

        assert completed.status == RetestStatus.COMPLETED
        assert completed.completed_at is not None

        # Lot flag should be cleared
        test_db.refresh(lot)
        assert lot.has_pending_retest is False

    def test_rejects_completing_already_completed_retest(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should reject completing an already completed retest."""
        lot = lot_with_failing_tests

        request = retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[lot.test_results[0].id],
            reason="Test reason",
            user_id=qc_manager.id,
        )
        retest_service.complete_retest(test_db, request.id, qc_manager.id)

        with pytest.raises(ValueError) as exc_info:
            retest_service.complete_retest(test_db, request.id, qc_manager.id)

        assert "already completed" in str(exc_info.value)

    def test_rejects_completing_nonexistent_retest(self, test_db, qc_manager):
        """Should reject completing nonexistent retest."""
        with pytest.raises(ValueError) as exc_info:
            retest_service.complete_retest(test_db, 99999, qc_manager.id)

        assert "not found" in str(exc_info.value)


# =============================================================================
# PDF GENERATION TESTS
# =============================================================================

class TestGenerateRetestPdf:
    """Tests for PDF generation."""

    def test_generates_pdf_successfully(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should generate a valid PDF."""
        lot = lot_with_failing_tests

        request = retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[lot.test_results[0].id, lot.test_results[1].id],
            reason="Suspected lab contamination - values inconsistent with historical data",
            user_id=qc_manager.id,
        )

        pdf_bytes = retest_service.generate_retest_pdf(test_db, request.id)

        # Verify it's a valid PDF (starts with PDF header)
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 1000  # Should be substantial

    def test_rejects_pdf_for_nonexistent_request(self, test_db):
        """Should reject PDF generation for nonexistent request."""
        with pytest.raises(ValueError) as exc_info:
            retest_service.generate_retest_pdf(test_db, 99999)

        assert "not found" in str(exc_info.value)


# =============================================================================
# RETEST ITEMS FOR TEST RESULT TESTS
# =============================================================================

class TestGetRetestItemsForTestResult:
    """Tests for getting retest history for a specific test result."""

    def test_returns_retest_items_for_test_result(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """Should return all retest items for a specific test result."""
        lot = lot_with_failing_tests
        failing_test = lot.test_results[0]

        # Create two retest requests for the same test
        retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[failing_test.id],
            reason="First retest",
            user_id=qc_manager.id,
        )
        # Complete first retest to allow second
        failing_test.result_value = "Still failing"
        test_db.commit()

        retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[failing_test.id],
            reason="Second retest",
            user_id=qc_manager.id,
        )

        items = retest_service.get_retest_items_for_test_result(test_db, failing_test.id)

        assert len(items) == 2
        # Each item should have the retest request loaded
        assert all(item.retest_request is not None for item in items)

    def test_returns_empty_list_for_test_without_retests(
        self, test_db, lot_with_failing_tests
    ):
        """Should return empty list for test that was never retested."""
        lot = lot_with_failing_tests
        passing_test = lot.test_results[2]  # The passing Lead test

        items = retest_service.get_retest_items_for_test_result(test_db, passing_test.id)

        assert items == []


# =============================================================================
# AUDIT TRAIL RETEST CONTEXT TESTS
# =============================================================================

class TestAuditTrailRetestContext:
    """Tests for retest context in audit trail when updating test results."""

    def test_audit_includes_retest_context_when_updating_test_in_pending_retest(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """
        When updating a test result that is part of a pending retest,
        the audit entry should include retest context (request ID and reference number).
        """
        import json
        from app.models.audit import AuditLog
        from app.models.enums import AuditAction

        lot = lot_with_failing_tests
        failing_test = lot.test_results[0]  # TPC = 15000

        # Ensure test is in draft status so it can be updated
        failing_test.status = TestResultStatus.DRAFT
        test_db.commit()

        # Create a pending retest request
        request = retest_service.create_retest_request(
            db=test_db,
            lot_id=lot.id,
            test_result_ids=[failing_test.id],
            reason="Testing audit context",
            user_id=qc_manager.id,
        )

        # Now simulate the update via the endpoint logic
        # (We replicate what the endpoint does to test the audit context)
        from app.models.retest_request import RetestRequest, RetestItem
        from app.models.enums import RetestStatus
        from app.services.audit_service import AuditService

        # Check for pending retest
        pending_retest_item = (
            test_db.query(RetestItem)
            .join(RetestRequest)
            .filter(
                RetestItem.test_result_id == failing_test.id,
                RetestRequest.status == RetestStatus.PENDING,
            )
            .first()
        )

        assert pending_retest_item is not None, "Should have a pending retest item"

        # Prepare audit values
        old_values = {"result_value": failing_test.result_value}
        new_values = {"result_value": "5000"}  # New value

        # Add retest context (this is what the endpoint does)
        retest_ref = pending_retest_item.retest_request.reference_number
        new_values["retest_context"] = {
            "retest_request_id": pending_retest_item.retest_request_id,
            "reference_number": retest_ref,
        }
        audit_reason = f"Retest result entry ({retest_ref}): {failing_test.test_type}"

        # Log the audit entry
        audit_service = AuditService()
        audit_service.log_action(
            db=test_db,
            table_name="test_results",
            record_id=failing_test.id,
            action=AuditAction.UPDATE,
            user_id=qc_manager.id,
            old_values=old_values,
            new_values=new_values,
            reason=audit_reason,
        )
        test_db.commit()

        # Verify the audit entry
        audit_entry = (
            test_db.query(AuditLog)
            .filter(
                AuditLog.table_name == "test_results",
                AuditLog.record_id == failing_test.id,
                AuditLog.action == AuditAction.UPDATE,
            )
            .order_by(AuditLog.timestamp.desc())
            .first()
        )

        assert audit_entry is not None
        assert f"Retest result entry ({request.reference_number})" in audit_entry.reason

        new_values_dict = json.loads(audit_entry.new_values)
        assert "retest_context" in new_values_dict
        assert new_values_dict["retest_context"]["retest_request_id"] == request.id
        assert new_values_dict["retest_context"]["reference_number"] == request.reference_number

    def test_audit_does_not_include_retest_context_for_normal_update(
        self, test_db, lot_with_failing_tests, qc_manager
    ):
        """
        When updating a test result that is NOT part of a pending retest,
        the audit entry should NOT include retest context.
        """
        import json
        from app.models.audit import AuditLog
        from app.models.enums import AuditAction
        from app.models.retest_request import RetestRequest, RetestItem
        from app.models.enums import RetestStatus
        from app.services.audit_service import AuditService

        lot = lot_with_failing_tests
        passing_test = lot.test_results[2]  # Lead test - not in any retest

        # Ensure test is in draft status
        passing_test.status = TestResultStatus.DRAFT
        test_db.commit()

        # Check for pending retest (should be None)
        pending_retest_item = (
            test_db.query(RetestItem)
            .join(RetestRequest)
            .filter(
                RetestItem.test_result_id == passing_test.id,
                RetestRequest.status == RetestStatus.PENDING,
            )
            .first()
        )

        assert pending_retest_item is None, "Should NOT have a pending retest item"

        # Prepare audit values (no retest context)
        old_values = {"result_value": passing_test.result_value}
        new_values = {"result_value": "0.03"}  # New value
        audit_reason = f"Test result update: {passing_test.test_type}"

        # Log the audit entry
        audit_service = AuditService()
        audit_service.log_action(
            db=test_db,
            table_name="test_results",
            record_id=passing_test.id,
            action=AuditAction.UPDATE,
            user_id=qc_manager.id,
            old_values=old_values,
            new_values=new_values,
            reason=audit_reason,
        )
        test_db.commit()

        # Verify the audit entry
        audit_entry = (
            test_db.query(AuditLog)
            .filter(
                AuditLog.table_name == "test_results",
                AuditLog.record_id == passing_test.id,
                AuditLog.action == AuditAction.UPDATE,
            )
            .order_by(AuditLog.timestamp.desc())
            .first()
        )

        assert audit_entry is not None
        assert "Retest result entry" not in audit_entry.reason
        assert "Test result update:" in audit_entry.reason

        new_values_dict = json.loads(audit_entry.new_values)
        assert "retest_context" not in new_values_dict
