"""Sample service for managing lab sample creation and tracking."""

from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.lot import Lot
from app.models.test_result import TestResult
from app.models.enums import LotStatus, TestResultStatus
from app.services.base import BaseService
from app.services.lot_service import LotService
from app.utils.logger import logger


class SampleService(BaseService[TestResult]):
    """
    Service for managing laboratory samples and test results.

    Provides functionality for:
    - Creating samples with reference numbers
    - Managing test results
    - Sample status tracking
    - Lab communication
    """

    def __init__(self):
        """Initialize sample service."""
        super().__init__(TestResult)
        self.lot_service = LotService()

    def create_sample_for_lot(
        self,
        db: Session,
        lot_id: int,
        test_types: List[str],
        user_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Tuple[Lot, List[TestResult]]:
        """
        Create sample for a lot with specified test types.

        Args:
            db: Database session
            lot_id: ID of the lot to sample
            test_types: List of test types to perform
            user_id: ID of user creating the sample
            notes: Optional notes for the sample

        Returns:
            Tuple of (lot with reference number, created test results)

        Raises:
            ValueError: If lot not found or already has samples
        """
        # Get lot
        lot = self.lot_service.get(db, lot_id)
        if not lot:
            raise ValueError(f"Lot with ID {lot_id} not found")

        # Check if lot already has test results
        existing_tests = (
            db.query(TestResult).filter(TestResult.lot_id == lot_id).count()
        )

        if existing_tests > 0:
            raise ValueError(f"Lot {lot.lot_number} already has test results")

        # Generate reference number if not present
        if not lot.reference_number:
            lot.reference_number = self.lot_service.generate_reference_number(db)
            db.add(lot)

        # Create test result records
        test_results = []
        for test_type in test_types:
            test_result = TestResult(
                lot_id=lot_id,
                test_type=test_type,
                status=TestResultStatus.DRAFT,
                notes=notes,
            )
            db.add(test_result)
            test_results.append(test_result)

        try:
            db.flush()

            # Log audit for each test result
            for test_result in test_results:
                self._log_audit(
                    db=db,
                    action="insert",
                    record_id=test_result.id,
                    new_values=test_result.to_dict(),
                    user_id=user_id,
                )

            db.commit()
            db.refresh(lot)

            logger.info(
                f"Created {len(test_results)} test samples for lot {lot.lot_number} "
                f"with reference {lot.reference_number}"
            )

            return lot, test_results

        except IntegrityError as e:
            db.rollback()
            logger.error(f"Error creating samples: {e}")
            raise

    def update_test_result(
        self,
        db: Session,
        test_result_id: int,
        result_data: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> TestResult:
        """
        Update test result with validation.

        Args:
            db: Database session
            test_result_id: ID of test result to update
            result_data: Dictionary with result data
            user_id: ID of user updating the result

        Returns:
            Updated test result

        Raises:
            ValueError: If test result not found or update invalid
        """
        test_result = self.get(db, test_result_id)
        if not test_result:
            raise ValueError(f"Test result with ID {test_result_id} not found")

        # Validate status transitions
        if "status" in result_data:
            new_status = result_data["status"]
            if isinstance(new_status, str):
                new_status = TestResultStatus(new_status)

            # Check valid transition
            current_status = test_result.status
            valid_transitions = {
                TestResultStatus.DRAFT: [TestResultStatus.REVIEWED],
                TestResultStatus.REVIEWED: [
                    TestResultStatus.APPROVED,
                    TestResultStatus.DRAFT,
                ],
                TestResultStatus.APPROVED: [
                    TestResultStatus.DRAFT
                ],  # Only admin can revert
            }

            if (
                new_status != current_status
                and new_status not in valid_transitions.get(current_status, [])
            ):
                raise ValueError(
                    f"Invalid status transition from {current_status.value} to {new_status.value}"
                )

        # Update test result
        return self.update(
            db=db, db_obj=test_result, obj_in=result_data, user_id=user_id
        )

    def get_pending_results(
        self, db: Session, skip: int = 0, limit: int = 100
    ) -> List[TestResult]:
        """
        Get test results pending review.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of pending test results
        """
        return (
            db.query(TestResult)
            .filter(TestResult.status == TestResultStatus.DRAFT)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_results_by_lot(self, db: Session, lot_id: int) -> List[TestResult]:
        """
        Get all test results for a lot.

        Args:
            db: Database session
            lot_id: Lot ID

        Returns:
            List of test results
        """
        return (
            db.query(TestResult)
            .filter(TestResult.lot_id == lot_id)
            .order_by(TestResult.test_type)
            .all()
        )

    def get_results_by_reference(
        self, db: Session, reference_number: str
    ) -> List[TestResult]:
        """
        Get test results by lot reference number.

        Args:
            db: Database session
            reference_number: Lot reference number

        Returns:
            List of test results
        """
        lot = (
            db.query(Lot)
            .filter(Lot.reference_number == reference_number.upper())
            .first()
        )

        if not lot:
            return []

        return self.get_results_by_lot(db, lot.id)

    def bulk_update_results(
        self, db: Session, updates: List[Dict[str, Any]], user_id: Optional[int] = None
    ) -> List[TestResult]:
        """
        Update multiple test results in a single transaction.

        Args:
            db: Database session
            updates: List of dictionaries with 'id' and update data
            user_id: ID of user making updates

        Returns:
            List of updated test results
        """
        updated_results = []

        try:
            for update in updates:
                test_result_id = update.pop("id")
                test_result = self.get(db, test_result_id)

                if not test_result:
                    logger.warning(f"Test result {test_result_id} not found, skipping")
                    continue

                # Update each result
                for key, value in update.items():
                    setattr(test_result, key, value)

                updated_results.append(test_result)

            db.flush()

            # Log audit for bulk update
            for result in updated_results:
                self._log_audit(
                    db=db,
                    action="update",
                    record_id=result.id,
                    new_values=result.to_dict(),
                    user_id=user_id,
                )

            db.commit()

            logger.info(f"Bulk updated {len(updated_results)} test results")
            return updated_results

        except Exception as e:
            db.rollback()
            logger.error(f"Error in bulk update: {e}")
            raise

    def get_lab_queue(
        self,
        db: Session,
        test_date_from: Optional[datetime] = None,
        test_date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get samples in lab queue with lot information.

        Args:
            db: Database session
            test_date_from: Filter by test date from
            test_date_to: Filter by test date to
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of sample queue items with lot details
        """
        query = (
            db.query(TestResult, Lot)
            .join(Lot)
            .filter(TestResult.status == TestResultStatus.DRAFT)
        )

        if test_date_from:
            query = query.filter(TestResult.test_date >= test_date_from)

        if test_date_to:
            query = query.filter(TestResult.test_date <= test_date_to)

        results = query.offset(skip).limit(limit).all()

        lab_queue = []
        for test_result, lot in results:
            lab_queue.append(
                {
                    "test_result_id": test_result.id,
                    "lot_number": lot.lot_number,
                    "reference_number": lot.reference_number,
                    "test_type": test_result.test_type,
                    "test_date": test_result.test_date,
                    "status": test_result.status.value,
                    "products": [p.get_full_name() for p in lot.products],
                }
            )

        return lab_queue

    def calculate_completion_stats(
        self, db: Session, lot_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate test completion statistics.

        Args:
            db: Database session
            lot_id: Optional lot ID to filter by

        Returns:
            Dictionary with completion statistics
        """
        query = db.query(TestResult)

        if lot_id:
            query = query.filter(TestResult.lot_id == lot_id)

        total_tests = query.count()

        if total_tests == 0:
            return {
                "total_tests": 0,
                "draft": 0,
                "reviewed": 0,
                "approved": 0,
                "completion_percentage": 0.0,
            }

        draft_count = query.filter(TestResult.status == TestResultStatus.DRAFT).count()
        reviewed_count = query.filter(
            TestResult.status == TestResultStatus.REVIEWED
        ).count()
        approved_count = query.filter(
            TestResult.status == TestResultStatus.APPROVED
        ).count()

        return {
            "total_tests": total_tests,
            "draft": draft_count,
            "reviewed": reviewed_count,
            "approved": approved_count,
            "completion_percentage": (approved_count / total_tests) * 100,
        }


# Add missing import
from typing import Tuple
