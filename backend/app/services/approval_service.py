"""Approval service for managing approval workflows."""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func as db_func
from app.models.test_result import TestResult
from app.models.lot import Lot
from app.models.user import User
from app.models.enums import TestResultStatus, LotStatus, UserRole, AuditAction
from app.models.audit import AuditLog
from app.services.base import BaseService
from app.utils.logger import logger


class ApprovalService(BaseService[TestResult]):
    """
    Service for managing approval workflows.

    Provides functionality for:
    - Test result approval/rejection
    - Lot approval workflows
    - Multi-level approval chains
    - Approval history tracking
    """

    def __init__(self):
        """Initialize approval service."""
        super().__init__(TestResult)

    def approve_test_result(
        self,
        db: Session,
        test_result_id: int,
        approver_user_id: int,
        notes: Optional[str] = None,
        audit_metadata: Optional[Dict[str, Any]] = None,
    ) -> TestResult:
        """
        Approve a test result.

        Args:
            db: Database session
            test_result_id: ID of test result to approve
            approver_user_id: ID of user approving the result
            notes: Optional approval notes
            audit_metadata: Additional metadata for audit

        Returns:
            Approved test result

        Raises:
            ValueError: If user lacks permission or result cannot be approved
        """
        # Get test result
        test_result = self.get(db, test_result_id)
        if not test_result:
            raise ValueError(f"Test result with ID {test_result_id} not found")

        # Get approver
        approver = db.query(User).filter(User.id == approver_user_id).first()
        if not approver:
            raise ValueError("Approver user not found")

        # Check permissions
        if not approver.can_approve:
            raise ValueError(
                f"User {approver.username} does not have approval permissions"
            )

        # Validate current status
        if test_result.status == TestResultStatus.APPROVED:
            raise ValueError("Test result is already approved")

        # Perform approval
        old_values = test_result.to_dict()

        test_result.status = TestResultStatus.APPROVED
        test_result.approved_by_id = approver_user_id
        test_result.approved_at = datetime.utcnow()

        if notes:
            existing_notes = test_result.notes or ""
            test_result.notes = f"Approved: {notes}\n{existing_notes}".strip()

        db.flush()

        # Create audit log
        self._log_audit(
            db=db,
            action=AuditAction.APPROVE,
            record_id=test_result.id,
            old_values=old_values,
            new_values=test_result.to_dict(),
            user_id=approver_user_id,
            metadata=audit_metadata,
        )

        db.commit()
        db.refresh(test_result)

        logger.info(
            f"Test result {test_result_id} approved by user {approver.username}"
        )

        # Check if all test results for the lot are approved
        self._check_lot_approval_status(db, test_result.lot_id, approver_user_id)
        
        # Refresh to get updated lot status
        db.refresh(test_result)

        return test_result

    def reject_test_result(
        self,
        db: Session,
        test_result_id: int,
        rejector_user_id: int,
        reason: str,
        audit_metadata: Optional[Dict[str, Any]] = None,
    ) -> TestResult:
        """
        Reject a test result and revert to draft.

        Args:
            db: Database session
            test_result_id: ID of test result to reject
            rejector_user_id: ID of user rejecting the result
            reason: Reason for rejection (required)
            audit_metadata: Additional metadata for audit

        Returns:
            Rejected test result

        Raises:
            ValueError: If user lacks permission or reason not provided
        """
        if not reason:
            raise ValueError("Reason is required for rejection")

        # Get test result
        test_result = self.get(db, test_result_id)
        if not test_result:
            raise ValueError(f"Test result with ID {test_result_id} not found")

        # Get rejector
        rejector = db.query(User).filter(User.id == rejector_user_id).first()
        if not rejector:
            raise ValueError("Rejector user not found")

        # Check permissions
        if not rejector.can_approve:
            raise ValueError(
                f"User {rejector.username} does not have rejection permissions"
            )

        # Perform rejection
        old_values = test_result.to_dict()

        test_result.status = TestResultStatus.DRAFT
        test_result.approved_by_id = None
        test_result.approved_at = None

        # Add rejection note
        existing_notes = test_result.notes or ""
        test_result.notes = (
            f"Rejected by {rejector.username}: {reason}\n{existing_notes}".strip()
        )

        db.flush()

        # Create audit log
        self._log_audit(
            db=db,
            action=AuditAction.REJECT,
            record_id=test_result.id,
            old_values=old_values,
            new_values=test_result.to_dict(),
            user_id=rejector_user_id,
            reason=reason,
            metadata=audit_metadata,
        )

        db.commit()
        db.refresh(test_result)

        logger.info(
            f"Test result {test_result_id} rejected by user {rejector.username}: {reason}"
        )

        return test_result

    def bulk_approve_results(
        self,
        db: Session,
        test_result_ids: List[int],
        approver_user_id: int,
        notes: Optional[str] = None,
    ) -> List[TestResult]:
        """
        Approve multiple test results in a single transaction.

        Args:
            db: Database session
            test_result_ids: List of test result IDs to approve
            approver_user_id: ID of user approving the results
            notes: Optional approval notes

        Returns:
            List of approved test results
        """
        approved_results = []

        try:
            for test_result_id in test_result_ids:
                try:
                    result = self.approve_test_result(
                        db=db,
                        test_result_id=test_result_id,
                        approver_user_id=approver_user_id,
                        notes=notes,
                    )
                    approved_results.append(result)
                except ValueError as e:
                    logger.warning(
                        f"Could not approve test result {test_result_id}: {e}"
                    )
                    # Continue with other approvals

            # Update lot status based on test completeness for each affected lot
            lot_ids = set()
            for result in approved_results:
                if result.lot_id:
                    lot_ids.add(result.lot_id)
            
            for lot_id in lot_ids:
                self._update_lot_status_from_completeness(db, lot_id)

            logger.info(f"Bulk approved {len(approved_results)} test results")
            return approved_results

        except Exception as e:
            db.rollback()
            logger.error(f"Error in bulk approval: {e}")
            raise

    def get_pending_approvals(
        self,
        db: Session,
        approver_user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get test results pending approval.

        Args:
            db: Database session
            approver_user_id: Optional filter by approver capabilities
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of pending approval items with details
        """
        # Check if filtering by approver
        if approver_user_id:
            approver = db.query(User).filter(User.id == approver_user_id).first()
            if not approver or not approver.can_approve:
                return []

        # Get pending test results
        query = (
            db.query(TestResult, Lot)
            .join(Lot)
            .filter(TestResult.status == TestResultStatus.DRAFT)
        )

        results = query.offset(skip).limit(limit).all()

        pending_approvals = []
        for test_result, lot in results:
            pending_approvals.append(
                {
                    "test_result_id": test_result.id,
                    "lot_number": lot.lot_number,
                    "lot_type": lot.lot_type.value,
                    "test_type": test_result.test_type,
                    "test_date": test_result.test_date,
                    "result_value": test_result.result_value,
                    "confidence_score": (
                        float(test_result.confidence_score)
                        if test_result.confidence_score
                        else None
                    ),
                    "needs_manual_review": test_result.needs_review,
                }
            )

        return pending_approvals

    def get_approval_history(
        self,
        db: Session,
        user_id: Optional[int] = None,
        days_back: int = 30,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get approval history.

        Args:
            db: Database session
            user_id: Optional filter by approver
            days_back: Number of days to look back
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of approval history items
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)

        query = db.query(AuditLog).filter(
            AuditLog.table_name == "test_results",
            AuditLog.action.in_([AuditAction.APPROVE, AuditAction.REJECT]),
            AuditLog.timestamp >= cutoff_date,
        )

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        results = (
            query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
        )

        history = []
        for audit in results:
            # Get related test result if it still exists
            test_result = (
                db.query(TestResult).filter(TestResult.id == audit.record_id).first()
            )

            history_item = {
                "audit_id": audit.id,
                "action": audit.action.value,
                "timestamp": audit.timestamp,
                "user_id": audit.user_id,
                "user": audit.user.username if audit.user else None,
                "reason": audit.reason,
                "test_result_id": audit.record_id,
            }

            if test_result:
                history_item.update(
                    {
                        "lot_number": test_result.lot.lot_number,
                        "test_type": test_result.test_type,
                        "current_status": test_result.status.value,
                    }
                )

            history.append(history_item)

        return history

    def _check_lot_approval_status(
        self, db: Session, lot_id: int, user_id: int
    ) -> None:
        """
        Check if all test results for a lot are approved and update lot status.

        Args:
            db: Database session
            lot_id: ID of the lot to check
            user_id: ID of user triggering the check
        """
        # Get all test results for the lot
        test_results = db.query(TestResult).filter(TestResult.lot_id == lot_id).all()

        if not test_results:
            return

        # Check if all existing tests are approved
        all_approved = all(
            tr.status == TestResultStatus.APPROVED for tr in test_results
        )

        if not all_approved:
            # Don't change status if not all tests are approved
            return
            
        # Check test completeness
        completeness = self.check_test_completeness(db, lot_id)
        
        # Get the lot
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if not lot or lot.status not in [LotStatus.AWAITING_RESULTS, LotStatus.UNDER_REVIEW, LotStatus.PARTIAL_RESULTS]:
            if lot:
                logger.info(
                    f"Lot {lot.lot_number} not updated - current status {lot.status.value} "
                    f"not in [AWAITING_RESULTS, UNDER_REVIEW, PARTIAL_RESULTS]"
                )
            return
        
        old_status = lot.status
        
        # Determine new status based on completeness and test results
        if not completeness["is_complete"]:
            # Missing required tests - set to PARTIAL_RESULTS
            lot.status = LotStatus.PARTIAL_RESULTS
            reason = f"Partial results - missing required tests: {', '.join(completeness['missing_required'])}"
        else:
            # All required tests present - set to UNDER_REVIEW for manual approval
            # Manual review is required even if all tests pass
            lot.status = LotStatus.UNDER_REVIEW
            all_passing = self._check_all_tests_passing(test_results)
            if all_passing:
                reason = "All required tests present and passing - awaiting manual QC review"
            else:
                reason = "All required tests present but some failing specifications - awaiting manual QC review"
        
        # Log the change if status changed
        if lot.status != old_status:
            AuditLog.log_change(
                session=db,
                table_name="lots",
                record_id=lot.id,
                action=AuditAction.UPDATE,
                old_values={"status": old_status.value},
                new_values={"status": lot.status.value},
                user=user_id,
                reason=reason,
            )

            logger.info(
                f"Lot {lot.lot_number} automatically updated from {old_status.value} to {lot.status.value} status - {reason}"
            )
            
            # Commit the lot status change
            db.commit()
            db.refresh(lot)

    def _check_all_tests_passing(self, test_results: List[TestResult]) -> bool:
        """
        Check if all test results are passing their specifications.
        
        Args:
            test_results: List of test results to check
            
        Returns:
            True if all tests pass, False if any test fails
        """
        for result in test_results:
            if not self._check_test_passes_spec(result):
                return False
        return True
    
    def _check_test_passes_spec(self, result: TestResult) -> bool:
        """
        Check if a single test result passes its specification.
        
        Args:
            result: Test result to check
            
        Returns:
            True if test passes, False if it fails
        """
        # If no specification, assume pass
        if not result.specification:
            return True
        
        # Get the specification and result value
        spec = result.specification.strip().lower()
        value = result.result_value.strip().lower() if result.result_value else ""
        
        # Handle common "pass" values
        if value in ["nd", "not detected", "absent", "negative", "none", "nil"]:
            return True
        
        # Handle "< X" specifications
        if spec.startswith("<"):
            # If result also starts with "<", it's passing
            if value.startswith("<"):
                return True
            # Try to extract numeric values
            try:
                spec_limit = float(spec[1:].strip())
                if value.replace(".", "").replace("-", "").isdigit():
                    result_val = float(value)
                    return result_val < spec_limit
            except:
                pass
        
        # Handle "> X" specifications
        if spec.startswith(">"):
            # If result also starts with ">", it's passing
            if value.startswith(">"):
                return True
            # Try to extract numeric values
            try:
                spec_limit = float(spec[1:].strip())
                if value.replace(".", "").replace("-", "").isdigit():
                    result_val = float(value)
                    return result_val > spec_limit
            except:
                pass
        
        # Handle range specifications (e.g., "10-20")
        if "-" in spec and not spec.startswith("-"):
            try:
                parts = spec.split("-")
                if len(parts) == 2:
                    min_val = float(parts[0].strip())
                    max_val = float(parts[1].strip())
                    if value.replace(".", "").replace("-", "").isdigit():
                        result_val = float(value)
                        return min_val <= result_val <= max_val
            except:
                pass
        
        # Handle exact match specifications
        if spec == value:
            return True
        
        # Handle "absent" specifications
        if "absent" in spec and value in ["nd", "not detected", "absent", "negative"]:
            return True
        
        # Handle "negative" specifications
        if "negative" in spec and value in ["negative", "nd", "not detected", "absent"]:
            return True
        
        # Default: if we can't determine pass/fail, assume pass
        # This prevents false rejections for complex specifications
        logger.warning(
            f"Could not determine pass/fail for test '{result.test_type}' "
            f"with spec '{result.specification}' and value '{result.result_value}'. "
            f"Assuming pass."
        )
        return True

    def get_approval_metrics(
        self,
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get approval workflow metrics.

        Args:
            db: Database session
            start_date: Start date for metrics
            end_date: End date for metrics

        Returns:
            Dictionary with approval metrics
        """
        query = db.query(TestResult)

        if start_date:
            query = query.filter(TestResult.created_at >= start_date)

        if end_date:
            query = query.filter(TestResult.created_at <= end_date)

        total_results = query.count()
        approved_results = query.filter(
            TestResult.status == TestResultStatus.APPROVED
        ).count()

        # Calculate average approval time
        approved_with_time = query.filter(
            TestResult.status == TestResultStatus.APPROVED,
            TestResult.approved_at.isnot(None),
        ).all()

        if approved_with_time:
            total_hours = sum(
                (tr.approved_at - tr.created_at).total_seconds() / 3600
                for tr in approved_with_time
            )
            avg_approval_hours = total_hours / len(approved_with_time)
        else:
            avg_approval_hours = 0

        # Get approver statistics
        approver_stats = (
            db.query(
                User.username, db.func.count(TestResult.id).label("approval_count")
            )
            .join(TestResult, TestResult.approved_by_id == User.id)
            .filter(TestResult.status == TestResultStatus.APPROVED)
            .group_by(User.username)
            .all()
        )

        return {
            "total_test_results": total_results,
            "approved_results": approved_results,
            "pending_approval": query.filter(
                TestResult.status == TestResultStatus.DRAFT
            ).count(),
            "approval_rate": (
                (approved_results / total_results * 100) if total_results > 0 else 0
            ),
            "average_approval_time_hours": round(avg_approval_hours, 2),
            "approvers": [
                {"username": username, "approval_count": count}
                for username, count in approver_stats
            ],
        }

    def _update_lot_status_from_completeness(self, db: Session, lot_id: int):
        """
        Update lot status based on test completeness after test results are approved.
        
        Args:
            db: Database session
            lot_id: ID of the lot to check
        """
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if not lot:
            return
            
        # Only update lots in PENDING status
        if lot.status != LotStatus.AWAITING_RESULTS:
            return
            
        # Check test completeness
        completeness = self.check_test_completeness(db, lot_id)
        
        # If we have some results but missing required tests, set to PARTIAL_RESULTS
        if lot.test_results and not completeness["is_complete"]:
            old_status = lot.status
            lot.status = LotStatus.PARTIAL_RESULTS
            
            # Log the status change
            self._log_audit(
                db=db,
                action="update",
                record_id=lot.id,
                old_values={"status": old_status.value},
                new_values={"status": lot.status.value},
                reason="Automatic update - partial test results received"
            )
            
            logger.info(
                f"Lot {lot.lot_number} updated to PARTIAL_RESULTS - "
                f"missing {len(completeness['missing_required'])} required tests"
            )

    def check_test_completeness(
        self,
        db: Session,
        lot_id: int
    ) -> Dict[str, Any]:
        """
        Check if lot has all required tests.
        
        Returns:
            {
                "is_complete": bool,
                "missing_required": List[str],
                "present_optional": List[str],
                "status_recommendation": LotStatus
            }
        """
        from app.services.product_service import ProductService
        
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if not lot or not lot.lot_products:
            return {
                "is_complete": False,
                "missing_required": [],
                "present_optional": [],
                "status_recommendation": LotStatus.AWAITING_RESULTS
            }
        
        # Get primary product (for now, use first product)
        primary_product = lot.lot_products[0].product
        
        # Get completed test types from test results
        completed_tests = [
            tr.test_type for tr in lot.test_results
        ]
        
        # Get missing required tests
        product_service = ProductService()
        missing_specs = product_service.get_missing_required_tests(
            db, primary_product.id, completed_tests
        )
        
        missing_required = [
            spec.lab_test_type.test_name for spec in missing_specs
        ]
        
        # Get optional tests that were performed
        present_optional = []
        for test_result in lot.test_results:
            spec = primary_product.get_specification_for_test(test_result.test_type)
            if spec and not spec.is_required:
                present_optional.append(test_result.test_type)
        
        # Determine status recommendation
        if not lot.test_results:
            status_recommendation = LotStatus.AWAITING_RESULTS
        elif missing_required:
            status_recommendation = LotStatus.PARTIAL_RESULTS
        else:
            status_recommendation = LotStatus.UNDER_REVIEW
        
        return {
            "is_complete": len(missing_required) == 0,
            "missing_required": missing_required,
            "present_optional": present_optional,
            "status_recommendation": status_recommendation
        }

    def update_lot_status_after_results(
        self,
        db: Session,
        lot_id: int
    ) -> None:
        """
        Update lot status based on test completeness.
        
        This should be called after:
        - PDF parsing creates test results
        - Manual test result entry
        - Test result deletion
        """
        check = self.check_test_completeness(db, lot_id)
        
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if lot and lot.status == LotStatus.AWAITING_RESULTS:
            old_status = lot.status
            lot.status = check["status_recommendation"]
            
            # Log the change
            self._log_audit(
                db=db,
                action=AuditAction.UPDATE,
                record_id=lot.id,
                old_values={"status": old_status.value},
                new_values={"status": lot.status.value},
                reason=f"Auto-update based on test completeness. Missing: {check['missing_required']}"
            )
            
            db.commit()
            
            logger.info(
                f"Updated lot {lot.lot_number} from {old_status.value} to {lot.status.value}. "
                f"Missing tests: {check['missing_required']}"
            )

    def validate_lot_for_approval(
        self,
        db: Session,
        lot_id: int
    ) -> Dict[str, Any]:
        """
        Comprehensive validation before lot approval.
        
        Returns:
            {
                "can_approve": bool,
                "issues": List[str],
                "warnings": List[str]
            }
        """
        issues = []
        warnings = []
        
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if not lot:
            return {
                "can_approve": False,
                "issues": ["Lot not found"],
                "warnings": []
            }
        
        # Check test completeness
        completeness = self.check_test_completeness(db, lot_id)
        if not completeness["is_complete"]:
            issues.append(
                f"Missing required tests: {', '.join(completeness['missing_required'])}"
            )
        
        # Check if all test results are approved
        unapproved_tests = [
            tr.test_type for tr in lot.test_results 
            if tr.status != TestResultStatus.APPROVED
        ]
        if unapproved_tests:
            issues.append(
                f"Unapproved test results: {', '.join(unapproved_tests)}"
            )
        
        # Check if any tests fail specifications
        from app.services.product_service import ProductService
        product_service = ProductService()
        
        if lot.lot_products:
            product = lot.lot_products[0].product
            
            for test_result in lot.test_results:
                validation = product_service.validate_test_result(
                    db,
                    product.id,
                    test_result.test_type,
                    test_result.result_value
                )
                
                if not validation["passes"]:
                    issues.append(
                        f"Test '{test_result.test_type}' fails specification: "
                        f"{test_result.result_value} (spec: {validation['specification']})"
                    )
        
        # Warnings for optional tests
        if completeness["present_optional"]:
            warnings.append(
                f"Optional tests performed: {', '.join(completeness['present_optional'])}"
            )
        
        return {
            "can_approve": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }
