"""Product management endpoints."""

from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DbSession, CurrentUser, AdminUser
from app.models import Product, ProductTestSpecification, LabTestType
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductWithSpecsResponse,
    ProductListResponse,
    TestSpecificationCreate,
    TestSpecificationUpdate,
    TestSpecificationResponse,
    ProductBulkImportRow,
    ProductBulkImportResult,
)

router = APIRouter()


@router.get("", response_model=ProductListResponse)
async def list_products(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    brand: Optional[str] = None,
) -> ProductListResponse:
    """List all products with pagination and filtering."""
    query = db.query(Product)

    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Product.brand.ilike(search_term))
            | (Product.product_name.ilike(search_term))
            | (Product.display_name.ilike(search_term))
            | (Product.flavor.ilike(search_term))
        )

    if brand:
        query = query.filter(Product.brand == brand)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    products = (
        query.order_by(Product.brand, Product.product_name)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/brands", response_model=list[str])
async def list_brands(
    db: DbSession,
    current_user: CurrentUser,
) -> list[str]:
    """Get list of unique product brands."""
    brands = (
        db.query(Product.brand)
        .distinct()
        .order_by(Product.brand)
        .all()
    )
    return [b[0] for b in brands]


@router.get("/{product_id}", response_model=ProductWithSpecsResponse)
async def get_product(
    product_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductWithSpecsResponse:
    """Get a product by ID with test specifications."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Build response with specs
    response = ProductWithSpecsResponse.model_validate(product)
    response.test_specifications = [
        {
            "id": spec.id,
            "lab_test_type_id": spec.lab_test_type_id,
            "test_name": spec.lab_test_type.test_name if spec.lab_test_type else "",
            "test_category": spec.lab_test_type.test_category if spec.lab_test_type else None,
            "test_method": spec.lab_test_type.test_method if spec.lab_test_type else None,
            "test_unit": spec.lab_test_type.default_unit if spec.lab_test_type else None,
            "specification": spec.specification,
            "is_required": spec.is_required,
        }
        for spec in product.test_specifications
    ]

    return response


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_in: ProductCreate,
    db: DbSession,
    current_user: AdminUser,
) -> ProductResponse:
    """Create a new product (admin only)."""
    # Check for duplicate display name
    existing = (
        db.query(Product)
        .filter(Product.display_name == product_in.display_name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product with this display name already exists",
        )

    product = Product(
        brand=product_in.brand,
        product_name=product_in.product_name,
        flavor=product_in.flavor,
        size=product_in.size,
        display_name=product_in.display_name,
        serving_size=product_in.serving_size,
        expiry_duration_months=product_in.expiry_duration_months,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    return ProductResponse.model_validate(product)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_in: ProductUpdate,
    db: DbSession,
    current_user: AdminUser,
) -> ProductResponse:
    """Update a product (admin only)."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Check display name uniqueness if updating
    update_data = product_in.model_dump(exclude_unset=True)
    if "display_name" in update_data:
        existing = (
            db.query(Product)
            .filter(
                Product.display_name == update_data["display_name"],
                Product.id != product_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product with this display name already exists",
            )

    # Update fields
    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)

    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    db: DbSession,
    current_user: AdminUser,
) -> None:
    """Delete a product (admin only)."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Delete product
    db.delete(product)
    db.commit()


# Test Specification endpoints
@router.get("/{product_id}/test-specifications", response_model=list[TestSpecificationResponse])
async def list_product_test_specs(
    product_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[TestSpecificationResponse]:
    """List all test specifications for a product."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    specs = (
        db.query(ProductTestSpecification)
        .filter(ProductTestSpecification.product_id == product_id)
        .all()
    )

    return [
        TestSpecificationResponse(
            id=spec.id,
            lab_test_type_id=spec.lab_test_type_id,
            test_name=spec.lab_test_type.test_name if spec.lab_test_type else "",
            test_category=spec.lab_test_type.test_category if spec.lab_test_type else None,
            test_method=spec.lab_test_type.test_method if spec.lab_test_type else None,
            test_unit=spec.lab_test_type.default_unit if spec.lab_test_type else None,
            specification=spec.specification,
            is_required=spec.is_required,
        )
        for spec in specs
    ]


