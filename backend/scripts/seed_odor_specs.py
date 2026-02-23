"""One-time script to seed Odor test specs into an existing database.

Usage:
    cd backend
    python scripts/seed_odor_specs.py
"""

import os
import sys

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func

from app.database import Base, SessionLocal, engine
from app.models import LabTestType, Product, ProductTestSpecification

ODOR_TEST_NAME = "Odor"
ODOR_TEST_METHOD = "Organoleptic"
ODOR_TEST_CATEGORY = "Physical"
ODOR_DEFAULT_SPEC = "Conforms to standard"


def seed_odor_specs() -> None:
    db = SessionLocal()
    try:
        # 1) Ensure Odor lab test type exists.
        odor_test = (
            db.query(LabTestType)
            .filter(func.lower(LabTestType.test_name) == ODOR_TEST_NAME.lower())
            .first()
        )
        test_created = False

        if odor_test is None:
            odor_test = LabTestType(
                test_name=ODOR_TEST_NAME,
                test_method=ODOR_TEST_METHOD,
                test_category=ODOR_TEST_CATEGORY,
                default_specification=ODOR_DEFAULT_SPEC,
                default_unit=None,
                is_active=True,
            )
            db.add(odor_test)
            db.flush()  # Needed to get odor_test.id
            test_created = True

        # 2) Add Odor product specs where missing.
        products = db.query(Product).all()
        existing_product_ids = {
            product_id
            for (product_id,) in (
                db.query(ProductTestSpecification.product_id)
                .filter(ProductTestSpecification.lab_test_type_id == odor_test.id)
                .all()
            )
        }

        created_specs = 0
        existing_specs = 0

        for product in products:
            if product.id in existing_product_ids:
                existing_specs += 1
                continue

            db.add(
                ProductTestSpecification(
                    product_id=product.id,
                    lab_test_type_id=odor_test.id,
                    specification=ODOR_DEFAULT_SPEC,
                    is_required=True,
                )
            )
            created_specs += 1

        db.commit()

        print("Seed complete:")
        print(f"  Odor test type created: {'yes' if test_created else 'no'}")
        print(f"  Product specs created:  {created_specs}")
        print(f"  Product specs existing: {existing_specs}")
        print(f"  Products scanned:       {len(products)}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed_odor_specs()
