"""Integration tests for Lab Test Types feature."""

import pytest
import json
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import LabTestType, Product, ProductTestSpecification
from app.services.lab_test_type_service import LabTestTypeService
from app.models.enums import UserRole


@pytest.mark.integration
class TestLabTestTypeDatabase:
    """Test Lab Test Type database operations."""
    
    def test_create_lab_test_type(self, test_db):
        """Test creating a lab test type with all fields."""
        test_type = LabTestType(
            test_name="Salmonella",
            test_category="Microbiological",
            default_unit="Positive/Negative",
            test_method="AOAC 2016.01",
            description="Test for Salmonella species",
            abbreviations='["Salmonella spp.", "Salm"]',
            is_active=True
        )
        test_db.add(test_type)
        test_db.commit()
        
        # Verify all fields
        assert test_type.id is not None
        assert test_type.test_name == "Salmonella"
        assert test_type.test_category == "Microbiological"
        assert test_type.default_unit == "Positive/Negative"
        assert test_type.test_method == "AOAC 2016.01"
        assert test_type.description == "Test for Salmonella species"
        assert test_type.abbreviations == '["Salmonella spp.", "Salm"]'
        assert test_type.is_active is True
        assert test_type.created_at is not None
        assert test_type.updated_at is not None
    
    def test_unique_test_name_constraint(self, test_db):
        """Test that test names must be unique."""
        test1 = LabTestType(
            test_name="Yeast & Mold",
            test_category="Microbiological",
            default_unit="CFU/g"
        )
        test_db.add(test1)
        test_db.commit()
        
        # Try to create duplicate
        test2 = LabTestType(
            test_name="Yeast & Mold",  # Same name
            test_category="Physical",   # Different category
            default_unit="CFU/g"
        )
        test_db.add(test2)
        
        with pytest.raises(IntegrityError):
            test_db.commit()
    
    def test_validate_test_name(self, test_db):
        """Test test name validation."""
        # Empty test name should raise ValueError
        with pytest.raises(ValueError, match="Test name cannot be empty"):
            test_type = LabTestType(
                test_name="",
                test_category="Microbiological",
                default_unit="CFU/g"
            )
    
    def test_validate_test_category(self, test_db):
        """Test test category validation."""
        # Empty category should raise ValueError
        with pytest.raises(ValueError, match="Test category cannot be empty"):
            test_type = LabTestType(
                test_name="Test",
                test_category="",
                default_unit="CFU/g"
            )
    
    def test_abbreviations_json_storage(self, test_db):
        """Test abbreviations are stored and retrieved as JSON."""
        abbrevs = ["Heavy Metal", "Hg", "Mercury (Hg)"]
        test_type = LabTestType(
            test_name="Mercury",
            test_category="Heavy Metals",
            default_unit="ppb",
            abbreviations=json.dumps(abbrevs)
        )
        test_db.add(test_type)
        test_db.commit()
        
        # Retrieve and verify
        saved = test_db.query(LabTestType).filter(
            LabTestType.test_name == "Mercury"
        ).first()
        
        assert saved.abbreviations is not None
        loaded_abbrevs = json.loads(saved.abbreviations)
        assert loaded_abbrevs == abbrevs
    
    def test_cascade_delete_prevention(self, test_db, sample_product, sample_lab_test_types):
        """Test that lab test types can't be deleted if in use."""
        # Create a product test specification
        spec = ProductTestSpecification(
            product_id=sample_product.id,
            lab_test_type_id=sample_lab_test_types[0].id,
            specification="< 1000",
            is_required=True
        )
        test_db.add(spec)
        test_db.commit()
        
        # Try to delete the test type
        test_db.delete(sample_lab_test_types[0])
        
        with pytest.raises(ValueError, match="Cannot delete test type"):
            test_db.commit()
    
    def test_update_lab_test_type(self, test_db, sample_lab_test_types):
        """Test updating lab test type fields."""
        test_type = sample_lab_test_types[0]
        original_name = test_type.test_name
        
        # Update fields
        test_type.test_method = "Updated Method"
        test_type.description = "Updated description"
        test_type.is_active = False
        
        test_db.commit()
        test_db.refresh(test_type)
        
        assert test_type.test_name == original_name  # Name unchanged
        assert test_type.test_method == "Updated Method"
        assert test_type.description == "Updated description"
        assert test_type.is_active is False
        assert test_type.updated_at > test_type.created_at


