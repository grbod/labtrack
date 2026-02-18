"""Populate sample tracker with dummy data for testing."""

import sys
import os
from datetime import date, timedelta
from random import choice, randint

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app.models import Product, Lot, LotProduct, TestResult, User
from app.models.enums import LotType, LotStatus, TestResultStatus

# Ensure tables exist
Base.metadata.create_all(bind=engine)

def create_sample_data():
    db = SessionLocal()

    try:
        # Check if we already have data
        existing_lots = db.query(Lot).count()
        if existing_lots > 5:
            print(f"Already have {existing_lots} lots, skipping population")
            return

        # Create or get products
        products = db.query(Product).limit(3).all()
        if not products:
            # Create some products
            product_data = [
                {"brand": "NutraPure", "product_name": "Whey Protein Isolate", "flavor": "Vanilla", "size": "2 lb"},
                {"brand": "NutraPure", "product_name": "Whey Protein Isolate", "flavor": "Chocolate", "size": "2 lb"},
                {"brand": "VitaMax", "product_name": "Multivitamin Gummies", "flavor": "Mixed Berry", "size": "60 ct"},
            ]
            for pd in product_data:
                p = Product(
                    brand=pd["brand"],
                    product_name=pd["product_name"],
                    flavor=pd["flavor"],
                    size=pd["size"],
                    display_name=f"{pd['brand']} {pd['product_name']} - {pd['flavor']} ({pd['size']})"
                )
                db.add(p)
            db.commit()
            products = db.query(Product).limit(3).all()

        print(f"Using {len(products)} products")

        # Get admin user for test result creation
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            print("No admin user found, creating one...")
            from app.services.user_service import UserService
            us = UserService()
            admin = us.create_user(db, "admin", "admin@example.com", "admin123", role="admin")

        # Sample test types with specs (max 4 per sample)
        test_configs = [
            {"type": "Total Plate Count", "unit": "CFU/g", "spec": "< 10000", "pass_values": ["< 100", "< 500", "2500", "5000"], "fail_values": ["15000", "25000"]},
            {"type": "E. coli", "unit": "", "spec": "Negative", "pass_values": ["Negative", "ND", "Not Detected"], "fail_values": ["Positive", "Detected"]},
            {"type": "Lead", "unit": "ppm", "spec": "< 0.5", "pass_values": ["0.05", "0.1", "0.25", "< 0.1"], "fail_values": ["0.8", "1.2"]},
            {"type": "Arsenic", "unit": "ppm", "spec": "< 0.2", "pass_values": ["0.02", "0.05", "< 0.1"], "fail_values": ["0.5", "0.3"]},
        ]

        # Statuses for sample tracker (not approved/released)
        statuses = [
            LotStatus.AWAITING_RESULTS,
            LotStatus.PARTIAL_RESULTS,
            LotStatus.UNDER_REVIEW,
        ]

        # Create 6 sample lots
        today = date.today()
        ref_date = today.strftime("%y%m%d")

        samples = [
            {"lot": "WPI-2026-001", "status": LotStatus.AWAITING_RESULTS, "tests": 0},
            {"lot": "WPI-2026-002", "status": LotStatus.PARTIAL_RESULTS, "tests": 2},
            {"lot": "WPI-2026-003", "status": LotStatus.UNDER_REVIEW, "tests": 4},
            {"lot": "CHO-2026-001", "status": LotStatus.PARTIAL_RESULTS, "tests": 3},
            {"lot": "VMG-2026-001", "status": LotStatus.UNDER_REVIEW, "tests": 4},
            {"lot": "WPI-2026-004", "status": LotStatus.AWAITING_RESULTS, "tests": 1},
        ]

        for i, sample in enumerate(samples):
            # Create lot
            lot = Lot(
                lot_number=sample["lot"],
                lot_type=LotType.STANDARD,
                reference_number=f"{ref_date}-{str(i+1).zfill(3)}",
                mfg_date=today - timedelta(days=randint(5, 30)),
                exp_date=today + timedelta(days=365),
                status=sample["status"],
                generate_coa=True,
            )
            db.add(lot)
            db.flush()

            # Link to a product
            product = products[i % len(products)]
            lot_product = LotProduct(lot_id=lot.id, product_id=product.id)
            db.add(lot_product)

            # Add test results (max 4)
            num_tests = sample["tests"]
            for j in range(num_tests):
                config = test_configs[j]
                # 80% pass, 20% fail
                if randint(1, 10) <= 8:
                    result_value = choice(config["pass_values"])
                else:
                    result_value = choice(config["fail_values"])

                test = TestResult(
                    lot_id=lot.id,
                    test_type=config["type"],
                    result_value=result_value,
                    unit=config["unit"],
                    specification=config["spec"],
                    test_date=today - timedelta(days=randint(1, 5)),
                    status=TestResultStatus.APPROVED if sample["status"] == LotStatus.UNDER_REVIEW else TestResultStatus.DRAFT,
                )
                db.add(test)

            print(f"Created lot {sample['lot']} with {num_tests} tests, status: {sample['status'].value}")

        db.commit()
        print("\nDone! Created 6 sample lots for tracker testing.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_sample_data()
