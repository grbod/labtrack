"""Integration tests for Product Test Specifications feature."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Product, LabTestType, ProductTestSpecification
from app.services.product_service import ProductService
from app.services.lab_test_type_service import LabTestTypeService


@pytest.mark.integration
class TestProductTestSpecificationDatabase:
    """Test Product Test Specification database operations."""
    
    def test_create_product_test_specification(self, test_db, sample_product, sample_lab_test_types):
        """Test creating a product test specification with all fields."""
        spec = ProductTestSpecification(
            product_id=sample_product.id,
            lab_test_type_id=sample_lab_test_types[0].id,
            specification="< 5000",
            is_required=True,
            notes="Batch release criteria",
            min_value="0",
            max_value="5000"
        )
        test_db.add(spec)
        test_db.commit()
        
        # Verify all fields
        assert spec.id is not None
        assert spec.product_id == sample_product.id
        assert spec.lab_test_type_id == sample_lab_test_types[0].id
        assert spec.specification == "< 5000"
        assert spec.is_required is True
        assert spec.notes == "Batch release criteria"
        assert spec.min_value == "0"
        assert spec.max_value == "5000"
        assert spec.created_at is not None
        assert spec.updated_at is not None
    
    def test_unique_constraint_product_test_combo(self, test_db, sample_product, sample_lab_test_types):
        """Test unique constraint on product/test combination."""
        # Create first specification
        spec1 = ProductTestSpecification(
            product_id=sample_product.id,
            lab_test_type_id=sample_lab_test_types[0].id,
            specification="< 10000",
            is_required=True
        )
        test_db.add(spec1)
        test_db.commit()
        
        # Try to create duplicate
        spec2 = ProductTestSpecification(
            product_id=sample_product.id,
            lab_test_type_id=sample_lab_test_types[0].id,  # Same test
            specification="< 5000",  # Different spec
            is_required=False
        )
        test_db.add(spec2)
        
        with pytest.raises(IntegrityError):
            test_db.commit()
    
    def test_cascade_delete_from_product(self, test_db, sample_product_with_specs):
        """Test cascade delete of specifications when product is deleted."""
        product_id = sample_product_with_specs.id
        spec_count = len(sample_product_with_specs.test_specifications)
        assert spec_count > 0
        
        # Delete product
        test_db.delete(sample_product_with_specs)
        test_db.commit()
        
        # Verify specifications are gone
        remaining_specs = test_db.query(ProductTestSpecification).filter(
            ProductTestSpecification.product_id == product_id
        ).count()
        assert remaining_specs == 0
    
    def test_cascade_delete_prevented_from_lab_test(self, test_db, sample_product_with_specs, sample_lab_test_types):
        """Test that lab test types can't be deleted if they have specifications."""
        # Try to delete a lab test type that has specifications
        test_type = sample_lab_test_types[0]  # Total Plate Count
        
        test_db.delete(test_type)
        with pytest.raises(ValueError, match="Cannot delete test type"):
            test_db.commit()
    
    def test_specification_validation(self, test_db, sample_product, sample_lab_test_types):
        """Test specification field validation."""
        # Empty specification should raise ValueError
        with pytest.raises(ValueError, match="Specification cannot be empty"):
            spec = ProductTestSpecification(
                product_id=sample_product.id,
                lab_test_type_id=sample_lab_test_types[0].id,
                specification="",  # Empty
                is_required=True
            )
    
    def test_relationship_properties(self, test_db, sample_product_with_specs):
        """Test relationship properties work correctly."""
        spec = sample_product_with_specs.test_specifications[0]
        
        # Test product relationship
        assert spec.product is not None
        assert spec.product.id == sample_product_with_specs.id
        
        # Test lab_test_type relationship
        assert spec.lab_test_type is not None
        assert spec.lab_test_type.test_name == "Total Plate Count"
        
        # Test computed properties
        assert spec.test_name == "Total Plate Count"
        assert spec.test_unit == "CFU/g"
        assert spec.test_category == "Microbiological"


