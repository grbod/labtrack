"""Customer management endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DbSession, CurrentUser, AdminUser
from app.models import Customer
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
)
from app.schemas.product import ArchiveRequest

router = APIRouter()


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: Optional[str] = None,
    include_inactive: bool = False,
) -> CustomerListResponse:
    """List all customers with pagination and filtering."""
    query = db.query(Customer)

    # Filter by active status
    if not include_inactive:
        query = query.filter(Customer.is_active == True)

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Customer.company_name.ilike(search_term))
            | (Customer.contact_name.ilike(search_term))
            | (Customer.email.ilike(search_term))
        )

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    customers = (
        query.order_by(Customer.company_name)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return CustomerListResponse(
        items=[CustomerResponse.model_validate(c) for c in customers],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> CustomerResponse:
    """Get a customer by ID."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    return CustomerResponse.model_validate(customer)


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_in: CustomerCreate,
    db: DbSession,
    current_user: AdminUser,
) -> CustomerResponse:
    """Create a new customer (admin only)."""
    # Check for duplicate email
    existing = (
        db.query(Customer)
        .filter(Customer.email == customer_in.email.lower())
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer with this email already exists",
        )

    customer = Customer(
        company_name=customer_in.company_name,
        contact_name=customer_in.contact_name,
        email=customer_in.email.lower(),
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    return CustomerResponse.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    customer_in: CustomerUpdate,
    db: DbSession,
    current_user: AdminUser,
) -> CustomerResponse:
    """Update a customer (admin only)."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    # Check email uniqueness if updating
    update_data = customer_in.model_dump(exclude_unset=True)
    if "email" in update_data:
        existing = (
            db.query(Customer)
            .filter(
                Customer.email == update_data["email"].lower(),
                Customer.id != customer_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer with this email already exists",
            )
        update_data["email"] = update_data["email"].lower()

    # Update fields
    for field, value in update_data.items():
        setattr(customer, field, value)

    db.commit()
    db.refresh(customer)

    return CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}", response_model=CustomerResponse)
async def archive_customer(
    customer_id: int,
    archive_request: ArchiveRequest,
    db: DbSession,
    current_user: AdminUser,
) -> CustomerResponse:
    """Archive a customer (soft delete, admin only). Requires a reason."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    if not customer.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer is already archived",
        )

    # Archive (soft delete)
    customer.archive(user_id=current_user.id, reason=archive_request.reason)
    db.commit()
    db.refresh(customer)

    return CustomerResponse.model_validate(customer)


@router.post("/{customer_id}/restore", response_model=CustomerResponse)
async def restore_customer(
    customer_id: int,
    db: DbSession,
    current_user: AdminUser,
) -> CustomerResponse:
    """Restore an archived customer (admin only)."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    if customer.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer is not archived",
        )

    # Restore
    customer.restore()
    db.commit()
    db.refresh(customer)

    return CustomerResponse.model_validate(customer)


# Keep the old activate endpoint for backward compatibility
@router.post("/{customer_id}/activate", response_model=CustomerResponse)
async def activate_customer(
    customer_id: int,
    db: DbSession,
    current_user: AdminUser,
) -> CustomerResponse:
    """Reactivate an archived customer (admin only). Deprecated - use /restore instead."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    # Use restore method
    customer.restore()
    db.commit()
    db.refresh(customer)

    return CustomerResponse.model_validate(customer)


@router.get("/archived", response_model=CustomerListResponse)
async def list_archived_customers(
    db: DbSession,
    current_user: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: Optional[str] = None,
) -> CustomerListResponse:
    """List archived customers (admin only)."""
    query = db.query(Customer).filter(Customer.is_active == False)

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Customer.company_name.ilike(search_term))
            | (Customer.contact_name.ilike(search_term))
            | (Customer.email.ilike(search_term))
        )

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    customers = (
        query.order_by(Customer.archived_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return CustomerListResponse(
        items=[CustomerResponse.model_validate(c) for c in customers],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
