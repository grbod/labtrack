"""Golden tests for the canonical specification engine."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import pytest

from app.specs import (
    ResultValue,
    SpecRule,
    Verdict,
    VerdictKind,
    evaluate,
    parse_result,
    parse_spec,
)


MAPPING_PATH = Path(__file__).resolve().parents[1] / "product_test_mapping.csv"


def _spec_census() -> Counter[str]:
    counts: Counter[str] = Counter()
    with MAPPING_PATH.open(newline="") as handle:
        for row in csv.DictReader(handle):
            for spec in row["Specifications"].split(";"):
                cleaned = spec.strip()
                if cleaned:
                    counts[cleaned] += 1
    return counts


SPEC_CENSUS = _spec_census()


def _passing_result_for_real_spec(spec: str) -> tuple[str, VerdictKind]:
    if spec == "Negative":
        return "Negative", VerdictKind.PASS
    if spec.startswith("<"):
        unit = "ppm" if "ppm" in spec.lower() else "CFU/g"
        return f"1 {unit}", VerdictKind.PASS
    return spec, VerdictKind.INDETERMINATE


def test_public_exports_are_available():
    assert callable(evaluate)
    assert callable(parse_spec)
    assert callable(parse_result)
    assert Verdict
    assert VerdictKind
    assert SpecRule
    assert ResultValue


def test_product_mapping_spec_format_census_count():
    assert len(SPEC_CENSUS) == 120


@pytest.mark.parametrize(
    ("spec_text", "result_text", "expected"),
    [(spec, *_passing_result_for_real_spec(spec)) for spec in sorted(SPEC_CENSUS)],
)
def test_every_product_mapping_spec_format_has_expected_verdict(
    spec_text: str,
    result_text: str,
    expected: VerdictKind,
):
    assert evaluate(spec_text, result_text).kind == expected


@pytest.mark.parametrize(
    ("spec_text", "result_text", "expected"),
    [
        ("< 100", "<10", VerdictKind.PASS),
        ("< 100", "< 100", VerdictKind.PASS),
        ("< 100", "<500", VerdictKind.INDETERMINATE),
        ("< 10,000 CFU/g", "9,999 cfu/g", VerdictKind.PASS),
        ("< 10,000 CFU/g", "10,000 CFU/g", VerdictKind.FAIL),
        ("<= 10 ppm", "10 ppm", VerdictKind.PASS),
        ("≤ 10 ppm", "10 ppm", VerdictKind.PASS),
        ("> 15", "15", VerdictKind.FAIL),
        (">= 15", "15", VerdictKind.PASS),
        ("≥ 15", "15", VerdictKind.PASS),
        ("20-25", "22.5", VerdictKind.PASS),
        ("20 - 25", "25.1", VerdictKind.FAIL),
        ("< 100 CFU/g", "ND", VerdictKind.PASS),
        ("Negative", "ND", VerdictKind.PASS),
        ("Negative", "Not Detected", VerdictKind.PASS),
        ("Negative", "Absent", VerdictKind.PASS),
        ("Negative", "Detected", VerdictKind.FAIL),
        ("Negative", "Present", VerdictKind.FAIL),
        ("Negative", "42", VerdictKind.INDETERMINATE),
        ("< 100 CFU/g", "TNTC", VerdictKind.FAIL),
        ("< 100 ppm", "TNTC", VerdictKind.INDETERMINATE),
        ("< 100 ppm", "50 ppb", VerdictKind.INDETERMINATE),
        ("< bad", "1", VerdictKind.INDETERMINATE),
        ("< 100", "not a number", VerdictKind.INDETERMINATE),
        ("Conforms to standard", "Conforms to standard", VerdictKind.INDETERMINATE),
        (None, "anything", VerdictKind.NO_SPEC),
        ("", "anything", VerdictKind.NO_SPEC),
        ("< 100", "", VerdictKind.NOT_TESTED),
        ("< 100", None, VerdictKind.NOT_TESTED),
        ("  <   100   CFU/g  ", "  99   CFU/g ", VerdictKind.PASS),
        ("Negative", "negative", VerdictKind.PASS),
    ],
)
def test_evaluation_rules(spec_text, result_text, expected):
    assert evaluate(spec_text, result_text).kind == expected


def test_result_unit_argument_is_used_for_unit_mismatch_detection():
    assert evaluate("< 100 CFU/g", "50", result_unit="cfu/g").kind == VerdictKind.PASS
    assert (
        evaluate("< 100 CFU/g", "50", result_unit="ppm").kind
        == VerdictKind.INDETERMINATE
    )
