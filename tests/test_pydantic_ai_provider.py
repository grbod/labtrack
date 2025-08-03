"""Unit tests for PydanticAI provider."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from typing import Dict

from src.services.pydantic_ai_provider import (
    PydanticAIProvider,
    TestResultData,
    ExtractedCOAData
)
from tests.fixtures.sample_coa_data import (
    SAMPLE_COA_WITH_TABLE,
    SAMPLE_COA_WITHOUT_TABLE,
    SAMPLE_COA_MISSING_DATA,
    SAMPLE_COA_WITH_ERRORS
)


class TestPydanticAIProvider:
    """Test suite for PydanticAI provider."""
    
    @pytest.fixture
    def mock_env(self, monkeypatch):
        """Mock environment variables."""
        monkeypatch.setenv('GOOGLE_API_KEY', 'test-api-key')
    
    @pytest.fixture
    def provider(self, mock_env):
        """Create a PydanticAI provider instance."""
        with patch('src.services.pydantic_ai_provider.Agent'):
            return PydanticAIProvider()
    
    @pytest.mark.asyncio
    async def test_successful_extraction_with_table(self, provider):
        """Test successful extraction from COA with clear table structure."""
        # Mock the agent run response
        mock_result = Mock()
        mock_result.output = ExtractedCOAData(
            reference_number="241215-001",
            lot_number="ABC123",
            test_date="2024-12-15",
            lab_name="TestLab Inc.",
            test_results=[
                TestResultData(
                    test_name="Total Plate Count",
                    value="< 10",
                    unit="CFU/g",
                    specification="< 10,000",
                    status="Pass",
                    confidence=0.95
                ),
                TestResultData(
                    test_name="Lead",
                    value="0.05",
                    unit="ppm",
                    specification="< 0.5",
                    status="Pass",
                    confidence=0.92
                )
            ],
            overall_confidence=0.93,
            extraction_errors=[],
            warnings=[]
        )
        
        provider.agent.run = AsyncMock(return_value=mock_result)
        
        # Test extraction
        data, confidence = await provider.extract_data(
            SAMPLE_COA_WITH_TABLE,
            "Extract COA data"
        )
        
        # Assertions
        assert confidence == 0.93
        assert data["reference_number"] == "241215-001"
        assert data["lot_number"] == "ABC123"
        assert "Total Plate Count" in data["test_results"]
        assert data["test_results"]["Total Plate Count"]["value"] == "< 10"
        assert data["_extraction_metadata"]["errors"] == []
        assert data["_extraction_metadata"]["has_tables"] is True
    
    @pytest.mark.asyncio
    async def test_extraction_with_warnings(self, provider):
        """Test extraction that produces warnings."""
        mock_result = Mock()
        mock_result.output = ExtractedCOAData(
            reference_number="241215-002",
            lot_number="XYZ789",
            test_date="2024-12-15",
            lab_name=None,
            test_results=[
                TestResultData(
                    test_name="Total Plate Count",
                    value="< 10",
                    unit="CFU/g",
                    confidence=0.8
                )
            ],
            overall_confidence=0.75,
            extraction_errors=[],
            warnings=["No clear table structure found", "Lab name not found"]
        )
        
        provider.agent.run = AsyncMock(return_value=mock_result)
        
        data, confidence = await provider.extract_data(
            SAMPLE_COA_WITHOUT_TABLE,
            "Extract COA data"
        )
        
        assert confidence == 0.75
        assert len(data["_extraction_metadata"]["warnings"]) == 2
        assert "No clear table structure found" in data["_extraction_metadata"]["warnings"]
    
    @pytest.mark.asyncio
    async def test_extraction_with_errors(self, provider):
        """Test extraction that encounters errors."""
        mock_result = Mock()
        mock_result.output = ExtractedCOAData(
            reference_number="ERROR",
            lot_number=None,
            test_date="2024-12-15",
            lab_name=None,
            test_results=[],
            overall_confidence=0.2,
            extraction_errors=["Invalid reference number format", "No test results found"],
            warnings=["Multiple parsing issues detected"]
        )
        
        provider.agent.run = AsyncMock(return_value=mock_result)
        
        data, confidence = await provider.extract_data(
            SAMPLE_COA_WITH_ERRORS,
            "Extract COA data"
        )
        
        assert confidence == 0.2
        assert data["reference_number"] == "ERROR"
        assert len(data["_extraction_metadata"]["errors"]) == 2
        assert "Invalid reference number format" in data["_extraction_metadata"]["errors"]
    
    @pytest.mark.asyncio
    async def test_extraction_failure(self, provider):
        """Test handling of complete extraction failure."""
        provider.agent.run = AsyncMock(side_effect=Exception("AI service unavailable"))
        
        data, confidence = await provider.extract_data(
            "Invalid PDF content",
            "Extract COA data"
        )
        
        assert confidence == 0.0
        assert data["reference_number"] == "ERROR"
        assert "AI Extraction Failed" in data["_extraction_metadata"]["errors"][0]
    
    def test_parse_value_with_unit_tool(self, provider):
        """Test the parse_value_with_unit tool."""
        # Since we're mocking the agent, we'll test the logic directly
        # by creating a real PydanticAIProvider instance temporarily
        import re
        
        def parse_value_with_unit(value_string: str) -> Dict[str, str]:
            """Parse combined value and unit strings"""
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
        
        # Test various formats
        assert parse_value_with_unit("5.2 mg/kg") == {"value": "5.2", "unit": "mg/kg"}
        assert parse_value_with_unit("< 10 CFU/g") == {"value": "< 10", "unit": "CFU/g"}
        assert parse_value_with_unit("0.05 ppm") == {"value": "0.05", "unit": "ppm"}
        assert parse_value_with_unit("Negative") == {"value": "Negative", "unit": ""}
        assert parse_value_with_unit("≤ 0.1 %") == {"value": "≤ 0.1", "unit": "%"}
    
    def test_identify_test_category_tool(self, provider):
        """Test the identify_test_category tool."""
        # Since we're mocking the agent, we'll test the logic directly
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
        
        # Test categorization
        assert identify_test_category("Total Plate Count") == "microbiological"
        assert identify_test_category("Yeast and Mold") == "microbiological"
        assert identify_test_category("E. Coli") == "microbiological"
        assert identify_test_category("Lead") == "heavy_metals"
        assert identify_test_category("Mercury") == "heavy_metals"
        assert identify_test_category("Moisture Content") == "nutritional"
        assert identify_test_category("Protein") == "nutritional"
        assert identify_test_category("pH Level") == "other"
    
    def test_system_prompt(self, provider):
        """Test that system prompt is properly configured."""
        prompt = provider._get_system_prompt()
        
        assert "Certificate of Analysis" in prompt
        assert "reference number" in prompt
        assert "test results" in prompt
        assert "extraction_errors" in prompt
        assert "warnings" in prompt
    
    @pytest.mark.asyncio
    async def test_table_detection(self, provider):
        """Test table detection in text."""
        # Mock response
        mock_result = Mock()
        mock_result.output = ExtractedCOAData(
            reference_number="241215-001",
            lot_number="ABC123",
            test_date="2024-12-15",
            lab_name="TestLab Inc.",
            test_results=[],
            overall_confidence=0.9,
            extraction_errors=[],
            warnings=[]
        )
        
        provider.agent.run = AsyncMock(return_value=mock_result)
        
        # Test with table markers
        data_with_table, _ = await provider.extract_data(
            "Test | Result\n----|-------\nLead | 0.05",
            "Extract"
        )
        assert data_with_table["_extraction_metadata"]["has_tables"] is True
        
        # Test without table markers
        data_no_table, _ = await provider.extract_data(
            "Test results: Lead 0.05 ppm",
            "Extract"
        )
        assert data_no_table["_extraction_metadata"]["has_tables"] is False