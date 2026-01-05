"""Release service for managing COA release workflow."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_

from app.models.coa_release import COARelease
from app.models.email_history import EmailHistory
from app.models.lot import Lot
from app.models.test_result import TestResult
from app.models.user import User
from app.models.enums import COAReleaseStatus, LotStatus, AuditAction
from app.services.base import BaseService
from app.utils.logger import logger


class ReleaseService(BaseService[COARelease]):
    """
    Service for managing COA release workflow.

    Provides functionality for:
    - Viewing release queue
    - Saving draft data (customer, notes)
    - Approving releases
    - Sending back to QC review
    - Email history tracking
    """

    def __init__(self):
        """Initialize release service."""
        super().__init__(COARelease)

    def get_queue(self, db: Session) -> List[COARelease]:
        """
        Get all COA releases awaiting release.

        Args:
            db: Database session

        Returns:
            List of COARelease with status=AWAITING_RELEASE, ordered by created_at
        """
        return (
            db.query(COARelease)
            .options(
                joinedload(COARelease.lot),
                joinedload(COARelease.product),
                joinedload(COARelease.customer),
            )
            .filter(COARelease.status == COAReleaseStatus.AWAITING_RELEASE)
            .order_by(COARelease.created_at.desc())
            .all()
        )

    def get_by_id(self, db: Session, id: int) -> Optional[COARelease]:
        """
        Get a single COARelease by ID with all relations.

        Args:
            db: Database session
            id: COARelease ID

        Returns:
            COARelease with lot, product, customer relations, or None
        """
        return (
            db.query(COARelease)
            .options(
                joinedload(COARelease.lot),
                joinedload(COARelease.product),
                joinedload(COARelease.customer),
                joinedload(COARelease.released_by),
                joinedload(COARelease.email_history).joinedload(EmailHistory.sent_by),
            )
            .filter(COARelease.id == id)
            .first()
        )

    def get_source_pdfs(self, db: Session, lot_id: int) -> List[str]:
        """
        Get unique source PDF filenames from TestResult for a lot.

        Args:
            db: Database session
            lot_id: Lot ID

        Returns:
            List of unique PDF source filenames
        """
        results = (
            db.query(TestResult.pdf_source)
            .filter(
                TestResult.lot_id == lot_id,
                TestResult.pdf_source.isnot(None),
                TestResult.pdf_source != "",
            )
            .distinct()
            .all()
        )
        return [r[0] for r in results if r[0]]

    def save_draft(
        self,
        db: Session,
        id: int,
        customer_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> COARelease:
        """
        Save draft data for a COARelease (auto-saved on blur).

        Args:
            db: Database session
            id: COARelease ID
            customer_id: Optional customer ID
            notes: Optional notes for COA footer

        Returns:
            Updated COARelease

        Raises:
            ValueError: If COARelease not found
        """
        release = self.get(db, id)
        if not release:
            raise ValueError(f"COARelease with ID {id} not found")

        # Update draft_data JSON field for auto-restore
        release.save_draft(customer_id=customer_id, notes=notes)

        # Also update the main fields
        release.customer_id = customer_id
        release.notes = notes

        db.commit()
        db.refresh(release)

        logger.info(f"Saved draft for COARelease {id}")
        return release

    def approve_release(
        self,
        db: Session,
        id: int,
        user_id: int,
    ) -> COARelease:
        """
        Approve a COARelease (set status=RELEASED).

        Args:
            db: Database session
            id: COARelease ID
            user_id: ID of user approving the release

        Returns:
            Updated COARelease

        Raises:
            ValueError: If COARelease not found or user lacks permission
        """
        release = self.get_by_id(db, id)
        if not release:
            raise ValueError(f"COARelease with ID {id} not found")

        # Check user exists and has permission
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        if not user.can_approve:
            raise ValueError(f"User {user.username} does not have release permissions")

        # Check current status
        if release.status != COAReleaseStatus.AWAITING_RELEASE:
            raise ValueError(
                f"Cannot approve release with status '{release.status.value}'. "
                f"Must be 'awaiting_release'."
            )

        # Capture old values for audit
        old_values = {
            "status": release.status.value,
            "released_at": None,
            "released_by_id": None,
        }

        # Perform release
        release.release(user_id)

        # Log audit
        self._log_audit(
            db=db,
            action=AuditAction.APPROVE,
            record_id=release.id,
            old_values=old_values,
            new_values={
                "status": release.status.value,
                "released_at": release.released_at.isoformat() if release.released_at else None,
                "released_by_id": user_id,
            },
            user_id=user_id,
        )

        # Check if all COARelease for this lot are now released
        self._check_lot_release_complete(db, release.lot_id, user_id)

        db.commit()
        db.refresh(release)

        logger.info(f"COARelease {id} approved by user {user.username}")
        return release

    def send_back(
        self,
        db: Session,
        id: int,
        user_id: int,
        reason: str,
    ) -> COARelease:
        """
        Send a COARelease back to Sample Tracker (QC review).

        Args:
            db: Database session
            id: COARelease ID
            user_id: ID of user sending back
            reason: Reason for sending back (required)

        Returns:
            Updated COARelease

        Raises:
            ValueError: If COARelease not found or reason not provided
        """
        if not reason or not reason.strip():
            raise ValueError("Reason is required when sending back")

        release = self.get_by_id(db, id)
        if not release:
            raise ValueError(f"COARelease with ID {id} not found")

        # Check user exists and has permission
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        if not user.can_approve:
            raise ValueError(f"User {user.username} does not have permission to send back")

        # Check current status
        if release.status != COAReleaseStatus.AWAITING_RELEASE:
            raise ValueError(
                f"Cannot send back release with status '{release.status.value}'. "
                f"Must be 'awaiting_release'."
            )

        # Capture old values
        old_status = release.status.value

        # Update COARelease
        release.send_back_reason = reason.strip()

        # Update lot status back to UNDER_REVIEW
        lot = release.lot
        if lot:
            old_lot_status = lot.status
            lot.status = LotStatus.UNDER_REVIEW

            # Log lot status change
            self._log_audit(
                db=db,
                action=AuditAction.UPDATE,
                record_id=lot.id,
                old_values={"status": old_lot_status.value},
                new_values={"status": lot.status.value},
                user_id=user_id,
                reason=f"Sent back from release: {reason}",
            )

        # Log release audit
        self._log_audit(
            db=db,
            action=AuditAction.UPDATE,
            record_id=release.id,
            old_values={"status": old_status, "send_back_reason": None},
            new_values={
                "status": release.status.value,
                "send_back_reason": release.send_back_reason,
            },
            user_id=user_id,
            reason=reason,
        )

        db.commit()
        db.refresh(release)

        logger.info(f"COARelease {id} sent back by user {user.username}: {reason}")
        return release

    def log_email_sent(
        self,
        db: Session,
        id: int,
        recipient_email: str,
        user_id: int,
    ) -> EmailHistory:
        """
        Log that an email was sent for a COARelease.

        Note: This is a placeholder - no actual email is sent.

        Args:
            db: Database session
            id: COARelease ID
            recipient_email: Email address the COA was sent to
            user_id: ID of user who sent the email

        Returns:
            Created EmailHistory record

        Raises:
            ValueError: If COARelease not found
        """
        release = self.get(db, id)
        if not release:
            raise ValueError(f"COARelease with ID {id} not found")

        # Create email history record
        email_record = EmailHistory(
            coa_release_id=id,
            recipient_email=recipient_email.strip().lower(),
            sent_at=datetime.utcnow(),
            sent_by_id=user_id,
        )
        db.add(email_record)
        db.commit()
        db.refresh(email_record)

        logger.info(f"Email logged for COARelease {id} to {recipient_email}")
        return email_record

    def get_email_history(self, db: Session, id: int) -> List[EmailHistory]:
        """
        Get email history for a COARelease.

        Args:
            db: Database session
            id: COARelease ID

        Returns:
            List of EmailHistory records, ordered by sent_at desc
        """
        return (
            db.query(EmailHistory)
            .options(joinedload(EmailHistory.sent_by))
            .filter(EmailHistory.coa_release_id == id)
            .order_by(EmailHistory.sent_at.desc())
            .all()
        )

    def _check_lot_release_complete(
        self,
        db: Session,
        lot_id: int,
        user_id: int,
    ) -> None:
        """
        Check if all COARelease for a lot are released and update lot status.

        Args:
            db: Database session
            lot_id: Lot ID to check
            user_id: ID of user triggering the check
        """
        # Get all COARelease for this lot
        releases = (
            db.query(COARelease)
            .filter(COARelease.lot_id == lot_id)
            .all()
        )

        if not releases:
            return

        # Check if all are released
        all_released = all(
            r.status == COAReleaseStatus.RELEASED for r in releases
        )

        if all_released:
            lot = db.query(Lot).filter(Lot.id == lot_id).first()
            if lot and lot.status == LotStatus.APPROVED:
                old_status = lot.status
                lot.status = LotStatus.RELEASED

                # Log the change
                self._log_audit(
                    db=db,
                    action=AuditAction.UPDATE,
                    record_id=lot.id,
                    old_values={"status": old_status.value},
                    new_values={"status": lot.status.value},
                    user_id=user_id,
                    reason="All COAs released",
                )

                logger.info(f"Lot {lot.lot_number} status updated to RELEASED")
