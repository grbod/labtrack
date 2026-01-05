"""Database models for COA Management System."""

# Import all models
from app.models.base import BaseModel
from app.models.enums import (
    UserRole,
    LotType,
    LotStatus,
    TestResultStatus,
    ParsingStatus,
    AuditAction,
    COAReleaseStatus,
)
from app.models.product import Product
from app.models.product_size import ProductSize
from app.models.lot import Lot, Sublot, LotProduct
from app.models.user import User
from app.models.test_result import TestResult
from app.models.audit import AuditLog
from app.models.parsing import ParsingQueue
from app.models.coa import COAHistory
from app.models.lab_test_type import LabTestType
from app.models.product_test_spec import ProductTestSpecification
from app.models.customer import Customer
from app.models.coa_release import COARelease
from app.models.email_history import EmailHistory
from app.models.email_template import EmailTemplate

# Export all models and enums
__all__ = [
    # Base
    "BaseModel",
    # Enums
    "UserRole",
    "LotType",
    "LotStatus",
    "TestResultStatus",
    "ParsingStatus",
    "AuditAction",
    "COAReleaseStatus",
    # Models
    "Product",
    "ProductSize",
    "Lot",
    "Sublot",
    "LotProduct",
    "User",
    "TestResult",
    "AuditLog",
    "ParsingQueue",
    "COAHistory",
    "LabTestType",
    "ProductTestSpecification",
    "Customer",
    "COARelease",
    "EmailHistory",
    "EmailTemplate",
]
