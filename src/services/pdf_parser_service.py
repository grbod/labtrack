"""PDF parsing service with AI integration for extracting lab test results."""

import json
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from abc import ABC, abstractmethod

from sqlalchemy.orm import Session
from loguru import logger

from ..models import ParsingQueue, ParsingStatus, TestResult, Lot
from ..services.base import BaseService
from ..utils.pdf_utils import extract_text_from_pdf, extract_text_with_tables, extract_images_from_pdf


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    async def extract_data(
        self, text: str, prompt: str
    ) -> Tuple[Dict[str, Any], float]:
        """Extract data from text using AI. Returns (data, confidence)."""
        pass


class MockAIProvider(AIProvider):
    """Mock AI provider for testing."""

    async def extract_data(
        self, text: str, prompt: str
    ) -> Tuple[Dict[str, Any], float]:
        """Mock extraction that returns sample data."""
        # Simple pattern matching for testing
        reference_match = re.search(r"REF[:\s]*(\d{6}-\d{3})", text, re.IGNORECASE)
        lot_match = re.search(r"LOT[:\s]*([A-Z0-9]+)", text, re.IGNORECASE)

        mock_data = {
            "reference_number": (
                reference_match.group(1) if reference_match else "241001-001"
            ),
            "lot_number": lot_match.group(1) if lot_match else "ABC123",
            "test_date": "2024-10-01",
            "lab_name": "Test Lab Inc",
            "test_results": {
                "Total Plate Count": {
                    "value": "< 10",
                    "unit": "CFU/g",
                    "confidence": 0.95,
                },
                "Yeast/Mold": {"value": "< 10", "unit": "CFU/g", "confidence": 0.92},
                "E. Coli": {"value": "Negative", "unit": "", "confidence": 0.98},
                "Salmonella": {"value": "Negative", "unit": "", "confidence": 0.97},
                "Lead": {"value": "0.05", "unit": "ppm", "confidence": 0.88},
                "Mercury": {"value": "< 0.01", "unit": "ppm", "confidence": 0.85},
                "Cadmium": {"value": "0.02", "unit": "ppm", "confidence": 0.87},
                "Arsenic": {"value": "< 0.1", "unit": "ppm", "confidence": 0.86},
            },
        }

        # Calculate overall confidence
        confidences = [r["confidence"] for r in mock_data["test_results"].values()]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.5

        return mock_data, overall_confidence


