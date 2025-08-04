"""Base service class with common functionality."""

from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.models.base import BaseModel
from src.models.audit import AuditLog
from src.models.enums import AuditAction
from src.utils.logger import logger

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseService(Generic[ModelType]):
    """
    Base service class providing common CRUD operations and audit logging.

    This class provides:
    - Standard CRUD operations with automatic audit logging
    - Error handling and logging
    - Transaction management
    - Permission checking hooks
    """

    def __init__(self, model: Type[ModelType]):
        """
        Initialize base service.

        Args:
            model: SQLAlchemy model class
        """
        self.model = model
        self.model_name = model.__name__.lower()

    def get(self, db: Session, id: int) -> Optional[ModelType]:
        """
        Get a record by ID.

        Args:
            db: Database session
            id: Record ID

        Returns:
            Model instance or None if not found
        """
        try:
            return db.query(self.model).filter(self.model.id == id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error fetching {self.model_name} with id {id}: {e}")
            raise

    def get_multi(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ModelType]:
        """
        Get multiple records with optional filtering.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Optional filter conditions

        Returns:
            List of model instances
        """
        try:
            query = db.query(self.model)

            if filters:
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        query = query.filter(getattr(self.model, key) == value)

            return query.offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error fetching {self.model_name} records: {e}")
            raise

    def create(
        self,
        db: Session,
        obj_in: Dict[str, Any],
        user_id: Optional[int] = None,
        audit_metadata: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """
        Create a new record with audit logging.

        Args:
            db: Database session
            obj_in: Dictionary with creation data
            user_id: ID of user performing the action
            audit_metadata: Additional metadata for audit log

        Returns:
            Created model instance
        """
        try:
            db_obj = self.model(**obj_in)
            db.add(db_obj)
            db.flush()  # Flush to get the ID without committing

            # Log audit trail
            self._log_audit(
                db=db,
                action=AuditAction.INSERT,
                record_id=db_obj.id,
                new_values=db_obj.to_dict(),
                user_id=user_id,
                metadata=audit_metadata,
            )

            db.commit()
            db.refresh(db_obj)

            logger.info(f"Created {self.model_name} with id {db_obj.id}")
            return db_obj

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error creating {self.model_name}: {e}")
            raise

    def update(
        self,
        db: Session,
        db_obj: ModelType,
        obj_in: Dict[str, Any],
        user_id: Optional[int] = None,
        audit_metadata: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """
        Update an existing record with audit logging.

        Args:
            db: Database session
            db_obj: Existing model instance
            obj_in: Dictionary with update data
            user_id: ID of user performing the action
            audit_metadata: Additional metadata for audit log

        Returns:
            Updated model instance
        """
        try:
            # Capture old values before update
            old_values = db_obj.to_dict()

            # Update object attributes
            for field, value in obj_in.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)

            db.flush()

            # Log audit trail
            self._log_audit(
                db=db,
                action=AuditAction.UPDATE,
                record_id=db_obj.id,
                old_values=old_values,
                new_values=db_obj.to_dict(),
                user_id=user_id,
                metadata=audit_metadata,
            )

            db.commit()
            db.refresh(db_obj)

            logger.info(f"Updated {self.model_name} with id {db_obj.id}")
            return db_obj

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error updating {self.model_name}: {e}")
            raise

    def delete(
        self,
        db: Session,
        id: int,
        user_id: Optional[int] = None,
        reason: Optional[str] = None,
        audit_metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Delete a record with audit logging.

        Args:
            db: Database session
            id: Record ID to delete
            user_id: ID of user performing the action
            reason: Reason for deletion (required)
            audit_metadata: Additional metadata for audit log

        Returns:
            True if deleted successfully

        Raises:
            ValueError: If reason is not provided
        """
        if not reason:
            raise ValueError("Reason is required for deletion")

        try:
            db_obj = self.get(db, id=id)
            if not db_obj:
                return False

            # Capture values before deletion
            old_values = db_obj.to_dict()

            # Log audit trail before deletion
            self._log_audit(
                db=db,
                action=AuditAction.DELETE,
                record_id=id,
                old_values=old_values,
                user_id=user_id,
                reason=reason,
                metadata=audit_metadata,
            )

            db.delete(db_obj)
            db.commit()

            logger.info(f"Deleted {self.model_name} with id {id}")
            return True

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error deleting {self.model_name}: {e}")
            raise

    def _log_audit(
        self,
        db: Session,
        action: AuditAction,
        record_id: int,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Create audit log entry.

        Args:
            db: Database session
            action: Type of action performed
            record_id: ID of the affected record
            old_values: Values before the change
            new_values: Values after the change
            user_id: ID of user performing the action
            reason: Reason for the action
            metadata: Additional metadata (IP address, user agent, etc.)
        """
        try:
            ip_address = metadata.get("ip_address") if metadata else None
            user_agent = metadata.get("user_agent") if metadata else None

            AuditLog.log_change(
                session=db,
                table_name=self.model.__tablename__,
                record_id=record_id,
                action=action,
                old_values=old_values,
                new_values=new_values,
                user=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                reason=reason,
            )
        except Exception as e:
            # Log error but don't fail the main operation
            logger.error(f"Failed to create audit log: {e}")

    def count(self, db: Session, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records with optional filtering.

        Args:
            db: Database session
            filters: Optional filter conditions

        Returns:
            Number of records
        """
        try:
            query = db.query(self.model)

            if filters:
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        query = query.filter(getattr(self.model, key) == value)

            return query.count()
        except SQLAlchemyError as e:
            logger.error(f"Error counting {self.model_name} records: {e}")
            raise
