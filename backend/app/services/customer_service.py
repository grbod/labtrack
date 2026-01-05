"""Customer service for managing customer records."""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.customer import Customer
from app.services.base import BaseService
from app.utils.logger import logger


class CustomerService(BaseService[Customer]):
    """
    Service for managing customers.

    Provides specialized methods for customer management including:
    - Getting active customers for dropdown lists
    - Soft delete (deactivate) functionality
    - Search and filtering
    """

    def __init__(self):
        """Initialize customer service."""
        super().__init__(Customer)

    def get_all_active(self, db: Session) -> List[Customer]:
        """
        Get all active customers.

        Args:
            db: Database session

        Returns:
            List of active customers ordered by company name
        """
        try:
            return (
                db.query(Customer)
                .filter(Customer.is_active == True)
                .order_by(Customer.company_name)
                .all()
            )
        except Exception as e:
            logger.error(f"Error fetching active customers: {e}")
            raise

    def get_by_id(self, db: Session, customer_id: int) -> Optional[Customer]:
        """
        Get a customer by ID.

        Args:
            db: Database session
            customer_id: Customer ID

        Returns:
            Customer instance or None if not found
        """
        return self.get(db, customer_id)

    def create_customer(
        self,
        db: Session,
        data: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> Customer:
        """
        Create a new customer.

        Args:
            db: Database session
            data: Dictionary with customer data (company_name, contact_name, email)
            user_id: ID of user performing the action

        Returns:
            Created customer

        Raises:
            ValueError: If email is already in use
        """
        # Check for existing email
        existing = (
            db.query(Customer)
            .filter(Customer.email == data.get("email", "").lower())
            .first()
        )
        if existing:
            raise ValueError(f"Customer with email {data['email']} already exists")

        return self.create(db, data, user_id)

    def update_customer(
        self,
        db: Session,
        customer_id: int,
        data: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> Customer:
        """
        Update an existing customer.

        Args:
            db: Database session
            customer_id: Customer ID
            data: Dictionary with update data
            user_id: ID of user performing the action

        Returns:
            Updated customer

        Raises:
            ValueError: If customer not found or email already in use
        """
        customer = self.get(db, customer_id)
        if not customer:
            raise ValueError("Customer not found")

        # Check email uniqueness if updating email
        if "email" in data and data["email"] != customer.email:
            existing = (
                db.query(Customer)
                .filter(
                    Customer.email == data["email"].lower(),
                    Customer.id != customer_id,
                )
                .first()
            )
            if existing:
                raise ValueError(f"Customer with email {data['email']} already exists")

        return self.update(db, customer, data, user_id)

    def deactivate(
        self,
        db: Session,
        customer_id: int,
        user_id: Optional[int] = None,
    ) -> Customer:
        """
        Deactivate a customer (soft delete).

        Args:
            db: Database session
            customer_id: Customer ID
            user_id: ID of user performing the action

        Returns:
            Deactivated customer

        Raises:
            ValueError: If customer not found
        """
        customer = self.get(db, customer_id)
        if not customer:
            raise ValueError("Customer not found")

        customer.deactivate()
        return self.update(db, customer, {"is_active": False}, user_id)

    def activate(
        self,
        db: Session,
        customer_id: int,
        user_id: Optional[int] = None,
    ) -> Customer:
        """
        Reactivate a customer.

        Args:
            db: Database session
            customer_id: Customer ID
            user_id: ID of user performing the action

        Returns:
            Activated customer

        Raises:
            ValueError: If customer not found
        """
        customer = self.get(db, customer_id)
        if not customer:
            raise ValueError("Customer not found")

        customer.activate()
        return self.update(db, customer, {"is_active": True}, user_id)

    def search(
        self,
        db: Session,
        search_term: Optional[str] = None,
        include_inactive: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Customer]:
        """
        Search customers with optional filters.

        Args:
            db: Database session
            search_term: Search term for company name, contact name, or email
            include_inactive: Whether to include inactive customers
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matching customers
        """
        try:
            query = db.query(Customer)

            if not include_inactive:
                query = query.filter(Customer.is_active == True)

            if search_term:
                search_pattern = f"%{search_term}%"
                query = query.filter(
                    or_(
                        Customer.company_name.ilike(search_pattern),
                        Customer.contact_name.ilike(search_pattern),
                        Customer.email.ilike(search_pattern),
                    )
                )

            return (
                query.order_by(Customer.company_name)
                .offset(skip)
                .limit(limit)
                .all()
            )

        except Exception as e:
            logger.error(f"Error searching customers: {e}")
            raise

    def count(
        self,
        db: Session,
        include_inactive: bool = False,
        search_term: Optional[str] = None,
    ) -> int:
        """
        Count customers with optional filters.

        Args:
            db: Database session
            include_inactive: Whether to include inactive customers
            search_term: Optional search term

        Returns:
            Number of matching customers
        """
        try:
            query = db.query(Customer)

            if not include_inactive:
                query = query.filter(Customer.is_active == True)

            if search_term:
                search_pattern = f"%{search_term}%"
                query = query.filter(
                    or_(
                        Customer.company_name.ilike(search_pattern),
                        Customer.contact_name.ilike(search_pattern),
                        Customer.email.ilike(search_pattern),
                    )
                )

            return query.count()

        except Exception as e:
            logger.error(f"Error counting customers: {e}")
            raise