@router.post("/{product_id}/test-specifications", response_model=TestSpecificationResponse, status_code=status.HTTP_201_CREATED)
async def create_product_test_spec(
    product_id: int,
    spec_in: TestSpecificationCreate,
    db: DbSession,
    current_user: AdminUser,
) -> TestSpecificationResponse:
    """Add a test specification to a product (admin only)."""
    # Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Verify lab test type exists
    lab_test = db.query(LabTestType).filter(LabTestType.id == spec_in.lab_test_type_id).first()
    if not lab_test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab test type not found",
        )

    # Check for duplicate
    existing = (
        db.query(ProductTestSpecification)
        .filter(
            ProductTestSpecification.product_id == product_id,
            ProductTestSpecification.lab_test_type_id == spec_in.lab_test_type_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test specification already exists for this product",
        )

    # Create specification
    spec = ProductTestSpecification(
        product_id=product_id,
        lab_test_type_id=spec_in.lab_test_type_id,
        specification=spec_in.specification,
        is_required=spec_in.is_required,
    )
    db.add(spec)
    db.commit()
    db.refresh(spec)

    return TestSpecificationResponse(
        id=spec.id,
        lab_test_type_id=spec.lab_test_type_id,
        test_name=lab_test.test_name,
        test_category=lab_test.test_category,
        test_method=lab_test.test_method,
        test_unit=lab_test.default_unit,
        specification=spec.specification,
        is_required=spec.is_required,
    )


@router.patch("/{product_id}/test-specifications/{spec_id}", response_model=TestSpecificationResponse)
async def update_product_test_spec(
    product_id: int,
    spec_id: int,
    spec_in: TestSpecificationUpdate,
    db: DbSession,
    current_user: AdminUser,
) -> TestSpecificationResponse:
    """Update a test specification (admin only)."""
    spec = (
        db.query(ProductTestSpecification)
        .filter(
            ProductTestSpecification.id == spec_id,
            ProductTestSpecification.product_id == product_id,
        )
        .first()
    )
    if not spec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test specification not found",
        )

    # Update fields
    update_data = spec_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(spec, field, value)

    db.commit()
    db.refresh(spec)

    return TestSpecificationResponse(
        id=spec.id,
        lab_test_type_id=spec.lab_test_type_id,
        test_name=spec.lab_test_type.test_name if spec.lab_test_type else "",
        test_category=spec.lab_test_type.test_category if spec.lab_test_type else None,
        test_method=spec.lab_test_type.test_method if spec.lab_test_type else None,
        test_unit=spec.lab_test_type.default_unit if spec.lab_test_type else None,
        specification=spec.specification,
        is_required=spec.is_required,
    )


@router.delete("/{product_id}/test-specifications/{spec_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_test_spec(
    product_id: int,
    spec_id: int,
    db: DbSession,
    current_user: AdminUser,
) -> None:
    """Delete a test specification (admin only)."""
    spec = (
        db.query(ProductTestSpecification)
        .filter(
            ProductTestSpecification.id == spec_id,
            ProductTestSpecification.product_id == product_id,
        )
        .first()
    )
    if not spec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test specification not found",
        )

    db.delete(spec)
    db.commit()


@router.post("/bulk-import", response_model=ProductBulkImportResult)
async def bulk_import_products(
    rows: List[ProductBulkImportRow],
    db: DbSession,
    current_user: AdminUser,
) -> ProductBulkImportResult:
    """Bulk import products (admin only)."""
    total_rows = len(rows)
    imported = 0
    skipped = 0
    errors = []

    # Get existing display names for duplicate detection
    existing_display_names = {
        p.display_name.lower() for p in db.query(Product.display_name).all()
    }

    for idx, row in enumerate(rows, start=1):
        try:
            # Validate required fields
            if not row.brand or not row.product_name or not row.display_name:
                errors.append(f"Row {idx}: Missing required fields")
                skipped += 1
                continue

            # Check duplicates
            if row.display_name.lower() in existing_display_names:
                errors.append(
                    f"Row {idx}: Product '{row.display_name}' already exists"
                )
                skipped += 1
                continue

            # Create product
            product = Product(
                brand=row.brand,
                product_name=row.product_name,
                flavor=row.flavor,
                size=row.size,
                display_name=row.display_name,
                serving_size=row.serving_size,
                expiry_duration_months=row.expiry_duration_months,
            )
            db.add(product)
            existing_display_names.add(row.display_name.lower())
            imported += 1

        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")
            skipped += 1

    if imported > 0:
        db.commit()

    return ProductBulkImportResult(
        total_rows=total_rows,
        imported=imported,
        skipped=skipped,
        errors=errors,
    )
