"""Database models for LabTrack."""

# Import all models
from app.models.audit import AuditAnnotation, AuditLog
from app.models.base import BaseModel
from app.models.coa import COAHistory
from app.models.coa_category_order import COACategoryOrder
from app.models.coa_release import COARelease
from app.models.coa_snapshot import COASerialCounter, COASnapshot
from app.models.customer import Customer
from app.models.daane_coc_daily_counter import DaaneCOCDailyCounter
from app.models.daane_test_mapping import DaaneTestMapping
from app.models.email_history import EmailHistory
from app.models.email_template import EmailTemplate
from app.models.enums import (
    AuditAction,
    COAReleaseStatus,
    LotStatus,
    LotType,
    ResultImportStatus,
    RetestStatus,
    TestResultStatus,
    UserRole,
)
from app.models.lab_info import LabInfo
from app.models.lab_test_alias import LabTestAlias
from app.models.lab_test_type import LabTestType
from app.models.lot import Lot, LotProduct, Sublot
from app.models.product import Product
from app.models.product_size import ProductSize
from app.models.product_test_spec import ProductTestSpecification
from app.models.release_sensory_attest import ReleaseSensoryAttest
from app.models.result_import import ResultImport, ResultImportLedger
from app.models.retest_request import RetestItem, RetestRequest
from app.models.test_result import TestResult
from app.models.user import User

# Export all models and enums
__all__ = [
    # Base
    "BaseModel",
    # Enums
    "UserRole",
    "LotType",
    "LotStatus",
    "TestResultStatus",
    "ResultImportStatus",
    "AuditAction",
    "COAReleaseStatus",
    "RetestStatus",
    # Models
    "Product",
    "ProductSize",
    "Lot",
    "Sublot",
    "LotProduct",
    "User",
    "TestResult",
    "AuditLog",
    "AuditAnnotation",
    "ResultImport",
    "ResultImportLedger",
    "COAHistory",
    "LabTestType",
    "LabTestAlias",
    "ProductTestSpecification",
    "Customer",
    "COARelease",
    "ReleaseSensoryAttest",
    "COASnapshot",
    "COASerialCounter",
    "EmailHistory",
    "EmailTemplate",
    "COACategoryOrder",
    "LabInfo",
    "RetestRequest",
    "RetestItem",
    "DaaneTestMapping",
    "DaaneCOCDailyCounter",
]
