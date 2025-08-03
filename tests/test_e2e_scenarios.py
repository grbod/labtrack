"""End-to-end test scenarios for COA PDF parsing with PydanticAI."""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models import User, Product, Lot, TestResult, ParsingQueue, ParsingStatus
from src.services.pdf_parser_service import PDFParserService
from src.services.pydantic_ai_provider import PydanticAIProvider
from src.services.user_service import UserService
from src.services.lot_service import LotService
from src.services.test_result_service import TestResultService
from tests.fixtures.sample_coa_data import MOCK_PDF_SCENARIOS


class TestE2EScenarios:
    """End-to-end test scenarios for the complete PDF parsing workflow."""
    
    @pytest.fixture
    def test_db(self):
        """Create a test database with initial data."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        # Create test user
        user = User(
            username="testuser",
            email="test@example.com",
            role="QC_MANAGER",
            is_active=True
        )
        user.set_password("testpass123")
        session.add(user)
        
        # Create test product
        product = Product(
            name="Organic Protein Powder",
            sku="OPP-001",
            category="Nutritional Supplements"
        )
        session.add(product)
        session.commit()
        
        yield session
        session.close()
    
    @pytest.fixture
    def mock_pdf_files(self):
        """Create mock PDF files for testing."""
        pdf_files = {}
        
        for scenario_name, scenario_data in MOCK_PDF_SCENARIOS.items():
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                f.write(b"%PDF-1.4\n" + scenario_data["text"].encode())
                pdf_files[scenario_name] = Path(f.name)
        
        yield pdf_files
        
        # Cleanup
        for pdf_path in pdf_files.values():
            if pdf_path.exists():
                os.unlink(pdf_path)
    
    @pytest.mark.asyncio
    async def test_complete_workflow_perfect_coa(self, test_db, mock_pdf_files):
        """Test complete workflow with a perfect COA."""
        # Setup services
        user_service = UserService()
        lot_service = LotService()
        test_result_service = TestResultService()
        
        # Get test user and product
        user = test_db.query(User).first()
        product = test_db.query(Product).first()
        
        # Create lot
        lot = lot_service.create_lot(
            test_db,
            lot_number="ABC123",
            product_id=product.id,
            production_date=datetime.now(),
            quantity=1000.0,
            unit="kg",
            created_by=user.id
        )
        
        # Mock AI provider
        with patch('src.services.pdf_parser_service.PydanticAIProvider') as mock_provider_class:
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            
            # Setup mock extraction
            async def mock_extract(text, prompt):
                if "241215-001" in text:
                    return {
                        "reference_number": lot.reference_number,
                        "lot_number": "ABC123",
                        "test_date": "2024-12-15",
                        "lab_name": "TestLab Inc.",
                        "test_results": {
                            "Total Plate Count": {
                                "value": "< 10",
                                "unit": "CFU/g",
                                "specification": "< 10,000",
                                "status": "Pass",
                                "confidence": 0.95
                            },
                            "Lead": {
                                "value": "0.05",
                                "unit": "ppm",
                                "specification": "< 0.5",
                                "status": "Pass",
                                "confidence": 0.93
                            }
                        },
                        "_extraction_metadata": {
                            "errors": [],
                            "warnings": [],
                            "has_tables": True
                        }
                    }, 0.94
                return {}, 0.0
            
            mock_provider.extract_data = mock_extract
            
            # Mock text extraction
            with patch('src.services.pdf_parser_service.extract_text_with_tables') as mock_extract_text:
                mock_extract_text.return_value = MOCK_PDF_SCENARIOS["perfect_coa"]["text"]
                
                # Parse PDF
                parser = PDFParserService()
                result = await parser.parse_pdf(
                    test_db,
                    mock_pdf_files["perfect_coa"]
                )
        
        # Verify parsing results
        assert result["status"] == "success"
        assert result["confidence"] == 0.94
        assert result["data"]["reference_number"] == lot.reference_number
        
        # Check database state
        # 1. Parsing queue entry
        queue_entry = test_db.query(ParsingQueue).first()
        assert queue_entry is not None
        assert queue_entry.status == ParsingStatus.RESOLVED
        assert queue_entry.confidence_score == 0.94
        
        # 2. Test results created
        test_results = test_db.query(TestResult).filter_by(lot_id=lot.id).all()
        assert len(test_results) == 2
        
        # Verify test results
        tpc_result = next((r for r in test_results if r.test_type == "Total Plate Count"), None)
        assert tpc_result is not None
        assert tpc_result.value == "< 10"
        assert tpc_result.unit == "CFU/g"
        assert tpc_result.status == "DRAFT"
        
        lead_result = next((r for r in test_results if r.test_type == "Lead"), None)
        assert lead_result is not None
        assert lead_result.value == "0.05"
        assert lead_result.unit == "ppm"
    
    @pytest.mark.asyncio
    async def test_workflow_with_manual_review(self, test_db):
        """Test workflow requiring manual review and correction."""
        # Create initial lot
        product = test_db.query(Product).first()
        user = test_db.query(User).first()
        
        lot_service = LotService()
        lot = lot_service.create_lot(
            test_db,
            lot_number="XYZ789",
            product_id=product.id,
            production_date=datetime.now(),
            quantity=500.0,
            unit="kg",
            created_by=user.id
        )
        
        # Create low-confidence parsing result
        queue_entry = ParsingQueue(
            pdf_filename="unclear_coa.pdf",
            status=ParsingStatus.PENDING,
            confidence_score=0.45,
            extracted_data={
                "reference_number": "UNCLEAR",
                "lot_number": "XYZ???",
                "test_results": {
                    "Unknown Test": {"value": "5.2", "unit": "???"}
                },
                "_extraction_metadata": {
                    "errors": ["Reference number unclear", "Test names not recognized"],
                    "warnings": ["Low quality scan"]
                }
            },
            error_message="Low confidence extraction"
        )
        test_db.add(queue_entry)
        test_db.commit()
        
        # Simulate manual review and correction
        parser = PDFParserService()
        
        corrected_data = {
            "reference_number": lot.reference_number,
            "lot_number": "XYZ789",
            "test_date": "2024-12-15",
            "lab_name": "Quality Labs",
            "test_results": {
                "Total Plate Count": {
                    "value": "< 100",
                    "unit": "CFU/g",
                    "specification": "< 10,000",
                    "confidence": 1.0  # Manual entry = 100% confidence
                }
            }
        }
        
        # Update with corrected data
        success = parser.update_parsed_data(
            test_db,
            queue_entry.id,
            corrected_data,
            user_id=user.id
        )
        
        assert success is True
        
        # Verify queue entry updated
        updated_entry = test_db.query(ParsingQueue).filter_by(id=queue_entry.id).first()
        assert updated_entry.status == ParsingStatus.RESOLVED
        assert updated_entry.assigned_to == str(user.id)
        
        # Verify test results created
        test_results = test_db.query(TestResult).filter_by(lot_id=lot.id).all()
        assert len(test_results) == 1
        assert test_results[0].test_type == "Total Plate Count"
        assert test_results[0].value == "< 100"
    
    @pytest.mark.asyncio
    async def test_bulk_pdf_processing(self, test_db, mock_pdf_files):
        """Test processing multiple PDFs in sequence."""
        # Create multiple lots
        product = test_db.query(Product).first()
        user = test_db.query(User).first()
        lot_service = LotService()
        
        lots = []
        for i in range(3):
            lot = lot_service.create_lot(
                test_db,
                lot_number=f"BATCH{i:03d}",
                product_id=product.id,
                production_date=datetime.now(),
                quantity=100.0 * (i + 1),
                unit="kg",
                created_by=user.id
            )
            lots.append(lot)
        
        # Mock AI provider with different responses
        with patch('src.services.pdf_parser_service.PydanticAIProvider') as mock_provider_class:
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            
            # Track calls
            call_count = 0
            
            async def mock_extract(text, prompt):
                nonlocal call_count
                call_count += 1
                
                # Return different data for each call
                if call_count == 1:
                    return {
                        "reference_number": lots[0].reference_number,
                        "lot_number": "BATCH000",
                        "test_results": {"Test1": {"value": "1", "unit": "mg"}},
                        "_extraction_metadata": {"errors": [], "warnings": [], "has_tables": True}
                    }, 0.9
                elif call_count == 2:
                    return {
                        "reference_number": lots[1].reference_number,
                        "lot_number": "BATCH001",
                        "test_results": {"Test2": {"value": "2", "unit": "mg"}},
                        "_extraction_metadata": {"errors": [], "warnings": ["Some warnings"], "has_tables": True}
                    }, 0.8
                else:
                    return {
                        "reference_number": lots[2].reference_number,
                        "lot_number": "BATCH002",
                        "test_results": {"Test3": {"value": "3", "unit": "mg"}},
                        "_extraction_metadata": {"errors": ["Minor error"], "warnings": [], "has_tables": False}
                    }, 0.6
            
            mock_provider.extract_data = mock_extract
            
            # Process multiple PDFs
            parser = PDFParserService()
            results = []
            
            with patch('src.services.pdf_parser_service.extract_text_with_tables') as mock_extract_text:
                for pdf_path in list(mock_pdf_files.values())[:3]:
                    mock_extract_text.return_value = f"Mock content for {pdf_path.name}"
                    result = await parser.parse_pdf(test_db, pdf_path)
                    results.append(result)
        
        # Verify results
        assert len(results) == 3
        assert results[0]["confidence"] == 0.9
        assert results[1]["confidence"] == 0.8
        assert results[2]["confidence"] == 0.6
        
        # Check queue entries
        queue_entries = test_db.query(ParsingQueue).all()
        assert len(queue_entries) == 3
        assert queue_entries[0].status == ParsingStatus.RESOLVED
        assert queue_entries[1].status == ParsingStatus.RESOLVED
        assert queue_entries[2].status == ParsingStatus.PENDING  # Low confidence
        
        # Check test results
        all_test_results = test_db.query(TestResult).all()
        assert len(all_test_results) == 3  # One per lot
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, test_db):
        """Test error recovery and retry mechanisms."""
        product = test_db.query(Product).first()
        user = test_db.query(User).first()
        
        # Create lot
        lot_service = LotService()
        lot = lot_service.create_lot(
            test_db,
            lot_number="ERROR123",
            product_id=product.id,
            production_date=datetime.now(),
            quantity=250.0,
            unit="kg",
            created_by=user.id
        )
        
        # Mock AI provider that fails then succeeds
        with patch('src.services.pdf_parser_service.PydanticAIProvider') as mock_provider_class:
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            
            attempt_count = 0
            
            async def mock_extract(text, prompt):
                nonlocal attempt_count
                attempt_count += 1
                
                if attempt_count <= 2:
                    raise Exception("Temporary AI service error")
                
                return {
                    "reference_number": lot.reference_number,
                    "lot_number": "ERROR123",
                    "test_results": {"Recovery Test": {"value": "OK", "unit": "-"}},
                    "_extraction_metadata": {"errors": [], "warnings": ["Recovered after retry"], "has_tables": True}
                }, 0.85
            
            mock_provider.extract_data = mock_extract
            
            # Create mock PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                f.write(b"%PDF-1.4\nError test content")
                pdf_path = Path(f.name)
            
            try:
                with patch('src.services.pdf_parser_service.extract_text_with_tables') as mock_extract_text:
                    mock_extract_text.return_value = "Error recovery test content"
                    
                    parser = PDFParserService()
                    result = await parser.parse_pdf(
                        test_db,
                        pdf_path,
                        max_retries=3
                    )
                
                # Should succeed after retries
                assert result["status"] == "success"
                assert attempt_count == 3
                assert "Recovered after retry" in result["data"]["_extraction_metadata"]["warnings"]
                
            finally:
                if pdf_path.exists():
                    os.unlink(pdf_path)
    
    def test_statistics_and_reporting(self, test_db):
        """Test confidence statistics and reporting features."""
        # Create various parsing results
        entries = [
            ParsingQueue(pdf_filename="high1.pdf", confidence_score=0.95, status=ParsingStatus.RESOLVED),
            ParsingQueue(pdf_filename="high2.pdf", confidence_score=0.88, status=ParsingStatus.RESOLVED),
            ParsingQueue(pdf_filename="medium1.pdf", confidence_score=0.65, status=ParsingStatus.PENDING),
            ParsingQueue(pdf_filename="medium2.pdf", confidence_score=0.60, status=ParsingStatus.PENDING),
            ParsingQueue(pdf_filename="low1.pdf", confidence_score=0.45, status=ParsingStatus.PENDING),
            ParsingQueue(pdf_filename="failed1.pdf", confidence_score=None, status=ParsingStatus.FAILED),
        ]
        
        for entry in entries:
            test_db.add(entry)
        test_db.commit()
        
        # Get statistics
        parser = PDFParserService()
        stats = parser.get_confidence_statistics(test_db)
        
        # Verify statistics
        assert stats["total_parsed"] == 5  # Excludes failed entry
        assert stats["average_confidence"] == pytest.approx(0.706, rel=0.01)  # (0.95+0.88+0.65+0.60+0.45)/5
        assert stats["high_confidence"] == 2  # >= 0.7
        assert stats["low_confidence"] == 3   # < 0.7
        
        # Test review queue filtering
        pending_items = parser.review_parsing_queue(test_db, ParsingStatus.PENDING)
        assert len(pending_items) == 3
        
        resolved_items = parser.review_parsing_queue(test_db, ParsingStatus.RESOLVED)
        assert len(resolved_items) == 2