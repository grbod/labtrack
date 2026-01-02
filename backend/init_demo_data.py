#!/usr/bin/env python3
"""Initialize demo data for COA Management System."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import date, timedelta
from app.database import get_db, init_db
from app.models import Product, Lot, User, TestResult
from app.models.enums import UserRole, LotType, LotStatus, TestResultStatus
from app.services.user_service import UserService

def create_demo_data():
    """Create demo data for testing."""
    # Initialize database
    init_db()
    
    # Get database session
    db = next(get_db())
    
    try:
        # Create users
        user_service = UserService()
        
        # Create admin user
        admin = user_service.create_user(
            db,
            username="admin",
            email="admin@coasystem.com",
            password="admin123",
            role=UserRole.ADMIN
        )
        
        # Create QC Manager
        qc_manager = user_service.create_user(
            db,
            username="qcmanager",
            email="qc@coasystem.com",
            password="qc123",
            role=UserRole.QC_MANAGER
        )
        
        # Create Lab Tech
        lab_tech = user_service.create_user(
            db,
            username="labtech",
            email="lab@coasystem.com",
            password="lab123",
            role=UserRole.LAB_TECH
        )
        
        print("✅ Created users: admin, qcmanager, labtech")
        
        # Create products
        products = []
        product_data = [
            ("Truvani", "Organic Whey Protein", "Chocolate Peanut Butter", "20 serving"),
            ("Truvani", "Organic Whey Protein", "Vanilla", "20 serving"),
            ("Truvani", "Plant Based Protein", "Chocolate", "20 serving"),
            ("Truvani", "Plant Based Protein", "Vanilla", "20 serving"),
            ("Garden of Life", "Raw Organic Protein", "Vanilla", "22 oz"),
            ("Garden of Life", "Raw Organic Protein", "Chocolate", "22 oz"),
        ]
        
        for brand, name, flavor, size in product_data:
            product = Product(
                brand=brand,
                product_name=name,
                flavor=flavor,
                size=size,
                display_name=f"{brand} {name} - {flavor} ({size})"
            )
            db.add(product)
            products.append(product)
        
        db.commit()
        print(f"✅ Created {len(products)} products")
        
        # Create lots
        lots = []
        lot_data = [
            ("LOT2024001", LotType.STANDARD, date(2024, 10, 1), date(2027, 10, 1), LotStatus.APPROVED, products[0]),
            ("LOT2024002", LotType.STANDARD, date(2024, 10, 15), date(2027, 10, 15), LotStatus.TESTED, products[1]),
            ("LOT2024003", LotType.STANDARD, date(2024, 11, 1), date(2027, 11, 1), LotStatus.PENDING, products[2]),
            ("PARENT2024001", LotType.PARENT_LOT, date(2024, 9, 1), date(2027, 9, 1), LotStatus.APPROVED, products[3]),
        ]
        
        for lot_num, lot_type, mfg, exp, status, product in lot_data:
            lot = Lot(
                lot_number=lot_num,
                lot_type=lot_type,
                reference_number=f"24{mfg.month:02d}{mfg.day:02d}-001",
                mfg_date=mfg,
                exp_date=exp,
                status=status,
                generate_coa=True
            )
            db.add(lot)
            db.flush()
            
            # Associate product with lot
            from app.models import LotProduct
            lot_product = LotProduct(lot_id=lot.id, product_id=product.id)
            db.add(lot_product)
            lots.append(lot)
        
        db.commit()
        print(f"✅ Created {len(lots)} lots")
        
        # Create test results for approved lots
        test_types = [
            ("Total Plate Count", "< 10", "CFU/g", TestResultStatus.APPROVED),
            ("Yeast/Mold", "< 10", "CFU/g", TestResultStatus.APPROVED),
            ("E. Coli", "Negative", "", TestResultStatus.APPROVED),
            ("Salmonella", "Negative", "", TestResultStatus.APPROVED),
            ("Lead", "0.05", "ppm", TestResultStatus.APPROVED),
            ("Mercury", "< 0.01", "ppm", TestResultStatus.REVIEWED),
            ("Cadmium", "0.02", "ppm", TestResultStatus.DRAFT),
        ]
        
        test_count = 0
        for lot in lots[:2]:  # First two lots
            for test_type, value, unit, status in test_types:
                test_result = TestResult(
                    lot_id=lot.id,
                    test_type=test_type,
                    result_value=value,
                    unit=unit,
                    test_date=lot.mfg_date + timedelta(days=5),
                    status=status,
                    confidence_score=0.95,
                    pdf_source="lab_report_001.pdf"
                )
                
                if status == TestResultStatus.APPROVED:
                    test_result.approved_by_id = qc_manager.id
                    test_result.approved_at = date.today()
                
                db.add(test_result)
                test_count += 1
        
        db.commit()
        print(f"✅ Created {test_count} test results")
        
        print("\n🎉 Demo data created successfully!")
        print("\nYou can now log in with:")
        print("  Username: admin, Password: admin123 (Admin)")
        print("  Username: qcmanager, Password: qc123 (QC Manager)")
        print("  Username: labtech, Password: lab123 (Lab Tech)")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating demo data: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_demo_data()