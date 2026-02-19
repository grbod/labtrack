# LabTrack Database Models

This directory contains all SQLAlchemy database models for the LabTrack.

## Models Overview

### base.py
- `BaseModel`: Abstract base class with common fields (id, created_at, updated_at)
- Provides automatic table naming and common methods

### enums.py
Database enum types:
- `UserRole`: admin, qc_manager, lab_tech, read_only
- `LotType`: standard, parent_lot, multi_sku_composite  
- `LotStatus`: pending, tested, approved, released
- `TestResultStatus`: draft, reviewed, approved
- `ParsingStatus`: pending, processing, resolved, failed
- `AuditAction`: insert, update, delete, approve, reject

### product.py
- `Product`: Standardized product catalog with brand, name, flavor, size

### lot.py
- `Lot`: Main lots including parent lots and composites
- `Sublot`: Production sublots under parent lots
- `LotProduct`: Association table linking lots to products with percentages

### user.py
- `User`: System users with role-based access control

### test_result.py
- `TestResult`: Lab test results with approval workflow and confidence scoring

### audit.py
- `AuditLog`: Complete audit trail of all system changes

### parsing.py
- `ParsingQueue`: PDF parsing queue for manual review of failed extractions

### coa.py
- `COAHistory`: History of all generated COAs with metadata

## Key Features

1. **Comprehensive Relationships**: All models are properly related with foreign keys
2. **Data Validation**: Built-in validators for data integrity
3. **Performance Indexes**: Strategic indexes on commonly queried fields
4. **Audit Trail**: Complete tracking of all changes for compliance
5. **Approval Workflow**: Multi-stage approval process for test results
6. **Enum Types**: Type-safe enumerations for status fields

## Usage Example

```python
from src.models import Product, Lot, TestResult, User
from src.models.enums import LotType, TestResultStatus

# Create a product
product = Product(
    brand="Truvani",
    product_name="Organic Whey Protein",
    flavor="Vanilla",
    size="2.5 lbs",
    display_name="Truvani Organic Whey Protein - Vanilla"
)

# Create a lot
lot = Lot(
    lot_number="ABC123",
    lot_type=LotType.STANDARD,
    reference_number="REF-001",
    generate_coa=True
)

# Create test results
test_result = TestResult(
    lot_id=lot.id,
    test_type="Total Plate Count",
    result_value="<10",
    unit="CFU/g",
    status=TestResultStatus.DRAFT
)
```