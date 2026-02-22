"""Database seeding for first-time startup."""

import csv
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import User, LabTestType, Product, ProductTestSpecification
from app.models.enums import UserRole
from app.core.security import get_password_hash
from app.utils.logger import logger

SEED_TESTS_CSV = Path(__file__).parent.parent / "seed_tests.csv"
PRODUCT_CSV = Path(__file__).parent.parent.parent / "product_seed_data.csv"
PRODUCT_TEST_MAPPING_CSV = Path(__file__).parent.parent / "product_test_mapping.csv"


def _build_users() -> list[User]:
    """Build the default user objects."""
    return [
        User(
            username="admin",
            email="admin@labtrack.com",
            role=UserRole.ADMIN,
            password_hash=get_password_hash("admin123"),
            active=True,
            full_name="Greg Simek",
            title="President",
        ),
        User(
            username="qcmanager",
            email="qc@labtrack.com",
            role=UserRole.QC_MANAGER,
            password_hash=get_password_hash("qc123"),
            active=True,
            full_name="Tatyana Villegas",
            title="Quality Assurance Manager",
        ),
        User(
            username="labtech",
            email="lab@labtrack.com",
            role=UserRole.LAB_TECH,
            password_hash=get_password_hash("lab123"),
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


def _load_product_test_specs(session: Session) -> int:
    """Load product-test specifications from the mapping CSV.

    Must be called AFTER products and lab test types have been committed,
    since we look them up by name to resolve IDs. Does NOT commit -- the
    caller is responsible for committing the session.

    Returns the number of specs added to the session.
    """
    if not PRODUCT_TEST_MAPPING_CSV.exists():
        logger.warning(
            f"Product test mapping CSV not found at {PRODUCT_TEST_MAPPING_CSV}, "
            "skipping product test specs"
        )
        return 0

    # Build lookup dicts: (brand, product_name, flavor) -> product_id
    products = session.query(Product).all()
    product_lookup: dict[tuple, int] = {}
    for p in products:
        key = (p.brand.lower(), p.product_name.lower(), (p.flavor or "").lower())
        product_lookup[key] = p.id

    # Build lookup dict: test_name -> lab_test_type_id
    test_types = session.query(LabTestType).all()
    test_lookup: dict[str, int] = {t.test_name.lower(): t.id for t in test_types}

    specs: list[ProductTestSpecification] = []
    skipped = 0

    with open(PRODUCT_TEST_MAPPING_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tests_str = row.get("Required Tests", "").strip()
            specs_str = row.get("Specifications", "").strip()
            if not tests_str:
                continue

            brand = row["Brand"].strip()
            product_name = row["Product"].strip()
            flavor = row.get("Flavor", "").strip()

            product_key = (brand.lower(), product_name.lower(), flavor.lower())
            product_id = product_lookup.get(product_key)
            if product_id is None:
                logger.warning(
                    f"Product not found for spec seeding: "
                    f"brand={brand!r}, product={product_name!r}, flavor={flavor!r}"
                )
                skipped += 1
                continue

            test_names = [t.strip() for t in tests_str.split(";")]
            specifications = [s.strip() for s in specs_str.split(";")] if specs_str else []

            for i, test_name in enumerate(test_names):
                test_id = test_lookup.get(test_name.lower())
                if test_id is None:
                    logger.warning(f"Test type '{test_name}' not found, skipping")
                    continue

                spec_value = specifications[i] if i < len(specifications) else "TBD"
                specs.append(
                    ProductTestSpecification(
                        product_id=product_id,
                        lab_test_type_id=test_id,
                        specification=spec_value,
                        is_required=True,
                    )
                )

    if specs:
        session.add_all(specs)

    if skipped:
        logger.warning(f"Skipped {skipped} rows with unmatched products")

    return len(specs)


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
            # Check if product test specs need backfill (e.g. after a partial seed)
            spec_count = session.execute(
                text("SELECT COUNT(*) FROM product_test_specifications")
            ).scalar()
            if spec_count == 0:
                logger.info("No product test specs found, backfilling...")
                created = _load_product_test_specs(session)
                session.commit()
                logger.info(f"Backfilled {created} product test specs")
            return

        users = _build_users()
        test_types = _load_lab_test_types()
        products = _load_products()

        session.add_all(users)
        session.add_all(test_types)
        session.add_all(products)

        session.commit()

        # Load product-test specs after products and test types are committed
        spec_count = _load_product_test_specs(session)
        session.commit()

        logger.info(
            f"Database seeded: {len(users)} users, "
            f"{len(test_types)} lab test types, "
            f"{len(products)} products, "
            f"{spec_count} product test specs"
        )
    except Exception:
        session.rollback()
        logger.exception("Failed to seed database")
    finally:
        session.close()
