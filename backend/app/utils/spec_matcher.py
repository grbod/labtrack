"""Shared specification matcher for evaluating test result pass/fail.

This module provides a standalone ``specification_matches`` function extracted
from ``ProductTestSpecification.matches_result`` so that ad-hoc test results
(not tied to a ProductTestSpecification row) can be evaluated the same way.
"""

import re

# Accepted result values for specs that start with "Negative" (case-insensitive)
NEGATIVE_ACCEPTED_VALUES = ['negative', 'nd', 'not detected', 'bdl']

# Accepted result values for specs that start with "Positive" (case-insensitive)
POSITIVE_ACCEPTED_VALUES = ['positive', 'detected', 'present', '+']


def _parse_numeric_value(s):
    """
    Parse a numeric value from a string, handling commas as thousands separators
    and stripping any trailing text (like units).

    Args:
        s: The string to parse (e.g., "10,000", "10,000 CFU/g", "10.5")

    Returns:
        float or None if not a valid number
    """
    cleaned = s.replace(',', '').strip()
    match = re.match(r'^-?[\d.]+', cleaned)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def specification_matches(specification, test_unit, result_value) -> bool:
    """Return True if result_value satisfies the specification string.

    Args:
        specification: Acceptance criteria string (e.g. "< 10,000 CFU/g",
            "Negative", "Negative in 10g", "> 15", "20-25").  If None or
            blank there is no spec to enforce and any non-empty result passes.
        test_unit: Unit string from the associated lab test type (e.g.
            "Positive/Negative", "CFU/g").  May be None.
        result_value: The actual test result value entered by a lab tech.

    Returns:
        True if the result passes the specification, False otherwise.
    """
    # No spec to enforce → pass (covers ad-hoc test results without a spec)
    if specification is None or not str(specification).strip():
        return True

    if not result_value:
        return False

    spec = str(specification).strip().lower()
    value = str(result_value).strip().lower()

    # Handle Positive/Negative results (legacy unit-based check)
    if test_unit == "Positive/Negative":
        if spec == "negative" and value in NEGATIVE_ACCEPTED_VALUES:
            return True
        if spec == "positive" and value in POSITIVE_ACCEPTED_VALUES:
            return True
        return False

    # Handle specs starting with "Negative" (e.g., "Negative in 10g")
    if spec.startswith("negative"):
        # Accept: Negative, ND, Not Detected, BDL, or any <X value
        if value in NEGATIVE_ACCEPTED_VALUES:
            return True
        # Also accept "<X" values (below detection limit)
        if value.startswith("<"):
            return True
        return False

    # Handle specs starting with "Positive" (e.g., "Positive in 10g")
    if spec.startswith("positive"):
        # Accept: Positive, Detected, Present, +
        return value in POSITIVE_ACCEPTED_VALUES

    # Handle "< X" specifications (supports commas and units like "<10,000 CFU/g")
    if spec.startswith("<"):
        spec_limit = _parse_numeric_value(spec[1:])
        if spec_limit is None:
            return False
        if value.startswith("<"):
            # Both are "less than" values
            return True
        result_val = _parse_numeric_value(value)
        if result_val is None:
            return False
        return result_val < spec_limit

    # Handle "> X" specifications (supports commas and units)
    if spec.startswith(">"):
        spec_limit = _parse_numeric_value(spec[1:])
        if spec_limit is None:
            return False
        if value.startswith(">"):
            # Both are "greater than" values
            return True
        result_val = _parse_numeric_value(value)
        if result_val is None:
            return False
        return result_val > spec_limit

    # Handle range specifications (e.g., "5-10", "1,000-10,000")
    if "-" in spec and not spec.startswith("-"):
        parts = spec.split("-")
        if len(parts) == 2:
            min_val = _parse_numeric_value(parts[0])
            max_val = _parse_numeric_value(parts[1])
            result_val = _parse_numeric_value(value)
            if min_val is not None and max_val is not None and result_val is not None:
                return min_val <= result_val <= max_val
        return False

    # Handle exact match
    return spec == value
