"""Service for managing COA category display order."""

from typing import List
from sqlalchemy.orm import Session
from app.models import COACategoryOrder, LabTestType
from app.services.base import BaseService
from app.utils.logger import logger


class COACategoryOrderService(BaseService[COACategoryOrder]):
    """Service for COA category order operations."""

    def __init__(self):
        super().__init__(COACategoryOrder)

    def get_or_create_default(self, db: Session) -> COACategoryOrder:
        """
        Get the current category order, creating a default if none exists.

        This ensures there is always exactly one row in the table.

        Args:
            db: Database session

        Returns:
            COACategoryOrder instance
        """
        order = db.query(COACategoryOrder).first()

        if not order:
            # Create default order
            order = COACategoryOrder(
                category_order=COACategoryOrder.get_default_order()
            )
            db.add(order)
            db.commit()
            db.refresh(order)
            logger.info("Created default COA category order")

        return order

    def update_order(
        self,
        db: Session,
        category_order: List[str],
        user_id: int | None = None,
    ) -> COACategoryOrder:
        """
        Update the category display order.

        Args:
            db: Database session
            category_order: Ordered list of category names
            user_id: ID of user making the change

        Returns:
            Updated COACategoryOrder instance
        """
        order = self.get_or_create_default(db)

        # Validate all categories exist (from active test types)
        valid_categories = self._get_active_categories(db)
        for category in category_order:
            if category not in valid_categories:
                logger.warning(
                    f"Category '{category}' in order but no active tests use it"
                )

        order.category_order = category_order
        db.commit()
        db.refresh(order)

        logger.info(f"Updated COA category order to: {category_order}")
        return order

    def reset_to_defaults(
        self,
        db: Session,
        user_id: int | None = None,
    ) -> COACategoryOrder:
        """
        Reset the category order to default (alphabetical).

        Args:
            db: Database session
            user_id: ID of user making the change

        Returns:
            Reset COACategoryOrder instance
        """
        order = self.get_or_create_default(db)
        order.category_order = COACategoryOrder.get_default_order()
        db.commit()
        db.refresh(order)

        logger.info("Reset COA category order to defaults")
        return order

    def get_ordered_categories(self, db: Session) -> List[str]:
        """
        Get the list of categories in configured display order.

        Args:
            db: Database session

        Returns:
            List of category names in display order
        """
        order = self.get_or_create_default(db)
        return order.category_order or []

    def _get_active_categories(self, db: Session) -> set[str]:
        """Get all categories that have at least one active test type."""
        results = (
            db.query(LabTestType.test_category)
            .filter(LabTestType.is_active == True)
            .distinct()
            .all()
        )
        return {r[0] for r in results}

    def get_all_active_categories_ordered(self, db: Session) -> List[str]:
        """
        Get all active categories, ordered by the configured order.

        Categories in the configured order appear first (in that order),
        followed by any unconfigured categories in alphabetical order.

        Args:
            db: Database session

        Returns:
            List of category names in display order
        """
        configured_order = self.get_ordered_categories(db)
        active_categories = self._get_active_categories(db)

        # Start with configured categories that are still active
        result = [c for c in configured_order if c in active_categories]

        # Add any active categories not in the configured order (alphabetically)
        unconfigured = sorted(active_categories - set(configured_order))
        result.extend(unconfigured)

        return result


# Singleton instance
coa_category_order_service = COACategoryOrderService()
