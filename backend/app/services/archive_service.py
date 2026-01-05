"""Archive service for searching and managing released COAs."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_

from app.models.coa_release import COARelease
from app.models.email_history import EmailHistory
from app.models.lot import Lot
from app.models.enums import COAReleaseStatus
from app.services.base import BaseService
from app.utils.logger import logger


class ArchiveService(BaseService[COARelease]):
    """
    Service for managing archived (released) COAs.

    Provides functionality for:
    - Searching released COAs with filters
    - Retrieving archived COA details
    - Re-sending emails to different recipients
    """

    def __init__(self):
        """Initialize archive service."""
        super().__init__(COARelease)

    def search(
        self,
        db: Session,
        product_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        lot_number: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[COARelease], int]:
        """
        Search released COAs with filters.

        Args:
            db: Database session
            product_id: Filter by product ID
            customer_id: Filter by customer ID
            date_from: Filter by released_at >= date_from
            date_to: Filter by released_at <= date_to
            lot_number: Filter by lot number (partial match)
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return

        Returns:
            Tuple of (list of matching COARelease, total count)
        """
        # Base query for released COAs
        query = (
            db.query(COARelease)
            .options(
                joinedload(COARelease.lot),
                joinedload(COARelease.product),
                joinedload(COARelease.customer),
                joinedload(COARelease.released_by),
            )
            .filter(COARelease.status == COAReleaseStatus.RELEASED)
        )

        # Apply filters
        if product_id is not None:
            query = query.filter(COARelease.product_id == product_id)

        if customer_id is not None:
            query = query.filter(COARelease.customer_id == customer_id)

        if date_from is not None:
            query = query.filter(COARelease.released_at >= date_from)

        if date_to is not None:
            query = query.filter(COARelease.released_at <= date_to)

        if lot_number:
            # Join with Lot to filter by lot_number
            query = query.join(COARelease.lot).filter(
                Lot.lot_number.ilike(f"%{lot_number}%")
            )

        # Get total count before pagination
        total = query.count()

        # Apply pagination and ordering
        releases = (
            query.order_by(COARelease.released_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return releases, total

    def get_by_id(self, db: Session, id: int) -> Optional[COARelease]:
        """
        Get an archived COARelease by ID with all relations.

        Args:
            db: Database session
            id: COARelease ID

        Returns:
            COARelease with relations, or None
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
            .filter(
                COARelease.id == id,
                COARelease.status == COAReleaseStatus.RELEASED,
            )
            .first()
        )

    def resend_email(
        self,
        db: Session,
        id: int,
        recipient_email: str,
        user_id: int,
    ) -> EmailHistory:
        """
        Log a re-sent email for an archived COARelease.

        Note: This is a placeholder - no actual email is sent.

        Args:
            db: Database session
            id: COARelease ID
            recipient_email: Email address to re-send to
            user_id: ID of user re-sending the email

        Returns:
            Created EmailHistory record

        Raises:
            ValueError: If COARelease not found or not released
        """
        release = self.get_by_id(db, id)
        if not release:
            raise ValueError(f"Released COA with ID {id} not found")

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

        logger.info(f"Email re-sent for archived COARelease {id} to {recipient_email}")
        return email_record

    def get_email_history(self, db: Session, id: int) -> List[EmailHistory]:
        """
        Get email history for an archived COARelease.

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
