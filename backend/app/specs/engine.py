"""Canonical LabTrack specification evaluation engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.specs.parser import (
    ResultValue,
    ResultValueKind,
    SpecRule,
    SpecRuleKind,
    parse_result,
    parse_spec,
)


class VerdictKind(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"
    NO_SPEC = "NO_SPEC"
    NOT_TESTED = "NOT_TESTED"


@dataclass(frozen=True)
class Verdict:
    kind: VerdictKind
    reason: str


def evaluate(
    spec_text: str | None,
    result_value: str | None,
    *,
    result_unit: str | None = None,
) -> Verdict:
    """Evaluate a result against a specification using safe deterministic rules."""
    spec = parse_spec(spec_text)
    result = parse_result(result_value)
    if result_unit:
        result = ResultValue(
            kind=result.kind,
            raw=result.raw,
            value=result.value,
            unit=_normalize_unit(result_unit),
            text=result.text,
        )
    return _evaluate_parsed(spec, result, spec_text)


def _evaluate_parsed(
    spec: SpecRule | None,
    result: ResultValue,
    original_spec_text: str | None,
) -> Verdict:
    if spec is None:
        if original_spec_text is None or not str(original_spec_text).strip():
            return Verdict(VerdictKind.NO_SPEC, "No specification provided.")
        return Verdict(VerdictKind.INDETERMINATE, "Specification could not be parsed.")

    if result.kind == ResultValueKind.EMPTY:
        return Verdict(VerdictKind.NOT_TESTED, "Result value is empty.")

    if spec.kind == SpecRuleKind.INFORMATIONAL:
        return Verdict(VerdictKind.NO_SPEC, "Specification is informational only.")

    if spec.kind == SpecRuleKind.JUDGMENT:
        return Verdict(
            VerdictKind.INDETERMINATE,
            "Judgment-based specification requires human review.",
        )

    if spec.kind in {SpecRuleKind.NEGATIVE_REQUIRED, SpecRuleKind.ABSENT_REQUIRED}:
        return _evaluate_negative_required(result)

    if spec.kind in {
        SpecRuleKind.LT,
        SpecRuleKind.LTE,
        SpecRuleKind.GT,
        SpecRuleKind.GTE,
        SpecRuleKind.RANGE,
    }:
        if _unit_mismatch(spec.unit, result.unit):
            return Verdict(
                VerdictKind.INDETERMINATE,
                f"Unit mismatch: specification uses {spec.unit}, result uses {result.unit}.",
            )
        return _evaluate_numeric(spec, result)

    if spec.kind == SpecRuleKind.TEXT_MATCH:
        return _evaluate_text_match(spec, result)

    return Verdict(VerdictKind.INDETERMINATE, "Unsupported specification rule.")


def _evaluate_negative_required(result: ResultValue) -> Verdict:
    if result.kind == ResultValueKind.ND:
        return Verdict(
            VerdictKind.PASS, "Negative/absent result satisfies specification."
        )
    if result.kind == ResultValueKind.TEXT:
        text = result.text or ""
        if text in {"positive", "detected", "present", "+"}:
            return Verdict(
                VerdictKind.FAIL, "Positive/detected result violates specification."
            )
        if text in {"negative", "not detected", "absent", "nd"}:
            return Verdict(
                VerdictKind.PASS, "Negative/absent result satisfies specification."
            )
    if result.kind in {
        ResultValueKind.NUMERIC,
        ResultValueKind.CENSORED_LT,
        ResultValueKind.CENSORED_GT,
    }:
        return Verdict(
            VerdictKind.INDETERMINATE,
            "Numeric result cannot prove a negative/absent specification.",
        )
    return Verdict(
        VerdictKind.INDETERMINATE,
        "Result text cannot be mapped to negative/positive semantics.",
    )


def _evaluate_numeric(spec: SpecRule, result: ResultValue) -> Verdict:
    if result.kind == ResultValueKind.ND:
        if spec.kind in {SpecRuleKind.LT, SpecRuleKind.LTE}:
            return Verdict(
                VerdictKind.PASS, "ND satisfies an upper-limit specification."
            )
        return Verdict(
            VerdictKind.INDETERMINATE,
            "ND cannot be compared to this numeric specification.",
        )
    if result.kind == ResultValueKind.TNTC:
        if spec.kind in {SpecRuleKind.LT, SpecRuleKind.LTE} and _is_count_unit(
            spec.unit
        ):
            return Verdict(VerdictKind.FAIL, "TNTC violates a count-based upper limit.")
        return Verdict(
            VerdictKind.INDETERMINATE,
            "TNTC cannot be compared to this numeric specification.",
        )
    if result.kind == ResultValueKind.TEXT:
        return Verdict(
            VerdictKind.INDETERMINATE,
            "Text result cannot be compared to a numeric specification.",
        )

    if spec.kind == SpecRuleKind.LT:
        return _evaluate_lt(spec.threshold, result, inclusive=False)
    if spec.kind == SpecRuleKind.LTE:
        return _evaluate_lt(spec.threshold, result, inclusive=True)
    if spec.kind == SpecRuleKind.GT:
        return _evaluate_gt(spec.threshold, result, inclusive=False)
    if spec.kind == SpecRuleKind.GTE:
        return _evaluate_gt(spec.threshold, result, inclusive=True)
    if spec.kind == SpecRuleKind.RANGE:
        return _evaluate_range(spec, result)

    return Verdict(VerdictKind.INDETERMINATE, "Unsupported numeric rule.")


def _evaluate_lt(
    threshold: float | None,
    result: ResultValue,
    *,
    inclusive: bool,
) -> Verdict:
    if threshold is None or result.value is None:
        return Verdict(VerdictKind.INDETERMINATE, "Numeric value could not be parsed.")
    if result.kind == ResultValueKind.NUMERIC:
        passes = result.value <= threshold if inclusive else result.value < threshold
        return Verdict(
            VerdictKind.PASS if passes else VerdictKind.FAIL,
            "Numeric result compared to upper limit.",
        )
    if result.kind == ResultValueKind.CENSORED_LT:
        passes = result.value <= threshold
        return Verdict(
            VerdictKind.PASS if passes else VerdictKind.INDETERMINATE,
            "Censored less-than result compared to upper limit.",
        )
    if result.kind == ResultValueKind.CENSORED_GT:
        if result.value >= threshold:
            return Verdict(
                VerdictKind.FAIL, "Censored greater-than result exceeds upper limit."
            )
        return Verdict(
            VerdictKind.INDETERMINATE,
            "Censored greater-than result may exceed upper limit.",
        )
    return Verdict(VerdictKind.INDETERMINATE, "Result is not numeric.")


def _evaluate_gt(
    threshold: float | None,
    result: ResultValue,
    *,
    inclusive: bool,
) -> Verdict:
    if threshold is None or result.value is None:
        return Verdict(VerdictKind.INDETERMINATE, "Numeric value could not be parsed.")
    if result.kind == ResultValueKind.NUMERIC:
        passes = result.value >= threshold if inclusive else result.value > threshold
        return Verdict(
            VerdictKind.PASS if passes else VerdictKind.FAIL,
            "Numeric result compared to lower limit.",
        )
    if result.kind == ResultValueKind.CENSORED_GT:
        passes = result.value >= threshold
        return Verdict(
            VerdictKind.PASS if passes else VerdictKind.INDETERMINATE,
            "Censored greater-than result compared to lower limit.",
        )
    if result.kind == ResultValueKind.CENSORED_LT:
        if result.value <= threshold:
            return Verdict(
                VerdictKind.FAIL, "Censored less-than result is below lower limit."
            )
        return Verdict(
            VerdictKind.INDETERMINATE,
            "Censored less-than result may be below lower limit.",
        )
    return Verdict(VerdictKind.INDETERMINATE, "Result is not numeric.")


def _evaluate_range(spec: SpecRule, result: ResultValue) -> Verdict:
    if spec.lower is None or spec.upper is None or result.value is None:
        return Verdict(VerdictKind.INDETERMINATE, "Numeric value could not be parsed.")
    if result.kind == ResultValueKind.NUMERIC:
        passes = spec.lower <= result.value <= spec.upper
        return Verdict(
            VerdictKind.PASS if passes else VerdictKind.FAIL,
            "Numeric result compared to inclusive range.",
        )
    if result.kind == ResultValueKind.CENSORED_LT and result.value <= spec.lower:
        return Verdict(VerdictKind.FAIL, "Censored result is below the allowed range.")
    if result.kind == ResultValueKind.CENSORED_GT and result.value >= spec.upper:
        return Verdict(VerdictKind.FAIL, "Censored result is above the allowed range.")
    return Verdict(
        VerdictKind.INDETERMINATE,
        "Censored result cannot prove range compliance.",
    )


def _evaluate_text_match(spec: SpecRule, result: ResultValue) -> Verdict:
    if result.kind != ResultValueKind.TEXT:
        if spec.text and result.raw is not None:
            passes = spec.text == " ".join(str(result.raw).strip().lower().split())
            return Verdict(
                VerdictKind.PASS if passes else VerdictKind.FAIL,
                "Raw result compared to exact text specification.",
            )
        return Verdict(
            VerdictKind.INDETERMINATE,
            "Non-text result cannot be compared to text specification.",
        )
    passes = (spec.text or "") == (result.text or "")
    return Verdict(
        VerdictKind.PASS if passes else VerdictKind.FAIL,
        "Text result compared to exact text specification.",
    )


def _unit_mismatch(spec_unit: str | None, result_unit: str | None) -> bool:
    return bool(spec_unit and result_unit and spec_unit != result_unit)


def _normalize_unit(unit: str) -> str:
    return unit.replace(",", "").strip().lower().replace(" / ", "/")


def _is_count_unit(unit: str | None) -> bool:
    return bool(unit and ("cfu" in unit or "/g" in unit or "/ml" in unit))


__all__ = ["Verdict", "VerdictKind", "evaluate"]
