"""Base parsing strategy for COA PDFs."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import re
from pathlib import Path
from app.utils.logger import logger


class BaseParsingStrategy(ABC):
    """
    Abstract base class for PDF parsing strategies.

    Each strategy implements parsing logic for specific lab formats or document types.
    """

    def __init__(self):
        """Initialize base parsing strategy."""
        self.confidence_threshold = 0.7
        self.field_patterns = self._define_field_patterns()

    @abstractmethod
    def _define_field_patterns(self) -> Dict[str, str]:
        """
        Define regex patterns for extracting fields.

        Returns:
            Dictionary mapping field names to regex patterns
        """
        pass

    @abstractmethod
    def parse(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse PDF content and extract relevant fields.

        Args:
            content: Dictionary with extracted PDF content (text, tables, etc.)

        Returns:
            Dictionary with extracted fields and confidence scores
        """
        pass

    @abstractmethod
    def get_ai_prompt(self, text: str) -> str:
        """
        Generate AI prompt for parsing assistance.

        Args:
            text: Extracted text from PDF

        Returns:
            Formatted prompt for AI model
        """
        pass

    def calculate_confidence(self, value: Any, field_name: str) -> float:
        """
        Calculate confidence score for extracted value.

        Args:
            value: Extracted value
            field_name: Name of the field

        Returns:
            Confidence score between 0.0 and 1.0
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            return 0.0

        confidence = 0.5  # Base confidence

        # Increase confidence based on field-specific criteria
        if field_name == "reference_number":
            if re.match(r"^[A-Z0-9-]+$", str(value)):
                confidence += 0.3
            if len(str(value)) >= 6:
                confidence += 0.2

        elif field_name == "lot_number":
            if re.match(r"^[A-Z0-9-]+$", str(value)):
                confidence += 0.3
            if len(str(value)) >= 4:
                confidence += 0.2

        elif field_name in ["test_date", "expiry_date", "manufacture_date"]:
            try:
                # Try to parse as date
                self.parse_date(str(value))
                confidence += 0.5
            except:
                confidence -= 0.2

        elif field_name.endswith("_result"):
            # Check if it contains a number and unit
            if re.search(r"\d+\.?\d*\s*[a-zA-Z/]+", str(value)):
                confidence += 0.4

        return min(1.0, max(0.0, confidence))

    def extract_field(self, text: str, pattern: str) -> Optional[str]:
        """
        Extract field using regex pattern.

        Args:
            text: Text to search
            pattern: Regex pattern

        Returns:
            Extracted value or None
        """
        try:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                # Return first capturing group or full match
                return match.group(1) if len(match.groups()) > 0 else match.group(0)
        except re.error as e:
            logger.error(f"Invalid regex pattern: {e}")

        return None

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date from various formats.

        Args:
            date_str: Date string

        Returns:
            Parsed datetime or None
        """
        date_formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
            "%d %b %Y",
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def parse_test_result(
        self, result_str: str
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        Parse test result value and unit.

        Args:
            result_str: Result string (e.g., "25.5 mg/kg", "< 0.1 CFU/g")

        Returns:
            Tuple of (value, unit) or (None, None)
        """
        # Handle "less than" results
        less_than_match = re.match(r"<\s*(\d+\.?\d*)\s*([a-zA-Z/]+)", result_str)
        if less_than_match:
            value = float(less_than_match.group(1))
            unit = less_than_match.group(2)
            return (-value, unit)  # Negative to indicate "less than"

        # Handle standard results
        standard_match = re.match(r"(\d+\.?\d*)\s*([a-zA-Z/%]+)", result_str)
        if standard_match:
            value = float(standard_match.group(1))
            unit = standard_match.group(2)
            return (value, unit)

        # Handle "ND" (Not Detected) or similar
        if result_str.upper() in ["ND", "NOT DETECTED", "NONE DETECTED", "ABSENT"]:
            return (0.0, "ND")

        return (None, None)

    def extract_from_table(
        self, tables: List[List[List[str]]], header_pattern: str, row_identifier: str
    ) -> Optional[str]:
        """
        Extract value from tables based on header and row patterns.

        Args:
            tables: List of tables from PDF
            header_pattern: Pattern to match header
            row_identifier: Pattern to identify the row

        Returns:
            Extracted value or None
        """
        for table in tables:
            if not table or len(table) < 2:
                continue

            # Find header row
            header_row = None
            header_col = None

            for i, row in enumerate(table[:3]):  # Check first 3 rows for header
                for j, cell in enumerate(row):
                    if cell and re.search(header_pattern, cell, re.IGNORECASE):
                        header_row = i
                        header_col = j
                        break
                if header_row is not None:
                    break

            if header_row is None:
                continue

            # Find data row
            for row in table[header_row + 1 :]:
                if (
                    len(row) > 0
                    and row[0]
                    and re.search(row_identifier, row[0], re.IGNORECASE)
                ):
                    if header_col < len(row):
                        return row[header_col]

        return None

    def validate_extracted_data(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Validate extracted data and return validation errors.

        Args:
            data: Extracted data dictionary

        Returns:
            Dictionary mapping field names to list of validation errors
        """
        errors = {}

        # Check required fields
        required_fields = ["reference_number", "lot_number"]
        for field in required_fields:
            if not data.get(field):
                errors.setdefault(field, []).append(f"{field} is required")

        # Validate dates
        date_fields = ["test_date", "expiry_date", "manufacture_date"]
        for field in date_fields:
            if field in data and data[field]:
                if not isinstance(data[field], datetime):
                    try:
                        self.parse_date(data[field])
                    except:
                        errors.setdefault(field, []).append(
                            f"Invalid date format for {field}"
                        )

        # Validate test results
        for key, value in data.items():
            if key.endswith("_result") and value:
                result_value, unit = self.parse_test_result(str(value))
                if result_value is None:
                    errors.setdefault(key, []).append(
                        f"Invalid test result format for {key}"
                    )

        return errors

    def merge_with_ai_results(
        self, regex_results: Dict[str, Any], ai_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge regex extraction results with AI extraction results.

        Args:
            regex_results: Results from regex extraction
            ai_results: Results from AI extraction

        Returns:
            Merged results with highest confidence values
        """
        merged = regex_results.copy()

        for field, ai_value in ai_results.items():
            if field.endswith("_confidence"):
                continue

            regex_value = regex_results.get(field)
            regex_confidence = regex_results.get(f"{field}_confidence", 0.0)
            ai_confidence = ai_results.get(f"{field}_confidence", 0.5)

            # Use value with higher confidence
            if not regex_value or ai_confidence > regex_confidence:
                merged[field] = ai_value
                merged[f"{field}_confidence"] = ai_confidence

        return merged
