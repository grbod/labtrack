# PydanticAI PDF Parsing Implementation

## Overview

This implementation integrates PydanticAI with Google's Gemini 2.5 Flash model to enhance the COA (Certificate of Analysis) PDF parsing capabilities in the existing COA Management System.

## Key Features

### 1. **PydanticAI Provider** (`src/services/pydantic_ai_provider.py`)
- Structured data extraction using Pydantic models
- Integration with Google Gemini 2.5 Flash via `google-gla` provider
- Advanced error and warning tracking through extraction metadata
- AI tools for parsing value/unit combinations and categorizing test types
- Automatic table detection in PDF content

### 2. **Enhanced PDF Table Extraction** (`src/utils/pdf_utils.py`)
- Improved table extraction using pdfplumber
- Table formatting optimized for AI comprehension
- Multi-page table support
- Handles locked/protected PDFs with pikepdf

### 3. **Integration with Existing System**
- Automatic provider selection based on GOOGLE_API_KEY environment variable
- Preserves existing queue and confidence scoring system
- Backward compatible with MockAIProvider
- Enhanced error display in Streamlit UI

## Configuration

### Environment Variables
```bash
GOOGLE_API_KEY=your_google_api_key_here  # Required for PydanticAI
```

### Dependencies Added
```
pydantic-ai>=0.0.49
pikepdf>=8.0.0
```

## Data Models

### TestResultData
- `test_name`: str
- `value`: str | float
- `unit`: str
- `specification`: str | None
- `status`: str | None (Pass/Fail/Within Range)
- `confidence`: float (0.0-1.0)

### ExtractedCOAData
- `reference_number`: str (Required, format: YYMMDD-XXX)
- `lot_number`: str | None
- `test_date`: str
- `lab_name`: str | None
- `test_results`: List[TestResultData]
- `overall_confidence`: float (0.0-1.0)
- `extraction_errors`: List[str]
- `warnings`: List[str]

## Usage

### Automatic Provider Selection
The system automatically selects PydanticAI when GOOGLE_API_KEY is set:

```python
# In PDFParserService.__init__
if ai_provider is None and os.getenv('GOOGLE_API_KEY'):
    self.ai_provider = PydanticAIProvider()
```

### Enhanced Extraction
```python
# PDFs are processed with table-aware extraction
text_with_tables = extract_text_with_tables(pdf_path)

# AI extracts structured data
data, confidence = await ai_provider.extract_data(text_with_tables, prompt)

# Extraction metadata provides detailed feedback
if data.get("_extraction_metadata", {}).get("errors"):
    # Handle extraction errors
```

## Test Coverage

### Unit Tests (`tests/test_pydantic_ai_provider.py`)
- ✅ Successful extraction with tables
- ✅ Extraction with warnings
- ✅ Extraction with errors
- ✅ Complete failure handling
- ✅ Tool function tests
- ✅ Table detection

### Integration Tests (`tests/test_pdf_parser_integration.py`)
- ✅ Successful PDF parsing flow
- ✅ Low confidence handling
- ✅ Retry mechanism
- ✅ Missing lot handling
- ✅ Queue review and statistics
- ✅ Manual data updates
- ✅ Provider initialization

### Table Extraction Tests (`tests/test_table_extraction.py`)
- ✅ Table formatting for AI
- ✅ Empty cell handling
- ✅ Multi-page extraction
- ✅ Complex table structures
- ✅ Error handling

## Error Handling

The system provides comprehensive error tracking:

1. **Extraction Errors**: Critical issues preventing proper parsing
2. **Warnings**: Non-critical issues that may affect accuracy
3. **Confidence Scores**: Per-field and overall confidence metrics

## Future Enhancements

1. **Real-time streaming**: Use PydanticAI's streaming capabilities
2. **Custom prompts**: Allow per-lab custom extraction prompts
3. **Multi-model support**: Add support for other LLMs
4. **Advanced validation**: Implement business rule validation
5. **Batch processing**: Process multiple PDFs in parallel