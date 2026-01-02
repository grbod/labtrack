"""User service for authentication and role management."""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import hashlib
import secrets
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.user import User
from app.models.enums import UserRole
from app.services.base import BaseService
from app.utils.logger import logger


class UserService(BaseService[User]):
    """
    Service for managing users, authentication, and authorization.

    Provides functionality for:
    - User creation and management
    - Password hashing and verification
    - Role-based access control
    - Session management
    """

    def __init__(self):
        """Initialize user service."""
        super().__init__(User)

    def create_user(
        self,
        db: Session,
        username: str,
        email: str,
        password: str,
        role: UserRole = UserRole.READ_ONLY,
        created_by_user_id: Optional[int] = None,
    ) -> User:
        """
        Create a new user with hashed password.

        Args:
            db: Database session
            username: Unique username
            email: User email address
            password: Plain text password
            role: User role
            created_by_user_id: ID of user creating this user

        Returns:
            Created user

        Raises:
            ValueError: If username or email already exists
        """
        # Check if username exists
        if self.get_by_username(db, username):
            raise ValueError(f"Username '{username}' already exists")

        # Check if email exists
        if self.get_by_email(db, email):
            raise ValueError(f"Email '{email}' already exists")

        # Hash password
        password_hash = self._hash_password(password)

        user_data = {
            "username": username.lower(),
            "email": email.lower(),
            "password_hash": password_hash,
            "role": role,
            "active": True,
        }

        try:
            return self.create(db=db, obj_in=user_data, user_id=created_by_user_id)
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Error creating user: {e}")
            raise ValueError(
                "Error creating user - username or email may already exist"
            )

    def authenticate(self, db: Session, username: str, password: str) -> Optional[User]:
        """
        Authenticate user with username and password.

        Args:
            db: Database session
            username: Username or email
            password: Plain text password

        Returns:
            Authenticated user or None
        """
        # Try to find user by username or email
        user = self.get_by_username(db, username)
        if not user:
            user = self.get_by_email(db, username)

        if not user:
            logger.warning(f"Authentication failed - user not found: {username}")
            return None

        if not user.active:
            logger.warning(f"Authentication failed - inactive user: {username}")
            return None

        # Verify password
        if not self._verify_password(password, user.password_hash):
            logger.warning(f"Authentication failed - invalid password: {username}")
            return None

        logger.info(f"User authenticated successfully: {username}")
        return user

    def change_password(
        self,
        db: Session,
        user_id: int,
        old_password: str,
        new_password: str,
        changed_by_user_id: Optional[int] = None,
    ) -> User:
        """
        Change user password.

        Args:
            db: Database session
            user_id: ID of user whose password to change
            old_password: Current password
            new_password: New password
            changed_by_user_id: ID of user making the change

        Returns:
            Updated user

        Raises:
            ValueError: If old password is incorrect or user not found
        """
        user = self.get(db, user_id)
        if not user:
            raise ValueError("User not found")

        # Verify old password (skip for admin override)
        if changed_by_user_id != user_id:  # Admin changing another user's password
            admin = self.get(db, changed_by_user_id)
            if not admin or not admin.is_admin:
                # Not admin, must verify old password
                if not self._verify_password(old_password, user.password_hash):
                    raise ValueError("Invalid current password")
        else:
            # User changing own password, must verify
            if not self._verify_password(old_password, user.password_hash):
                raise ValueError("Invalid current password")

        # Hash new password
        new_password_hash = self._hash_password(new_password)

        return self.update(
            db=db,
            db_obj=user,
            obj_in={"password_hash": new_password_hash},
            user_id=changed_by_user_id,
        )

    def update_user_role(
        self,
        db: Session,
        user_id: int,
        new_role: UserRole,
        updated_by_user_id: int,
        reason: Optional[str] = None,
    ) -> User:
        """
        Update user role with permission check.

        Args:
            db: Database session
            user_id: ID of user to update
            new_role: New role to assign
            updated_by_user_id: ID of user making the change
            reason: Reason for role change

        Returns:
            Updated user

        Raises:
            ValueError: If permission denied or user not found
        """
        # Check permissions
        admin_user = self.get(db, updated_by_user_id)
        if not admin_user or not admin_user.is_admin:
            raise ValueError("Only administrators can change user roles")

        user = self.get(db, user_id)
        if not user:
            raise ValueError("User not found")

        old_role = user.role

        # Update role with audit
        updated_user = self.update(
            db=db,
            db_obj=user,
            obj_in={"role": new_role},
            user_id=updated_by_user_id,
            audit_metadata={"reason": reason} if reason else None,
        )

        logger.info(
            f"User {user.username} role changed from {old_role.value} to {new_role.value}"
        )
        return updated_user

    def deactivate_user(
        self, db: Session, user_id: int, deactivated_by_user_id: int, reason: str
    ) -> User:
        """
        Deactivate a user account.

        Args:
            db: Database session
            user_id: ID of user to deactivate
            deactivated_by_user_id: ID of user performing deactivation
            reason: Reason for deactivation

        Returns:
            Deactivated user

        Raises:
            ValueError: If permission denied or user not found
        """
        # Check permissions
        admin_user = self.get(db, deactivated_by_user_id)
        if not admin_user or not admin_user.has_permission("manage_users"):
            raise ValueError("Insufficient permissions to deactivate users")

        user = self.get(db, user_id)
        if not user:
            raise ValueError("User not found")

        if not user.active:
            raise ValueError("User is already inactive")

        # Prevent self-deactivation
        if user_id == deactivated_by_user_id:
            raise ValueError("Cannot deactivate your own account")

        return self.update(
            db=db,
            db_obj=user,
            obj_in={"active": False},
            user_id=deactivated_by_user_id,
            audit_metadata={"reason": reason},
        )

    def reactivate_user(
        self, db: Session, user_id: int, reactivated_by_user_id: int, reason: str
    ) -> User:
        """
        Reactivate a user account.

        Args:
            db: Database session
            user_id: ID of user to reactivate
            reactivated_by_user_id: ID of user performing reactivation
            reason: Reason for reactivation

        Returns:
            Reactivated user
        """
        # Check permissions
        admin_user = self.get(db, reactivated_by_user_id)
        if not admin_user or not admin_user.has_permission("manage_users"):
            raise ValueError("Insufficient permissions to reactivate users")

        user = self.get(db, user_id)
        if not user:
            raise ValueError("User not found")

        if user.active:
            raise ValueError("User is already active")

        return self.update(
            db=db,
            db_obj=user,
            obj_in={"active": True},
            user_id=reactivated_by_user_id,
            audit_metadata={"reason": reason},
        )

    def get_by_username(self, db: Session, username: str) -> Optional[User]:
        """
        Get user by username.

        Args:
            db: Database session
            username: Username to search for

        Returns:
            User or None
        """
        return db.query(User).filter(User.username == username.lower()).first()

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """
        Get user by email.

        Args:
            db: Database session
            email: Email to search for

        Returns:
            User or None
        """
        return db.query(User).filter(User.email == email.lower()).first()

    def get_users_by_role(
        self,
        db: Session,
        role: UserRole,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> List[User]:
        """
        Get users filtered by role.

        Args:
            db: Database session
            role: User role to filter by
            active_only: Only return active users
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of users
        """
        query = db.query(User).filter(User.role == role)

        if active_only:
            query = query.filter(User.active == True)

        return query.offset(skip).limit(limit).all()

    def check_permission(self, db: Session, user_id: int, action: str) -> bool:
        """
        Check if user has permission for an action.

        Args:
            db: Database session
            user_id: User ID
            action: Action to check permission for

        Returns:
            True if user has permission
        """
        user = self.get(db, user_id)
        if not user:
            return False

        return user.has_permission(action)

    def _hash_password(self, password: str) -> str:
        """
        Hash password using SHA256.

        Note: In production, use bcrypt or similar.

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        # Add salt for better security
        salt = "coa_system_salt_"  # In production, use random salt per user
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.

        Args:
            plain_password: Plain text password
            hashed_password: Hashed password to compare

        Returns:
            True if password matches
        """
        return self._hash_password(plain_password) == hashed_password

    def get_user_stats(self, db: Session) -> Dict[str, Any]:
        """
        Get user statistics.

        Args:
            db: Database session

        Returns:
            Dictionary with user statistics
        """
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.active == True).count()

        role_counts = {}
        for role in UserRole:
            count = db.query(User).filter(User.role == role).count()
            role_counts[role.value] = count

        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "users_by_role": role_counts,
        }

    def generate_api_token(self, user_id: int) -> str:
        """
        Generate API token for user.

        Note: This is a simple implementation. In production,
        use JWT or similar token system.

        Args:
            user_id: User ID

        Returns:
            Generated token
        """
        # Simple token generation - in production use JWT
        timestamp = datetime.now().isoformat()
        random_part = secrets.token_hex(16)
        return f"{user_id}:{timestamp}:{random_part}"
