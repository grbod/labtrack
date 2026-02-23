"""One-time script to update heavy metals spec values in an existing database.

Updates default specifications on LabTestType rows and
ProductTestSpecification rows for Arsenic, Cadmium, Lead, Mercury.

Old → New:
  Arsenic:  < 1.5 ppm  → < 15 ppm
  Cadmium:  < 0.5 ppm  → < 10 ppm
  Lead:     < 0.5 ppm  → < 10 ppm
  Mercury:  < 0.2 ppm  → < 3 ppm

Usage:
    cd backend
    python scripts/update_metals_specs.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func

from app.database import Base, SessionLocal, engine
from app.models import LabTestType, ProductTestSpecification

# Mapping: test_name → (old_spec, new_spec)
METALS_UPDATES = {
    "Arsenic": ("< 1.5 ppm", "< 15 ppm"),
    "Cadmium": ("< 0.5 ppm", "< 10 ppm"),
    "Lead": ("< 0.5 ppm", "< 10 ppm"),
    "Mercury": ("< 0.2 ppm", "< 3 ppm"),
    "Heavy Metals Panel (As, Cd, Hg, Pb)": (
        "As < 1.5, Cd < 0.5, Pb < 0.5, Hg < 0.2",
        "As < 15, Cd < 10, Pb < 10, Hg < 3",
    ),
}


def update_metals_specs() -> None:
    db = SessionLocal()
    try:
        test_types_updated = 0
        product_specs_updated = 0

        for test_name, (old_spec, new_spec) in METALS_UPDATES.items():
            lab_test = (
                db.query(LabTestType)
                .filter(func.lower(LabTestType.test_name) == test_name.lower())
                .first()
            )
            if lab_test is None:
                print(f"  SKIP: LabTestType '{test_name}' not found")
                continue

            # Update default_specification on the test type itself
            if lab_test.default_specification == old_spec:
                lab_test.default_specification = new_spec
                test_types_updated += 1
                print(f"  LabTestType '{test_name}': {old_spec} → {new_spec}")
            elif lab_test.default_specification == new_spec:
                print(f"  LabTestType '{test_name}': already up to date")
            else:
                print(
                    f"  WARN: LabTestType '{test_name}' has unexpected spec: "
                    f"'{lab_test.default_specification}'"
                )

            # Update all ProductTestSpecification rows for this test type
            specs = (
                db.query(ProductTestSpecification)
                .filter(
                    ProductTestSpecification.lab_test_type_id == lab_test.id,
                    ProductTestSpecification.specification == old_spec,
                )
                .all()
            )
            for spec in specs:
                spec.specification = new_spec
                product_specs_updated += 1

            already = (
                db.query(ProductTestSpecification)
                .filter(
                    ProductTestSpecification.lab_test_type_id == lab_test.id,
                    ProductTestSpecification.specification == new_spec,
                )
                .count()
            )
            print(
                f"    ProductSpecs updated: {len(specs)}, already current: {already}"
            )

        db.commit()

        print("\nSummary:")
        print(f"  LabTestTypes updated:        {test_types_updated}")
        print(f"  ProductTestSpecs updated:     {product_specs_updated}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    update_metals_specs()
