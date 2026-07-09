"""Canonical specification parsing and evaluation API."""

from app.specs.engine import Verdict, VerdictKind, evaluate
from app.specs.parser import ResultValue, SpecRule, parse_result, parse_spec

__all__ = [
    "ResultValue",
    "SpecRule",
    "Verdict",
    "VerdictKind",
    "evaluate",
    "parse_result",
    "parse_spec",
]
