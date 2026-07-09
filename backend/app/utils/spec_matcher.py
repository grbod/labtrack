"""Boolean compatibility wrapper for the canonical specification engine."""

# Accepted result values for specs that start with "Negative" (case-insensitive)
NEGATIVE_ACCEPTED_VALUES = ["negative", "nd", "not detected", "bdl"]

# Accepted result values for specs that start with "Positive" (case-insensitive)
POSITIVE_ACCEPTED_VALUES = ["positive", "detected", "present", "+"]


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
    from app.specs import VerdictKind, evaluate

    verdict = evaluate(specification, result_value, result_unit=test_unit)
    # Compatibility policy for boolean callers:
    # PASS means true, FAIL/INDETERMINATE/NOT_TESTED mean false, and NO_SPEC
    # remains true because this wrapper is used for ad-hoc rows where no
    # acceptance criterion exists to enforce.
    return verdict.kind in {VerdictKind.PASS, VerdictKind.NO_SPEC}