@pytest.mark.integration
class TestSpecificationMatching:
    """Test specification matching logic."""
    
    def test_match_less_than_specification(self, test_db, sample_product_with_specs):
        """Test matching '< X' specifications."""
        # Get the Total Plate Count spec (< 10000)
        spec = next(s for s in sample_product_with_specs.test_specifications 
                   if s.test_name == "Total Plate Count")
        
        # Test passing values
        assert spec.matches_result("5000") is True
        assert spec.matches_result("9999") is True
        assert spec.matches_result("0") is True
        assert spec.matches_result("< 10") is True  # Less than value passes
        
        # Test failing values
        assert spec.matches_result("10000") is False
        assert spec.matches_result("15000") is False
        assert spec.matches_result("10001") is False
    
    def test_match_greater_than_specification(self, test_db, sample_product, sample_lab_test_types):
        """Test matching '> X' specifications."""
        # Create a > specification
        spec = ProductTestSpecification(
            product_id=sample_product.id,
            lab_test_type_id=sample_lab_test_types[4].id,  # Protein
            specification="> 15",
            is_required=True
        )
        test_db.add(spec)
        test_db.commit()
        
        # Test passing values
        assert spec.matches_result("16") is True
        assert spec.matches_result("20") is True
        assert spec.matches_result("15.1") is True
        assert spec.matches_result("> 20") is True  # Greater than value passes
        
        # Test failing values
        assert spec.matches_result("15") is False
        assert spec.matches_result("14.9") is False
        assert spec.matches_result("10") is False
    
    def test_match_range_specification(self, test_db, sample_product_with_specs):
        """Test matching range specifications."""
        # Get the Protein spec (20-25)
        spec = next(s for s in sample_product_with_specs.test_specifications 
                   if s.test_name == "Protein")
        
        # Test passing values
        assert spec.matches_result("20") is True
        assert spec.matches_result("22.5") is True
        assert spec.matches_result("25") is True
        
        # Test failing values
        assert spec.matches_result("19.9") is False
        assert spec.matches_result("25.1") is False
        assert spec.matches_result("30") is False
    
    def test_match_positive_negative_specification(self, test_db, sample_product_with_specs):
        """Test matching Positive/Negative specifications."""
        # Get the E. coli spec (Negative)
        spec = next(s for s in sample_product_with_specs.test_specifications 
                   if s.test_name == "E. coli")
        
        # Test passing values
        assert spec.matches_result("Negative") is True
        assert spec.matches_result("negative") is True
        assert spec.matches_result("ND") is True
        assert spec.matches_result("Not Detected") is True
        
        # Test failing values
        assert spec.matches_result("Positive") is False
        assert spec.matches_result("positive") is False
        assert spec.matches_result("Detected") is False
    
    def test_match_exact_specification(self, test_db, sample_product, sample_lab_test_types):
        """Test matching exact value specifications."""
        # Create an exact match specification
        spec = ProductTestSpecification(
            product_id=sample_product.id,
            lab_test_type_id=sample_lab_test_types[5].id,  # Gluten
            specification="5",
            is_required=True
        )
        test_db.add(spec)
        test_db.commit()
        
        # Test exact match
        assert spec.matches_result("5") is True
        
        # Test non-matches
        assert spec.matches_result("4") is False
        assert spec.matches_result("6") is False
        assert spec.matches_result("5.0") is False
    
    def test_match_invalid_values(self, test_db, sample_product_with_specs):
        """Test matching with invalid/empty values."""
        spec = sample_product_with_specs.test_specifications[0]
        
        # Test invalid values
        assert spec.matches_result(None) is False
        assert spec.matches_result("") is False
        assert spec.matches_result("N/A") is False
        assert spec.matches_result("Invalid") is False


