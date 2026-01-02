"""Tests for PDF parsing functionality."""

import pytest
import asyncio
from pathlib import Path
from datetime import date

from app.services.pdf_parser_service import PDFParserService, MockAIProvider
from app.models import ParsingQueue, ParsingStatus, Lot, TestResult


class TestPDFParsing:
    """Test PDF parsing service."""

    @pytest.fixture
    def mock_pdf_content(self):
        """Mock PDF text content."""
        return """
        Laboratory Test Report
        
        Reference Number: REF: 241101-001
        LOT: ABC123
        Test Date: November 1, 2024
        
        Microbiological Analysis:
        Total Plate Count: < 10 CFU/g
        E. Coli: Negative
        Salmonella: Negative
        
        Heavy Metals:
        Lead: 0.05 ppm
        Mercury: < 0.01 ppm
        """

    def test_mock_ai_extraction(self, mock_pdf_content):
        """Test mock AI provider extraction."""
        provider = MockAIProvider()

        # Run async function
        data, confidence = asyncio.run(
            provider.extract_data(mock_pdf_content, "extract test data")
        )

        # Debug print to see what's returned
        print(f"Extracted data: {data}")

        assert data["reference_number"] == "241101-001"
        assert data["lot_number"] == "ABC123"
        assert confidence > 0.8

    def test_parsing_queue_creation(self, test_db, tmp_path):
        """Test that parsing creates queue entry."""
        service = PDFParserService()

        # Create a mock PDF file
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_text("mock pdf content")

        # Mock the PDF extraction
        async def mock_parse():
            try:
                result = await service.parse_pdf(test_db, pdf_path)
                return result
            except:
                # Expected to fail without real PDF
                pass

        asyncio.run(mock_parse())

        # Check queue entry was created
        queue_entries = test_db.query(ParsingQueue).all()
        assert len(queue_entries) == 1
        assert queue_entries[0].pdf_filename == "test.pdf"

    def test_confidence_threshold(self, test_db):
        """Test confidence threshold handling."""
        service = PDFParserService()

        # Default threshold
        assert service.confidence_threshold == 0.7

        # Low confidence should go to review
        # (Would test with actual PDF parsing)

    def test_process_extracted_data(self, test_db, sample_lot):
        """Test processing extracted data into test results."""
        service = PDFParserService()

        # Mock extracted data
        data = {
            "reference_number": sample_lot.reference_number,
            "lot_number": sample_lot.lot_number,
            "test_date": "2024-11-01",
            "lab_name": "Test Lab",
            "test_results": {
                "Total Plate Count": {
                    "value": "< 10",
                    "unit": "CFU/g",
                    "confidence": 0.95,
                },
                "E. Coli": {"value": "Negative", "unit": "", "confidence": 0.98},
            },
        }

        # Process the data
        asyncio.run(service._process_extracted_data(test_db, data, "test.pdf"))

        # Check test results were created
        results = test_db.query(TestResult).filter_by(lot_id=sample_lot.id).all()
        assert len(results) == 2

        # Check specific results
        plate_count = next(r for r in results if r.test_type == "Total Plate Count")
        assert plate_count.result_value == "< 10"
        assert plate_count.unit == "CFU/g"
        assert plate_count.pdf_source == "test.pdf"

    def test_review_queue_update(self, test_db):
        """Test manual review queue updates."""
        service = PDFParserService()

        # Create a pending queue entry
        queue_entry = ParsingQueue(
            pdf_filename="review.pdf",
            status=ParsingStatus.PENDING,
            reference_number="241101-002",
        )
        test_db.add(queue_entry)
        test_db.commit()

        # Update with manual data
        manual_data = {
            "reference_number": "241101-002",
            "lot_number": "MANUAL123",
            "test_date": "2024-11-01",
            "test_results": {},
        }

        success = service.update_parsed_data(test_db, queue_entry.id, manual_data, user_id=1)

        assert success
        test_db.refresh(queue_entry)
        assert queue_entry.status == ParsingStatus.RESOLVED
        assert queue_entry.assigned_to == "1"
