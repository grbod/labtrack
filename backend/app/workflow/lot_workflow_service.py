"""Database-backed lot workflow transition service."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Optional

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import AuditAction, LotStatus, TestResultStatus
from app.models.lot import Lot
from app.models.product_test_spec import ProductTestSpecification
from app.models.test_result import TestResult
from app.services.base import BaseService
from app.workflow.lot_state_machine import (
    TransitionContext,
    TransitionResult,
    validate_transition,
)

_TRANSITION_TOKEN_ATTR = "_lot_workflow_transition_token"


class WorkflowTransitionError(ValueError):
    """Raised when the canonical lot workflow denies a transition."""

    def __init__(self, result: TransitionResult):
        super().__init__(result.reason)
        self.result = result
        self.code = result.code
        self.reason = result.reason


class LotWorkflowService(BaseService[Lot]):
    """Canonical DB wrapper around the pure lot state machine."""

    def __init__(self):
        super().__init__(Lot)

    def transition(
        self,
        db: Session,
        lot: Lot,
        target: LotStatus,
        actor,
        *,
        reason: Optional[str] = None,
        override: bool = False,
        trigger: str = "manual",
    ) -> Lot:
        """Validate and apply a lot status transition without committing."""

        old_status = lot.status
        ctx = self.build_context(
            db,
            lot,
            actor,
            reason=reason,
            override=override,
            trigger=trigger,
        )
        result = validate_transition(old_status, target, ctx)
        if not result.allowed:
            raise WorkflowTransitionError(result)

        with _allow_lot_status_assignment(lot):
            lot.status = target

        self._log_audit(
            db=db,
            action=self._audit_action(target, override),
            record_id=lot.id,
            old_values={"status": old_status.value},
            new_values={"status": target.value},
            user_id=ctx.actor_id,
            reason=reason or result.reason,
            metadata={
                "workflow_code": result.code,
                "trigger": trigger,
                "override": override,
            },
        )
        db.flush()
        return lot

    def build_context(
        self,
        db: Session,
        lot: Lot,
        actor,
        *,
        reason: Optional[str],
        override: bool,
        trigger: str,
    ) -> TransitionContext:
        """Build the pure transition context from persisted lot data."""

        results = db.query(TestResult).filter(TestResult.lot_id == lot.id).all()
        required_specs = list(_required_non_sensory_specs(lot))
        missing_tests = _missing_required_tests(required_specs, results)
        machine_fail_tests = _machine_fail_tests(required_specs, results)

        return TransitionContext(
            actor_role=getattr(actor, "role", actor),
            actor_id=getattr(actor, "id", None),
            results_total=len(results),
            results_approved=sum(
                1 for result in results if result.status == TestResultStatus.APPROVED
            ),
            results_with_values=sum(1 for result in results if _has_value(result)),
            required_lab_tests_missing=missing_tests,
            machine_fail_tests=machine_fail_tests,
            is_legacy_import=_is_legacy_import(lot),
            override=override,
            override_reason=reason,
            trigger=trigger,  # type: ignore[arg-type]
        )

    @staticmethod
    def _audit_action(target: LotStatus, override: bool) -> AuditAction:
        if override:
            return AuditAction.OVERRIDE
        if target == LotStatus.REJECTED:
            return AuditAction.REJECT
        return AuditAction.UPDATE


def _required_non_sensory_specs(lot: Lot) -> Iterable[ProductTestSpecification]:
    seen: set[int] = set()
    for lot_product in lot.lot_products:
        product = lot_product.product
        if not product:
            continue
        for spec in product.test_specifications:
            if not spec.is_required or not spec.lab_test_type:
                continue
            if spec.lab_test_type_id in seen:
                continue
            if _is_sensory_spec(spec):
                continue
            seen.add(spec.lab_test_type_id)
            yield spec


def _is_sensory_spec(spec: ProductTestSpecification) -> bool:
    lab_test_type = spec.lab_test_type
    haystack = " ".join(
        str(part or "")
        for part in (
            getattr(lab_test_type, "test_name", ""),
            getattr(lab_test_type, "test_category", ""),
        )
    ).lower()
    return any(
        token in haystack for token in ("taste", "appearance", "odor", "organoleptic")
    )


def _missing_required_tests(
    required_specs: list[ProductTestSpecification], results: list[TestResult]
) -> list[str]:
    covered_ids = {
        result.lab_test_type_id
        for result in results
        if result.lab_test_type_id is not None and _has_value(result)
    }
    covered_names = {
        _normalize_name(result.test_type) for result in results if _has_value(result)
    }

    missing: list[str] = []
    for spec in required_specs:
        test_name = spec.test_name or f"lab_test_type_id={spec.lab_test_type_id}"
        if spec.lab_test_type_id in covered_ids:
            continue
        if _normalize_name(test_name) in covered_names:
            continue
        missing.append(test_name)
    return missing


def _machine_fail_tests(
    required_specs: list[ProductTestSpecification], results: list[TestResult]
) -> list[str]:
    try:
        from app.specs import VerdictKind, evaluate
    except ImportError:
        return []

    specs_by_id = {spec.lab_test_type_id: spec for spec in required_specs}
    specs_by_name = {
        _normalize_name(spec.test_name or ""): spec
        for spec in required_specs
        if spec.test_name
    }
    failing: list[str] = []

    for result in results:
        if not _has_value(result):
            continue

        spec = None
        if result.lab_test_type_id is not None:
            spec = specs_by_id.get(result.lab_test_type_id)
        if spec is None:
            spec = specs_by_name.get(_normalize_name(result.test_type))

        spec_text = spec.specification if spec is not None else result.specification
        try:
            verdict = evaluate(spec_text, result.result_value)
        except Exception:
            failing.append(result.test_type)
            continue

        verdict_kind = getattr(verdict, "kind", verdict)
        if verdict_kind in {VerdictKind.FAIL, VerdictKind.INDETERMINATE}:
            failing.append(result.test_type)

    return failing


def _has_value(result: TestResult) -> bool:
    return result.result_value is not None and str(result.result_value).strip() != ""


def _normalize_name(value: str) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _is_legacy_import(lot: Lot) -> bool:
    return bool(
        getattr(lot, "legacy_import", False)
        or getattr(lot, "imported_from_register", False)
    )


@contextmanager
def _allow_lot_status_assignment(lot: Lot):
    setattr(lot, _TRANSITION_TOKEN_ATTR, True)
    try:
        yield
    finally:
        if hasattr(lot, _TRANSITION_TOKEN_ATTR):
            delattr(lot, _TRANSITION_TOKEN_ATTR)


@event.listens_for(Lot.status, "set", retval=True)
def _guard_lot_status_assignment(target, value, oldvalue, initiator):
    """Optionally reject raw Lot.status assignments outside LotWorkflowService."""

    if not settings.workflow_enforce_transitions:
        return value

    if getattr(target, "id", None) is None:
        return value

    if getattr(target, _TRANSITION_TOKEN_ATTR, False):
        return value

    raise ValueError(
        "Lot.status assignment must flow through LotWorkflowService.transition"
    )
