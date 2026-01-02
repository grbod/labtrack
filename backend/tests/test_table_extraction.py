"""Tests for PDF table extraction functionality."""

import pytest
from pathlib import Path
import tempfile
import os
from unittest.mock import Mock, patch

from app.utils.pdf_utils import (
    extract_tables_from_pdf,
    format_table_for_ai,
    extract_text_with_tables
)


class TestTableExtraction:
    """Test suite for table extraction from PDFs."""
    
    @pytest.fixture
    def mock_pdf_with_tables(self):
        """Create a mock PDF with table data."""
        # Mock pdfplumber page
        mock_page = Mock()
        mock_page.extract_tables.return_value = [
            # Simple table
            [
                ["Test Parameter", "Result", "Unit", "Specification"],
                ["Total Plate Count", "< 10", "CFU/g", "< 10,000"],
                ["Yeast & Mold", "< 10", "CFU/g", "< 1,000"],
                ["E. Coli", "Negative", "-", "Negative"]
            ],
            # Table with empty cells
            [
                ["Heavy Metal", "Result", "Unit", "Limit"],
                ["Lead", "0.05", "ppm", "< 0.5"],
                ["Mercury", None, "ppm", "< 0.1"],  # Missing value
                ["Cadmium", "0.02", "", "< 0.1"]    # Missing unit
            ]
        ]
        
        # Mock PDF
        mock_pdf = Mock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)
        
        return mock_pdf
    
    def test_format_table_for_ai(self):
        """Test formatting tables for AI comprehension."""
        # Test normal table
        table = [
            ["Test", "Result", "Unit"],
            ["Lead", "0.05", "ppm"],
            ["Mercury", "< 0.01", "ppm"]
        ]
        
        formatted = format_table_for_ai(table)
        
        assert "Test | Result | Unit" in formatted
        assert "Lead | 0.05 | ppm" in formatted
        assert "Mercury | < 0.01 | ppm" in formatted
        assert "---" in formatted  # Separator line
        
        # Test empty table
        assert format_table_for_ai([]) == ""
        assert format_table_for_ai(None) == ""
    
    def test_format_table_with_empty_cells(self):
        """Test formatting tables with empty/None cells."""
        table = [
            ["Test", "Result", "Unit"],
            ["Lead", None, "ppm"],
            ["Mercury", "0.01", ""],
            ["", "0.02", "ppm"]
        ]
        
        formatted = format_table_for_ai(table)
        
        assert "Lead |  | ppm" in formatted  # None becomes empty string
        assert "Mercury | 0.01 | " in formatted  # Empty string preserved
        assert " | 0.02 | ppm" in formatted  # Empty first cell
    
    @patch('pdfplumber.open')
    def test_extract_tables_from_pdf(self, mock_pdfplumber_open, mock_pdf_with_tables):
        """Test extracting tables from PDF."""
        mock_pdfplumber_open.return_value = mock_pdf_with_tables
        
        # Create a fake PDF path
        pdf_path = Path("test.pdf")
        
        tables = extract_tables_from_pdf(pdf_path)
        
        # Assertions
        assert len(tables) == 2
        
        # First table
        assert tables[0]['page'] == 1
        assert tables[0]['table_index'] == 1
        assert tables[0]['headers'] == ["Test Parameter", "Result", "Unit", "Specification"]
        assert len(tables[0]['rows']) == 3
        assert tables[0]['rows'][0] == ["Total Plate Count", "< 10", "CFU/g", "< 10,000"]
        
        # Check formatted output
        assert "Test Parameter | Result | Unit | Specification" in tables[0]['formatted']
        
        # Second table with None values
        assert tables[1]['headers'] == ["Heavy Metal", "Result", "Unit", "Limit"]
        assert tables[1]['rows'][1][1] == ""  # None converted to empty string
    
    @patch('pdfplumber.open')
    def test_extract_tables_error_handling(self, mock_pdfplumber_open):
        """Test error handling in table extraction."""
        # Mock pdfplumber to raise an exception
        mock_pdfplumber_open.side_effect = Exception("PDF read error")
        
        pdf_path = Path("test.pdf")
        tables = extract_tables_from_pdf(pdf_path)
        
        # Should return empty list on error
        assert tables == []
    
    @patch('pdfplumber.open')
    def test_extract_text_with_tables(self, mock_pdfplumber_open, mock_pdf_with_tables):
        """Test combined text and table extraction."""
        # Mock text extraction
        mock_page = mock_pdf_with_tables.pages[0]
        mock_page.extract_text.return_value = "Certificate of Analysis\nReference: 241215-001"
        
        mock_pdfplumber_open.return_value = mock_pdf_with_tables
        
        with patch('src.utils.pdf_utils.extract_text_from_pdf') as mock_text_extract:
            mock_text_extract.return_value = "Certificate of Analysis\nReference: 241215-001"
            
            pdf_path = Path("test.pdf")
            combined_text = extract_text_with_tables(pdf_path)
        
        # Check that both text and tables are included
        assert "Certificate of Analysis" in combined_text
        assert "Reference: 241215-001" in combined_text
        assert "=== EXTRACTED TABLES ===" in combined_text
        assert "Page 1 - Table 1:" in combined_text
        assert "Test Parameter | Result | Unit | Specification" in combined_text
        assert "Total Plate Count | < 10 | CFU/g | < 10,000" in combined_text
    
    def test_table_with_complex_structure(self):
        """Test formatting complex table with merged cells and special characters."""
        table = [
            ["Test Category", "Parameter", "Result ± SD", "Unit", "Method", "Status"],
            ["Microbiological", "Total Plate Count", "< 10", "CFU/g", "USP <2021>", "✓ Pass"],
            ["", "Yeast & Mold", "< 10", "CFU/g", "USP <2021>", "✓ Pass"],
            ["Heavy Metals", "Lead (Pb)", "0.05 ± 0.01", "μg/g", "ICP-MS", "✓ Pass"],
            ["", "Mercury (Hg)", "< 0.01", "μg/g", "ICP-MS", "✓ Pass"]
        ]
        
        formatted = format_table_for_ai(table)
        
        # Check special characters are preserved
        assert "± SD" in formatted
        assert "μg/g" in formatted
        assert "✓ Pass" in formatted
        assert "USP <2021>" in formatted
        
        # Check structure
        lines = formatted.split('\n')
        assert len(lines) == 6  # Header + separator + 4 data rows
    
    @patch('pdfplumber.open')
    def test_multi_page_table_extraction(self, mock_pdfplumber_open):
        """Test extracting tables from multiple pages."""
        # Mock multiple pages
        page1 = Mock()
        page1.extract_tables.return_value = [
            [["Test", "Result"], ["Lead", "0.05"]]
        ]
        
        page2 = Mock()
        page2.extract_tables.return_value = [
            [["Test", "Result"], ["Mercury", "0.01"]],
            [["Test", "Result"], ["Cadmium", "0.02"]]
        ]
        
        mock_pdf = Mock()
        mock_pdf.pages = [page1, page2]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)
        
        mock_pdfplumber_open.return_value = mock_pdf
        
        tables = extract_tables_from_pdf(Path("test.pdf"))
        
        assert len(tables) == 3
        assert tables[0]['page'] == 1
        assert tables[1]['page'] == 2
        assert tables[2]['page'] == 2
        assert tables[1]['table_index'] == 1
        assert tables[2]['table_index'] == 2
    
    def test_empty_table_handling(self):
        """Test handling of empty or malformed tables."""
        # Empty table
        assert format_table_for_ai([]) == ""
        
        # Table with only headers
        table = [["Header1", "Header2", "Header3"]]
        formatted = format_table_for_ai(table)
        assert "Header1 | Header2 | Header3" in formatted
        assert len(formatted.split('\n')) == 2  # Header + separator only
        
        # Table with inconsistent columns
        table = [
            ["A", "B", "C"],
            ["1", "2"],  # Missing column
            ["3", "4", "5", "6"]  # Extra column
        ]
        formatted = format_table_for_ai(table)
        assert "1 | 2" in formatted
        assert "3 | 4 | 5 | 6" in formatted