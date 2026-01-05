"""Integration tests for PDF parser service with PydanticAI."""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import tempfile
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.pdf_parser_service import PDFParserService
from app.services.pydantic_ai_provider import PydanticAIProvider
from app.database import Base
from app.models import ParsingQueue, ParsingStatus, Lot, TestResult, LotStatus
from tests.fixtures.sample_coa_data import MOCK_PDF_SCENARIOS


class TestPDFParserIntegration:
    """Integration tests for PDF parser service."""
    
    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()
    
    @pytest.fixture
    def mock_pdf_file(self):
        """Create a mock PDF file."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b"%PDF-1.4\nMock PDF content")
            temp_path = f.name
        
        yield Path(temp_path)
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def mock_ai_provider(self):
        """Create a mock AI provider that simulates PydanticAI behavior."""
        provider = Mock(spec=PydanticAIProvider)
        
        async def mock_extract(text, prompt):
            # Simulate different scenarios based on text content
            if "241215-001" in text:
                return {
                    "reference_number": "241215-001",
                    "lot_number": "ABC123",
                    "test_date": "2024-12-15",
                    "lab_name": "TestLab Inc.",
                    "test_results": {
                        "Total Plate Count": {
                            "value": "< 10",
                            "unit": "CFU/g",
                            "confidence": 0.95
                        }
                    },
                    "_extraction_metadata": {
                        "errors": [],
                        "warnings": [],
                        "has_tables": True
                    }
                }, 0.95
            elif "ERROR" in text:
                return {
                    "reference_number": "ERROR",
                    "lot_number": None,
                    "test_date": datetime.now().strftime("%Y-%m-%d"),
                    "lab_name": None,
                    "test_results": {},
                    "_extraction_metadata": {
                        "errors": ["Invalid format detected"],
                        "warnings": ["Missing critical data"],
                        "has_tables": False
                    }
                }, 0.3
            else:
                return {
                    "reference_number": "DEFAULT-001",
                    "lot_number": "TEST123",
                    "test_date": "2024-12-15",
                    "lab_name": "Default Lab",
                    "test_results": {},
                    "_extraction_metadata": {
                        "errors": [],
                        "warnings": ["Using default extraction"],
                        "has_tables": False
                    }
                }, 0.7
        
        provider.extract_data = AsyncMock(side_effect=mock_extract)
        return provider
    
    @pytest.mark.asyncio
    async def test_successful_pdf_parsing(self, test_db, mock_pdf_file, mock_ai_provider):
        """Test successful PDF parsing with high confidence."""
        # Create a lot for the reference number
        lot = Lot(
            lot_number="ABC123",
            reference_number="241215-001",
            status=LotStatus.AWAITING_RESULTS
        )
        test_db.add(lot)
        test_db.commit()
        
        # Mock text extraction
        with patch('app.services.pdf_parser_service.extract_text_with_tables') as mock_extract:
            mock_extract.return_value = MOCK_PDF_SCENARIOS["perfect_coa"]["text"]
            
            # Create parser with mock provider
            parser = PDFParserService(ai_provider=mock_ai_provider)
            
            # Parse PDF
            result = await parser.parse_pdf(test_db, mock_pdf_file)
        
        # Assertions
        assert result["status"] == "success"
        assert result["confidence"] == 0.95
        assert result["data"]["reference_number"] == "241215-001"
        
        # Check database entries
        queue_entry = test_db.query(ParsingQueue).first()
        assert queue_entry is not None
        assert queue_entry.status == ParsingStatus.RESOLVED
        assert float(queue_entry.confidence_score) == 0.95
        
        # Check test results were created
        test_results = test_db.query(TestResult).all()
        assert len(test_results) == 1
        assert test_results[0].test_type == "Total Plate Count"
    
    @pytest.mark.asyncio
    async def test_low_confidence_parsing(self, test_db, mock_pdf_file, mock_ai_provider):
        """Test PDF parsing with low confidence requiring review."""
        with patch('app.services.pdf_parser_service.extract_text_with_tables') as mock_extract:
            mock_extract.return_value = "ERROR in PDF content"
            
            parser = PDFParserService(ai_provider=mock_ai_provider)
            result = await parser.parse_pdf(test_db, mock_pdf_file)
        
        assert result["status"] == "review_needed"
        assert result["confidence"] == 0.3
        
        # Check queue entry
        queue_entry = test_db.query(ParsingQueue).first()
        assert queue_entry.status == ParsingStatus.PENDING
        assert "Invalid format detected" in queue_entry.error_message
        assert "Missing critical data" in queue_entry.notes
    
    @pytest.mark.asyncio
    async def test_parsing_with_retry(self, test_db, mock_pdf_file):
        """Test parsing with retry mechanism."""
        # Mock AI provider that fails first, then succeeds
        provider = Mock(spec=PydanticAIProvider)
        attempt_count = 0
        
        async def mock_extract(text, prompt):
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count == 1:
                raise Exception("Temporary failure")
            
            return {
                "reference_number": "241215-001",
                "lot_number": "ABC123",
                "test_date": "2024-12-15",
                "lab_name": "TestLab",
                "test_results": {},
                "_extraction_metadata": {"errors": [], "warnings": [], "has_tables": False}
            }, 0.8
        
        provider.extract_data = AsyncMock(side_effect=mock_extract)
        
        with patch('app.services.pdf_parser_service.extract_text_with_tables') as mock_extract:
            mock_extract.return_value = "Test PDF content"
            
            parser = PDFParserService(ai_provider=provider)
            result = await parser.parse_pdf(test_db, mock_pdf_file, max_retries=3)
        
        assert result["status"] == "success"
        assert attempt_count == 2  # Failed once, succeeded on second attempt
    
    @pytest.mark.asyncio
    async def test_parsing_complete_failure(self, test_db, mock_pdf_file):
        """Test handling of complete parsing failure."""
        # Mock AI provider that always fails
        provider = Mock(spec=PydanticAIProvider)
        provider.extract_data = AsyncMock(side_effect=Exception("AI service down"))
        
        with patch('app.services.pdf_parser_service.extract_text_with_tables') as mock_extract:
            mock_extract.return_value = "Test PDF content"
            
            parser = PDFParserService(ai_provider=provider)
            result = await parser.parse_pdf(test_db, mock_pdf_file, max_retries=2)
        
        assert result["status"] == "failed"
        assert "Failed to extract data from PDF" in result["error"]
        
        # Check queue entry
        queue_entry = test_db.query(ParsingQueue).first()
        assert queue_entry.status == ParsingStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_missing_lot_handling(self, test_db, mock_pdf_file, mock_ai_provider):
        """Test handling when lot is not found for reference number."""
        # Don't create a lot - simulate missing lot scenario
        with patch('app.services.pdf_parser_service.extract_text_with_tables') as mock_extract:
            mock_extract.return_value = MOCK_PDF_SCENARIOS["perfect_coa"]["text"]
            
            parser = PDFParserService(ai_provider=mock_ai_provider)
            result = await parser.parse_pdf(test_db, mock_pdf_file)
        
        # Should still succeed but not create test results
        assert result["status"] == "success"
        
        # No test results should be created
        test_results = test_db.query(TestResult).all()
        assert len(test_results) == 0
    
    def test_review_parsing_queue(self, test_db):
        """Test reviewing parsing queue entries."""
        # Create queue entries
        entries = [
            ParsingQueue(
                pdf_filename="test1.pdf",
                status=ParsingStatus.PENDING,
                confidence_score=0.6
            ),
            ParsingQueue(
                pdf_filename="test2.pdf",
                status=ParsingStatus.RESOLVED,
                confidence_score=0.9
            ),
            ParsingQueue(
                pdf_filename="test3.pdf",
                status=ParsingStatus.FAILED,
                error_message="Parse error"
            )
        ]
        
        for entry in entries:
            test_db.add(entry)
        test_db.commit()
        
        parser = PDFParserService()
        
        # Test filtering by status
        pending = parser.review_parsing_queue(test_db, ParsingStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].pdf_filename == "test1.pdf"
        
        # Test getting all entries
        all_entries = parser.review_parsing_queue(test_db)
        assert len(all_entries) == 3
    
    def test_confidence_statistics(self, test_db):
        """Test getting confidence statistics."""
        # Create queue entries with various confidence scores
        entries = [
            ParsingQueue(pdf_filename="test1.pdf", confidence_score=0.9),
            ParsingQueue(pdf_filename="test2.pdf", confidence_score=0.8),
            ParsingQueue(pdf_filename="test3.pdf", confidence_score=0.6),
            ParsingQueue(pdf_filename="test4.pdf", confidence_score=0.5),
            ParsingQueue(pdf_filename="test5.pdf", confidence_score=None),  # No score
        ]
        
        for entry in entries:
            test_db.add(entry)
        test_db.commit()
        
        parser = PDFParserService()
        stats = parser.get_confidence_statistics(test_db)
        
        assert stats["total_parsed"] == 4  # Excludes entry with no score
        assert float(stats["average_confidence"]) == pytest.approx(0.7, rel=0.01)  # (0.9+0.8+0.6+0.5)/4
        assert stats["high_confidence"] == 2  # >= 0.7
        assert stats["low_confidence"] == 2   # < 0.7
    
    @pytest.mark.asyncio
    async def test_update_parsed_data(self, test_db):
        """Test manually updating parsed data."""
        # Create a queue entry
        queue_entry = ParsingQueue(
            pdf_filename="test.pdf",
            status=ParsingStatus.PENDING
        )
        test_db.add(queue_entry)
        test_db.commit()
        
        # Create a lot
        lot = Lot(
            lot_number="ABC123",
            reference_number="241215-001",
            status=LotStatus.AWAITING_RESULTS
        )
        test_db.add(lot)
        test_db.commit()
        
        parser = PDFParserService()
        
        # Update with corrected data
        corrected_data = {
            "reference_number": "241215-001",
            "lot_number": "ABC123",
            "test_date": "2024-12-15",
            "lab_name": "TestLab",
            "test_results": {
                "Lead": {"value": "0.05", "unit": "ppm", "confidence": 0.9}
            }
        }
        
        success = parser.update_parsed_data(test_db, queue_entry.id, corrected_data, user_id=1)
        
        assert success is True
        
        # Check queue entry was updated
        updated_entry = test_db.query(ParsingQueue).filter_by(id=queue_entry.id).first()
        assert updated_entry.status == ParsingStatus.RESOLVED
        assert updated_entry.assigned_to == "1"
    
    def test_pydantic_ai_initialization(self, monkeypatch):
        """Test that AI provider is initialized properly."""
        # Clear any existing API keys
        monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
        monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)

        # Test parser initialization
        parser1 = PDFParserService()
        assert parser1.ai_provider is not None
        # Provider could be PydanticAIProvider or MockAIProvider based on config

        # Test with API key - should still work
        monkeypatch.setenv('GOOGLE_API_KEY', 'test-key')
        parser2 = PDFParserService()
        assert parser2.ai_provider is not None
        # When configured with a key, should use PydanticAIProvider
        assert isinstance(parser2.ai_provider, PydanticAIProvider)