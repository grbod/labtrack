"""User model for authentication and authorization."""

from sqlalchemy import Column, String, Boolean, Enum, Index
from sqlalchemy.orm import relationship, validates
from app.models.base import BaseModel
from app.models.enums import UserRole


class User(BaseModel):
    """
    User model for system authentication and role-based access control.

    Attributes:
        username: Unique username for login
        email: Unique email address
        role: User role determining permissions
        active: Whether user account is active
    """

    __tablename__ = "users"

    # Core fields
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.READ_ONLY)
    active = Column(Boolean, default=True, nullable=False)

    # Password should be hashed - placeholder for now
    # In production, use proper password hashing like bcrypt
    password_hash = Column(String(255), nullable=True)

    # Profile fields for COA signing
    full_name = Column(String(200), nullable=True)
    title = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    signature_path = Column(String(500), nullable=True)

    # Relationships
    audit_logs = relationship(
        "AuditLog", back_populates="user", cascade="all, delete-orphan"
    )
    approved_results = relationship(
        "TestResult",
        back_populates="approved_by_user",
        foreign_keys="TestResult.approved_by_id",
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_user_username", "username"),
        Index("idx_user_email", "email"),
        Index("idx_user_active", "active"),
        Index("idx_user_role_active", "role", "active"),
    )

    @validates("username")
    def validate_username(self, key, value):
        """Validate username is not empty and properly formatted."""
        if not value or not value.strip():
            raise ValueError("Username cannot be empty")
        value = value.strip().lower()
        if not value.replace("_", "").isalnum():
            raise ValueError(
                "Username must contain only letters, numbers, and underscores"
            )
        return value

    @validates("email")
    def validate_email(self, key, value):
        """Validate email format."""
        if not value or not value.strip():
            raise ValueError("Email cannot be empty")
        value = value.strip().lower()
        if "@" not in value or "." not in value.split("@")[1]:
            raise ValueError("Invalid email format")
        return value

    @property
    def is_admin(self):
        """Check if user is admin."""
        return self.role == UserRole.ADMIN

    @property
    def is_qc_manager(self):
        """Check if user is QC manager or higher."""
        return self.role in [UserRole.ADMIN, UserRole.QC_MANAGER]

    @property
    def can_approve(self):
        """Check if user can approve test results."""
        return self.is_qc_manager and self.active

    @property
    def can_edit(self):
        """Check if user can edit data."""
        return (
            self.role in [UserRole.ADMIN, UserRole.QC_MANAGER, UserRole.LAB_TECH]
            and self.active
        )

    def has_permission(self, action):
        """Check if user has permission for specific action."""
        if not self.active:
            return False

        permissions = {
            UserRole.READ_ONLY: ["view"],
            UserRole.LAB_TECH: ["view", "create", "edit_draft", "edit_reviewed"],
            UserRole.QC_MANAGER: [
                "view",
                "create",
                "edit_draft",
                "edit_reviewed",
                "approve",
                "reject",
            ],
            UserRole.ADMIN: [
                "view",
                "create",
                "edit_draft",
                "edit_reviewed",
                "approve",
                "reject",
                "delete",
                "manage_users",
                "override",
            ],
        }

        return action in permissions.get(self.role, [])

    def set_password(self, password):
        """Set user password using bcrypt."""
        from app.core.security import get_password_hash

        self.password_hash = get_password_hash(password)

    def check_password(self, password):
        """Check password using bcrypt."""
        if not self.active:
            return False
        if not self.password_hash:
            return False
        from app.core.security import verify_password

        return verify_password(password, self.password_hash)

    def deactivate(self):
        """Deactivate user account."""
        self.active = False

    def __repr__(self):
        """String representation of User."""
        return f"<User(id={self.id}, username='{self.username}', role='{self.role.value}', active={self.active})>"
