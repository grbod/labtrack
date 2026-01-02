"""Product service for managing product catalog."""

from typing import Optional, List, Dict, Any
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.product import Product
from app.services.base import BaseService
from app.utils.logger import logger


class ProductService(BaseService[Product]):
    """
    Service for managing products in the catalog.

    Provides specialized methods for product management including:
    - Finding products by brand and name
    - Bulk product operations
    - Product standardization
    """

    def __init__(self):
        """Initialize product service."""
        super().__init__(Product)

    def create(
        self,
        db: Session,
        obj_in: Dict[str, Any],
        user_id: Optional[int] = None,
        audit_metadata: Optional[Dict[str, Any]] = None,
    ) -> Product:
        """
        Create a new product with duplicate checking.

        Args:
            db: Database session
            obj_in: Dictionary with creation data
            user_id: ID of user performing the action
            audit_metadata: Additional metadata for audit log

        Returns:
            Created product

        Raises:
            ValueError: If product already exists
        """
        # Check for existing product
        existing = self.find_by_brand_and_name(
            db,
            obj_in.get("brand", ""),
            obj_in.get("product_name", ""),
            obj_in.get("flavor"),
            obj_in.get("size"),
        )

        if existing:
            raise ValueError(
                f"Product already exists: {obj_in.get('brand')} {obj_in.get('product_name')} "
                f"{obj_in.get('flavor', '')} {obj_in.get('size', '')}"
            )

        # Call parent create method
        return super().create(db, obj_in, user_id, audit_metadata)

    def find_by_brand_and_name(
        self,
        db: Session,
        brand: str,
        product_name: str,
        flavor: Optional[str] = None,
        size: Optional[str] = None,
    ) -> Optional[Product]:
        """
        Find a product by brand, name, and optional attributes.

        Args:
            db: Database session
            brand: Product brand
            product_name: Product name
            flavor: Optional flavor
            size: Optional size

        Returns:
            Product instance or None if not found
        """
        try:
            query = db.query(Product).filter(
                Product.brand == brand.strip(),
                Product.product_name == product_name.strip(),
            )

            if flavor:
                query = query.filter(Product.flavor == flavor.strip())
            else:
                query = query.filter(Product.flavor.is_(None))

            if size:
                query = query.filter(Product.size == size.strip())
            else:
                query = query.filter(Product.size.is_(None))

            return query.first()

        except Exception as e:
            logger.error(f"Error finding product: {e}")
            raise

    def create_or_update(
        self, db: Session, product_data: Dict[str, Any], user_id: Optional[int] = None
    ) -> Product:
        """
        Create a new product or update existing one.

        Args:
            db: Database session
            product_data: Product data dictionary
            user_id: ID of user performing the action

        Returns:
            Created or updated product
        """
        # Check if product already exists
        existing_product = self.find_by_brand_and_name(
            db=db,
            brand=product_data.get("brand", ""),
            product_name=product_data.get("product_name", ""),
            flavor=product_data.get("flavor"),
            size=product_data.get("size"),
        )

        if existing_product:
            # Update existing product
            return self.update(
                db=db, db_obj=existing_product, obj_in=product_data, user_id=user_id
            )
        else:
            # Create new product
            return self.create(db=db, obj_in=product_data, user_id=user_id)

    def search_products(
        self,
        db: Session,
        search_term: Optional[str] = None,
        brand: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Product]:
        """
        Search products with optional filters.

        Args:
            db: Database session
            search_term: Search term for product name or display name
            brand: Filter by brand
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matching products
        """
        try:
            query = db.query(Product)

            if brand:
                query = query.filter(Product.brand == brand)

            if search_term:
                search_pattern = f"%{search_term}%"
                query = query.filter(
                    or_(
                        Product.product_name.ilike(search_pattern),
                        Product.display_name.ilike(search_pattern),
                        Product.flavor.ilike(search_pattern),
                    )
                )

            return query.offset(skip).limit(limit).all()

        except Exception as e:
            logger.error(f"Error searching products: {e}")
            raise

    def get_brands(self, db: Session) -> List[str]:
        """
        Get list of unique brands.

        Args:
            db: Database session

        Returns:
            List of brand names
        """
        try:
            brands = db.query(Product.brand).distinct().order_by(Product.brand).all()
            return [brand[0] for brand in brands]
        except Exception as e:
            logger.error(f"Error fetching brands: {e}")
            raise

    def bulk_create(
        self,
        db: Session,
        products_data: List[Dict[str, Any]],
        user_id: Optional[int] = None,
    ) -> List[Product]:
        """
        Create multiple products in a single transaction.

        Args:
            db: Database session
            products_data: List of product data dictionaries
            user_id: ID of user performing the action

        Returns:
            List of created products
        """
        created_products = []

        try:
            for product_data in products_data:
                # Check for duplicates
                existing = self.find_by_brand_and_name(
                    db=db,
                    brand=product_data.get("brand", ""),
                    product_name=product_data.get("product_name", ""),
                    flavor=product_data.get("flavor"),
                    size=product_data.get("size"),
                )

                if not existing:
                    product = Product(**product_data)
                    db.add(product)
                    created_products.append(product)

            if created_products:
                db.flush()

                # Log audit for bulk creation
                for product in created_products:
                    self._log_audit(
                        db=db,
                        action="insert",
                        record_id=product.id,
                        new_values=product.to_dict(),
                        user_id=user_id,
                    )

            db.commit()

            logger.info(f"Bulk created {len(created_products)} products")
            return created_products

        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error during bulk create: {e}")
            raise ValueError("Duplicate products found in bulk create")
        except Exception as e:
            db.rollback()
            logger.error(f"Error during bulk create: {e}")
            raise

    def standardize_display_name(
        self,
        brand: str,
        product_name: str,
        flavor: Optional[str] = None,
        size: Optional[str] = None,
    ) -> str:
        """
        Generate standardized display name for a product.

        Args:
            brand: Product brand
            product_name: Product name
            flavor: Optional flavor
            size: Optional size

        Returns:
            Standardized display name
        """
        parts = [brand, product_name]

        if flavor:
            parts.append(flavor)

        if size:
            parts.append(f"({size})")

        return " - ".join(parts)

    def validate_product_data(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean product data before creation/update.

        Args:
            product_data: Raw product data

        Returns:
            Cleaned product data

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Required fields
        if not product_data.get("brand"):
            raise ValueError("Brand is required")

        if not product_data.get("product_name"):
            raise ValueError("Product name is required")

        # Clean data
        cleaned_data = {
            "brand": product_data["brand"].strip(),
            "product_name": product_data["product_name"].strip(),
            "flavor": product_data.get("flavor", "").strip() or None,
            "size": product_data.get("size", "").strip() or None,
        }

        # Generate display name if not provided
        if "display_name" not in product_data or not product_data["display_name"]:
            cleaned_data["display_name"] = self.standardize_display_name(
                brand=cleaned_data["brand"],
                product_name=cleaned_data["product_name"],
                flavor=cleaned_data["flavor"],
                size=cleaned_data["size"],
            )
        else:
            cleaned_data["display_name"] = product_data["display_name"].strip()

        return cleaned_data

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
        from app.models import ProductTestSpecification
        
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
        from app.models import ProductTestSpecification
        
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
    ) -> List["ProductTestSpecification"]:
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
            if spec.lab_test_type.test_name.lower() not in completed_lower:
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
    
    def add_test_specification(
        self,
        db: Session,
        product_id: int,
        test_type_id: int,
        specification: str,
        is_required: bool = True,
        notes: str = None,
        min_value: str = None,
        max_value: str = None
    ) -> "ProductTestSpecification":
        """
        Add a test specification to a product.
        
        Args:
            db: Database session
            product_id: Product ID
            test_type_id: Lab test type ID
            specification: Specification text (e.g., "< 10 CFU/g")
            is_required: Whether this test is required for lot approval
            notes: Optional notes
            min_value: Minimum acceptable value
            max_value: Maximum acceptable value
            
        Returns:
            Created ProductTestSpecification
        """
        from app.models.product_test_spec import ProductTestSpecification
        
        # Check if specification already exists
        existing = db.query(ProductTestSpecification).filter(
            ProductTestSpecification.product_id == product_id,
            ProductTestSpecification.lab_test_type_id == test_type_id
        ).first()
        
        if existing:
            raise ValueError("Test specification already exists for this product and test type")
        
        # Create new specification
        spec = ProductTestSpecification(
            product_id=product_id,
            lab_test_type_id=test_type_id,
            specification=specification,
            is_required=is_required,
            notes=notes,
            min_value=min_value,
            max_value=max_value
        )
        
        db.add(spec)
        db.commit()
        db.refresh(spec)
        
        logger.info(f"Added test specification for product {product_id}, test {test_type_id}")
        return spec
    
    def remove_test_specification(
        self,
        db: Session,
        product_id: int,
        test_type_id: int
    ) -> bool:
        """
        Remove a test specification from a product.
        
        Args:
            db: Database session
            product_id: Product ID
            test_type_id: Lab test type ID
            
        Returns:
            True if removed, False if not found
        """
        from app.models.product_test_spec import ProductTestSpecification
        
        spec = db.query(ProductTestSpecification).filter(
            ProductTestSpecification.product_id == product_id,
            ProductTestSpecification.lab_test_type_id == test_type_id
        ).first()
        
        if spec:
            db.delete(spec)
            db.commit()
            logger.info(f"Removed test specification for product {product_id}, test {test_type_id}")
            return True
        
        return False
    
    def update_test_specification(
        self,
        db: Session,
        product_id: int,
        test_type_id: int,
        specification: str,
        is_required: bool = True,
        notes: str = None,
        min_value: str = None,
        max_value: str = None
    ) -> "ProductTestSpecification":
        """
        Update an existing test specification for a product.
        
        Args:
            db: Database session
            product_id: Product ID
            test_type_id: Lab test type ID
            specification: Updated specification text (e.g., "< 10 CFU/g")
            is_required: Whether this test is required for lot approval
            notes: Optional notes
            min_value: Minimum acceptable value
            max_value: Maximum acceptable value
            
        Returns:
            Updated ProductTestSpecification
            
        Raises:
            ValueError: If specification doesn't exist
        """
        from app.models.product_test_spec import ProductTestSpecification
        
        # Find existing specification
        spec = db.query(ProductTestSpecification).filter(
            ProductTestSpecification.product_id == product_id,
            ProductTestSpecification.lab_test_type_id == test_type_id
        ).first()
        
        if not spec:
            raise ValueError("Test specification not found for this product and test type")
        
        # Update specification
        spec.specification = specification
        spec.is_required = is_required
        if notes is not None:
            spec.notes = notes
        if min_value is not None:
            spec.min_value = min_value
        if max_value is not None:
            spec.max_value = max_value
        
        db.commit()
        db.refresh(spec)
        
        logger.info(f"Updated test specification for product {product_id}, test {test_type_id}")
        return spec
