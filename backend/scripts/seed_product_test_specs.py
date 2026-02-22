"""One-time script to seed product-test specifications into an existing database.

Usage:
    cd backend
    python scripts/seed_product_test_specs.py
"""

import csv
import sys
import os
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import and_
from app.database import SessionLocal, engine, Base
from app.models import Product, LabTestType, ProductTestSpecification

MAPPING_CSV = Path(__file__).parent.parent / "product_test_mapping.csv"


def seed_specs():
    if not MAPPING_CSV.exists():
        print(f"ERROR: Mapping CSV not found at {MAPPING_CSV}")
        sys.exit(1)

    db = SessionLocal()
    try:
        # Build lookup dicts
        products = db.query(Product).all()
        product_lookup: dict[tuple, int] = {}
        for p in products:
            key = (p.brand.lower(), p.product_name.lower(), (p.flavor or "").lower())
            product_lookup[key] = p.id

        test_types = db.query(LabTestType).all()
        test_lookup: dict[str, int] = {t.test_name.lower(): t.id for t in test_types}

        print(f"Found {len(product_lookup)} products and {len(test_lookup)} test types in DB")

        created = 0
        skipped_existing = 0
        skipped_no_product = 0
        skipped_no_test = 0
        skipped_no_tests_col = 0

        with open(MAPPING_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tests_str = row.get("Required Tests", "").strip()
                specs_str = row.get("Specifications", "").strip()
                if not tests_str:
                    skipped_no_tests_col += 1
                    continue

                brand = row["Brand"].strip()
                product_name = row["Product"].strip()
                flavor = row.get("Flavor", "").strip()

                product_key = (brand.lower(), product_name.lower(), flavor.lower())
                product_id = product_lookup.get(product_key)
                if product_id is None:
                    skipped_no_product += 1
                    continue

                test_names = [t.strip() for t in tests_str.split(";")]
                specifications = [s.strip() for s in specs_str.split(";")] if specs_str else []

                for i, test_name in enumerate(test_names):
                    test_id = test_lookup.get(test_name.lower())
                    if test_id is None:
                        print(f"  WARNING: Test type '{test_name}' not found")
                        skipped_no_test += 1
                        continue

                    # Check if this spec already exists
                    existing = db.query(ProductTestSpecification).filter(
                        and_(
                            ProductTestSpecification.product_id == product_id,
                            ProductTestSpecification.lab_test_type_id == test_id,
                        )
                    ).first()
                    if existing:
                        skipped_existing += 1
                        continue

                    spec_value = specifications[i] if i < len(specifications) else "TBD"
                    db.add(
                        ProductTestSpecification(
                            product_id=product_id,
                            lab_test_type_id=test_id,
                            specification=spec_value,
                            is_required=True,
                        )
                    )
                    created += 1

        db.commit()

        print(f"\nResults:")
        print(f"  Created:              {created}")
        print(f"  Skipped (existing):   {skipped_existing}")
        print(f"  Skipped (no product): {skipped_no_product}")
        print(f"  Skipped (no test):    {skipped_no_test}")
        print(f"  Skipped (no tests):   {skipped_no_tests_col}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed_specs()
