"""One-time script to merge Physical→Organoleptic for sensory tests.

Updates Appearance, Taste, and Odor lab test types:
  - test_category: Physical → Organoleptic
  - test_method:   Visual   → Organoleptic  (Appearance only)

Usage:
    cd backend
    python scripts/merge_organoleptic_category.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func

from app.database import Base, SessionLocal, engine
from app.models import LabTestType

TESTS_TO_UPDATE = ["Appearance", "Taste", "Odor"]


def merge_organoleptic() -> None:
    db = SessionLocal()
    try:
        updated = 0
        for name in TESTS_TO_UPDATE:
            test = (
                db.query(LabTestType)
                .filter(func.lower(LabTestType.test_name) == name.lower())
                .first()
            )
            if test is None:
                print(f"  SKIP: '{name}' not found")
                continue

            changed = False
            if test.test_category != "Organoleptic":
                print(f"  {name}: test_category '{test.test_category}' → 'Organoleptic'")
                test.test_category = "Organoleptic"
                changed = True
            if test.test_method != "Organoleptic":
                print(f"  {name}: test_method '{test.test_method}' → 'Organoleptic'")
                test.test_method = "Organoleptic"
                changed = True

            if changed:
                updated += 1
            else:
                print(f"  {name}: already up to date")

        db.commit()
        print(f"\nUpdated {updated} lab test type(s)")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    merge_organoleptic()