@pytest.mark.integration
class TestProductServiceIntegration:
    """Test Product Service integration with specifications."""
    
    def test_set_test_specifications(self, test_db, sample_product, sample_lab_test_types):
        """Test setting test specifications for a product."""
        service = ProductService()
        
        specifications = [
            {
                "lab_test_type_id": sample_lab_test_types[0].id,
                "specification": "< 1000",
                "is_required": True,
                "notes": "Strict limit"
            },
            {
                "lab_test_type_id": sample_lab_test_types[1].id,
                "specification": "Negative",
                "is_required": True
            },
            {
                "lab_test_type_id": sample_lab_test_types[2].id,
                "specification": "< 0.1",
                "is_required": False,
                "notes": "Optional heavy metal test"
            }
        ]
        
        updated_product = service.set_test_specifications(
            test_db, sample_product.id, specifications
        )
        
        assert len(updated_product.test_specifications) == 3
        assert len(updated_product.required_tests) == 2
        assert len(updated_product.optional_tests) == 1
    
    def test_replace_test_specifications(self, test_db, sample_product_with_specs):
        """Test replacing existing specifications."""
        service = ProductService()
        
        # Verify initial count
        initial_count = len(sample_product_with_specs.test_specifications)
        assert initial_count > 0
        
        # Replace with new specifications
        new_specs = [
            {
                "lab_test_type_id": sample_product_with_specs.test_specifications[0].lab_test_type_id,
                "specification": "< 500",  # Stricter limit
                "is_required": True
            }
        ]
        
        updated_product = service.set_test_specifications(
            test_db, sample_product_with_specs.id, new_specs
        )
        
        assert len(updated_product.test_specifications) == 1
        assert updated_product.test_specifications[0].specification == "< 500"
    
    def test_get_product_with_specifications(self, test_db, sample_product_with_specs):
        """Test eager loading of specifications."""
        service = ProductService()
        
        # Get product with specifications loaded
        product = service.get_product_with_specifications(
            test_db, sample_product_with_specs.id
        )
        
        # Verify relationships are loaded
        assert product is not None
        assert len(product.test_specifications) > 0
        
        # Access nested relationship without additional queries
        spec = product.test_specifications[0]
        assert spec.lab_test_type.test_name is not None
    
    def test_copy_test_specifications(self, test_db, sample_product_with_specs, sample_lab_test_types):
        """Test copying specifications between products."""
        service = ProductService()
        
        # Create a new product
        new_product = Product(
            brand="NewBrand",
            product_name="NewProduct",
            display_name="NewBrand NewProduct"
        )
        test_db.add(new_product)
        test_db.commit()
        
        # Copy specifications
        updated_product = service.copy_test_specifications(
            test_db,
            from_product_id=sample_product_with_specs.id,
            to_product_id=new_product.id
        )
        
        # Verify specifications were copied
        assert len(updated_product.test_specifications) == len(sample_product_with_specs.test_specifications)
        
        # Verify they're separate instances
        for orig, copy in zip(sample_product_with_specs.test_specifications, 
                             updated_product.test_specifications):
            assert orig.id != copy.id
            assert orig.specification == copy.specification
            assert orig.is_required == copy.is_required
    
    def test_get_missing_required_tests(self, test_db, sample_product_with_specs):
        """Test identifying missing required tests."""
        service = ProductService()
        
        # Get all required test names
        all_required = sample_product_with_specs.get_required_test_names()
        assert len(all_required) == 4  # TPC, E.coli, Lead, Protein
        
        # Simulate having completed some tests
        completed_tests = ["Total Plate Count", "E. coli"]
        
        missing = service.get_missing_required_tests(
            test_db,
            sample_product_with_specs.id,
            completed_tests
        )
        
        assert len(missing) == 2
        missing_names = [spec.test_name for spec in missing]
        assert "Lead" in missing_names
        assert "Protein" in missing_names
    
    def test_validate_test_result(self, test_db, sample_product_with_specs):
        """Test validating test results against specifications."""
        service = ProductService()
        
        # Test passing result
        result = service.validate_test_result(
            test_db,
            sample_product_with_specs.id,
            "Total Plate Count",
            "5000"
        )
        assert result["passes"] is True
        assert result["specification"] == "< 10000"
        assert result["is_required"] is True
        
        # Test failing result
        result = service.validate_test_result(
            test_db,
            sample_product_with_specs.id,
            "Total Plate Count",
            "15000"
        )
        assert result["passes"] is False
        assert result["specification"] == "< 10000"
        
        # Test result for test not in specifications
        result = service.validate_test_result(
            test_db,
            sample_product_with_specs.id,
            "Unknown Test",
            "100"
        )
        assert result["passes"] is True  # No spec means it passes
        assert result["specification"] is None
        assert result["is_required"] is False
    
    def test_product_properties(self, test_db, sample_product_with_specs):
        """Test product model properties related to specifications."""
        product = sample_product_with_specs
        
        # Test has_test_specifications
        assert product.has_test_specifications is True
        
        # Test required_tests property
        required = product.required_tests
        assert len(required) == 4
        assert all(spec.is_required for spec in required)
        
        # Test optional_tests property
        optional = product.optional_tests
        assert len(optional) == 1
        assert all(not spec.is_required for spec in optional)
        
        # Test get_specification_for_test
        spec = product.get_specification_for_test("E. coli")
        assert spec is not None
        assert spec.specification == "Negative"
        
        # Test case insensitive search
        spec = product.get_specification_for_test("e. COLI")
        assert spec is not None
        
        # Test non-existent test
        spec = product.get_specification_for_test("Non-existent")
        assert spec is None
        
        # Test get_all_test_names
        all_tests = product.get_all_test_names()
        assert len(all_tests) == 5
        assert "Total Plate Count" in all_tests
        assert "Arsenic" in all_tests  # Optional test included


