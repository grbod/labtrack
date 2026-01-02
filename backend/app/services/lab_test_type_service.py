"""Service for managing lab test types."""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import LabTestType
from app.services.base import BaseService
from app.utils.logger import logger


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
        default_specification: Optional[str] = None,
        description: Optional[str] = None,
        abbreviations: Optional[List[str]] = None,
        sort_order: Optional[int] = None,
        is_active: Optional[bool] = True
    ) -> LabTestType:
        """
        Create new lab test type with validation.
        
        Args:
            db: Database session
            name: Test name (must be unique)
            category: Test category
            unit_of_measurement: Unit for results
            default_method: Default test method
            default_specification: Default specification (e.g., "< 10,000 CFU/g")
            description: Optional description
            abbreviations: List of alternative names
            sort_order: Display order within category
            is_active: Whether test is active
            
        Returns:
            Created LabTestType
            
        Raises:
            ValueError: If name already exists or category invalid
        """
        # Check for duplicate name
        existing = db.query(LabTestType).filter(
            func.lower(LabTestType.test_name) == func.lower(name)
        ).first()
        
        if existing:
            raise ValueError(f"Lab test type '{name}' already exists")
        
        # Validate category
        valid_categories = [
            LabTestType.CATEGORY_MICROBIOLOGICAL, 
            LabTestType.CATEGORY_HEAVY_METALS,
            LabTestType.CATEGORY_PESTICIDES,
            LabTestType.CATEGORY_NUTRITIONAL,
            LabTestType.CATEGORY_PHYSICAL,
            LabTestType.CATEGORY_CHEMICAL,
            LabTestType.CATEGORY_ALLERGENS,
            LabTestType.CATEGORY_ORGANOLEPTIC
        ]
        
        if category not in valid_categories:
            raise ValueError(
                f"Invalid category. Must be one of: {valid_categories}"
            )
        
        # Create test type
        lab_test = LabTestType(
            test_name=name,
            test_category=category,
            default_unit=unit_of_measurement,
            test_method=default_method,
            default_specification=default_specification,
            description=description,
            is_active=is_active
        )
        
        if abbreviations:
            # Store abbreviations as JSON
            import json
            lab_test.abbreviations = json.dumps(abbreviations)
        
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
        if "test_name" in kwargs and kwargs["test_name"] != test_type.test_name:
            existing = db.query(LabTestType).filter(
                func.lower(LabTestType.test_name) == func.lower(kwargs["test_name"]),
                LabTestType.id != test_type_id
            ).first()
            
            if existing:
                raise ValueError(f"Lab test type '{kwargs['test_name']}' already exists")
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(test_type, key):
                setattr(test_type, key, value)
        
        db.commit()
        db.refresh(test_type)
        
        logger.info(f"Updated lab test type: {test_type.test_name}")
        return test_type
    
    def get_by_category(
        self, 
        db: Session, 
        category: str
    ) -> List[LabTestType]:
        """Get all test types in a category, ordered."""
        return db.query(LabTestType).filter(
            LabTestType.test_category == category,
            LabTestType.is_active == True
        ).order_by(
            LabTestType.test_name
        ).all()
    
    def get_all_grouped(self, db: Session, include_inactive: bool = False) -> Dict[str, List[LabTestType]]:
        """
        Get all test types grouped by category.
        
        Args:
            include_inactive: If True, includes inactive tests. If False, only active tests.
        
        Returns:
            Dict with category names as keys and lists of test types as values
        """
        query = db.query(LabTestType)
        
        if not include_inactive:
            query = query.filter(LabTestType.is_active == True)
        
        all_tests = query.order_by(
            LabTestType.test_category,
            LabTestType.test_name
        ).all()
        
        grouped = {}
        for test in all_tests:
            if test.test_category not in grouped:
                grouped[test.test_category] = []
            grouped[test.test_category].append(test)
        
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
            func.lower(LabTestType.test_name) == func.lower(search_term)
        ).first()
        
        if test:
            return test
        
        # Check abbreviations
        all_tests = db.query(LabTestType).all()
        search_lower = search_term.lower()
        
        for test in all_tests:
            if test.abbreviations:
                try:
                    import json
                    abbrevs = json.loads(test.abbreviations)
                    if any(search_lower == abbr.lower() for abbr in abbrevs):
                        return test
                except:
                    pass
        
        return None
    
    def get_categories(self, db: Session) -> List[str]:
        """Get list of all used categories."""
        results = db.query(LabTestType.test_category).distinct().all()
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
        
        logger.info(f"Deleted lab test type: {test_type.test_name}")
        return True