"""PydanticAI provider for PDF parsing with Gemini."""

import os
import json
from typing import Dict, Any, Tuple, List
from datetime import datetime, date
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.gemini import GeminiModel, GeminiModelSettings

from .pdf_parser_service import AIProvider
from loguru import logger


# Pydantic Models for Structured Extraction
class TestResultData(BaseModel):
    """Individual test result from COA"""
    test_name: str
    value: str | float
    unit: str = ""
    specification: str | None = None
    status: str | None = Field(None, description="Pass/Fail/Within Range")
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedCOAData(BaseModel):
    """Complete extracted COA data"""
    reference_number: str
    lot_number: str | None = None
    test_date: str  # Will be converted to date
    lab_name: str | None = None
    test_results: List[TestResultData]
    overall_confidence: float = Field(ge=0.0, le=1.0)
    extraction_errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class PydanticAIProvider(AIProvider):
    """AI provider using PydanticAI with Gemini for structured extraction."""
    
    def __init__(self):
        # Set up API key
        from src.config import settings
        api_key = settings.google_api_key or os.getenv('GOOGLE_API_KEY')
        if api_key:
            os.environ['GEMINI_API_KEY'] = api_key
        
        # Configure model
        self.model_settings = GeminiModelSettings(
            temperature=0.0,  # Zero for consistency
            top_p=0.95,
            max_output_tokens=8192
        )
        
        # Create agent
        self.agent = Agent(
            'google-gla:gemini-2.0-flash-exp',
            output_type=ExtractedCOAData,
            model_settings=self.model_settings,
            system_prompt=self._get_system_prompt()
        )
        
        # Add tools
        self._register_tools()
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for COA extraction."""
        return """You are an expert at parsing Certificate of Analysis (COA) documents.
        
        CRITICAL INSTRUCTIONS:
        1. Extract the reference number (format: YYMMDD-XXX) - this is REQUIRED
           - For DaaneLabs PDFs: Look for "SAMPLE NAME" field - this contains our reference number
           - For other labs: Look for "Reference", "Ref #", "Sample ID", or similar fields
        2. Extract lot/batch numbers
        3. Parse ALL test results from tables
        4. Each table row typically represents one test
        5. Common table columns: Test Name, Result/Value, Unit, Spec/Limit, Status
        
        LAB-SPECIFIC INSTRUCTIONS:
        - DaaneLabs: The "SAMPLE NAME" field contains our internal reference number (YYMMDD-XXX format)
        - Look for lab name/logo to identify the lab source
        
        For test results:
        - Preserve exact values including < > symbols
        - Separate values and units if combined (e.g., "5.2 mg/kg" → value: "5.2", unit: "mg/kg")
        - "ND" or "Not Detected" should be preserved as is
        - Calculate confidence based on data clarity
        
        If you encounter issues:
        - Add them to extraction_errors list
        - Add warnings for uncertain data
        - Still extract as much as possible
        
        Be thorough - it's better to include uncertain data with warnings than to miss data."""
    
    def _register_tools(self):
        """Register tools for the agent."""
        
        @self.agent.tool_plain
        def parse_value_with_unit(value_string: str) -> Dict[str, str]:
            """Parse combined value and unit strings"""
            import re
            
            # Pattern for number followed by unit
            pattern = r'^([\d.,<>≤≥\s-]+)\s*([a-zA-Z%°/]+.*)$'
            match = re.match(pattern, value_string.strip())
            
            if match:
                return {
                    'value': match.group(1).strip(),
                    'unit': match.group(2).strip()
                }
            
            return {
                'value': value_string.strip(),
                'unit': ''
            }
        
        @self.agent.tool_plain
        def identify_test_category(test_name: str) -> str:
            """Categorize test type for better parsing"""
            test_lower = test_name.lower()
            
            if any(term in test_lower for term in ['plate', 'cfu', 'yeast', 'mold', 'coli', 'salmonella']):
                return 'microbiological'
            elif any(term in test_lower for term in ['lead', 'mercury', 'cadmium', 'arsenic', 'metal']):
                return 'heavy_metals'
            elif any(term in test_lower for term in ['moisture', 'ash', 'protein', 'fat']):
                return 'nutritional'
            else:
                return 'other'
        
        @self.agent.tool_plain
        def identify_lab_from_text(text: str) -> Dict[str, str]:
            """Identify the lab from document text"""
            text_lower = text.lower()
            
            if 'daanelabs' in text_lower or 'daane labs' in text_lower:
                return {
                    'lab_name': 'DaaneLabs',
                    'reference_field': 'SAMPLE NAME',
                    'notes': 'For DaaneLabs, the SAMPLE NAME field contains our reference number'
                }
            
            # Add other labs as needed
            return {
                'lab_name': 'Unknown',
                'reference_field': 'Reference Number',
                'notes': 'Look for standard reference number fields'
            }
    
    async def extract_data(self, text: str, prompt: str) -> Tuple[Dict[str, Any], float]:
        """Extract data from text using PydanticAI."""
        try:
            # Check if we have table data in the text
            has_tables = "Table" in text or "|" in text
            
            # Enhance prompt with table awareness
            enhanced_prompt = f"""{prompt}
            
            DOCUMENT CONTENT:
            {text}
            
            IMPORTANT LAB-SPECIFIC NOTES:
            - If this is a DaaneLabs report, the "SAMPLE NAME" field contains our reference number (format: YYMMDD-XXX)
            - Look for lab identification (name, logo, header) to determine the source lab
            
            NOTE: {"This document contains tabular data. Pay special attention to table structure." if has_tables else "This document may not have clear table structure. Look for test results in any format."}
            
            Remember to extract ALL test results and include any errors or warnings you encounter."""
            
            # Run extraction
            result = await self.agent.run(enhanced_prompt)
            
            # Convert to expected format
            extracted_data = result.output
            
            # Format for compatibility with existing system
            formatted_data = {
                "reference_number": extracted_data.reference_number,
                "lot_number": extracted_data.lot_number,
                "test_date": extracted_data.test_date,
                "lab_name": extracted_data.lab_name,
                "test_results": {}
            }
            
            # Convert test results to expected format
            for test in extracted_data.test_results:
                formatted_data["test_results"][test.test_name] = {
                    "value": str(test.value),
                    "unit": test.unit,
                    "confidence": test.confidence,
                    "specification": test.specification,
                    "status": test.status
                }
            
            # Add metadata for UI display
            formatted_data["_extraction_metadata"] = {
                "errors": extracted_data.extraction_errors,
                "warnings": extracted_data.warnings,
                "has_tables": has_tables
            }
            
            return formatted_data, extracted_data.overall_confidence
            
        except Exception as e:
            logger.error(f"PydanticAI extraction failed: {e}")
            
            # Return error in a format the UI can display
            error_data = {
                "reference_number": "ERROR",
                "lot_number": None,
                "test_date": datetime.now().strftime("%Y-%m-%d"),
                "lab_name": "Unknown",
                "test_results": {},
                "_extraction_metadata": {
                    "errors": [f"AI Extraction Failed: {str(e)}"],
                    "warnings": [],
                    "has_tables": False
                }
            }
            
            return error_data, 0.0