@pytest.mark.integration
@pytest.mark.slow
class TestProductSpecificationBulkOperations:
    """Test bulk operations and complex scenarios."""
    
    def test_multiple_products_sharing_test_types(self, test_db, sample_lab_test_types):
        """Test multiple products can share the same test types."""
        service = ProductService()
        
        # Create multiple products
        products = []
        for i in range(3):
            product = Product(
                brand=f"Brand{i}",
                product_name="Protein Powder",
                flavor=f"Flavor{i}",
                display_name=f"Brand{i} Protein Powder - Flavor{i}"
            )
            test_db.add(product)
            products.append(product)
        
        test_db.commit()
        
        # Set same test specifications for all products
        base_specs = [
            {
                "lab_test_type_id": sample_lab_test_types[0].id,
                "specification": "< 10000",
                "is_required": True
            },
            {
                "lab_test_type_id": sample_lab_test_types[1].id,
                "specification": "Negative",
                "is_required": True
            }
        ]
        
        for product in products:
            service.set_test_specifications(test_db, product.id, base_specs)
        
        # Verify all products have specifications
        for product in products:
            test_db.refresh(product)
            assert len(product.test_specifications) == 2
        
        # Verify lab test type knows about all products
        test_type = sample_lab_test_types[0]
        products_using_test = test_type.get_products_using_test()
        assert len(products_using_test) >= 3
    
    def test_product_families_with_similar_specs(self, test_db, sample_lab_test_types):
        """Test product families with similar but not identical specifications."""
        service = ProductService()
        
        # Create product family
        base_product = Product(
            brand="HealthCo",
            product_name="Whey Protein",
            flavor="Vanilla",
            size="2 lb",
            display_name="HealthCo Whey Protein - Vanilla (2 lb)"
        )
        test_db.add(base_product)
        test_db.commit()
        
        # Set base specifications
        base_specs = [
            {
                "lab_test_type_id": sample_lab_test_types[0].id,  # TPC
                "specification": "< 10000",
                "is_required": True
            },
            {
                "lab_test_type_id": sample_lab_test_types[1].id,  # E. coli
                "specification": "Negative",
                "is_required": True
            },
            {
                "lab_test_type_id": sample_lab_test_types[4].id,  # Protein
                "specification": "75-85",  # High protein content
                "is_required": True
            }
        ]
        
        service.set_test_specifications(test_db, base_product.id, base_specs)
        
        # Create variant with stricter micro limits
        strict_variant = Product(
            brand="HealthCo",
            product_name="Whey Protein",
            flavor="Vanilla",
            size="5 lb",
            display_name="HealthCo Whey Protein - Vanilla (5 lb)"
        )
        test_db.add(strict_variant)
        test_db.commit()
        
        # Copy and modify specifications
        service.copy_test_specifications(
            test_db,
            from_product_id=base_product.id,
            to_product_id=strict_variant.id
        )
        
        # Update to stricter limits
        stricter_specs = base_specs.copy()
        stricter_specs[0]["specification"] = "< 1000"  # Stricter TPC
        
        service.set_test_specifications(test_db, strict_variant.id, stricter_specs)
        
        # Verify different specifications
        test_db.refresh(base_product)
        test_db.refresh(strict_variant)
        
        base_tpc = next(s for s in base_product.test_specifications if s.test_name == "Total Plate Count")
        strict_tpc = next(s for s in strict_variant.test_specifications if s.test_name == "Total Plate Count")
        
        assert base_tpc.specification == "< 10000"
        assert strict_tpc.specification == "< 1000"