@pytest.mark.integration
class TestLabTestTypeService:
    """Test Lab Test Type service operations."""
    
    def test_create_lab_test_type_valid_category(self, test_db):
        """Test creating lab test type with valid category."""
        service = LabTestTypeService()
        
        test_type = service.create_lab_test_type(
            db=test_db,
            name="Cadmium",
            category="Heavy Metals",
            unit_of_measurement="ppm",
            default_method="ICP-MS",
            description="Cadmium testing",
            abbreviations=["Cd", "Cadmium (Cd)"],
            is_active=True
        )
        
        assert test_type.id is not None
        assert test_type.test_name == "Cadmium"
        assert test_type.test_category == "Heavy Metals"
        assert json.loads(test_type.abbreviations) == ["Cd", "Cadmium (Cd)"]
    
    def test_create_lab_test_type_invalid_category(self, test_db):
        """Test creating lab test type with invalid category."""
        service = LabTestTypeService()
        
        with pytest.raises(ValueError, match="Invalid category"):
            service.create_lab_test_type(
                db=test_db,
                name="Test",
                category="Invalid Category",  # Not in allowed list
                unit_of_measurement="unit"
            )
    
    def test_create_duplicate_test_name(self, test_db, sample_lab_test_types):
        """Test creating lab test type with duplicate name."""
        service = LabTestTypeService()
        
        # Try to create duplicate of existing test
        with pytest.raises(ValueError, match="already exists"):
            service.create_lab_test_type(
                db=test_db,
                name="Total Plate Count",  # Already exists
                category="Microbiological",
                unit_of_measurement="CFU/g"
            )
    
    def test_update_lab_test_type_name_conflict(self, test_db, sample_lab_test_types):
        """Test updating lab test type to existing name."""
        service = LabTestTypeService()
        
        # Try to update test1 name to test2 name
        with pytest.raises(ValueError, match="already exists"):
            service.update_lab_test_type(
                db=test_db,
                test_type_id=sample_lab_test_types[0].id,
                test_name=sample_lab_test_types[1].test_name  # E. coli
            )
    
    def test_search_by_name(self, test_db, sample_lab_test_types):
        """Test searching by exact test name."""
        service = LabTestTypeService()
        
        # Search by exact name (case insensitive)
        result = service.search_by_name_or_abbreviation(test_db, "total plate count")
        assert result is not None
        assert result.test_name == "Total Plate Count"
        
        # Search by name that doesn't exist
        result = service.search_by_name_or_abbreviation(test_db, "Non-existent Test")
        assert result is None
    
    def test_search_by_abbreviation(self, test_db, sample_lab_test_types):
        """Test searching by abbreviation."""
        service = LabTestTypeService()
        
        # Search by abbreviation
        result = service.search_by_name_or_abbreviation(test_db, "TPC")
        assert result is not None
        assert result.test_name == "Total Plate Count"
        
        # Search by another abbreviation
        result = service.search_by_name_or_abbreviation(test_db, "E.coli")
        assert result is not None
        assert result.test_name == "E. coli"
        
        # Search by abbreviation that doesn't exist
        result = service.search_by_name_or_abbreviation(test_db, "XYZ")
        assert result is None
    
    def test_get_by_category(self, test_db, sample_lab_test_types):
        """Test getting tests by category."""
        service = LabTestTypeService()
        
        # Get microbiological tests
        micro_tests = service.get_by_category(test_db, "Microbiological")
        assert len(micro_tests) == 2
        assert all(t.test_category == "Microbiological" for t in micro_tests)
        assert all(t.is_active for t in micro_tests)
        
        # Get heavy metals tests
        metal_tests = service.get_by_category(test_db, "Heavy Metals")
        assert len(metal_tests) == 2
        assert all(t.test_category == "Heavy Metals" for t in metal_tests)
    
    def test_get_all_grouped(self, test_db, sample_lab_test_types):
        """Test getting all tests grouped by category."""
        service = LabTestTypeService()
        
        grouped = service.get_all_grouped(test_db)
        
        # Check structure
        assert isinstance(grouped, dict)
        assert "Microbiological" in grouped
        assert "Heavy Metals" in grouped
        assert "Nutritional" in grouped
        assert "Allergens" in grouped
        
        # Check counts
        assert len(grouped["Microbiological"]) == 2
        assert len(grouped["Heavy Metals"]) == 2
        assert len(grouped["Nutritional"]) == 1
        assert len(grouped["Allergens"]) == 1
        
        # Verify ordering within groups
        micro_tests = grouped["Microbiological"]
        assert micro_tests[0].test_name < micro_tests[1].test_name  # Alphabetical
    
    def test_get_categories(self, test_db, sample_lab_test_types):
        """Test getting list of used categories."""
        service = LabTestTypeService()
        
        categories = service.get_categories(test_db)
        
        assert isinstance(categories, list)
        assert len(categories) == 4  # 4 distinct categories in fixtures
        assert "Microbiological" in categories
        assert "Heavy Metals" in categories
        assert "Nutritional" in categories
        assert "Allergens" in categories
    
    def test_delete_unused_test_type(self, test_db):
        """Test deleting unused lab test type."""
        service = LabTestTypeService()
        
        # Create test type
        test_type = service.create_lab_test_type(
            db=test_db,
            name="Temporary Test",
            category="Physical",
            unit_of_measurement="unit"
        )
        test_id = test_type.id
        
        # Delete it
        result = service.delete_lab_test_type(test_db, test_id)
        assert result is True
        
        # Verify it's gone
        deleted = service.get(test_db, test_id)
        assert deleted is None
    
    def test_delete_used_test_type(self, test_db, sample_product_with_specs, sample_lab_test_types):
        """Test deleting lab test type that's in use."""
        service = LabTestTypeService()
        
        # Try to delete test type that has specifications
        with pytest.raises(ValueError, match="Cannot delete: Test type is used"):
            service.delete_lab_test_type(test_db, sample_lab_test_types[0].id)


