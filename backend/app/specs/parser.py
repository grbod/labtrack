"""Parsing primitives for LabTrack specification evaluation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SpecRuleKind(str, Enum):
    LT = "LT"
    LTE = "LTE"
    GT = "GT"
    GTE = "GTE"
    RANGE = "RANGE"
    NEGATIVE_REQUIRED = "NEGATIVE_REQUIRED"
    ABSENT_REQUIRED = "ABSENT_REQUIRED"
    TEXT_MATCH = "TEXT_MATCH"
    JUDGMENT = "JUDGMENT"
    INFORMATIONAL = "INFORMATIONAL"


class ResultValueKind(str, Enum):
    NUMERIC = "NUMERIC"
    CENSORED_LT = "CENSORED_LT"
    CENSORED_GT = "CENSORED_GT"
    ND = "ND"
    TNTC = "TNTC"
    TEXT = "TEXT"
    EMPTY = "EMPTY"


@dataclass(frozen=True)
class SpecRule:
    kind: SpecRuleKind
    raw: str
    threshold: Optional[float] = None
    lower: Optional[float] = None
    upper: Optional[float] = None
    unit: Optional[str] = None
    text: Optional[str] = None


@dataclass(frozen=True)
class ResultValue:
    kind: ResultValueKind
    raw: Optional[str]
    value: Optional[float] = None
    unit: Optional[str] = None
    text: Optional[str] = None


_NUMBER_RE = r"-?(?:\d+(?:,\d{3})*|\d+)(?:\.\d+)?"
_COMPARATOR_RE = re.compile(
    rf"^(?P<op><=|>=|<|>|≤|≥)\s*(?P<num>{_NUMBER_RE})\s*(?P<unit>.*)$",
    re.IGNORECASE,
)
_RANGE_RE = re.compile(
    rf"^(?P<lower>{_NUMBER_RE})\s*(?:-|–|—|to)\s*(?P<upper>{_NUMBER_RE})\s*(?P<unit>.*)$",
    re.IGNORECASE,
)
_NUMERIC_RESULT_RE = re.compile(
    rf"^(?P<num>{_NUMBER_RE})\s*(?P<unit>.*)$",
    re.IGNORECASE,
)

_NEGATIVE_TERMS = {"negative", "neg"}
_ABSENT_SPEC_TERMS = {"absent"}
_ND_TERMS = {
    "nd",
    "n.d.",
    "not detected",
    "none detected",
    "non-detect",
    "nondetect",
    "bdl",
    "below detection limit",
}
_TNTC_TERMS = {"tntc", "too numerous to count"}
_INFORMATIONAL_TERMS = {
    "n/a",
    "na",
    "not applicable",
    "report",
    "report only",
    "for information",
    "informational",
}
_JUDGMENT_PREFIXES = (
    "characteristic",
    "fine ",
    "capsules ",
)
_JUDGMENT_PHRASES = (
    "conforms to standard",
    "conforming to standard",
    "bland, characteristic",
)


def parse_spec(text: str | None) -> SpecRule | None:
    """Parse a specification string into a deterministic rule when possible."""
    if text is None:
        return None

    raw = str(text).strip()
    if not raw:
        return None

    normalized = _normalize_text(raw)
    if normalized in _INFORMATIONAL_TERMS:
        return SpecRule(SpecRuleKind.INFORMATIONAL, raw=raw, text=normalized)
    if normalized in _NEGATIVE_TERMS or normalized.startswith("negative "):
        return SpecRule(SpecRuleKind.NEGATIVE_REQUIRED, raw=raw, text=normalized)
    if normalized in _ABSENT_SPEC_TERMS or normalized.startswith("absent "):
        return SpecRule(SpecRuleKind.ABSENT_REQUIRED, raw=raw, text=normalized)
    if _is_judgment_spec(normalized):
        return SpecRule(SpecRuleKind.JUDGMENT, raw=raw, text=normalized)

    comparator = _COMPARATOR_RE.match(raw)
    if comparator:
        threshold = _parse_number(comparator.group("num"))
        unit = _normalize_unit(comparator.group("unit"))
        op = comparator.group("op")
        kind_by_op = {
            "<": SpecRuleKind.LT,
            "≤": SpecRuleKind.LTE,
            "<=": SpecRuleKind.LTE,
            ">": SpecRuleKind.GT,
            "≥": SpecRuleKind.GTE,
            ">=": SpecRuleKind.GTE,
        }
        return SpecRule(
            kind_by_op[op],
            raw=raw,
            threshold=threshold,
            unit=unit,
        )

    range_match = _RANGE_RE.match(raw)
    if range_match:
        lower = _parse_number(range_match.group("lower"))
        upper = _parse_number(range_match.group("upper"))
        if lower is not None and upper is not None and lower <= upper:
            return SpecRule(
                SpecRuleKind.RANGE,
                raw=raw,
                lower=lower,
                upper=upper,
                unit=_normalize_unit(range_match.group("unit")),
            )
        return None

    if _looks_malformed_numeric(raw):
        return None

    return SpecRule(SpecRuleKind.TEXT_MATCH, raw=raw, text=normalized)


def parse_result(text: str | None) -> ResultValue:
    """Parse a lab result value into a normalized result representation."""
    if text is None:
        return ResultValue(ResultValueKind.EMPTY, raw=text)

    raw = str(text).strip()
    if not raw:
        return ResultValue(ResultValueKind.EMPTY, raw=text)

    normalized = _normalize_text(raw)
    if normalized in _ND_TERMS or normalized in {"negative", "absent"}:
        return ResultValue(ResultValueKind.ND, raw=raw, text=normalized)
    if normalized in _TNTC_TERMS:
        return ResultValue(ResultValueKind.TNTC, raw=raw, text=normalized)

    comparator = _COMPARATOR_RE.match(raw)
    if comparator and comparator.group("op") in {"<", "≤", "<="}:
        return ResultValue(
            ResultValueKind.CENSORED_LT,
            raw=raw,
            value=_parse_number(comparator.group("num")),
            unit=_normalize_unit(comparator.group("unit")),
            text=normalized,
        )
    if comparator and comparator.group("op") in {">", "≥", ">="}:
        return ResultValue(
            ResultValueKind.CENSORED_GT,
            raw=raw,
            value=_parse_number(comparator.group("num")),
            unit=_normalize_unit(comparator.group("unit")),
            text=normalized,
        )

    numeric = _NUMERIC_RESULT_RE.match(raw)
    if numeric:
        return ResultValue(
            ResultValueKind.NUMERIC,
            raw=raw,
            value=_parse_number(numeric.group("num")),
            unit=_normalize_unit(numeric.group("unit")),
            text=normalized,
        )

    return ResultValue(ResultValueKind.TEXT, raw=raw, text=normalized)


def _parse_number(text: str | None) -> float | None:
    if text is None:
        return None
    try:
        return float(str(text).replace(",", "").strip())
    except ValueError:
        return None


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    cleaned = unit.strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", "")
    cleaned = re.sub(r"\s*/\s*", "/", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.lower()


def _is_judgment_spec(normalized: str) -> bool:
    return normalized.startswith(_JUDGMENT_PREFIXES) or any(
        phrase in normalized for phrase in _JUDGMENT_PHRASES
    )


def _looks_malformed_numeric(raw: str) -> bool:
    stripped = raw.strip()
    if stripped[0] in "<>≤≥":
        return True
    return bool(re.match(rf"^{_NUMBER_RE}\s*(?:-|–|—|to)\s*$", stripped))


__all__ = [
    "ResultValue",
    "ResultValueKind",
    "SpecRule",
    "SpecRuleKind",
    "parse_result",
    "parse_spec",
]
