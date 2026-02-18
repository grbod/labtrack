"""Database seeding for first-time startup."""

import csv
import hashlib
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import User, LabTestType, Product
from app.models.enums import UserRole
from app.utils.logger import logger

SEED_TESTS_CSV = Path(__file__).parent.parent / "seed_tests.csv"
PRODUCT_CSV = Path(__file__).parent.parent.parent / "product_seed_data.csv"


def _hash_password(password: str) -> str:
    """Hash a password using SHA256 with the application salt."""
    return hashlib.sha256(f"coa_system_salt_{password}".encode()).hexdigest()


def _build_users() -> list[User]:
    """Build the default user objects."""
    return [
        User(
            username="admin",
            email="admin@coasystem.com",
            role=UserRole.ADMIN,
            password_hash=_hash_password("admin123"),
            active=True,
            full_name="Greg Simek",
            title="President",
        ),
        User(
            username="qcmanager",
            email="qc@coasystem.com",
            role=UserRole.QC_MANAGER,
            password_hash=_hash_password("qc123"),
            active=True,
            full_name="Tatyana Villegas",
            title="Quality Assurance Manager",
        ),
        User(
            username="labtech",
            email="lab@coasystem.com",
            role=UserRole.LAB_TECH,
            password_hash=_hash_password("lab123"),
            active=True,
        ),
    ]


def _load_lab_test_types() -> list[LabTestType]:
    """Load lab test types from the seed CSV file."""
    if not SEED_TESTS_CSV.exists():
        logger.warning(f"Seed tests CSV not found at {SEED_TESTS_CSV}, skipping lab test types")
        return []

    test_types: list[LabTestType] = []
    with open(SEED_TESTS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_types.append(
                LabTestType(
                    test_name=row["test_name"],
                    test_method=row["test_method"] or None,
                    test_category=row["test_category"],
                    default_unit=row["default_unit"] or None,
                    default_specification=row["default_specification"] or None,
                    is_active=True,
                )
            )
    return test_types


def _load_products() -> list[Product]:
    """Load products from the seed CSV file."""
    if not PRODUCT_CSV.exists():
        logger.warning(f"Product CSV not found at {PRODUCT_CSV}, skipping products")
        return []

    products: list[Product] = []
    with open(PRODUCT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            brand = row["Brand"].strip()
            product_name = row["Product"].strip()
            flavor = row["Flavor"].strip() if row["Flavor"].strip() else None

            if flavor:
                display_name = f"{brand} {product_name} - {flavor}"
            else:
                display_name = f"{brand} {product_name}"

            products.append(
                Product(
                    brand=brand,
                    product_name=product_name,
                    flavor=flavor,
                    display_name=display_name,
                )
            )
    return products


def seed_if_empty(engine) -> None:
    """Seed the database with default data if it has not been seeded yet.

    Args:
        engine: SQLAlchemy engine instance. A session is created from this
                engine to perform all seed operations in a single transaction.
    """
    session = Session(bind=engine)
    try:
        user_count = session.execute(text("SELECT COUNT(*) FROM users")).scalar()
        if user_count > 0:
            logger.info("Database already seeded, skipping")
            return

        users = _build_users()
        test_types = _load_lab_test_types()
        products = _load_products()

        session.add_all(users)
        session.add_all(test_types)
        session.add_all(products)

        session.commit()

        logger.info(
            f"Database seeded: {len(users)} users, "
            f"{len(test_types)} lab test types, "
            f"{len(products)} products"
        )
    except Exception:
        session.rollback()
        logger.exception("Failed to seed database")
    finally:
        session.close()
