"""Generic lab PDF parsing strategy."""

from typing import Dict, Any, Optional, List
import re
from datetime import datetime
from app.services.parsing_strategies.base_strategy import BaseParsingStrategy
from app.utils.logger import logger


class GenericLabStrategy(BaseParsingStrategy):
    """
    Generic parsing strategy for laboratory COA PDFs.

    This strategy uses common patterns found in most lab reports.
    """

    def _define_field_patterns(self) -> Dict[str, str]:
        """Define regex patterns for common lab report fields."""
        return {
            # Reference/Report numbers
            "reference_number": r"(?:Report\s*#?|Reference\s*#?|COA\s*#?|Certificate\s*#?)\s*:?\s*([A-Z0-9-]+)",
            "lab_report_number": r"(?:Lab\s*Report\s*#?|Laboratory\s*#?)\s*:?\s*([A-Z0-9-]+)",
            # Lot/Batch numbers
            "lot_number": r"(?:Lot\s*#?|Batch\s*#?)\s*:?\s*([A-Z0-9-]+)",
            "batch_number": r"(?:Batch\s*#?|Lot\s*#?)\s*:?\s*([A-Z0-9-]+)",
            # Product information
            "product_name": r"(?:Product\s*Name|Sample\s*Name|Material)\s*:?\s*([^\n]+)",
            "product_code": r"(?:Product\s*Code|Item\s*#?|SKU)\s*:?\s*([A-Z0-9-]+)",
            # Dates
            "test_date": r"(?:Test\s*Date|Analysis\s*Date|Date\s*Tested)\s*:?\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})",
            "manufacture_date": r"(?:Manufacture\s*Date|Mfg\s*Date|Production\s*Date)\s*:?\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})",
            "expiry_date": r"(?:Expiry\s*Date|Expiration\s*Date|Best\s*Before)\s*:?\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})",
            "retest_date": r"(?:Retest\s*Date|Re-test\s*Date)\s*:?\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})",
            # Lab information
            "lab_name": r"(?:Laboratory|Lab\s*Name|Testing\s*Facility)\s*:?\s*([^\n]+)",
            "lab_address": r"(?:Lab\s*Address|Laboratory\s*Address)\s*:?\s*([^\n]+(?:\n[^\n]+)?)",
            # Common test results patterns
            "heavy_metals": r"(?:Heavy\s*Metals|Total\s*Heavy\s*Metals)\s*:?\s*([<>]?\s*\d+\.?\d*\s*[a-zA-Z/]+)",
            "lead": r"(?:Lead|Pb)\s*:?\s*([<>]?\s*\d+\.?\d*\s*[a-zA-Z/]+)",
            "arsenic": r"(?:Arsenic|As)\s*:?\s*([<>]?\s*\d+\.?\d*\s*[a-zA-Z/]+)",
            "cadmium": r"(?:Cadmium|Cd)\s*:?\s*([<>]?\s*\d+\.?\d*\s*[a-zA-Z/]+)",
            "mercury": r"(?:Mercury|Hg)\s*:?\s*([<>]?\s*\d+\.?\d*\s*[a-zA-Z/]+)",
            # Microbiological results
            "total_plate_count": r"(?:Total\s*Plate\s*Count|TPC|Aerobic\s*Plate\s*Count)\s*:?\s*([<>]?\s*\d+\.?\d*\s*[a-zA-Z/]+)",
            "yeast_mold": r"(?:Yeast\s*&?\s*Mold|Yeast\s*and\s*Mold)\s*:?\s*([<>]?\s*\d+\.?\d*\s*[a-zA-Z/]+)",
            "e_coli": r"(?:E\.\s*coli|Escherichia\s*coli)\s*:?\s*([<>]?\s*\d+\.?\d*\s*[a-zA-Z/]+|Negative|Absent)",
            "salmonella": r"(?:Salmonella)\s*:?\s*([<>]?\s*\d+\.?\d*\s*[a-zA-Z/]+|Negative|Absent)",
            "coliforms": r"(?:Coliforms|Total\s*Coliforms)\s*:?\s*([<>]?\s*\d+\.?\d*\s*[a-zA-Z/]+)",
            # Physical properties
            "moisture": r"(?:Moisture|Water\s*Content)\s*:?\s*([<>]?\s*\d+\.?\d*\s*%)",
            "ash": r"(?:Ash|Total\s*Ash)\s*:?\s*([<>]?\s*\d+\.?\d*\s*%)",
            "ph": r"(?:pH|Ph)\s*:?\s*(\d+\.?\d*)",
            # Conclusion/Status
            "conclusion": r"(?:Conclusion|Result|Status)\s*:?\s*(Pass|Fail|Complies|Does\s*not\s*comply)",
            "pass_fail": r"(?:Pass/Fail|Result)\s*:?\s*(Pass|Fail|PASS|FAIL)",
        }

    def parse(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse PDF content using regex patterns and table extraction.

        Args:
            content: Dictionary with extracted PDF content

        Returns:
            Dictionary with extracted fields and confidence scores
        """
        text = content.get("text", "")
        tables = content.get("tables", [])

        extracted_data = {}
        confidence_scores = {}

        # Extract using regex patterns
        for field_name, pattern in self.field_patterns.items():
            value = self.extract_field(text, pattern)
            if value:
                extracted_data[field_name] = value
                confidence_scores[f"{field_name}_confidence"] = (
                    self.calculate_confidence(value, field_name)
                )

        # Try to extract from tables
        if tables:
            table_data = self._extract_from_tables(tables)
            for field_name, value in table_data.items():
                if value and field_name not in extracted_data:
                    extracted_data[field_name] = value
                    confidence_scores[f"{field_name}_confidence"] = (
                        self.calculate_confidence(value, field_name)
                    )

        # Post-process dates
        for date_field in [
            "test_date",
            "manufacture_date",
            "expiry_date",
            "retest_date",
        ]:
            if date_field in extracted_data:
                parsed_date = self.parse_date(extracted_data[date_field])
                if parsed_date:
                    extracted_data[date_field] = parsed_date.strftime("%Y-%m-%d")

        # Post-process test results
        for field_name in list(extracted_data.keys()):
            if any(
                field_name.startswith(prefix)
                for prefix in [
                    "heavy_metals",
                    "lead",
                    "arsenic",
                    "cadmium",
                    "mercury",
                    "total_plate_count",
                    "yeast_mold",
                    "e_coli",
                    "salmonella",
                    "coliforms",
                    "moisture",
                    "ash",
                ]
            ):
                value_str = extracted_data[field_name]
                value, unit = self.parse_test_result(value_str)
                if value is not None:
                    extracted_data[f"{field_name}_value"] = value
                    extracted_data[f"{field_name}_unit"] = unit

        # Determine overall quality
        self._determine_overall_quality(extracted_data, confidence_scores)

        # Validate extracted data
        validation_errors = self.validate_extracted_data(extracted_data)

        return {
            "extracted_data": extracted_data,
            "confidence_scores": confidence_scores,
            "validation_errors": validation_errors,
            "extraction_method": "regex_and_tables",
        }

    def _extract_from_tables(self, tables: List[List[List[str]]]) -> Dict[str, Any]:
        """
        Extract data from tables in the PDF.

        Args:
            tables: List of tables extracted from PDF

        Returns:
            Dictionary of extracted values
        """
        extracted = {}

        # Common test result table headers
        test_headers = ["Test", "Parameter", "Analysis", "Test Name"]
        result_headers = ["Result", "Value", "Found", "Actual"]

        for table in tables:
            if not table or len(table) < 2:
                continue

            # Try to identify header row
            header_row = None
            test_col = None
            result_col = None

            for i, row in enumerate(table[:3]):
                for j, cell in enumerate(row):
                    if cell:
                        cell_clean = cell.strip()
                        if any(h in cell_clean for h in test_headers):
                            header_row = i
                            test_col = j
                        elif any(h in cell_clean for h in result_headers):
                            result_col = j

                if (
                    header_row is not None
                    and test_col is not None
                    and result_col is not None
                ):
                    break

            if header_row is None or test_col is None or result_col is None:
                continue

            # Extract test results from table
            for row in table[header_row + 1 :]:
                if len(row) > max(test_col, result_col):
                    test_name = row[test_col].strip() if row[test_col] else ""
                    result = row[result_col].strip() if row[result_col] else ""

                    if test_name and result:
                        # Map test names to field names
                        field_name = self._map_test_name_to_field(test_name)
                        if field_name:
                            extracted[field_name] = result

        return extracted

    def _map_test_name_to_field(self, test_name: str) -> Optional[str]:
        """
        Map test names from tables to standardized field names.

        Args:
            test_name: Test name from table

        Returns:
            Standardized field name or None
        """
        test_name_lower = test_name.lower()

        mappings = {
            "lead": "lead",
            "pb": "lead",
            "arsenic": "arsenic",
            "as": "arsenic",
            "cadmium": "cadmium",
            "cd": "cadmium",
            "mercury": "mercury",
            "hg": "mercury",
            "total plate count": "total_plate_count",
            "tpc": "total_plate_count",
            "aerobic plate count": "total_plate_count",
            "yeast & mold": "yeast_mold",
            "yeast and mold": "yeast_mold",
            "e. coli": "e_coli",
            "escherichia coli": "e_coli",
            "salmonella": "salmonella",
            "coliforms": "coliforms",
            "total coliforms": "coliforms",
            "moisture": "moisture",
            "water content": "moisture",
            "ash": "ash",
            "total ash": "ash",
            "ph": "ph",
        }

        for key, field in mappings.items():
            if key in test_name_lower:
                return field

        return None

    def _determine_overall_quality(
        self, data: Dict[str, Any], confidence_scores: Dict[str, float]
    ) -> None:
        """
        Determine overall data quality based on extracted fields and confidence.

        Args:
            data: Extracted data
            confidence_scores: Confidence scores for each field
        """
        # Count high confidence fields
        high_confidence_count = sum(
            1
            for score in confidence_scores.values()
            if score >= self.confidence_threshold
        )
        total_fields = len(confidence_scores)

        # Check critical fields
        critical_fields = ["reference_number", "lot_number"]
        critical_present = all(field in data for field in critical_fields)

        # Calculate overall quality score
        if total_fields > 0:
            quality_ratio = high_confidence_count / total_fields

            if critical_present and quality_ratio >= 0.8:
                data["overall_quality"] = "high"
            elif critical_present and quality_ratio >= 0.6:
                data["overall_quality"] = "medium"
            else:
                data["overall_quality"] = "low"
        else:
            data["overall_quality"] = "failed"

        confidence_scores["overall_confidence"] = (
            quality_ratio if total_fields > 0 else 0.0
        )

    def get_ai_prompt(self, text: str) -> str:
        """
        Generate AI prompt for parsing assistance.

        Args:
            text: Extracted text from PDF

        Returns:
            Formatted prompt for AI model
        """
        prompt = f"""You are a laboratory COA (Certificate of Analysis) parsing assistant. 
Please extract the following information from the provided laboratory report text:

1. Reference/Report Number
2. Lot/Batch Number
3. Product Name
4. Product Code/SKU
5. Test Date
6. Manufacture Date
7. Expiry Date
8. Laboratory Name
9. Test Results (with values and units):
   - Heavy Metals (Lead, Arsenic, Cadmium, Mercury)
   - Microbiological (Total Plate Count, Yeast & Mold, E. coli, Salmonella)
   - Physical Properties (Moisture, Ash, pH)
10. Overall Pass/Fail Status

For each extracted field, provide a confidence score between 0.0 and 1.0.

Format your response as a JSON object with the following structure:
{{
    "reference_number": "value",
    "reference_number_confidence": 0.9,
    "lot_number": "value",
    "lot_number_confidence": 0.8,
    // ... other fields
}}

For test results, use the format:
{{
    "lead": "< 0.5 mg/kg",
    "lead_confidence": 0.9,
    "lead_value": -0.5,
    "lead_unit": "mg/kg",
    // ... other results
}}

Note: Use negative values to indicate "less than" results.

Laboratory Report Text:
{text[:3000]}  # Limit to first 3000 characters

Please extract all available information and return ONLY the JSON object."""

        return prompt
