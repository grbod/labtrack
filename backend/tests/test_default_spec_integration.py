"""Integration tests for default specification pre-population."""

import pytest
from sqlalchemy.orm import Session

from app.models import LabTestType, Product, ProductTestSpecification
from app.services.lab_test_type_service import LabTestTypeService
from app.services.product_service import ProductService


class TestDefaultSpecificationIntegration:
    """Integration tests for default specification workflow."""

    @pytest.fixture
    def test_lab_types_with_defaults(self, test_db: Session):
        """Create test lab types with default specifications."""
        service = LabTestTypeService()
        
        lab_types = []
        
        # Microbiological tests
        tpc = service.create_lab_test_type(
            db=test_db,
            name="Total Plate Count",
            category="Microbiological",
            unit_of_measurement="CFU/g",
            default_specification="< 10,000 CFU/g"
        )
        lab_types.append(tpc)
        
        ecoli = service.create_lab_test_type(
            db=test_db,
            name="E. coli",
            category="Microbiological", 
            unit_of_measurement="Positive/Negative",
            default_specification="Negative"
        )
        lab_types.append(ecoli)
        
        # Heavy metals
        lead = service.create_lab_test_type(
            db=test_db,
            name="Lead",
            category="Heavy Metals",
            unit_of_measurement="ppm",
            default_specification="< 0.5 ppm"
        )
        lab_types.append(lead)
        
        # Test without default spec
        arsenic = service.create_lab_test_type(
            db=test_db,
            name="Arsenic",
            category="Heavy Metals",
            unit_of_measurement="ppm"
            # No default specification
        )
        lab_types.append(arsenic)
        
        return lab_types

    @pytest.fixture
    def test_product(self, test_db: Session):
        """Create a test product."""
        product = Product(
            brand="Test Brand",
            product_name="Test Protein",
            flavor="Vanilla",
            size="2 lbs",
            display_name="Test Brand Test Protein - Vanilla (2 lbs)",
            serving_size=28.5,
            expiry_duration_months=36
        )
        test_db.add(product)
        test_db.commit()
        test_db.refresh(product)
        return product

    def test_add_test_spec_with_default(
        self, test_db: Session, test_product: Product, test_lab_types_with_defaults
    ):
        """Test adding test specification uses default specification."""
        product_service = ProductService()
        
        # Get lab test type with default spec
        tpc_test = test_lab_types_with_defaults[0]  # Total Plate Count
        assert tpc_test.default_specification == "< 10,000 CFU/g"
        
        # Add test specification using default
        spec = product_service.add_test_specification(
            db=test_db,
            product_id=test_product.id,
            test_type_id=tpc_test.id,
            specification=tpc_test.default_specification,  # Use the default
            is_required=True
        )
        
        assert spec.specification == "< 10,000 CFU/g"
        assert spec.is_required is True
        assert spec.product_id == test_product.id
        assert spec.lab_test_type_id == tpc_test.id

    def test_add_test_spec_override_default(
        self, test_db: Session, test_product: Product, test_lab_types_with_defaults
    ):
        """Test adding test specification with custom value (overriding default)."""
        product_service = ProductService()
        
        # Get lab test type with default spec
        tpc_test = test_lab_types_with_defaults[0]  # Total Plate Count
        assert tpc_test.default_specification == "< 10,000 CFU/g"
        
        # Add test specification with custom value
        spec = product_service.add_test_specification(
            db=test_db,
            product_id=test_product.id,
            test_type_id=tpc_test.id,
            specification="< 5,000 CFU/g",  # Override default
            is_required=True
        )
        
        assert spec.specification == "< 5,000 CFU/g"  # Should use custom value
        assert spec.is_required is True

    def test_add_test_spec_no_default(
        self, test_db: Session, test_product: Product, test_lab_types_with_defaults
    ):
        """Test adding test specification for lab type without default."""
        product_service = ProductService()
        
        # Get lab test type without default spec
        arsenic_test = test_lab_types_with_defaults[3]  # Arsenic
        assert arsenic_test.default_specification is None
        
        # Add test specification with manual value
        spec = product_service.add_test_specification(
            db=test_db,
            product_id=test_product.id,
            test_type_id=arsenic_test.id,
            specification="< 0.2 ppm",  # Manual value
            is_required=False
        )
        
        assert spec.specification == "< 0.2 ppm"
        assert spec.is_required is False

    def test_multiple_defaults_workflow(
        self, test_db: Session, test_product: Product, test_lab_types_with_defaults
    ):
        """Test adding multiple test specifications using defaults."""
        product_service = ProductService()
        
        test_cases = [
            (0, "< 10,000 CFU/g", True),   # Total Plate Count
            (1, "Negative", True),          # E. coli  
            (2, "< 0.5 ppm", False),       # Lead
        ]
        
        for test_idx, expected_spec, is_required in test_cases:
            lab_test = test_lab_types_with_defaults[test_idx]
            
            spec = product_service.add_test_specification(
                db=test_db,
                product_id=test_product.id,
                test_type_id=lab_test.id,
                specification=lab_test.default_specification,  # Use default
                is_required=is_required
            )
            
            assert spec.specification == expected_spec
            assert spec.is_required == is_required
        
        # Verify all specs were added
        test_db.refresh(test_product)
        assert len(test_product.test_specifications) == 3
        
        # Check that specifications match defaults
        specs_by_test = {spec.lab_test_type_id: spec for spec in test_product.test_specifications}
        
        tpc_spec = specs_by_test[test_lab_types_with_defaults[0].id]
        assert tpc_spec.specification == "< 10,000 CFU/g"
        
        ecoli_spec = specs_by_test[test_lab_types_with_defaults[1].id] 
        assert ecoli_spec.specification == "Negative"
        
        lead_spec = specs_by_test[test_lab_types_with_defaults[2].id]
        assert lead_spec.specification == "< 0.5 ppm"

    def test_update_lab_test_default_affects_new_products(
        self, test_db: Session, test_lab_types_with_defaults
    ):
        """Test that updating lab test default spec affects new products."""
        lab_test_service = LabTestTypeService()
        product_service = ProductService()
        
        # Get lab test and update its default spec
        tpc_test = test_lab_types_with_defaults[0]
        updated_test = lab_test_service.update_lab_test_type(
            db=test_db,
            test_type_id=tpc_test.id,
            default_specification="< 5,000 CFU/g"  # Change default
        )
        
        assert updated_test.default_specification == "< 5,000 CFU/g"
        
        # Create new product and add this test
        new_product = Product(
            brand="New Brand",
            product_name="New Protein",
            display_name="New Brand New Protein"
        )
        test_db.add(new_product)
        test_db.commit()
        test_db.refresh(new_product)
        
        # Add test spec using new default
        spec = product_service.add_test_specification(
            db=test_db,
            product_id=new_product.id,
            test_type_id=updated_test.id,
            specification=updated_test.default_specification,  # Use updated default
            is_required=True
        )
        
        assert spec.specification == "< 5,000 CFU/g"

    def test_lab_test_grouped_with_defaults(
        self, test_db: Session, test_lab_types_with_defaults
    ):
        """Test that grouped lab tests include default specifications."""
        service = LabTestTypeService()
        
        grouped = service.get_all_grouped(test_db)
        
        # Check Microbiological category
        micro_tests = grouped.get("Microbiological", [])
        assert len(micro_tests) == 2
        
        # Find Total Plate Count
        tpc = next(t for t in micro_tests if t.test_name == "Total Plate Count")
        assert tpc.default_specification == "< 10,000 CFU/g"
        
        # Find E. coli
        ecoli = next(t for t in micro_tests if t.test_name == "E. coli")
        assert ecoli.default_specification == "Negative"
        
        # Check Heavy Metals category
        metal_tests = grouped.get("Heavy Metals", [])
        assert len(metal_tests) == 2
        
        # Find Lead
        lead = next(t for t in metal_tests if t.test_name == "Lead")
        assert lead.default_specification == "< 0.5 ppm"
        
        # Find Arsenic (no default)
        arsenic = next(t for t in metal_tests if t.test_name == "Arsenic")
        assert arsenic.default_specification is None

    def test_product_with_mixed_specs(
        self, test_db: Session, test_product: Product, test_lab_types_with_defaults
    ):
        """Test product with mix of default and custom specifications."""
        product_service = ProductService()
        
        # Add test using default spec
        product_service.add_test_specification(
            db=test_db,
            product_id=test_product.id,
            test_type_id=test_lab_types_with_defaults[0].id,  # Total Plate Count
            specification=test_lab_types_with_defaults[0].default_specification,
            is_required=True
        )
        
        # Add test with custom spec (overriding default)
        product_service.add_test_specification(
            db=test_db,
            product_id=test_product.id,
            test_type_id=test_lab_types_with_defaults[2].id,  # Lead
            specification="< 1.0 ppm",  # Custom, not default "< 0.5 ppm"
            is_required=True
        )
        
        # Add test for lab type without default
        product_service.add_test_specification(
            db=test_db,
            product_id=test_product.id,
            test_type_id=test_lab_types_with_defaults[3].id,  # Arsenic
            specification="< 0.1 ppm",  # Manual value
            is_required=False
        )
        
        # Verify specifications
        test_db.refresh(test_product)
        specs = {spec.lab_test_type.test_name: spec for spec in test_product.test_specifications}
        
        assert specs["Total Plate Count"].specification == "< 10,000 CFU/g"  # Default
        assert specs["Lead"].specification == "< 1.0 ppm"  # Custom override
        assert specs["Arsenic"].specification == "< 0.1 ppm"  # Manual


# Run with: pytest tests/test_default_spec_integration.py -v