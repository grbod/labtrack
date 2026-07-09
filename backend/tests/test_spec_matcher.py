"""Tests for the shared specification matcher."""

from app.utils.spec_matcher import specification_matches


class TestSpecificationMatches:
    # --- None/empty spec (new rule: no spec to enforce → pass) ---

    def test_none_specification_passes_anything(self):
        # Ad-hoc tests may have no spec; any entered result counts as passing
        assert specification_matches(None, None, "whatever") is True

    def test_empty_string_specification_passes_anything(self):
        assert specification_matches("", None, "whatever") is True

    def test_whitespace_only_specification_passes_anything(self):
        assert specification_matches("   ", None, "whatever") is True

    # --- Empty result always fails ---

    def test_empty_result_fails(self):
        assert specification_matches("< 10", None, "") is False

    def test_none_result_fails(self):
        assert specification_matches("Negative", None, None) is False

    # --- Positive/Negative unit-based branch (test_unit == "Positive/Negative") ---

    def test_positive_negative_unit_negative_spec_accepts_negative(self):
        assert (
            specification_matches("Negative", "Positive/Negative", "Negative") is True
        )

    def test_positive_negative_unit_negative_spec_accepts_nd(self):
        assert specification_matches("Negative", "Positive/Negative", "ND") is True

    def test_positive_negative_unit_negative_spec_accepts_not_detected(self):
        assert (
            specification_matches("Negative", "Positive/Negative", "Not Detected")
            is True
        )

    def test_positive_negative_unit_negative_spec_accepts_bdl(self):
        assert specification_matches("Negative", "Positive/Negative", "BDL") is True

    def test_positive_negative_unit_negative_spec_rejects_positive(self):
        assert (
            specification_matches("Negative", "Positive/Negative", "Positive") is False
        )

    def test_positive_negative_unit_positive_spec_accepts_positive(self):
        assert (
            specification_matches("Positive", "Positive/Negative", "Positive") is True
        )

    def test_positive_negative_unit_positive_spec_rejects_detected(self):
        assert (
            specification_matches("Positive", "Positive/Negative", "Detected") is False
        )

    def test_positive_negative_unit_positive_spec_rejects_negative(self):
        assert (
            specification_matches("Positive", "Positive/Negative", "Negative") is False
        )

    # --- "Negative" specs (no Positive/Negative unit) ---

    def test_negative_spec_accepts_negative(self):
        assert specification_matches("Negative", None, "Negative") is True

    def test_negative_spec_accepts_case_insensitive(self):
        assert specification_matches("Negative", None, "negative") is True

    def test_negative_spec_rejects_positive(self):
        assert specification_matches("Negative", None, "Positive") is False

    def test_negative_spec_accepts_nd(self):
        # ND / Not Detected are accepted for Negative specs
        assert specification_matches("Negative", None, "ND") is True

    def test_negative_spec_accepts_not_detected(self):
        assert specification_matches("Negative", None, "Not Detected") is True

    def test_negative_spec_accepts_bdl(self):
        assert specification_matches("Negative", None, "BDL") is True

    def test_negative_spec_rejects_less_than_value(self):
        # Censored numeric values cannot prove a negative-required spec.
        assert specification_matches("Negative", None, "< 0.5") is False
        assert specification_matches("Negative", None, "<10") is False

    def test_negative_in_xg_spec_accepts_negative(self):
        # "Negative in 10g" style specs start with "negative" so same branch
        assert specification_matches("Negative in 10g", None, "Negative") is True

    def test_negative_in_xg_spec_accepts_nd(self):
        assert specification_matches("Negative in 10g", None, "ND") is True

    def test_negative_in_xg_spec_rejects_less_than(self):
        assert specification_matches("Negative in 10g", None, "<0.1") is False

    def test_negative_in_xg_spec_rejects_positive(self):
        assert specification_matches("Negative in 10g", None, "Positive") is False

    # --- "Positive" specs (no Positive/Negative unit) ---

    def test_positive_spec_accepts_positive(self):
        assert specification_matches("Positive", None, "positive") is True

    def test_positive_spec_rejects_detected(self):
        assert specification_matches("Positive", None, "Detected") is False

    def test_positive_spec_rejects_present(self):
        assert specification_matches("Positive", None, "present") is False

    def test_positive_spec_rejects_plus_sign(self):
        assert specification_matches("Positive", None, "+") is False

    def test_positive_spec_rejects_negative(self):
        assert specification_matches("Positive", None, "Negative") is False

    # --- "< X" (less than) specs ---

    def test_less_than_spec_passes_lower_value(self):
        assert specification_matches("< 10,000 CFU/g", "CFU/g", "5000") is True

    def test_less_than_spec_fails_higher_value(self):
        assert specification_matches("< 10,000 CFU/g", "CFU/g", "20000") is False

    def test_less_than_spec_fails_equal_value(self):
        # boundary: < 10 means strictly less than
        assert specification_matches("< 10", None, "10000") is False

    def test_less_than_spec_passes_less_than_result(self):
        # result is itself a "<X" value → pass
        assert specification_matches("< 10,000 CFU/g", "CFU/g", "< 10") is True

    def test_less_than_spec_handles_commas_in_spec(self):
        assert specification_matches("< 10,000", None, "9999") is True

    def test_less_than_spec_handles_commas_in_result(self):
        # result with commas as thousands separator
        assert specification_matches("< 10,000", None, "5,000") is True

    # --- "> X" (greater than) specs ---

    def test_greater_than_spec_passes_higher_value(self):
        assert specification_matches("> 15", None, "16") is True

    def test_greater_than_spec_fails_lower_value(self):
        assert specification_matches("> 15", None, "14") is False

    def test_greater_than_spec_passes_greater_than_result(self):
        # result is itself a ">X" value → pass
        assert specification_matches("> 15", None, "> 20") is True

    # --- Range specs ---

    def test_range_spec_passes_in_range(self):
        assert specification_matches("20-25", None, "22") is True
        assert specification_matches("20-25", None, "20") is True
        assert specification_matches("20-25", None, "25") is True

    def test_range_spec_fails_out_of_range(self):
        assert specification_matches("20-25", None, "19.9") is False
        assert specification_matches("20-25", None, "25.1") is False

    # --- Exact match ---

    def test_exact_match_passes(self):
        assert specification_matches("Complies", None, "Complies") is True
        assert specification_matches("Complies", None, "complies") is True

    def test_exact_match_fails(self):
        assert specification_matches("Complies", None, "Fails") is False
