"""Tests for COA generation."""

import pytest
from pathlib import Path
from datetime import date

from app.services.coa_generator_service import COAGeneratorService
from app.models import LotStatus, TestResultStatus, COAHistory


class TestCOAGeneration:
    """Test COA generation service."""

    @pytest.fixture
    def approved_lot(self, test_db, sample_lot, sample_test_results):
        """Create a lot ready for COA generation."""
        # Update lot status
        sample_lot.status = LotStatus.APPROVED

        # Approve all test results (DRAFT -> APPROVED)
        for result in sample_test_results:
            if result.status == TestResultStatus.DRAFT:
                result.status = TestResultStatus.APPROVED
                result.approved_by_id = 1
                result.approved_at = date.today()

        test_db.commit()
        return sample_lot

    def test_generate_coa_validation(self, test_db, sample_lot):
        """Test COA generation validation."""
        service = COAGeneratorService()

        # Lot not approved
        with pytest.raises(ValueError, match="not approved"):
            service.generate_coa(test_db, sample_lot.id)

        # Lot doesn't exist
        with pytest.raises(ValueError, match="not found"):
            service.generate_coa(test_db, 99999)

    def test_generate_coa_success(self, test_db, approved_lot, tmp_path, monkeypatch):
        """Test successful COA generation."""
        # Set output directory via the underlying attribute
        monkeypatch.setattr("app.config.settings.coa_output_folder", tmp_path)

        service = COAGeneratorService()

        result = service.generate_coa(
            test_db,
            approved_lot.id,
            template="standard",
            output_format="docx",
            user_id=1,
        )

        assert result["status"] == "success"
        assert len(result["files"]) > 0
        assert result["lot_number"] == approved_lot.lot_number

        # Check lot status updated
        test_db.refresh(approved_lot)
        assert approved_lot.status == LotStatus.RELEASED

        # Check COA history created
        history = test_db.query(COAHistory).filter_by(lot_id=approved_lot.id).first()
        assert history is not None
        assert history.generated_by == "1"

    def test_filename_generation(self, test_db, approved_lot):
        """Test COA filename generation."""
        service = COAGeneratorService()

        filename = service._generate_filename(approved_lot)

        # Should contain date, brand, product, lot
        assert date.today().strftime("%Y%m%d") in filename
        # Check for brand/product info (might be truncated)
        assert approved_lot.lot_number in filename

    def test_batch_coa_generation(self, test_db, approved_lot, tmp_path, monkeypatch):
        """Test batch COA generation."""
        # Patch output folder before service creation
        from app.services.coa_generator_service import COAGeneratorService as COAGen

        monkeypatch.setattr("app.config.settings.coa_output_folder", tmp_path)

        # Create service after patch so it uses the tmp_path
        service = COAGen()

        # Create another approved lot
        from app.models import Lot, LotProduct

        lot2 = Lot(
            lot_number="TEST456",
            lot_type=approved_lot.lot_type,
            reference_number="241101-003",
            status=LotStatus.APPROVED,
            generate_coa=True,
        )
        test_db.add(lot2)
        test_db.commit()

        # Link to product
        lp = LotProduct(
            lot_id=lot2.id, product_id=approved_lot.lot_products[0].product_id
        )
        test_db.add(lp)

        # Copy test results
        for result in approved_lot.test_results:
            from app.models import TestResult

            new_result = TestResult(
                lot_id=lot2.id,
                test_type=result.test_type,
                result_value=result.result_value,
                unit=result.unit,
                status=TestResultStatus.APPROVED,
                approved_by_id=1,
                approved_at=date.today(),
            )
            test_db.add(new_result)

        test_db.commit()

        # Generate batch
        result = service.generate_batch_coas(
            test_db, [approved_lot.id, lot2.id], output_format="docx"
        )

        assert len(result["success"]) == 2
        assert len(result["failed"]) == 0
        assert len(result["files"]) == 2

    def test_coa_content(self, test_db, approved_lot, tmp_path, monkeypatch):
        """Test COA document content."""
        monkeypatch.setattr("app.config.settings.coa_output_folder", tmp_path)

        service = COAGeneratorService()

        # Generate COA
        result = service.generate_coa(test_db, approved_lot.id, output_format="docx")

        # Check file exists
        coa_file = result["files"][0]
        assert coa_file.exists()

        # Would need to parse DOCX to verify content
        # For now just check file was created
        assert coa_file.stat().st_size > 0