@pytest.mark.integration
@pytest.mark.slow
class TestLabTestTypeBulkOperations:
    """Test bulk operations and performance scenarios."""
    
    def test_seed_common_lab_tests(self, test_db):
        """Test seeding database with common lab tests."""
        service = LabTestTypeService()
        
        # Common microbiological tests
        micro_tests = [
            ("Coliform", "Microbiological", "CFU/g", "AOAC 991.14"),
            ("Staphylococcus aureus", "Microbiological", "CFU/g", "AOAC 2003.07"),
            ("Listeria monocytogenes", "Microbiological", "Positive/Negative", "AOAC 2013.10"),
            ("Bacillus cereus", "Microbiological", "CFU/g", "AOAC 2012.02"),
        ]
        
        # Common heavy metals
        metal_tests = [
            ("Cadmium", "Heavy Metals", "ppm", "USP <2232>"),
            ("Mercury", "Heavy Metals", "ppm", "USP <2232>"),
            ("Chromium", "Heavy Metals", "ppm", "USP <2232>"),
        ]
        
        # Common pesticides
        pesticide_tests = [
            ("Glyphosate", "Pesticides", "ppm", "LC-MS/MS"),
            ("Organophosphates", "Pesticides", "ppm", "GC-MS"),
            ("Organochlorines", "Pesticides", "ppm", "GC-MS"),
        ]
        
        created_count = 0
        
        for test_data in micro_tests + metal_tests + pesticide_tests:
            try:
                service.create_lab_test_type(
                    db=test_db,
                    name=test_data[0],
                    category=test_data[1],
                    unit_of_measurement=test_data[2],
                    default_method=test_data[3]
                )
                created_count += 1
            except ValueError:
                pass  # Skip duplicates
        
        assert created_count == 10  # All should be created
        
        # Verify grouping works with larger dataset
        grouped = service.get_all_grouped(test_db)
        assert len(grouped["Microbiological"]) >= 4
        assert len(grouped["Heavy Metals"]) >= 3
        assert len(grouped["Pesticides"]) == 3
    
    def test_inactive_tests_excluded_from_groups(self, test_db, sample_lab_test_types):
        """Test that inactive tests are excluded from grouped results."""
        service = LabTestTypeService()
        
        # Deactivate a test
        service.update_lab_test_type(
            db=test_db,
            test_type_id=sample_lab_test_types[0].id,
            is_active=False
        )
        
        # Get grouped tests
        grouped = service.get_all_grouped(test_db)
        
        # Verify deactivated test is not included
        micro_tests = grouped["Microbiological"]
        assert len(micro_tests) == 1  # Only E. coli remains
        assert micro_tests[0].test_name == "E. coli"