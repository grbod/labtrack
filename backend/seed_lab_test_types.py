#!/usr/bin/env python3
"""
Seed script for common lab test types.

This script populates the lab_test_types table with commonly used tests
for food/supplement products.
"""

import sys
from pathlib import Path
import json

# Add backend to path for app imports
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.services.lab_test_type_service import LabTestTypeService
from app.utils.logger import logger


def create_common_test_types():
    """Create common lab test types for food/supplement products."""
    
    # Common test types organized by category
    test_types_data = [
        # Microbiological Tests
        {
            "name": "Total Plate Count",
            "category": "Microbiological",
            "unit": "CFU/g",
            "description": "Total aerobic plate count",
            "method": "AOAC 990.12",
            "abbreviations": ["TPC", "APC", "Total Aerobic Count", "Aerobic Plate Count"]
        },
        {
            "name": "E. coli",
            "category": "Microbiological", 
            "unit": "CFU/g",
            "description": "Escherichia coli detection and enumeration",
            "method": "USP <2021>",
            "abbreviations": ["E.coli", "Escherichia coli", "E coli", "ECOLI"]
        },
        {
            "name": "Salmonella",
            "category": "Microbiological",
            "unit": "Present/Absent",
            "description": "Salmonella species detection",
            "method": "AOAC 967.25",
            "abbreviations": ["Salmonella spp", "Salmonella species"]
        },
        {
            "name": "Yeast & Mold",
            "category": "Microbiological",
            "unit": "CFU/g", 
            "description": "Combined yeast and mold count",
            "method": "AOAC 997.02",
            "abbreviations": ["Y&M", "Yeast and Mold", "YM", "Yeasts & Moulds"]
        },
        {
            "name": "Coliforms",
            "category": "Microbiological",
            "unit": "CFU/g",
            "description": "Total coliform bacteria count",
            "method": "AOAC 991.14",
            "abbreviations": ["Total Coliforms", "Coliform bacteria"]
        },
        
        # Heavy Metals
        {
            "name": "Lead",
            "category": "Heavy Metals",
            "unit": "ppm",
            "description": "Lead content analysis",
            "method": "USP <233>",
            "abbreviations": ["Pb", "Lead (Pb)"]
        },
        {
            "name": "Cadmium", 
            "category": "Heavy Metals",
            "unit": "ppm",
            "description": "Cadmium content analysis", 
            "method": "USP <233>",
            "abbreviations": ["Cd", "Cadmium (Cd)"]
        },
        {
            "name": "Mercury",
            "category": "Heavy Metals",
            "unit": "ppm", 
            "description": "Mercury content analysis",
            "method": "USP <233>",
            "abbreviations": ["Hg", "Mercury (Hg)"]
        },
        {
            "name": "Arsenic",
            "category": "Heavy Metals",
            "unit": "ppm",
            "description": "Arsenic content analysis", 
            "method": "USP <233>",
            "abbreviations": ["As", "Arsenic (As)"]
        },
        
        # Nutritional Tests
        {
            "name": "Protein",
            "category": "Nutritional",
            "unit": "%",
            "description": "Protein content by nitrogen determination",
            "method": "AOAC 992.15",
            "abbreviations": ["Crude Protein", "Total Protein"]
        },
        {
            "name": "Fat",
            "category": "Nutritional", 
            "unit": "%",
            "description": "Total fat content",
            "method": "AOAC 996.06",
            "abbreviations": ["Total Fat", "Crude Fat", "Lipids"]
        },
        {
            "name": "Moisture",
            "category": "Nutritional",
            "unit": "%", 
            "description": "Moisture content determination",
            "method": "AOAC 925.10",
            "abbreviations": ["Water Content", "Moisture Content"]
        },
        {
            "name": "Ash",
            "category": "Nutritional",
            "unit": "%",
            "description": "Ash content (total minerals)",
            "method": "AOAC 923.03", 
            "abbreviations": ["Total Ash", "Crude Ash", "Minerals"]
        },
        {
            "name": "Carbohydrates",
            "category": "Nutritional",
            "unit": "%",
            "description": "Total carbohydrate content",
            "method": "Calculation",
            "abbreviations": ["Total Carbs", "Carbs", "CHO"]
        },
        
        # Allergens
        {
            "name": "Gluten",
            "category": "Allergens",
            "unit": "ppm",
            "description": "Gluten content analysis",
            "method": "AOAC 991.19",
            "abbreviations": ["Gluten (ppm)", "Wheat Gluten"]
        },
        {
            "name": "Soy",
            "category": "Allergens", 
            "unit": "Positive/Negative",
            "description": "Soy protein detection",
            "method": "ELISA",
            "abbreviations": ["Soy Protein", "Soybean"]
        },
        {
            "name": "Milk",
            "category": "Allergens",
            "unit": "Positive/Negative", 
            "description": "Milk protein detection",
            "method": "ELISA",
            "abbreviations": ["Dairy", "Milk Protein", "Casein"]
        },
        {
            "name": "Egg",
            "category": "Allergens",
            "unit": "Positive/Negative",
            "description": "Egg protein detection",
            "method": "ELISA", 
            "abbreviations": ["Egg Protein", "Ovalbumin"]
        },
        
        # Physical Tests
        {
            "name": "pH",
            "category": "Physical",
            "unit": "pH units",
            "description": "pH measurement",
            "method": "USP <791>",
            "abbreviations": ["pH Value", "Acidity"]
        },
        {
            "name": "Water Activity",
            "category": "Physical",
            "unit": "aw",
            "description": "Water activity measurement", 
            "method": "AOAC 978.18",
            "abbreviations": ["aw", "Water Activity (aw)", "aW"]
        },
        {
            "name": "Bulk Density",
            "category": "Physical",
            "unit": "g/mL",
            "description": "Bulk density measurement",
            "method": "USP <616>",
            "abbreviations": ["Density", "Bulk Density (g/mL)"]
        },
        
        # Chemical Tests
        {
            "name": "Peroxide Value", 
            "category": "Chemical",
            "unit": "meq O2/kg",
            "description": "Peroxide value for oil quality",
            "method": "AOAC 965.33",
            "abbreviations": ["PV", "Peroxide Value (PV)"]
        },
        {
            "name": "Aflatoxins",
            "category": "Chemical",
            "unit": "ppb",
            "description": "Total aflatoxins (B1, B2, G1, G2)",
            "method": "AOAC 991.31", 
            "abbreviations": ["Total Aflatoxins", "AFT", "Aflatoxin Total"]
        }
    ]
    
    db = SessionLocal()
    service = LabTestTypeService()
    
    try:
        created_count = 0
        skipped_count = 0
        
        for test_data in test_types_data:
            try:
                # Check if test already exists
                from sqlalchemy import func
                from app.models import LabTestType
                existing = db.query(LabTestType).filter(
                    func.lower(LabTestType.test_name) == func.lower(test_data["name"])
                ).first()
                if existing:
                    logger.info(f"Test type '{test_data['name']}' already exists, skipping")
                    skipped_count += 1
                    continue
                
                # Create the test type
                test_type = service.create_lab_test_type(
                    db=db,
                    name=test_data["name"],
                    category=test_data["category"],
                    unit_of_measurement=test_data["unit"],
                    description=test_data.get("description"),
                    default_method=test_data.get("method"),
                    abbreviations=test_data.get("abbreviations", []),
                    is_active=True
                )
                
                logger.info(f"Created test type: {test_type.test_name}")
                created_count += 1
                
            except Exception as e:
                logger.error(f"Error creating test type '{test_data['name']}': {e}")
                continue
        
        logger.info(f"Seed complete: {created_count} created, {skipped_count} skipped")
        print(f"✅ Seed complete: {created_count} test types created, {skipped_count} already existed")
        
    except Exception as e:
        logger.error(f"Error during seeding: {e}")
        print(f"❌ Error during seeding: {e}")
        db.rollback()
        
    finally:
        db.close()


if __name__ == "__main__":
    print("🌱 Seeding common lab test types...")
    create_common_test_types()