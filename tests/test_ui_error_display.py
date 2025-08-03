"""Tests for UI error display functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import streamlit as st
from datetime import datetime
import tempfile
import os

from src.ui.pages.pdf_processing import (
    display_extraction_errors,
    display_queue_item,
    handle_pdf_upload
)
from src.models import ParsingQueue, ParsingStatus


class TestUIErrorDisplay:
    """Test suite for UI error display components."""
    
    @pytest.fixture
    def mock_streamlit(self):
        """Mock Streamlit components."""
        with patch('streamlit.error') as mock_error, \
             patch('streamlit.warning') as mock_warning, \
             patch('streamlit.success') as mock_success, \
             patch('streamlit.write') as mock_write, \
             patch('streamlit.expander') as mock_expander, \
             patch('streamlit.columns') as mock_columns, \
             patch('streamlit.button') as mock_button:
            
            # Setup expander mock
            mock_expander_instance = MagicMock()
            mock_expander_instance.__enter__ = Mock(return_value=mock_expander_instance)
            mock_expander_instance.__exit__ = Mock(return_value=None)
            mock_expander.return_value = mock_expander_instance
            
            # Setup columns mock
            mock_col = MagicMock()
            mock_columns.return_value = [mock_col] * 4
            
            yield {
                'error': mock_error,
                'warning': mock_warning,
                'success': mock_success,
                'write': mock_write,
                'expander': mock_expander,
                'expander_instance': mock_expander_instance,
                'columns': mock_columns,
                'button': mock_button,
                'col': mock_col
            }
    
    def test_display_extraction_errors_with_errors(self, mock_streamlit):
        """Test displaying extraction errors."""
        metadata = {
            "errors": [
                "Invalid reference number format",
                "Missing critical test data"
            ],
            "warnings": ["Lab name not found"],
            "has_tables": False
        }
        
        display_extraction_errors(metadata)
        
        # Check error display
        mock_streamlit['error'].assert_called_once_with("🔍 **Issues Found:**")
        assert mock_streamlit['write'].call_count >= 2
        
        # Check error messages were written
        calls = [call.args[0] for call in mock_streamlit['write'].call_args_list]
        assert any("Invalid reference number format" in str(call) for call in calls)
        assert any("Missing critical test data" in str(call) for call in calls)
    
    def test_display_extraction_errors_warnings_only(self, mock_streamlit):
        """Test displaying only warnings (no errors)."""
        metadata = {
            "errors": [],
            "warnings": [
                "No clear table structure found",
                "Using fuzzy matching for test names"
            ],
            "has_tables": False
        }
        
        display_extraction_errors(metadata)
        
        # Should use warning instead of error
        mock_streamlit['warning'].assert_called_once_with("⚠️ **Warnings:**")
        assert mock_streamlit['error'].call_count == 0
        
        # Check warning messages
        calls = [call.args[0] for call in mock_streamlit['write'].call_args_list]
        assert any("No clear table structure found" in str(call) for call in calls)
    
    def test_display_extraction_errors_no_issues(self, mock_streamlit):
        """Test when there are no errors or warnings."""
        metadata = {
            "errors": [],
            "warnings": [],
            "has_tables": True
        }
        
        display_extraction_errors(metadata)
        
        # Should not display anything
        assert mock_streamlit['error'].call_count == 0
        assert mock_streamlit['warning'].call_count == 0
        assert mock_streamlit['write'].call_count == 0
    
    def test_display_queue_item_pending(self, mock_streamlit):
        """Test displaying a pending queue item."""
        queue_item = ParsingQueue(
            id=1,
            pdf_filename="test_coa.pdf",
            status=ParsingStatus.PENDING,
            confidence_score=0.45,
            error_message="Low confidence extraction",
            notes="Multiple issues found during parsing",
            extracted_data={"reference_number": "241215-001"},
            created_at=datetime.now()
        )
        
        display_queue_item(queue_item, Mock())
        
        # Check expander was created with correct title
        mock_streamlit['expander'].assert_called()
        expander_title = mock_streamlit['expander'].call_args[0][0]
        assert "test_coa.pdf" in expander_title
        assert "⏳" in expander_title  # Pending icon
        
        # Check content within expander
        expander = mock_streamlit['expander_instance']
        write_calls = [call.args[0] for call in expander.write.call_args_list]
        
        assert any("Confidence Score: 45.0%" in str(call) for call in write_calls)
        assert any("Low confidence extraction" in str(call) for call in write_calls)
        assert any("Multiple issues found" in str(call) for call in write_calls)
    
    def test_display_queue_item_resolved(self, mock_streamlit):
        """Test displaying a resolved queue item."""
        queue_item = ParsingQueue(
            id=2,
            pdf_filename="successful_coa.pdf",
            status=ParsingStatus.RESOLVED,
            confidence_score=0.92,
            extracted_data={
                "reference_number": "241215-002",
                "lot_number": "ABC123",
                "_extraction_metadata": {
                    "warnings": ["Minor formatting issues"]
                }
            },
            created_at=datetime.now()
        )
        
        display_queue_item(queue_item, Mock())
        
        # Check resolved icon in title
        expander_title = mock_streamlit['expander'].call_args[0][0]
        assert "✅" in expander_title
        
        # Should show success for high confidence
        success_calls = [call.args[0] for call in mock_streamlit['success'].call_args_list]
        assert any("92.0%" in str(call) for call in success_calls)
    
    def test_display_queue_item_failed(self, mock_streamlit):
        """Test displaying a failed queue item."""
        queue_item = ParsingQueue(
            id=3,
            pdf_filename="corrupted.pdf",
            status=ParsingStatus.FAILED,
            error_message="Failed to extract text from PDF",
            created_at=datetime.now()
        )
        
        display_queue_item(queue_item, Mock())
        
        # Check failed icon
        expander_title = mock_streamlit['expander'].call_args[0][0]
        assert "❌" in expander_title
        
        # Check error message display
        error_calls = [call.args[0] for call in mock_streamlit['error'].call_args_list]
        assert any("Failed to extract text" in str(call) for call in error_calls)
    
    @patch('src.ui.pages.pdf_processing.PDFParserService')
    @patch('src.ui.pages.pdf_processing.asyncio.run')
    def test_handle_pdf_upload_success(self, mock_asyncio_run, mock_parser_service, mock_streamlit):
        """Test successful PDF upload handling."""
        # Create mock uploaded file
        mock_file = MagicMock()
        mock_file.name = "test_upload.pdf"
        mock_file.read.return_value = b"%PDF-1.4\nTest content"
        
        # Mock parser response
        mock_asyncio_run.return_value = {
            "status": "success",
            "confidence": 0.88,
            "data": {
                "reference_number": "241215-003",
                "_extraction_metadata": {
                    "errors": [],
                    "warnings": ["Some warnings"]
                }
            }
        }
        
        # Test upload
        with patch('tempfile.NamedTemporaryFile'):
            with patch('os.path.exists', return_value=True):
                with patch('os.unlink'):
                    handle_pdf_upload(mock_file, Mock())
        
        # Check success message
        mock_streamlit['success'].assert_called()
        success_msg = mock_streamlit['success'].call_args[0][0]
        assert "Successfully parsed" in success_msg
        assert "88%" in success_msg
    
    @patch('src.ui.pages.pdf_processing.PDFParserService')
    @patch('src.ui.pages.pdf_processing.asyncio.run')
    def test_handle_pdf_upload_review_needed(self, mock_asyncio_run, mock_parser_service, mock_streamlit):
        """Test PDF upload that needs review."""
        mock_file = MagicMock()
        mock_file.name = "low_quality.pdf"
        mock_file.read.return_value = b"%PDF-1.4\nPoor quality"
        
        # Mock low confidence response
        mock_asyncio_run.return_value = {
            "status": "review_needed",
            "confidence": 0.55,
            "data": {
                "reference_number": "UNCLEAR",
                "_extraction_metadata": {
                    "errors": ["Multiple parsing errors"],
                    "warnings": []
                }
            }
        }
        
        with patch('tempfile.NamedTemporaryFile'):
            with patch('os.path.exists', return_value=True):
                with patch('os.unlink'):
                    handle_pdf_upload(mock_file, Mock())
        
        # Check warning message
        mock_streamlit['warning'].assert_called()
        warning_msg = mock_streamlit['warning'].call_args[0][0]
        assert "requires review" in warning_msg.lower()
    
    def test_display_extraction_metadata_complex(self, mock_streamlit):
        """Test displaying complex extraction metadata."""
        metadata = {
            "errors": [
                "Reference number format invalid: expected YYMMDD-XXX",
                "Test date parsing failed: invalid date format '32/13/2024'",
                "Missing required test: Total Plate Count"
            ],
            "warnings": [
                "Lab name extracted with low confidence",
                "Some test results missing units",
                "Table structure partially damaged"
            ],
            "has_tables": True,
            "tables_extracted": 2,
            "confidence_breakdown": {
                "reference_number": 0.3,
                "lot_number": 0.9,
                "test_results": 0.6
            }
        }
        
        display_extraction_errors(metadata)
        
        # Should display errors first
        mock_streamlit['error'].assert_called_with("🔍 **Issues Found:**")
        
        # All errors should be displayed
        write_calls = [call.args[0] for call in mock_streamlit['write'].call_args_list]
        assert any("YYMMDD-XXX" in str(call) for call in write_calls)
        assert any("32/13/2024" in str(call) for call in write_calls)
        assert any("Total Plate Count" in str(call) for call in write_calls)
        
        # Warnings should also be shown
        assert any("low confidence" in str(call) for call in write_calls)
        assert any("missing units" in str(call) for call in write_calls)