class PDFParserService:
    """Service for parsing PDF lab reports and extracting test data."""

    def __init__(self, ai_provider: Optional[AIProvider] = None):
        # Use PydanticAI by default if GOOGLE_API_KEY is set
        from ..config import settings
        
        if ai_provider is None and settings.google_api_key:
            try:
                from .pydantic_ai_provider import PydanticAIProvider
                self.ai_provider = PydanticAIProvider()
                logger.info("Using PydanticAI provider with Gemini")
            except Exception as e:
                logger.warning(f"Failed to initialize PydanticAI provider: {e}")
                self.ai_provider = MockAIProvider()
        else:
            self.ai_provider = ai_provider or MockAIProvider()
        self.confidence_threshold = 0.7

    def get_extraction_prompt(self, lab_format: str = "generic") -> str:
        """Get the extraction prompt for the AI."""
        return """
        Extract the following information from this lab test report:
        
        1. Reference Number (format: YYMMDD-XXX)
        2. Lot Number
        3. Test Date
        4. Lab Name
        5. Test Results including:
           - Microbiological tests (Total Plate Count, Yeast/Mold, E. Coli, Salmonella, etc.)
           - Heavy metals (Lead, Mercury, Cadmium, Arsenic)
           - Any other test results
        
        For each test result, extract:
        - Test name
        - Value (including < or > symbols)
        - Unit (CFU/g, ppm, mg/kg, etc.)
        
        Return the data in JSON format with confidence scores (0.0-1.0) for each field.
        
        Example format:
        {
            "reference_number": "241001-001",
            "lot_number": "ABC123",
            "test_date": "2024-10-01",
            "lab_name": "Lab Name",
            "test_results": {
                "Total Plate Count": {"value": "< 10", "unit": "CFU/g", "confidence": 0.95},
                ...
            }
        }
        """

    async def parse_pdf(self, db: Session, pdf_path: Path, max_retries: int = 3) -> Dict[str, Any]:
        """Parse a PDF file and extract test data."""
        logger.info(f"Parsing PDF: {pdf_path}")

        # Create parsing queue entry
        queue_entry = ParsingQueue(
            pdf_filename=pdf_path.name, status=ParsingStatus.PROCESSING
        )
        db.add(queue_entry)
        db.commit()

        try:
            # Use enhanced text extraction with tables
            text = extract_text_with_tables(pdf_path)
            if not text:
                raise ValueError("No text extracted from PDF")

            # Try parsing with retries
            best_result = None
            best_confidence = 0.0

            for attempt in range(max_retries):
                try:
                    prompt = self.get_extraction_prompt()
                    data, confidence = await self.ai_provider.extract_data(text, prompt)

                    if confidence > best_confidence:
                        best_result = data
                        best_confidence = confidence

                    if confidence >= self.confidence_threshold:
                        break

                except Exception as e:
                    logger.warning(f"Parsing attempt {attempt + 1} failed: {e}")

            if not best_result:
                raise ValueError("Failed to extract data from PDF")

            # Update parsing queue
            queue_entry.extracted_data = json.dumps(best_result)
            queue_entry.confidence_score = best_confidence
            queue_entry.reference_number = best_result.get("reference_number")

            # Check for extraction metadata (errors and warnings)
            metadata = best_result.get("_extraction_metadata", {})
            
            if metadata.get("errors"):
                queue_entry.error_message = "; ".join(metadata["errors"])
            
            if metadata.get("warnings"):
                queue_entry.notes = f"Warnings: {'; '.join(metadata['warnings'])}"

            if best_confidence >= self.confidence_threshold:
                queue_entry.status = ParsingStatus.RESOLVED
                # Process the results
                await self._process_extracted_data(db, best_result, pdf_path.name)
            else:
                queue_entry.status = ParsingStatus.PENDING
                if not queue_entry.notes:
                    queue_entry.notes = f"Low confidence: {best_confidence:.2f}"
                else:
                    queue_entry.notes += f"; Low confidence: {best_confidence:.2f}"
                logger.warning(f"Low confidence extraction: {best_confidence:.2f}")

            db.commit()
            return {
                "status": (
                    "success"
                    if best_confidence >= self.confidence_threshold
                    else "review_needed"
                ),
                "data": best_result,
                "confidence": best_confidence,
                "queue_id": queue_entry.id,
            }

        except Exception as e:
            logger.error(f"Failed to parse PDF {pdf_path}: {e}")
            queue_entry.status = ParsingStatus.FAILED
            queue_entry.error_message = str(e)
            db.commit()

            return {"status": "failed", "error": str(e), "queue_id": queue_entry.id}

    async def _process_extracted_data(
        self, db: Session, data: Dict[str, Any], pdf_filename: str
    ) -> None:
        """Process extracted data and create test results."""
        # Find the lot by reference number
        reference_number = data.get("reference_number")
        if not reference_number:
            raise ValueError("No reference number found")

        lot = (
            db.query(Lot).filter_by(reference_number=reference_number).first()
        )
        if not lot:
            logger.warning(f"Lot not found for reference number: {reference_number}")
            return

        # Create test results
        test_date = datetime.strptime(data.get("test_date", ""), "%Y-%m-%d").date()

        for test_name, test_data in data.get("test_results", {}).items():
            test_result = TestResult(
                lot_id=lot.id,
                test_type=test_name,
                result_value=test_data["value"],
                unit=test_data.get("unit", ""),
                test_date=test_date,
                pdf_source=pdf_filename,
                confidence_score=test_data.get("confidence", 0.0),
                status="draft",
            )
            db.add(test_result)

        db.commit()
        logger.info(f"Created test results for lot {lot.lot_number}")

    def review_parsing_queue(
        self, db: Session, status: Optional[ParsingStatus] = None
    ) -> List[ParsingQueue]:
        """Get parsing queue entries for review."""
        query = db.query(ParsingQueue)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(ParsingQueue.created_at.desc()).all()

    def update_parsed_data(
        self, db: Session, queue_id: int, data: Dict[str, Any], user_id: int
    ) -> bool:
        """Manually update parsed data from the queue."""
        queue_entry = db.query(ParsingQueue).filter(ParsingQueue.id == queue_id).first()
        if not queue_entry:
            return False

        try:
            queue_entry.extracted_data = json.dumps(data)
            # Handle status transition properly
            if queue_entry.status == ParsingStatus.PENDING:
                queue_entry.status = ParsingStatus.PROCESSING
                db.flush()  # Ensure the transition is recorded
            queue_entry.status = ParsingStatus.RESOLVED
            queue_entry.resolved_at = datetime.utcnow()
            queue_entry.assigned_to = str(user_id)

            # Process the data
            import asyncio
            asyncio.create_task(self._process_extracted_data(db, data, queue_entry.pdf_filename))

            db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to update parsed data: {e}")
            db.rollback()
            return False

    def get_confidence_statistics(self, db: Session) -> Dict[str, Any]:
        """Get parsing confidence statistics."""
        queue_entries = (
            db.query(ParsingQueue)
            .filter(ParsingQueue.confidence_score.isnot(None))
            .all()
        )

        if not queue_entries:
            return {"average_confidence": 0, "total_parsed": 0}

        confidences = [e.confidence_score for e in queue_entries]
        return {
            "average_confidence": sum(confidences) / len(confidences),
            "total_parsed": len(queue_entries),
            "high_confidence": len(
                [c for c in confidences if c >= self.confidence_threshold]
            ),
            "low_confidence": len(
                [c for c in confidences if c < self.confidence_threshold]
            ),
        }
