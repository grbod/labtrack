"""Product management endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DbSession, CurrentUser, AdminUser
from app.models import Product
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductWithSpecsResponse,
    ProductListResponse,
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
    is_active: Optional[bool] = None,
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

    if is_active is not None:
        query = query.filter(Product.is_active == is_active)

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
        .filter(Product.is_active == True)
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
            "test_method": spec.lab_test_type.test_method if spec.lab_test_type else None,
            "specification_min": spec.specification_min,
            "specification_max": spec.specification_max,
            "unit": spec.unit,
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
        is_active=True,
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
    """Delete a product (admin only). Soft delete by setting is_active=False."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Soft delete
    product.is_active = False
    db.commit()
