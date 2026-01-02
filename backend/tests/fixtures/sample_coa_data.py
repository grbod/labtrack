"""Sample COA data for testing."""

# Sample COA text with table format
SAMPLE_COA_WITH_TABLE = """
Certificate of Analysis

Reference Number: 241215-001
Lot Number: ABC123
Product: Organic Protein Powder
Test Date: 2024-12-15
Laboratory: TestLab Inc.

=== EXTRACTED TABLES ===

Page 1 - Table 1:
Test Parameter | Result | Unit | Specification | Status
---------------------------------------------------------
Total Plate Count | < 10 | CFU/g | < 10,000 | Pass
Yeast & Mold | < 10 | CFU/g | < 1,000 | Pass
E. Coli | Negative | - | Negative | Pass
Salmonella | Negative | - | Negative | Pass

Page 2 - Table 1:
Test Parameter | Result | Unit | Specification | Status
---------------------------------------------------------
Lead | 0.05 | ppm | < 0.5 | Pass
Mercury | < 0.01 | ppm | < 0.1 | Pass
Cadmium | 0.02 | ppm | < 0.1 | Pass
Arsenic | < 0.1 | ppm | < 1.0 | Pass
"""

# Sample COA without clear table structure
SAMPLE_COA_WITHOUT_TABLE = """
Certificate of Analysis
Ref: 241215-002
Lot: XYZ789

Test Results:
Total Plate Count: Less than 10 CFU/g (Specification: < 10,000 CFU/g) - PASS
Yeast and Mold: Less than 10 CFU/g (Spec: < 1,000 CFU/g) - PASS
E. Coli: Not Detected
Salmonella: Not Detected

Heavy Metals:
Lead: 0.08 ppm (limit: 0.5 ppm)
Mercury: ND (limit: 0.1 ppm)
"""

# Sample COA with missing data
SAMPLE_COA_MISSING_DATA = """
Certificate of Analysis

Lot Number: DEF456
Test Date: 2024-12-15

Test Results:
Total Plate Count: < 10 CFU/g
Yeast & Mold: < 10
E. Coli: Negative
Lead: 0.05
"""

# Sample COA with complex table
SAMPLE_COA_COMPLEX_TABLE = """
Certificate of Analysis

Reference Number: 241215-003
Lot Number: BATCH-2024-100
Product: Multi-Vitamin Complex

=== EXTRACTED TABLES ===

Page 1 - Table 1:
Microbiological Analysis | Method | Result | Unit | Limit | Status | Notes
-------------------------------------------------------------------------
Total Aerobic Count | USP <2021> | < 10 | CFU/g | 10^3 CFU/g | Pass | -
Total Yeast and Mold Count | USP <2021> | < 10 | CFU/g | 10^2 CFU/g | Pass | -
E. Coli | USP <2022> | Absent | /g | Absent | Pass | -
Salmonella | USP <2022> | Absent | /10g | Absent | Pass | -
Staphylococcus aureus | USP <2022> | Absent | /g | Absent | Pass | -

Page 2 - Table 1:
Heavy Metal | Method | Result | Unit | USP Limit | Status
----------------------------------------------------------
Lead (Pb) | ICP-MS | 0.123 | μg/g | 0.5 μg/g | Pass
Cadmium (Cd) | ICP-MS | 0.045 | μg/g | 0.5 μg/g | Pass
Arsenic (As) | ICP-MS | 0.089 | μg/g | 1.5 μg/g | Pass
Mercury (Hg) | ICP-MS | < 0.01 | μg/g | 1.5 μg/g | Pass
"""

# Sample COA with errors
SAMPLE_COA_WITH_ERRORS = """
Certificate of Analysis

Reference: INVALID-REF
Lot: 123

Test Results:
Unknown Test 1: 5.2 unknown_unit
Invalid Date: 32/13/2024
Corrupted Value: ###ERROR###
"""

# Expected extraction results for testing
EXPECTED_EXTRACTION_TABLE = {
    "reference_number": "241215-001",
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
        "Yeast & Mold": {
            "value": "< 10",
            "unit": "CFU/g",
            "specification": "< 1,000",
            "status": "Pass",
            "confidence": 0.95
        },
        "E. Coli": {
            "value": "Negative",
            "unit": "-",
            "specification": "Negative",
            "status": "Pass",
            "confidence": 0.95
        },
        "Lead": {
            "value": "0.05",
            "unit": "ppm",
            "specification": "< 0.5",
            "status": "Pass",
            "confidence": 0.95
        }
    }
}

# Mock PDF content for various scenarios
MOCK_PDF_SCENARIOS = {
    "perfect_coa": {
        "text": SAMPLE_COA_WITH_TABLE,
        "expected_confidence": 0.95,
        "expected_status": "success",
        "expected_errors": [],
        "expected_warnings": []
    },
    "no_tables": {
        "text": SAMPLE_COA_WITHOUT_TABLE,
        "expected_confidence": 0.75,
        "expected_status": "success",
        "expected_errors": [],
        "expected_warnings": ["No clear table structure found"]
    },
    "missing_reference": {
        "text": SAMPLE_COA_MISSING_DATA,
        "expected_confidence": 0.6,
        "expected_status": "review_needed",
        "expected_errors": ["Missing reference number"],
        "expected_warnings": ["Missing units for some test results"]
    },
    "complex_table": {
        "text": SAMPLE_COA_COMPLEX_TABLE,
        "expected_confidence": 0.9,
        "expected_status": "success",
        "expected_errors": [],
        "expected_warnings": []
    },
    "invalid_data": {
        "text": SAMPLE_COA_WITH_ERRORS,
        "expected_confidence": 0.2,
        "expected_status": "review_needed",
        "expected_errors": ["Invalid reference number format", "Invalid date format"],
        "expected_warnings": ["Unknown test types found", "Corrupted values detected"]
    }
}