"""Unit tests for lab test type default specifications."""

import pytest
from sqlalchemy.orm import Session

from app.models import LabTestType
from app.services.lab_test_type_service import LabTestTypeService


class TestLabTestTypeDefaultSpecification:
    """Test default specification functionality."""

    def test_create_test_type_with_default_spec(self, test_db: Session):
        """Test creating lab test type with default specification."""
        service = LabTestTypeService()
        
        test_type = service.create_lab_test_type(
            db=test_db,
            name="Total Plate Count",
            category="Microbiological",
            unit_of_measurement="CFU/g",
            default_method="USP <2021>",
            default_specification="< 10,000 CFU/g"
        )
        
        assert test_type.default_specification == "< 10,000 CFU/g"
        assert test_type.test_name == "Total Plate Count"
        assert test_type.test_category == "Microbiological"

    def test_create_test_type_without_default_spec(self, test_db: Session):
        """Test creating lab test type without default specification."""
        service = LabTestTypeService()
        
        test_type = service.create_lab_test_type(
            db=test_db,
            name="E. coli",
            category="Microbiological",
            unit_of_measurement="Positive/Negative",
            default_method="USP <2022>"
        )
        
        assert test_type.default_specification is None
        assert test_type.test_name == "E. coli"

    def test_update_default_specification(self, test_db: Session):
        """Test updating default specification."""
        service = LabTestTypeService()
        
        # Create test type without default spec
        test_type = service.create_lab_test_type(
            db=test_db,
            name="Lead",
            category="Heavy Metals",
            unit_of_measurement="ppm"
        )
        
        assert test_type.default_specification is None
        
        # Update with default spec
        updated = service.update_lab_test_type(
            db=test_db,
            test_type_id=test_type.id,
            default_specification="< 0.5 ppm"
        )
        
        assert updated.default_specification == "< 0.5 ppm"
        
        # Update to different spec
        updated2 = service.update_lab_test_type(
            db=test_db,
            test_type_id=test_type.id,
            default_specification="< 1.0 ppm"
        )
        
        assert updated2.default_specification == "< 1.0 ppm"
        
        # Clear default spec
        updated3 = service.update_lab_test_type(
            db=test_db,
            test_type_id=test_type.id,
            default_specification=None
        )
        
        assert updated3.default_specification is None

    def test_default_spec_validation(self, test_db: Session):
        """Test default specification validation."""
        service = LabTestTypeService()
        
        # Empty string should be converted to None
        test_type = service.create_lab_test_type(
            db=test_db,
            name="Arsenic",
            category="Heavy Metals",
            unit_of_measurement="ppm",
            default_specification=""
        )
        
        # Model validation should convert empty string to None
        test_db.refresh(test_type)
        assert test_type.default_specification is None
        
        # Whitespace-only should be converted to None
        test_type2 = service.create_lab_test_type(
            db=test_db,
            name="Mercury",
            category="Heavy Metals", 
            unit_of_measurement="ppm",
            default_specification="   "
        )
        
        test_db.refresh(test_type2)
        assert test_type2.default_specification is None

    def test_common_default_specifications(self, test_db: Session):
        """Test creating test types with common default specifications."""
        service = LabTestTypeService()
        
        test_cases = [
            ("Total Plate Count", "< 10,000 CFU/g"),
            ("Yeast & Mold", "< 1,000 CFU/g"),
            ("E. coli", "Negative"),
            ("Salmonella", "Negative per 25g"),
            ("Lead", "< 0.5 ppm"),
            ("Arsenic", "< 0.2 ppm"),
            ("Protein", "20-25 g/100g"),
        ]
        
        for test_name, default_spec in test_cases:
            test_type = service.create_lab_test_type(
                db=test_db,
                name=test_name,
                category="Microbiological" if "CFU" in default_spec or "Negative" in default_spec else "Heavy Metals" if "ppm" in default_spec else "Nutritional",
                unit_of_measurement="CFU/g" if "CFU/g" in default_spec else "Positive/Negative" if "Negative" in default_spec else "ppm" if "ppm" in default_spec else "g/100g",
                default_specification=default_spec
            )
            
            assert test_type.default_specification == default_spec
            assert test_type.test_name == test_name

    def test_default_spec_in_grouped_query(self, test_db: Session):
        """Test that default specifications are included in grouped queries."""
        service = LabTestTypeService()
        
        # Create test types with default specs
        service.create_lab_test_type(
            db=test_db,
            name="Total Plate Count",
            category="Microbiological",
            unit_of_measurement="CFU/g",
            default_specification="< 10,000 CFU/g"
        )
        
        service.create_lab_test_type(
            db=test_db,
            name="Lead",
            category="Heavy Metals",
            unit_of_measurement="ppm",
            default_specification="< 0.5 ppm"
        )
        
        # Get grouped tests
        grouped = service.get_all_grouped(test_db)
        
        # Verify default specifications are present
        micro_tests = grouped.get("Microbiological", [])
        assert len(micro_tests) == 1
        assert micro_tests[0].default_specification == "< 10,000 CFU/g"
        
        metal_tests = grouped.get("Heavy Metals", [])
        assert len(metal_tests) == 1
        assert metal_tests[0].default_specification == "< 0.5 ppm"

    def test_search_with_default_spec(self, test_db: Session):
        """Test search functionality includes default specifications."""
        service = LabTestTypeService()
        
        test_type = service.create_lab_test_type(
            db=test_db,
            name="Total Plate Count",
            category="Microbiological",
            unit_of_measurement="CFU/g",
            default_specification="< 10,000 CFU/g",
            abbreviations=["TPC", "Aerobic Plate Count"]
        )
        
        # Search by name should return test with default spec
        found = service.search_by_name_or_abbreviation(test_db, "Total Plate Count")
        assert found is not None
        assert found.default_specification == "< 10,000 CFU/g"
        
        # Search by abbreviation should also work
        found_abbrev = service.search_by_name_or_abbreviation(test_db, "TPC")
        assert found_abbrev is not None
        assert found_abbrev.default_specification == "< 10,000 CFU/g"


# Run with: pytest tests/test_lab_test_type_default_spec.py -v