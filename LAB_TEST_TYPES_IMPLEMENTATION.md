# Ultra-Detailed Implementation Plan for Lab Test Types & Product Specifications System

## Overview

This document provides an ultra-detailed implementation plan for adding Lab Test Types and Product Test Specifications to LabTrack. This will enable products to have pre-defined testing requirements with specifications, required/optional designations, and automatic validation during the approval process.

## Table of Contents

1. [Database Schema & Model Creation](#phase-1-database-schema--model-creation)
2. [Service Layer Implementation](#phase-2-service-layer-implementation)
3. [UI Implementation](#phase-3-ui-implementation)
4. [Update Approval Dashboard](#phase-4-update-approval-dashboard)
5. [Update Status Transitions](#phase-5-update-status-transitions)
6. [Menu Updates](#phase-6-menu-updates)
7. [Database Migrations](#phase-7-database-migrations)
8. [Seed Data](#phase-8-seed-data)
9. [Testing Plan](#testing-plan)

## Phase 1: Database Schema & Model Creation

### 1.1 Create LabTestType Model (`/src/models/lab_test_type.py`)

```python
"""Lab test type model for defining available laboratory tests."""

from sqlalchemy import Column, String, Text, Index, UniqueConstraint, Integer
from sqlalchemy.orm import relationship, validates
from src.models.base import BaseModel


class LabTestType(BaseModel):
    """
    Lab test type model for managing available laboratory tests.
    
    Examples:
    - E. coli: unit="CFU/g", category="Microbiological"
    - Lead: unit="ppm", category="Heavy Metals"
    - Salmonella: unit="Positive/Negative", category="Microbiological"
    """
    
    __tablename__ = "lab_test_types"
    
    # Core fields
    name = Column(String(100), nullable=False, unique=True)
    category = Column(String(50), nullable=False)
    unit_of_measurement = Column(String(50), nullable=False)
    default_method = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    
    # Common abbreviations (for PDF parsing)
    abbreviations = Column(Text, nullable=True)  # JSON array of alternatives
    
    # Display order within category
    sort_order = Column(Integer, default=999)
    
    # Relationships
    product_specifications = relationship(
        "ProductTestSpecification", 
        back_populates="lab_test_type",
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_lab_test_name", "name"),
        Index("idx_lab_test_category", "category"),
        Index("idx_lab_test_category_order", "category", "sort_order"),
        UniqueConstraint("name", name="uq_lab_test_name"),
    )
    
    # Categories enum
    CATEGORIES = {
        "MICROBIOLOGICAL": "Microbiological",
        "HEAVY_METALS": "Heavy Metals", 
        "NUTRITIONAL": "Nutritional",
        "ALLERGENS": "Allergens",
        "PHYSICAL": "Physical",
        "CHEMICAL": "Chemical",
        "OTHER": "Other"
    }
    
    # Common units enum
    UNITS = {
        "CFU_G": "CFU/g",
        "CFU_ML": "CFU/mL",
        "PPM": "ppm",
        "PPB": "ppb",
        "PERCENT": "%",
        "MG_G": "mg/g",
        "POS_NEG": "Positive/Negative",
        "PRESENT_ABSENT": "Present/Absent",
        "IU_G": "IU/g",
        "QUALITATIVE": "Qualitative"
    }
    
    @validates("name")
    def validate_name(self, key, value):
        """Validate test name."""
        if not value or not value.strip():
            raise ValueError("Test name cannot be empty")
        return value.strip()
    
    @validates("category")
    def validate_category(self, key, value):
        """Validate category is from allowed list."""
        if value not in self.CATEGORIES.values():
            raise ValueError(f"Category must be one of: {list(self.CATEGORIES.values())}")
        return value
    
    @validates("unit_of_measurement")
    def validate_unit(self, key, value):
        """Validate unit of measurement."""
        if not value or not value.strip():
            raise ValueError("Unit of measurement cannot be empty")
        return value.strip()
    
    @property
    def is_microbiological(self):
        """Check if test is microbiological."""
        return self.category == "Microbiological"
    
    @property
    def is_heavy_metal(self):
        """Check if test is heavy metal."""
        return self.category == "Heavy Metals"
    
    @property
    def is_quantitative(self):
        """Check if test has numeric results."""
        return self.unit_of_measurement not in ["Positive/Negative", "Present/Absent", "Qualitative"]
    
    def get_abbreviations_list(self):
        """Get abbreviations as list."""
        if not self.abbreviations:
            return []
        try:
            import json
            return json.loads(self.abbreviations)
        except:
            return []
    
    def set_abbreviations_list(self, abbrev_list):
        """Set abbreviations from list."""
        if abbrev_list:
            import json
            self.abbreviations = json.dumps(abbrev_list)
        else:
            self.abbreviations = None
    
    def __repr__(self):
        """String representation."""
        return f"<LabTestType(name='{self.name}', category='{self.category}', unit='{self.unit_of_measurement}')>"
```

### 1.2 Create ProductTestSpecification Model (`/src/models/product_test_spec.py`)

```python
"""Product test specification model linking products to required/optional tests."""

from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship, validates
from src.models.base import BaseModel


class ProductTestSpecification(BaseModel):
    """
    Links products to lab test types with specifications.
    
    Example:
    - Product: "Organic Whey Protein"
    - Test: "E. coli"
    - Specification: "< 10"
    - Required: True
    """
    
    __tablename__ = "product_test_specifications"
    
    # Foreign keys
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    lab_test_type_id = Column(Integer, ForeignKey("lab_test_types.id"), nullable=False)
    
    # Specification details
    specification = Column(String(100), nullable=False)  # "< 10", "Negative", etc.
    is_required = Column(Boolean, default=True, nullable=False)
    
    # Additional fields
    notes = Column(Text, nullable=True)  # "Test only on first batch of year"
    min_value = Column(String(20), nullable=True)  # For range specs
    max_value = Column(String(20), nullable=True)  # For range specs
    
    # Relationships
    product = relationship("Product", back_populates="test_specifications")
    lab_test_type = relationship("LabTestType", back_populates="product_specifications")
    
    # Unique constraint - one spec per product/test combination
    __table_args__ = (
        UniqueConstraint("product_id", "lab_test_type_id", name="uq_product_test"),
    )
    
    @validates("specification")
    def validate_specification(self, key, value):
        """Validate specification format."""
        if not value or not value.strip():
            raise ValueError("Specification cannot be empty")
        return value.strip()
    
    @property
    def test_name(self):
        """Get test name from related lab test type."""
        return self.lab_test_type.name if self.lab_test_type else None
    
    @property
    def test_unit(self):
        """Get test unit from related lab test type."""
        return self.lab_test_type.unit_of_measurement if self.lab_test_type else None
    
    @property
    def test_category(self):
        """Get test category from related lab test type."""
        return self.lab_test_type.category if self.lab_test_type else None
    
    def matches_result(self, result_value):
        """
        Check if a test result matches this specification.
        
        Args:
            result_value: The actual test result value
            
        Returns:
            bool: True if passes, False if fails
        """
        if not result_value:
            return False
        
        spec = self.specification.strip().lower()
        value = str(result_value).strip().lower()
        
        # Handle Positive/Negative results
        if self.test_unit == "Positive/Negative":
            if spec == "negative" and value in ["negative", "nd", "not detected"]:
                return True
            if spec == "positive" and value == "positive":
                return True
            return False
        
        # Handle "< X" specifications
        if spec.startswith("<"):
            try:
                spec_limit = float(spec[1:].strip())
                if value.startswith("<"):
                    # Both are "less than" values
                    return True
                result_val = float(value)
                return result_val < spec_limit
            except:
                return False
        
        # Handle "> X" specifications
        if spec.startswith(">"):
            try:
                spec_limit = float(spec[1:].strip())
                if value.startswith(">"):
                    # Both are "greater than" values
                    return True
                result_val = float(value)
                return result_val > spec_limit
            except:
                return False
        
        # Handle range specifications
        if "-" in spec and not spec.startswith("-"):
            try:
                parts = spec.split("-")
                if len(parts) == 2:
                    min_val = float(parts[0].strip())
                    max_val = float(parts[1].strip())
                    result_val = float(value)
                    return min_val <= result_val <= max_val
            except:
                return False
        
        # Handle exact match
        return spec == value
    
    def __repr__(self):
        """String representation."""
        return (
            f"<ProductTestSpecification(product_id={self.product_id}, "
            f"test='{self.test_name}', spec='{self.specification}', "
            f"required={self.is_required})>"
        )
```

### 1.3 Update Product Model (`/src/models/product.py`)

Add to existing Product model:

```python
# Add to imports
from sqlalchemy.orm import relationship

# Add relationship
test_specifications = relationship(
    "ProductTestSpecification",
    back_populates="product", 
    cascade="all, delete-orphan",
    order_by="ProductTestSpecification.lab_test_type_id"
)

# Add properties
@property
def required_tests(self):
    """Get list of required test specifications."""
    return [spec for spec in self.test_specifications if spec.is_required]

@property
def optional_tests(self):
    """Get list of optional test specifications."""
    return [spec for spec in self.test_specifications if not spec.is_required]

@property
def has_test_specifications(self):
    """Check if product has any test specifications."""
    return len(self.test_specifications) > 0

def get_specification_for_test(self, test_name):
    """Get specification for a specific test by name."""
    for spec in self.test_specifications:
        if spec.lab_test_type.name.lower() == test_name.lower():
            return spec
    return None

def get_required_test_names(self):
    """Get list of required test names."""
    return [spec.test_name for spec in self.required_tests]

def get_all_test_names(self):
    """Get list of all test names (required and optional)."""
    return [spec.test_name for spec in self.test_specifications]
```

### 1.4 Update Enums (`/src/models/enums.py`)

```python
class LotStatus(str, enum.Enum):
    """Lot status enumeration."""
    
    PENDING = "pending"
    PARTIAL_RESULTS = "partial_results"  # NEW: Some results in, missing required tests
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    RELEASED = "released"
    REJECTED = "rejected"
```

### 1.5 Update Model Imports (`/src/models/__init__.py`)

```python
# Add to imports
from src.models.lab_test_type import LabTestType
from src.models.product_test_spec import ProductTestSpecification

# Add to __all__
__all__ = [
    # ... existing ...
    "LabTestType",
    "ProductTestSpecification",
]
```

## Phase 2: Service Layer Implementation

### 2.1 Create LabTestTypeService (`/src/services/lab_test_type_service.py`)

```python
"""Service for managing lab test types."""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.models import LabTestType
from src.services.base import BaseService
from src.utils.logger import logger


class LabTestTypeService(BaseService[LabTestType]):
    """Service for lab test type operations."""
    
    def __init__(self):
        super().__init__(LabTestType)
    
    def create_lab_test_type(
        self,
        db: Session,
        name: str,
        category: str,
        unit_of_measurement: str,
        default_method: Optional[str] = None,
        description: Optional[str] = None,
        abbreviations: Optional[List[str]] = None,
        sort_order: Optional[int] = None
    ) -> LabTestType:
        """
        Create new lab test type with validation.
        
        Args:
            db: Database session
            name: Test name (must be unique)
            category: Test category
            unit_of_measurement: Unit for results
            default_method: Default test method
            description: Optional description
            abbreviations: List of alternative names
            sort_order: Display order within category
            
        Returns:
            Created LabTestType
            
        Raises:
            ValueError: If name already exists or category invalid
        """
        # Check for duplicate name
        existing = db.query(LabTestType).filter(
            func.lower(LabTestType.name) == func.lower(name)
        ).first()
        
        if existing:
            raise ValueError(f"Lab test type '{name}' already exists")
        
        # Validate category
        if category not in LabTestType.CATEGORIES.values():
            raise ValueError(
                f"Invalid category. Must be one of: {list(LabTestType.CATEGORIES.values())}"
            )
        
        # Create test type
        lab_test = LabTestType(
            name=name,
            category=category,
            unit_of_measurement=unit_of_measurement,
            default_method=default_method,
            description=description,
            sort_order=sort_order or 999
        )
        
        if abbreviations:
            lab_test.set_abbreviations_list(abbreviations)
        
        db.add(lab_test)
        db.commit()
        db.refresh(lab_test)
        
        logger.info(f"Created lab test type: {name}")
        return lab_test
    
    def update_lab_test_type(
        self,
        db: Session,
        test_type_id: int,
        **kwargs
    ) -> LabTestType:
        """
        Update lab test type.
        
        Args:
            db: Database session
            test_type_id: Test type ID
            **kwargs: Fields to update
            
        Returns:
            Updated LabTestType
        """
        test_type = self.get(db, test_type_id)
        if not test_type:
            raise ValueError("Lab test type not found")
        
        # Check if renaming to existing name
        if "name" in kwargs and kwargs["name"] != test_type.name:
            existing = db.query(LabTestType).filter(
                func.lower(LabTestType.name) == func.lower(kwargs["name"]),
                LabTestType.id != test_type_id
            ).first()
            
            if existing:
                raise ValueError(f"Lab test type '{kwargs['name']}' already exists")
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(test_type, key):
                setattr(test_type, key, value)
        
        db.commit()
        db.refresh(test_type)
        
        logger.info(f"Updated lab test type: {test_type.name}")
        return test_type
    
    def get_by_category(
        self, 
        db: Session, 
        category: str
    ) -> List[LabTestType]:
        """Get all test types in a category, ordered."""
        return db.query(LabTestType).filter(
            LabTestType.category == category
        ).order_by(
            LabTestType.sort_order,
            LabTestType.name
        ).all()
    
    def get_all_grouped(self, db: Session) -> Dict[str, List[LabTestType]]:
        """
        Get all test types grouped by category.
        
        Returns:
            Dict with category names as keys and lists of test types as values
        """
        all_tests = db.query(LabTestType).order_by(
            LabTestType.category,
            LabTestType.sort_order,
            LabTestType.name
        ).all()
        
        grouped = {}
        for test in all_tests:
            if test.category not in grouped:
                grouped[test.category] = []
            grouped[test.category].append(test)
        
        return grouped
    
    def search_by_name_or_abbreviation(
        self,
        db: Session,
        search_term: str
    ) -> Optional[LabTestType]:
        """
        Find test type by name or abbreviation (useful for PDF parsing).
        
        Args:
            db: Database session
            search_term: Name or abbreviation to search
            
        Returns:
            LabTestType if found, None otherwise
        """
        # Direct name match (case insensitive)
        test = db.query(LabTestType).filter(
            func.lower(LabTestType.name) == func.lower(search_term)
        ).first()
        
        if test:
            return test
        
        # Check abbreviations
        all_tests = db.query(LabTestType).all()
        search_lower = search_term.lower()
        
        for test in all_tests:
            abbrevs = test.get_abbreviations_list()
            if any(search_lower == abbr.lower() for abbr in abbrevs):
                return test
        
        return None
    
    def update_sort_order(
        self,
        db: Session,
        test_type_id: int,
        new_order: int
    ) -> LabTestType:
        """Update display order within category."""
        test_type = self.get(db, test_type_id)
        if not test_type:
            raise ValueError("Lab test type not found")
        
        test_type.sort_order = new_order
        db.commit()
        db.refresh(test_type)
        
        return test_type
    
    def bulk_update_sort_order(
        self,
        db: Session,
        order_map: Dict[int, int]
    ) -> None:
        """
        Update sort order for multiple test types.
        
        Args:
            db: Database session
            order_map: Dict with test_type_id as key and new sort_order as value
        """
        for test_id, new_order in order_map.items():
            test_type = db.query(LabTestType).filter(
                LabTestType.id == test_id
            ).first()
            
            if test_type:
                test_type.sort_order = new_order
        
        db.commit()
        logger.info(f"Updated sort order for {len(order_map)} test types")
    
    def get_categories(self, db: Session) -> List[str]:
        """Get list of all used categories."""
        results = db.query(LabTestType.category).distinct().all()
        return [r[0] for r in results]
    
    def delete_lab_test_type(
        self,
        db: Session,
        test_type_id: int
    ) -> bool:
        """
        Delete lab test type if not in use.
        
        Args:
            db: Database session
            test_type_id: Test type ID
            
        Returns:
            True if deleted
            
        Raises:
            ValueError: If test type is in use by products
        """
        test_type = self.get(db, test_type_id)
        if not test_type:
            raise ValueError("Lab test type not found")
        
        # Check if in use
        if test_type.product_specifications:
            product_count = len(test_type.product_specifications)
            raise ValueError(
                f"Cannot delete: Test type is used by {product_count} products"
            )
        
        db.delete(test_type)
        db.commit()
        
        logger.info(f"Deleted lab test type: {test_type.name}")
        return True
```

### 2.2 Update ProductService (`/src/services/product_service.py`)

Add these methods to existing ProductService:

```python
def set_test_specifications(
    self,
    db: Session,
    product_id: int,
    specifications: List[Dict[str, Any]]
) -> Product:
    """
    Set test specifications for a product.
    
    Args:
        product_id: Product ID
        specifications: List of dicts with:
            - lab_test_type_id: int
            - specification: str (e.g., "< 10")
            - is_required: bool
            - notes: Optional[str]
    
    Returns:
        Updated Product
    """
    from src.models import ProductTestSpecification
    
    product = self.get(db, product_id)
    if not product:
        raise ValueError("Product not found")
    
    # Delete existing specifications
    db.query(ProductTestSpecification).filter(
        ProductTestSpecification.product_id == product_id
    ).delete()
    
    # Add new specifications
    for spec_data in specifications:
        spec = ProductTestSpecification(
            product_id=product_id,
            lab_test_type_id=spec_data["lab_test_type_id"],
            specification=spec_data["specification"],
            is_required=spec_data.get("is_required", True),
            notes=spec_data.get("notes")
        )
        db.add(spec)
    
    db.commit()
    db.refresh(product)
    
    logger.info(f"Updated test specifications for product {product.display_name}")
    return product

def get_product_with_specifications(
    self,
    db: Session,
    product_id: int
) -> Optional[Product]:
    """Get product with all test specifications loaded."""
    from sqlalchemy.orm import joinedload
    
    return db.query(Product).filter(
        Product.id == product_id
    ).options(
        joinedload(Product.test_specifications).joinedload(
            ProductTestSpecification.lab_test_type
        )
    ).first()

def copy_test_specifications(
    self,
    db: Session,
    from_product_id: int,
    to_product_id: int
) -> Product:
    """
    Copy test specifications from one product to another.
    
    Args:
        db: Database session
        from_product_id: Source product ID
        to_product_id: Target product ID
        
    Returns:
        Updated target product
    """
    source = self.get_product_with_specifications(db, from_product_id)
    if not source:
        raise ValueError("Source product not found")
    
    if not source.test_specifications:
        raise ValueError("Source product has no test specifications")
    
    # Copy specifications
    specs = []
    for spec in source.test_specifications:
        specs.append({
            "lab_test_type_id": spec.lab_test_type_id,
            "specification": spec.specification,
            "is_required": spec.is_required,
            "notes": spec.notes
        })
    
    return self.set_test_specifications(db, to_product_id, specs)

def get_missing_required_tests(
    self,
    db: Session,
    product_id: int,
    completed_test_types: List[str]
) -> List[ProductTestSpecification]:
    """
    Get list of required tests that haven't been completed.
    
    Args:
        product_id: Product ID
        completed_test_types: List of test type names already done
        
    Returns:
        List of missing required test specifications
    """
    product = self.get_product_with_specifications(db, product_id)
    if not product:
        return []
    
    completed_lower = [t.lower() for t in completed_test_types]
    
    missing = []
    for spec in product.required_tests:
        if spec.lab_test_type.name.lower() not in completed_lower:
            missing.append(spec)
    
    return missing

def validate_test_result(
    self,
    db: Session,
    product_id: int,
    test_name: str,
    result_value: str
) -> Dict[str, Any]:
    """
    Validate a test result against product specification.
    
    Args:
        db: Database session
        product_id: Product ID
        test_name: Name of the test
        result_value: Test result value
        
    Returns:
        Dict with:
            - passes: bool
            - specification: str
            - is_required: bool
            - notes: str
    """
    product = self.get_product_with_specifications(db, product_id)
    if not product:
        return {
            "passes": True,
            "specification": None,
            "is_required": False,
            "notes": "Product not found"
        }
    
    spec = product.get_specification_for_test(test_name)
    if not spec:
        return {
            "passes": True,
            "specification": None,
            "is_required": False,
            "notes": "No specification for this test"
        }
    
    passes = spec.matches_result(result_value)
    
    return {
        "passes": passes,
        "specification": spec.specification,
        "is_required": spec.is_required,
        "notes": spec.notes
    }
```

### 2.3 Update ApprovalService (`/src/services/approval_service.py`)

Add validation methods:

```python
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
    from src.services.product_service import ProductService
    
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot or not lot.lot_products:
        return {
            "is_complete": False,
            "missing_required": [],
            "present_optional": [],
            "status_recommendation": LotStatus.PENDING
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
        spec.lab_test_type.name for spec in missing_specs
    ]
    
    # Get optional tests that were performed
    present_optional = []
    for test_result in lot.test_results:
        spec = primary_product.get_specification_for_test(test_result.test_type)
        if spec and not spec.is_required:
            present_optional.append(test_result.test_type)
    
    # Determine status recommendation
    if not lot.test_results:
        status_recommendation = LotStatus.PENDING
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
    if lot and lot.status == LotStatus.PENDING:
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
    from src.services.product_service import ProductService
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
```

## Phase 3: UI Implementation

### 3.1 Create Lab Test Types Management Page (`/src/ui/pages/lab_test_types.py`)

```python
"""Lab Test Types management page."""

# NOTE: Originally planned for Streamlit; now implemented in React frontend
from sqlalchemy.orm import Session
import pandas as pd
from src.services.lab_test_type_service import LabTestTypeService
from src.models import LabTestType
from src.ui.components.auth import require_role
from src.models.enums import UserRole


def show(db: Session):
    """Display lab test types management page."""
    
    # Check permissions
    require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
    
    st.title("🧪 Lab Test Types")
    
    # Initialize service
    service = LabTestTypeService()
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["View Test Types", "Add New Test", "Import/Export"])
    
    with tab1:
        view_test_types(db, service)
    
    with tab2:
        add_test_type(db, service)
        
    with tab3:
        import_export_tests(db, service)


def view_test_types(db: Session, service: LabTestTypeService):
    """View and manage existing test types."""
    
    # Get all tests grouped by category
    grouped_tests = service.get_all_grouped(db)
    
    if not grouped_tests:
        st.info("No lab test types defined yet. Add some to get started!")
        return
    
    # Category filter
    categories = ["All"] + list(grouped_tests.keys())
    selected_category = st.selectbox("Filter by Category", categories)
    
    # Search
    search_term = st.text_input("Search test types", placeholder="E.g., E. coli, Lead")
    
    # Display tests
    for category, tests in grouped_tests.items():
        if selected_category != "All" and category != selected_category:
            continue
            
        # Filter by search
        if search_term:
            tests = [t for t in tests if search_term.lower() in t.name.lower()]
            
        if not tests:
            continue
            
        st.subheader(f"📁 {category}")
        
        # Create dataframe
        df_data = []
        for test in tests:
            df_data.append({
                "ID": test.id,
                "Test Name": test.name,
                "Unit": test.unit_of_measurement,
                "Method": test.default_method or "-",
                "Sort Order": test.sort_order
            })
        
        df = pd.DataFrame(df_data)
        
        # Display with edit/delete actions
        col1, col2 = st.columns([4, 1])
        
        with col1:
            st.dataframe(df, hide_index=True, use_container_width=True)
        
        with col2:
            st.write("**Actions**")
            for test in tests:
                col_edit, col_del = st.columns(2)
                
                with col_edit:
                    if st.button("✏️", key=f"edit_{test.id}", help=f"Edit {test.name}"):
                        st.session_state.editing_test_id = test.id
                        st.rerun()
                
                with col_del:
                    if st.button("🗑️", key=f"del_{test.id}", help=f"Delete {test.name}"):
                        if st.session_state.get(f"confirm_delete_{test.id}", False):
                            try:
                                service.delete_lab_test_type(db, test.id)
                                st.success(f"Deleted {test.name}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Cannot delete: {str(e)}")
                        else:
                            st.session_state[f"confirm_delete_{test.id}"] = True
                            st.warning("Click again to confirm deletion")
        
        st.divider()
    
    # Edit modal
    if "editing_test_id" in st.session_state:
        edit_test_modal(db, service, st.session_state.editing_test_id)


def add_test_type(db: Session, service: LabTestTypeService):
    """Add new lab test type."""
    
    st.subheader("Add New Lab Test Type")
    
    with st.form("add_test_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input(
                "Test Name *",
                placeholder="E.g., E. coli, Total Plate Count",
                help="Official name of the test"
            )
            
            category = st.selectbox(
                "Category *",
                options=list(LabTestType.CATEGORIES.values()),
                help="Test category for grouping"
            )
            
            unit = st.selectbox(
                "Unit of Measurement *",
                options=list(LabTestType.UNITS.values()),
                help="How results are measured"
            )
        
        with col2:
            method = st.text_input(
                "Default Method",
                placeholder="E.g., USP <2021>, AOAC 991.14",
                help="Standard test method (optional)"
            )
            
            # Abbreviations
            abbrev_input = st.text_area(
                "Alternative Names/Abbreviations",
                placeholder="One per line\nE.g., for E. coli:\nE.coli\nEscherichia coli\nE coli",
                help="Alternative names for PDF parsing"
            )
            
            sort_order = st.number_input(
                "Sort Order",
                min_value=1,
                max_value=999,
                value=99,
                help="Display order within category (lower = first)"
            )
        
        description = st.text_area(
            "Description",
            placeholder="Optional description or notes about this test",
            help="Additional information about the test"
        )
        
        submitted = st.form_submit_button("Add Test Type", type="primary")
        
        if submitted:
            if not name:
                st.error("Test name is required")
            else:
                try:
                    # Parse abbreviations
                    abbreviations = None
                    if abbrev_input:
                        abbreviations = [
                            line.strip() 
                            for line in abbrev_input.split('\n') 
                            if line.strip()
                        ]
                    
                    # Create test type
                    test_type = service.create_lab_test_type(
                        db=db,
                        name=name,
                        category=category,
                        unit_of_measurement=unit,
                        default_method=method,
                        description=description,
                        abbreviations=abbreviations,
                        sort_order=sort_order
                    )
                    
                    st.success(f"✅ Added lab test type: {name}")
                    st.balloons()
                    
                    # Clear form
                    st.rerun()
                    
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Error adding test type: {str(e)}")


def edit_test_modal(db: Session, service: LabTestTypeService, test_id: int):
    """Edit test type in modal."""
    
    @st.dialog("Edit Lab Test Type")
    def edit_dialog():
        test = service.get(db, test_id)
        if not test:
            st.error("Test type not found")
            return
        
        with st.form("edit_test_form"):
            name = st.text_input("Test Name *", value=test.name)
            
            category = st.selectbox(
                "Category *",
                options=list(LabTestType.CATEGORIES.values()),
                index=list(LabTestType.CATEGORIES.values()).index(test.category)
            )
            
            unit = st.selectbox(
                "Unit of Measurement *",
                options=list(LabTestType.UNITS.values()),
                index=list(LabTestType.UNITS.values()).index(test.unit_of_measurement)
                if test.unit_of_measurement in LabTestType.UNITS.values() else 0
            )
            
            method = st.text_input(
                "Default Method",
                value=test.default_method or ""
            )
            
            # Load abbreviations
            abbrev_text = ""
            abbrevs = test.get_abbreviations_list()
            if abbrevs:
                abbrev_text = "\n".join(abbrevs)
            
            abbrev_input = st.text_area(
                "Alternative Names/Abbreviations",
                value=abbrev_text
            )
            
            sort_order = st.number_input(
                "Sort Order",
                min_value=1,
                max_value=999,
                value=test.sort_order
            )
            
            description = st.text_area(
                "Description",
                value=test.description or ""
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.form_submit_button("Save Changes", type="primary"):
                    try:
                        # Parse abbreviations
                        abbreviations = None
                        if abbrev_input:
                            abbreviations = [
                                line.strip() 
                                for line in abbrev_input.split('\n') 
                                if line.strip()
                            ]
                        
                        # Update test type
                        service.update_lab_test_type(
                            db=db,
                            test_type_id=test_id,
                            name=name,
                            category=category,
                            unit_of_measurement=unit,
                            default_method=method,
                            description=description,
                            sort_order=sort_order
                        )
                        
                        # Update abbreviations
                        test.set_abbreviations_list(abbreviations)
                        db.commit()
                        
                        st.success("Updated successfully!")
                        del st.session_state.editing_test_id
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error updating: {str(e)}")
            
            with col2:
                if st.form_submit_button("Cancel"):
                    del st.session_state.editing_test_id
                    st.rerun()
    
    edit_dialog()


def import_export_tests(db: Session, service: LabTestTypeService):
    """Import/export lab test types."""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Export Test Types")
        
        if st.button("📥 Export to Excel", use_container_width=True):
            # Get all tests
            all_tests = db.query(LabTestType).order_by(
                LabTestType.category,
                LabTestType.sort_order
            ).all()
            
            if all_tests:
                # Create dataframe
                df_data = []
                for test in all_tests:
                    # Get abbreviations
                    abbrevs = test.get_abbreviations_list()
                    abbrev_str = "; ".join(abbrevs) if abbrevs else ""
                    
                    df_data.append({
                        "Name": test.name,
                        "Category": test.category,
                        "Unit": test.unit_of_measurement,
                        "Method": test.default_method or "",
                        "Abbreviations": abbrev_str,
                        "Sort Order": test.sort_order,
                        "Description": test.description or ""
                    })
                
                df = pd.DataFrame(df_data)
                
                # Export
                import io
                buffer = io.BytesIO()
                df.to_excel(buffer, index=False)
                
                st.download_button(
                    label="Download Excel",
                    data=buffer.getvalue(),
                    file_name="lab_test_types.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("No test types to export")
    
    with col2:
        st.subheader("Import Test Types")
        
        uploaded_file = st.file_uploader(
            "Choose Excel file",
            type=["xlsx", "xls"],
            help="File should have columns: Name, Category, Unit, Method, Abbreviations, Sort Order, Description"
        )
        
        if uploaded_file:
            try:
                df = pd.read_excel(uploaded_file)
                
                st.write("Preview:")
                st.dataframe(df.head(), use_container_width=True)
                
                if st.button("Import Test Types", type="primary"):
                    imported = 0
                    errors = []
                    
                    for _, row in df.iterrows():
                        try:
                            # Parse abbreviations
                            abbreviations = None
                            if pd.notna(row.get("Abbreviations")):
                                abbreviations = [
                                    a.strip() 
                                    for a in str(row["Abbreviations"]).split(";")
                                    if a.strip()
                                ]
                            
                            service.create_lab_test_type(
                                db=db,
                                name=row["Name"],
                                category=row["Category"],
                                unit_of_measurement=row["Unit"],
                                default_method=row.get("Method") if pd.notna(row.get("Method")) else None,
                                description=row.get("Description") if pd.notna(row.get("Description")) else None,
                                abbreviations=abbreviations,
                                sort_order=int(row.get("Sort Order", 99))
                            )
                            imported += 1
                            
                        except Exception as e:
                            errors.append(f"{row['Name']}: {str(e)}")
                    
                    st.success(f"✅ Imported {imported} test types")
                    
                    if errors:
                        with st.expander("Import Errors"):
                            for error in errors:
                                st.error(error)
                    
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
```

### 3.2 Update Product Management (`/src/ui/pages/products.py`)

Add test specifications tab to create/edit product:

```python
def product_form(db: Session, product: Optional[Product] = None):
    """Enhanced product form with test specifications."""
    
    # ... existing form fields ...
    
    # Add new tab for test specifications
    tab1, tab2, tab3 = st.tabs(["Product Info", "Test Specifications", "Preview"])
    
    with tab1:
        # ... existing product fields ...
        pass
    
    with tab2:
        show_test_specifications(db, product)
    
    with tab3:
        show_product_preview(db, product)


def show_test_specifications(db: Session, product: Optional[Product]):
    """Manage test specifications for a product."""
    
    from src.services.lab_test_type_service import LabTestTypeService
    
    st.subheader("Test Specifications")
    
    service = LabTestTypeService()
    grouped_tests = service.get_all_grouped(db)
    
    if not grouped_tests:
        st.warning("No lab test types defined. Please add test types first.")
        return
    
    # Initialize session state for specifications
    if "product_test_specs" not in st.session_state:
        if product and product.test_specifications:
            # Load existing specifications
            st.session_state.product_test_specs = []
            for spec in product.test_specifications:
                st.session_state.product_test_specs.append({
                    "lab_test_type_id": spec.lab_test_type_id,
                    "test_name": spec.lab_test_type.name,
                    "category": spec.lab_test_type.category,
                    "unit": spec.lab_test_type.unit_of_measurement,
                    "specification": spec.specification,
                    "is_required": spec.is_required,
                    "notes": spec.notes or ""
                })
        else:
            st.session_state.product_test_specs = []
    
    # Add test interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Category selector
        selected_category = st.selectbox(
            "Select Test Category",
            options=list(grouped_tests.keys()),
            key="add_test_category"
        )
        
        # Test selector
        if selected_category:
            tests_in_category = grouped_tests[selected_category]
            test_options = {
                f"{test.name} ({test.unit_of_measurement})": test 
                for test in tests_in_category
            }
            
            selected_test = st.selectbox(
                "Select Test",
                options=list(test_options.keys()),
                key="add_test_select"
            )
    
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        if st.button("➕ Add Test", use_container_width=True):
            if selected_test:
                test = test_options[selected_test]
                
                # Check if already added
                existing_ids = [s["lab_test_type_id"] for s in st.session_state.product_test_specs]
                if test.id not in existing_ids:
                    st.session_state.product_test_specs.append({
                        "lab_test_type_id": test.id,
                        "test_name": test.name,
                        "category": test.category,
                        "unit": test.unit_of_measurement,
                        "specification": "",
                        "is_required": True,
                        "notes": ""
                    })
                    st.rerun()
                else:
                    st.warning("Test already added")
    
    # Display current specifications
    if st.session_state.product_test_specs:
        st.divider()
        st.write("**Configured Test Specifications:**")
        
        # Group by category for display
        specs_by_category = {}
        for spec in st.session_state.product_test_specs:
            category = spec["category"]
            if category not in specs_by_category:
                specs_by_category[category] = []
            specs_by_category[category].append(spec)
        
        for category, specs in specs_by_category.items():
            st.write(f"**{category}**")
            
            for i, spec in enumerate(specs):
                # Find index in full list
                full_index = st.session_state.product_test_specs.index(spec)
                
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 2, 1])
                    
                    with col1:
                        st.text_input(
                            "Test",
                            value=f"{spec['test_name']} ({spec['unit']})",
                            disabled=True,
                            key=f"test_display_{full_index}"
                        )
                    
                    with col2:
                        new_spec = st.text_input(
                            "Specification",
                            value=spec["specification"],
                            placeholder=f"e.g., < 10, Negative",
                            key=f"spec_input_{full_index}",
                            help="Enter the acceptance criteria"
                        )
                        st.session_state.product_test_specs[full_index]["specification"] = new_spec
                    
                    with col3:
                        is_req = st.checkbox(
                            "Required",
                            value=spec["is_required"],
                            key=f"req_check_{full_index}"
                        )
                        st.session_state.product_test_specs[full_index]["is_required"] = is_req
                    
                    with col4:
                        notes = st.text_input(
                            "Notes",
                            value=spec["notes"],
                            placeholder="Optional notes",
                            key=f"notes_input_{full_index}"
                        )
                        st.session_state.product_test_specs[full_index]["notes"] = notes
                    
                    with col5:
                        if st.button("🗑️", key=f"remove_spec_{full_index}"):
                            st.session_state.product_test_specs.pop(full_index)
                            st.rerun()
            
            st.write("")  # Spacing
        
        # Summary
        st.divider()
        required_count = sum(1 for s in st.session_state.product_test_specs if s["is_required"])
        optional_count = len(st.session_state.product_test_specs) - required_count
        
        st.info(f"**Summary:** {required_count} required tests, {optional_count} optional tests")
    
    else:
        st.info("No test specifications configured yet. Add tests above.")


def save_product_with_specifications(db: Session, product_data: dict, specifications: list):
    """Save product and its test specifications."""
    
    from src.services.product_service import ProductService
    
    service = ProductService()
    
    # Create/update product
    if product_data.get("id"):
        # Update existing
        product = service.update(db, product_data["id"], product_data)
    else:
        # Create new
        product = service.create(db, product_data)
    
    # Save specifications
    spec_data = []
    for spec in specifications:
        if spec["specification"]:  # Only save if specification is provided
            spec_data.append({
                "lab_test_type_id": spec["lab_test_type_id"],
                "specification": spec["specification"],
                "is_required": spec["is_required"],
                "notes": spec["notes"] if spec["notes"] else None
            })
    
    if spec_data:
        service.set_test_specifications(db, product.id, spec_data)
    
    return product
```

### 3.3 Update Product Catalog View Modal (`/src/ui/pages/products.py`)

Add click handler and modal:

```python
def view_products(db: Session, product_service: ProductService):
    """Enhanced product catalog with test specification modal."""
    
    # ... existing code ...
    
    # Make table clickable
    selected_product_id = None
    
    if not products_df.empty:
        # Add selection column
        products_df.insert(0, "Select", False)
        
        edited_df = st.data_editor(
            products_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Select": st.column_config.CheckboxColumn(
                    "View",
                    help="Click to view test specifications",
                    default=False,
                    width="small"
                )
            },
            disabled=[col for col in products_df.columns if col != "Select"],
            key="product_catalog_selection"
        )
        
        # Check for selection
        selected_rows = edited_df[edited_df["Select"]]
        if not selected_rows.empty:
            selected_product_id = selected_rows.iloc[0]["id"]
    
    # Show modal if product selected
    if selected_product_id:
        show_product_test_specs_modal(db, selected_product_id)


def show_product_test_specs_modal(db: Session, product_id: int):
    """Show product test specifications in modal."""
    
    from src.services.product_service import ProductService
    
    @st.dialog("Product Test Specifications", width="large")
    def specs_dialog():
        service = ProductService()
        product = service.get_product_with_specifications(db, product_id)
        
        if not product:
            st.error("Product not found")
            return
        
        # Product header
        st.subheader(product.display_name)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Brand:** {product.brand}")
        with col2:
            st.write(f"**SKU:** {product.sku}")
        with col3:
            st.write(f"**Status:** {product.status}")
        
        st.divider()
        
        # Test specifications
        if product.test_specifications:
            # Separate required and optional
            required_specs = [s for s in product.test_specifications if s.is_required]
            optional_specs = [s for s in product.test_specifications if not s.is_required]
            
            # Required tests
            if required_specs:
                st.write("### ✅ Required Tests")
                
                req_data = []
                for spec in required_specs:
                    req_data.append({
                        "Test": spec.lab_test_type.name,
                        "Category": spec.lab_test_type.category,
                        "Specification": spec.specification,
                        "Unit": spec.lab_test_type.unit_of_measurement,
                        "Method": spec.lab_test_type.default_method or "-",
                        "Notes": spec.notes or "-"
                    })
                
                req_df = pd.DataFrame(req_data)
                st.dataframe(req_df, hide_index=True, use_container_width=True)
            
            # Optional tests
            if optional_specs:
                st.write("### ℹ️ Optional Tests")
                
                opt_data = []
                for spec in optional_specs:
                    opt_data.append({
                        "Test": spec.lab_test_type.name,
                        "Category": spec.lab_test_type.category,
                        "Specification": spec.specification,
                        "Unit": spec.lab_test_type.unit_of_measurement,
                        "Method": spec.lab_test_type.default_method or "-",
                        "Notes": spec.notes or "-"
                    })
                
                opt_df = pd.DataFrame(opt_data)
                st.dataframe(opt_df, hide_index=True, use_container_width=True)
            
            # Summary
            st.divider()
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Tests", len(product.test_specifications))
            with col2:
                st.metric("Required", len(required_specs))
            with col3:
                st.metric("Optional", len(optional_specs))
        
        else:
            st.info("No test specifications configured for this product")
        
        # Actions
        st.divider()
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col2:
            if st.button("Edit Product", use_container_width=True):
                st.session_state.editing_product_id = product_id
                st.rerun()
        
        with col3:
            if st.button("Close", type="primary", use_container_width=True):
                st.rerun()
    
    specs_dialog()
```

## Phase 4: Update Approval Dashboard

### 4.1 Enhanced Approval Dashboard (`/src/ui/pages/approvals.py`)

Update to show missing tests:

```python
def show_pending_approvals(db: Session, approval_service: ApprovalService):
    """Enhanced approval dashboard with missing test indicators."""
    
    # ... existing code ...
    
    # In the lot card display section:
    with col3:
        # Check test completeness
        completeness = approval_service.check_test_completeness(db, lot.id)
        
        if completeness["is_complete"]:
            st.success("✓ All Required Tests Present")
        else:
            st.error(f"⚠️ Missing {len(completeness['missing_required'])} Required Tests")
            
            # Show missing tests
            if st.button("View Missing", key=f"missing_{lot.id}"):
                @st.dialog("Missing Required Tests")
                def show_missing():
                    st.write(f"**Lot:** {lot.lot_number}")
                    st.write("**Missing Required Tests:**")
                    
                    for test_name in completeness["missing_required"]:
                        st.write(f"• {test_name}")
                    
                    st.info(
                        "These tests must be completed before this lot can be approved. "
                        "Upload additional test results or contact the lab."
                    )
                    
                    if st.button("Close"):
                        st.rerun()
                
                show_missing()
    
    # Update status display
    with col4:
        if lot.status == LotStatus.PARTIAL_RESULTS:
            st.warning("⚠️ PARTIAL RESULTS")
        elif lot.status == LotStatus.UNDER_REVIEW:
            st.info("🔵 UNDER REVIEW")
        else:
            st.metric("Status", lot.status.value)
    
    # In the approval button section:
    if st.button("✅ APPROVE LOT", ...):
        # Validate before approval
        validation = approval_service.validate_lot_for_approval(db, lot.id)
        
        if not validation["can_approve"]:
            st.error("Cannot approve lot:")
            for issue in validation["issues"]:
                st.error(f"• {issue}")
        else:
            # Show warnings if any
            if validation["warnings"]:
                for warning in validation["warnings"]:
                    st.warning(f"ℹ️ {warning}")
            
            # ... existing approval logic ...
```

### 4.2 Update Dashboard Metrics (`/src/ui/pages/dashboard.py`)

Add PARTIAL_RESULTS to status metrics:

```python
# In the status counts section:
status_counts = {
    "Pending": db.query(Lot).filter_by(status=LotStatus.PENDING).count(),
    "Partial Results": db.query(Lot).filter_by(status=LotStatus.PARTIAL_RESULTS).count(),
    "Under Review": db.query(Lot).filter_by(status=LotStatus.UNDER_REVIEW).count(),
    "Approved": db.query(Lot).filter_by(status=LotStatus.APPROVED).count(),
    "Released": db.query(Lot).filter_by(status=LotStatus.RELEASED).count(),
}

# Color mapping
status_colors = {
    "Pending": "#808080",
    "Partial Results": "#FFA500",  # Orange/Amber
    "Under Review": "#4169E1",     # Blue
    "Approved": "#32CD32",         # Green
    "Released": "#228B22",         # Dark Green
}
```

## Phase 5: Update Status Transitions

### 5.1 Update Lot Model (`/src/models/lot.py`)

```python
# Update valid transitions
valid_transitions = {
    LotStatus.PENDING: [LotStatus.PARTIAL_RESULTS, LotStatus.UNDER_REVIEW, LotStatus.REJECTED],
    LotStatus.PARTIAL_RESULTS: [LotStatus.UNDER_REVIEW, LotStatus.REJECTED],
    LotStatus.UNDER_REVIEW: [LotStatus.APPROVED, LotStatus.REJECTED],
    LotStatus.APPROVED: [LotStatus.RELEASED, LotStatus.REJECTED],
    LotStatus.RELEASED: [],  # Terminal state
    LotStatus.REJECTED: [LotStatus.PENDING],  # Can retry
}
```

### 5.2 Update PDF Parser Service

When creating test results, check completeness:

```python
# In create_test_results_from_parsing():
# After creating all test results...

# Update lot status based on completeness
approval_service = ApprovalService()
approval_service.update_lot_status_after_results(db, lot_id)
```

### 5.3 Update Manual Test Entry

If you have manual test result entry, update status after saving:

```python
# After saving test result
approval_service = ApprovalService()
approval_service.update_lot_status_after_results(db, test_result.lot_id)
```

## Phase 6: Menu Updates

### 6.1 Update Navigation (`/src/ui/components/navigation.py` or main app)

Add new menu item:

```python
# In menu configuration
menu_items = {
    # ... existing items ...
    "Lab Management": {
        "icon": "🧪",
        "items": {
            "Lab Test Types": lab_test_types_page,
            "Test Methods": test_methods_page,  # Future
        }
    }
}

# Or in the main app entry point
if page == "Lab Test Types":
    from src.ui.pages import lab_test_types
    lab_test_types.show(db)
```

## Phase 7: Database Migrations

### 7.1 Create Alembic Migration

```bash
alembic revision -m "add_lab_test_types_and_product_specifications"
```

Migration file content:

```python
"""add lab test types and product specifications

Revision ID: xxx
Revises: yyy
Create Date: 2025-08-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Create lab_test_types table
    op.create_table(
        'lab_test_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('unit_of_measurement', sa.String(50), nullable=False),
        sa.Column('default_method', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('abbreviations', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), default=999),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create indexes
    op.create_index('idx_lab_test_name', 'lab_test_types', ['name'])
    op.create_index('idx_lab_test_category', 'lab_test_types', ['category'])
    op.create_index('idx_lab_test_category_order', 'lab_test_types', ['category', 'sort_order'])
    
    # Create product_test_specifications table
    op.create_table(
        'product_test_specifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('lab_test_type_id', sa.Integer(), nullable=False),
        sa.Column('specification', sa.String(100), nullable=False),
        sa.Column('is_required', sa.Boolean(), default=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('min_value', sa.String(20), nullable=True),
        sa.Column('max_value', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.ForeignKeyConstraint(['lab_test_type_id'], ['lab_test_types.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'lab_test_type_id')
    )
    
    # Update lot_status enum (PostgreSQL specific)
    # For PostgreSQL:
    op.execute("ALTER TYPE lotstatus ADD VALUE 'partial_results' AFTER 'pending'")
    
    # For SQLite (requires recreation):
    # This is more complex for SQLite as it doesn't support ALTER TYPE

def downgrade():
    op.drop_table('product_test_specifications')
    op.drop_table('lab_test_types')
    # Note: Removing enum values is complex in PostgreSQL
```

### 7.2 SQLite Migration Alternative

For SQLite, you need to recreate the table:

```python
def upgrade():
    # ... create other tables ...
    
    # For SQLite - recreate lots table with new enum
    # 1. Rename old table
    op.rename_table('lots', 'lots_old')
    
    # 2. Create new table with updated enum
    op.create_table(
        'lots',
        # ... all columns ...
        sa.Column('status', sa.Enum('pending', 'partial_results', 'under_review', 
                                   'approved', 'released', 'rejected', 
                                   name='lotstatus'), nullable=False),
        # ... rest of columns ...
    )
    
    # 3. Copy data
    op.execute("""
        INSERT INTO lots 
        SELECT * FROM lots_old
    """)
    
    # 4. Drop old table
    op.drop_table('lots_old')
```

## Phase 8: Seed Data

### 8.1 Create Initial Lab Test Types (`/src/data/seed_lab_tests.py`)

```python
"""Seed lab test types data."""

from sqlalchemy.orm import Session
from src.services.lab_test_type_service import LabTestTypeService


def seed_lab_test_types(db: Session):
    """Seed common lab test types."""
    
    service = LabTestTypeService()
    
    test_data = [
        # Microbiological Tests
        {
            "name": "Total Plate Count",
            "category": "Microbiological",
            "unit": "CFU/g",
            "method": "FDA BAM Chapter 3",
            "abbreviations": ["TPC", "APC", "Aerobic Plate Count", "Standard Plate Count"],
            "sort_order": 10,
            "description": "Total aerobic microbial count"
        },
        {
            "name": "E. coli",
            "category": "Microbiological", 
            "unit": "Positive/Negative",
            "method": "AOAC 991.14",
            "abbreviations": ["E.coli", "Escherichia coli", "E coli"],
            "sort_order": 20,
            "description": "Pathogenic E. coli detection"
        },
        {
            "name": "Salmonella",
            "category": "Microbiological",
            "unit": "Positive/Negative",
            "method": "FDA BAM Chapter 5",
            "abbreviations": ["Salmonella spp.", "Salmonella species"],
            "sort_order": 30,
            "description": "Salmonella species detection"
        },
        {
            "name": "Yeast and Mold",
            "category": "Microbiological",
            "unit": "CFU/g",
            "method": "FDA BAM Chapter 18",
            "abbreviations": ["Y&M", "Yeast/Mold", "Yeast & Mold", "Yeasts and Molds"],
            "sort_order": 40,
            "description": "Combined yeast and mold count"
        },
        {
            "name": "Staphylococcus aureus",
            "category": "Microbiological",
            "unit": "CFU/g",
            "method": "FDA BAM Chapter 12",
            "abbreviations": ["S. aureus", "Staph aureus", "Staph"],
            "sort_order": 50
        },
        {
            "name": "Total Coliform Count",
            "category": "Microbiological",
            "unit": "CFU/g",
            "method": "FDA BAM Chapter 4",
            "abbreviations": ["Coliforms", "Total Coliforms"],
            "sort_order": 60
        },
        
        # Heavy Metals
        {
            "name": "Lead",
            "category": "Heavy Metals",
            "unit": "ppm",
            "method": "AOAC 2015.01",
            "abbreviations": ["Pb", "Lead (Pb)"],
            "sort_order": 10,
            "description": "Lead content"
        },
        {
            "name": "Arsenic",
            "category": "Heavy Metals",
            "unit": "ppm", 
            "method": "AOAC 2015.01",
            "abbreviations": ["As", "Arsenic (As)"],
            "sort_order": 20,
            "description": "Arsenic content"
        },
        {
            "name": "Cadmium",
            "category": "Heavy Metals",
            "unit": "ppm",
            "method": "AOAC 2015.01",
            "abbreviations": ["Cd", "Cadmium (Cd)"],
            "sort_order": 30,
            "description": "Cadmium content"
        },
        {
            "name": "Mercury",
            "category": "Heavy Metals",
            "unit": "ppm",
            "method": "AOAC 2015.01",
            "abbreviations": ["Hg", "Mercury (Hg)"],
            "sort_order": 40,
            "description": "Mercury content"
        },
        
        # Allergens
        {
            "name": "Gluten",
            "category": "Allergens",
            "unit": "ppm",
            "method": "AOAC 2012.01",
            "abbreviations": ["Gliadin", "Gluten Content"],
            "sort_order": 10,
            "description": "Gluten/gliadin content"
        },
        {
            "name": "Milk Allergen",
            "category": "Allergens",
            "unit": "ppm",
            "method": "ELISA",
            "abbreviations": ["Milk", "Dairy", "Casein", "Whey"],
            "sort_order": 20
        },
        {
            "name": "Soy Allergen",
            "category": "Allergens",
            "unit": "ppm",
            "method": "ELISA",
            "abbreviations": ["Soy", "Soya", "Soybean"],
            "sort_order": 30
        },
        
        # Nutritional
        {
            "name": "Protein",
            "category": "Nutritional",
            "unit": "%",
            "method": "AOAC 992.15",
            "abbreviations": ["Crude Protein", "Total Protein"],
            "sort_order": 10,
            "description": "Total protein content"
        },
        {
            "name": "Fat",
            "category": "Nutritional",
            "unit": "%",
            "method": "AOAC 922.06",
            "abbreviations": ["Total Fat", "Crude Fat", "Lipids"],
            "sort_order": 20
        },
        {
            "name": "Moisture",
            "category": "Nutritional",
            "unit": "%",
            "method": "AOAC 925.10",
            "abbreviations": ["Water Content", "Water", "Moisture Content"],
            "sort_order": 30
        },
        {
            "name": "Ash",
            "category": "Nutritional",
            "unit": "%",
            "method": "AOAC 923.03",
            "abbreviations": ["Total Ash", "Mineral Content"],
            "sort_order": 40
        },
        
        # Chemical
        {
            "name": "Aflatoxin",
            "category": "Chemical",
            "unit": "ppb",
            "method": "AOAC 991.31",
            "abbreviations": ["Aflatoxins", "Total Aflatoxins"],
            "sort_order": 10
        },
        {
            "name": "Pesticide Residues",
            "category": "Chemical",
            "unit": "ppm",
            "method": "AOAC 2007.01",
            "abbreviations": ["Pesticides", "Multi-Residue Pesticides"],
            "sort_order": 20
        },
        {
            "name": "Glyphosate",
            "category": "Chemical",
            "unit": "ppm",
            "method": "LC-MS/MS",
            "abbreviations": ["Glyphosate Residue"],
            "sort_order": 30
        },
        
        # Physical
        {
            "name": "Particle Size",
            "category": "Physical",
            "unit": "mesh",
            "method": "USP <786>",
            "abbreviations": ["Mesh Size", "Granulation"],
            "sort_order": 10
        },
        {
            "name": "Bulk Density",
            "category": "Physical",
            "unit": "g/mL",
            "method": "USP <616>",
            "abbreviations": ["Density", "Bulk Density"],
            "sort_order": 20
        }
    ]
    
    created_count = 0
    
    for test in test_data:
        try:
            service.create_lab_test_type(db, **test)
            print(f"✓ Created test type: {test['name']}")
            created_count += 1
        except ValueError as e:
            print(f"- Skipped {test['name']}: {e}")
        except Exception as e:
            print(f"✗ Error creating {test['name']}: {e}")
    
    print(f"\nCreated {created_count} lab test types")
    return created_count


def seed_sample_product_specifications(db: Session):
    """Create sample product specifications for demo products."""
    
    from src.services.product_service import ProductService
    from src.services.lab_test_type_service import LabTestTypeService
    
    product_service = ProductService()
    test_service = LabTestTypeService()
    
    # Get sample product (Organic Whey Protein)
    products = product_service.get_multi(db, skip=0, limit=10)
    whey_product = next((p for p in products if "Whey" in p.product_name), None)
    
    if not whey_product:
        print("No whey protein product found for demo specs")
        return
    
    # Define specifications for whey protein
    whey_specs = [
        # Required Microbiological
        ("E. coli", "Negative", True),
        ("Salmonella", "Negative", True),
        ("Total Plate Count", "< 10,000", True),
        ("Yeast and Mold", "< 1,000", True),
        ("Staphylococcus aureus", "< 10", True),
        
        # Required Heavy Metals
        ("Lead", "< 0.5", True),
        ("Arsenic", "< 1.0", True),
        ("Cadmium", "< 0.3", True),
        ("Mercury", "< 0.1", True),
        
        # Optional Tests
        ("Gluten", "< 20", False),  # Optional for allergen-free claim
        ("Protein", "> 80", False),  # Optional nutritional verification
    ]
    
    # Create specifications
    spec_data = []
    for test_name, spec, is_required in whey_specs:
        test_type = test_service.search_by_name_or_abbreviation(db, test_name)
        if test_type:
            spec_data.append({
                "lab_test_type_id": test_type.id,
                "specification": spec,
                "is_required": is_required,
                "notes": "Standard specification" if is_required else "Optional - test as needed"
            })
    
    if spec_data:
        product_service.set_test_specifications(db, whey_product.id, spec_data)
        print(f"✓ Created {len(spec_data)} test specifications for {whey_product.display_name}")


if __name__ == "__main__":
    from src.database import SessionLocal
    
    db = SessionLocal()
    try:
        seed_lab_test_types(db)
        seed_sample_product_specifications(db)
    finally:
        db.close()
```

## Testing Plan

### Unit Tests

Create test files for new functionality:

```python
# tests/test_lab_test_types.py
import pytest
from src.models import LabTestType
from src.services.lab_test_type_service import LabTestTypeService


def test_create_lab_test_type(test_db):
    """Test creating a lab test type."""
    service = LabTestTypeService()
    
    test_type = service.create_lab_test_type(
        db=test_db,
        name="Test E. coli",
        category="Microbiological",
        unit_of_measurement="CFU/g",
        default_method="Test Method",
        abbreviations=["E.coli", "E coli"]
    )
    
    assert test_type.id is not None
    assert test_type.name == "Test E. coli"
    assert test_type.get_abbreviations_list() == ["E.coli", "E coli"]


def test_search_by_abbreviation(test_db):
    """Test searching by abbreviation."""
    service = LabTestTypeService()
    
    # Create test type
    service.create_lab_test_type(
        db=test_db,
        name="Escherichia coli",
        category="Microbiological",
        unit_of_measurement="CFU/g",
        abbreviations=["E.coli", "E coli"]
    )
    
    # Search by abbreviation
    found = service.search_by_name_or_abbreviation(test_db, "E.coli")
    assert found is not None
    assert found.name == "Escherichia coli"


# tests/test_product_specifications.py
def test_product_test_specifications(test_db, sample_product):
    """Test product test specifications."""
    from src.services.product_service import ProductService
    
    service = ProductService()
    
    # Create test types first
    # ... create test types ...
    
    # Set specifications
    specs = [
        {
            "lab_test_type_id": 1,
            "specification": "< 10",
            "is_required": True,
            "notes": "Standard limit"
        }
    ]
    
    updated = service.set_test_specifications(
        test_db,
        sample_product.id,
        specs
    )
    
    assert len(updated.test_specifications) == 1
    assert updated.required_tests[0].specification == "< 10"


# tests/test_approval_completeness.py
def test_check_test_completeness(test_db):
    """Test checking test completeness."""
    from src.services.approval_service import ApprovalService
    
    service = ApprovalService()
    
    # Create lot with product that has required tests
    # ... setup ...
    
    # Check completeness
    result = service.check_test_completeness(test_db, lot_id)
    
    assert not result["is_complete"]
    assert len(result["missing_required"]) > 0
    assert result["status_recommendation"] == LotStatus.PARTIAL_RESULTS
```

### Integration Testing Checklist

1. **Lab Test Type Management**
   - [ ] Create new test type
   - [ ] Edit existing test type
   - [ ] Delete unused test type
   - [ ] Prevent deletion of in-use test type
   - [ ] Import/export test types

2. **Product Test Specifications**
   - [ ] Add test specifications to new product
   - [ ] Edit specifications on existing product
   - [ ] Copy specifications between products
   - [ ] View specifications in catalog modal
   - [ ] Required vs optional designation

3. **Approval Workflow**
   - [ ] Upload PDF with partial results → PARTIAL_RESULTS status
   - [ ] Upload remaining results → UNDER_REVIEW status
   - [ ] Block approval when missing required tests
   - [ ] Allow approval when all required tests present
   - [ ] Show warnings for optional tests

4. **Status Transitions**
   - [ ] PENDING → PARTIAL_RESULTS
   - [ ] PARTIAL_RESULTS → UNDER_REVIEW
   - [ ] UNDER_REVIEW → APPROVED
   - [ ] Rejection at any stage

5. **UI/UX Testing**
   - [ ] Test specifications display correctly
   - [ ] Missing tests clearly indicated
   - [ ] Status colors are distinct
   - [ ] Modal interactions work smoothly

### Manual Testing Script

```markdown
## Manual Testing Script for Lab Test Types Feature

### Setup
1. Run database migrations
2. Seed lab test types
3. Create test product with specifications

### Test 1: Lab Test Type Management
1. Navigate to Lab Management → Lab Test Types
2. Add new test type "Alpha Tox