"""Pure lot workflow state machine."""

from dataclasses import dataclass
from typing import Literal, Optional

from app.models.enums import LotStatus, UserRole

Trigger = Literal["auto", "manual"]


@dataclass(frozen=True)
class TransitionContext:
    """Context required to validate a lot status transition."""

    actor_role: UserRole | str
    actor_id: int | None
    results_total: int
    results_approved: int
    results_with_values: int
    required_lab_tests_missing: list[str]
    machine_fail_tests: list[str]
    is_legacy_import: bool
    override: bool
    override_reason: Optional[str]
    trigger: Trigger


@dataclass(frozen=True)
class TransitionResult:
    """Decision from the pure state machine."""

    allowed: bool
    code: str
    reason: str


AUTO_STATUSES = frozenset(
    {
        LotStatus.AWAITING_RESULTS,
        LotStatus.PARTIAL_RESULTS,
        LotStatus.UNDER_REVIEW,
        LotStatus.NEEDS_ATTENTION,
    }
)
QC_ROLES = frozenset({UserRole.QC_MANAGER.value, UserRole.ADMIN.value})
RESUBMIT_ROLES = frozenset(
    {UserRole.LAB_TECH.value, UserRole.QC_MANAGER.value, UserRole.ADMIN.value}
)


def validate_transition(
    current: LotStatus, target: LotStatus, ctx: TransitionContext
) -> TransitionResult:
    """Validate whether a lot may move from current to target under ctx."""

    if ctx.trigger not in {"auto", "manual"}:
        return _deny("INVALID_TRIGGER", "Trigger must be auto or manual")

    if current == target:
        return _deny("NOOP", "Target status matches current status")

    if ctx.trigger == "auto":
        return _validate_auto_transition(current, target, ctx)

    return _validate_manual_transition(current, target, ctx)


def _validate_auto_transition(
    current: LotStatus, target: LotStatus, ctx: TransitionContext
) -> TransitionResult:
    if current not in AUTO_STATUSES:
        return _deny(
            "AUTO_CURRENT_FORBIDDEN",
            f"Auto transitions cannot start from {current.value}",
        )
    if target not in AUTO_STATUSES:
        return _deny(
            "AUTO_TARGET_FORBIDDEN",
            f"Auto transitions cannot target {target.value}",
        )

    expected = _auto_target_for_context(ctx)
    if target != expected:
        return _deny(
            "AUTO_GUARD_FAILED",
            f"Auto context resolves to {expected.value}, not {target.value}",
        )

    return _allow("OK", f"Auto recalculation may move to {target.value}")


def _validate_manual_transition(
    current: LotStatus, target: LotStatus, ctx: TransitionContext
) -> TransitionResult:
    if (
        target in AUTO_STATUSES
        and not (
            current == LotStatus.AWAITING_RELEASE and target == LotStatus.UNDER_REVIEW
        )
        and not (current == LotStatus.REJECTED and target == LotStatus.UNDER_REVIEW)
    ):
        return _deny(
            "MANUAL_AUTO_DOMAIN_FORBIDDEN",
            f"Manual transition to {target.value} is not a manual gate",
        )

    if current in {LotStatus.UNDER_REVIEW, LotStatus.NEEDS_ATTENTION}:
        if target == LotStatus.AWAITING_RELEASE:
            return _validate_submit_for_release(ctx)

    if current == LotStatus.AWAITING_RELEASE:
        if target == LotStatus.RELEASED:
            return _validate_release(ctx)
        if target == LotStatus.UNDER_REVIEW:
            if not _is_qc_role(ctx.actor_role):
                return _deny(
                    "ROLE_FORBIDDEN", "Only QC Manager or Admin may return lots"
                )
            if not _has_reason(ctx.override_reason):
                return _deny("REASON_REQUIRED", "Return for review requires a reason")
            return _allow("OK", "Lot may be returned for review")

    if target == LotStatus.REJECTED and current != LotStatus.RELEASED:
        if not _is_qc_role(ctx.actor_role):
            return _deny("ROLE_FORBIDDEN", "Only QC Manager or Admin may reject lots")
        if not _has_reason(ctx.override_reason):
            return _deny("REASON_REQUIRED", "Rejecting a lot requires a reason")
        return _allow("OK", "Lot may be rejected")

    if current == LotStatus.REJECTED:
        if target == LotStatus.UNDER_REVIEW:
            if not _is_resubmit_role(ctx.actor_role):
                return _deny(
                    "ROLE_FORBIDDEN",
                    "Only Lab Tech, QC Manager, or Admin may resubmit rejected lots",
                )
            return _allow("OK", "Rejected lot may be resubmitted for review")
        return _deny(
            "REJECTED_TARGET_FORBIDDEN", "Rejected lots may only move to under_review"
        )

    if current == LotStatus.RELEASED:
        if target == LotStatus.AWAITING_RELEASE:
            if _role_value(ctx.actor_role) != UserRole.ADMIN.value:
                return _deny("ROLE_FORBIDDEN", "Only Admin may void a released lot")
            if not _has_reason(ctx.override_reason):
                return _deny(
                    "REASON_REQUIRED", "Voiding a released lot requires a reason"
                )
            return _allow("VOID", "Released lot may be voided and requeued")
        return _deny(
            "RELEASED_TERMINAL", "Released lots are terminal except admin void"
        )

    return _deny(
        "TRANSITION_FORBIDDEN",
        f"No manual transition from {current.value} to {target.value}",
    )


def _validate_submit_for_release(ctx: TransitionContext) -> TransitionResult:
    if ctx.trigger != "manual":
        return _deny("TRIGGER_REQUIRED", "Submit for release is a manual transition")

    override_allowed = _override_allowed(ctx)
    if ctx.results_total != ctx.results_approved and not override_allowed:
        return _deny("RESULTS_NOT_APPROVED", "All results must be approved")

    if (
        ctx.required_lab_tests_missing
        and not ctx.is_legacy_import
        and not override_allowed
    ):
        missing = ", ".join(ctx.required_lab_tests_missing)
        return _deny("REQUIRED_TESTS_MISSING", f"Missing required tests: {missing}")

    if ctx.machine_fail_tests and not override_allowed:
        failing = ", ".join(ctx.machine_fail_tests)
        return _deny("MACHINE_FAILS_PRESENT", f"Failing machine verdicts: {failing}")

    if ctx.override and not override_allowed:
        return _deny(
            "OVERRIDE_FORBIDDEN",
            "Override requires QC Manager or Admin and a non-empty reason",
        )

    return _allow("OK", "Lot may be submitted for release")


def _validate_release(ctx: TransitionContext) -> TransitionResult:
    if not _is_qc_role(ctx.actor_role):
        return _deny("ROLE_FORBIDDEN", "Only QC Manager or Admin may release lots")

    if ctx.machine_fail_tests and not _override_allowed(ctx):
        failing = ", ".join(ctx.machine_fail_tests)
        return _deny("MACHINE_FAILS_PRESENT", f"Failing machine verdicts: {failing}")

    if ctx.override and not _override_allowed(ctx):
        return _deny(
            "OVERRIDE_FORBIDDEN",
            "Override requires QC Manager or Admin and a non-empty reason",
        )

    return _allow("OK", "Lot may be released")


def _auto_target_for_context(ctx: TransitionContext) -> LotStatus:
    complete = not ctx.required_lab_tests_missing
    if complete and ctx.machine_fail_tests:
        return LotStatus.NEEDS_ATTENTION
    if complete:
        return LotStatus.UNDER_REVIEW
    if ctx.results_with_values > 0:
        return LotStatus.PARTIAL_RESULTS
    return LotStatus.AWAITING_RESULTS


def _override_allowed(ctx: TransitionContext) -> bool:
    return (
        ctx.override
        and _is_qc_role(ctx.actor_role)
        and _has_reason(ctx.override_reason)
    )


def _is_qc_role(role: UserRole | str) -> bool:
    return _role_value(role) in QC_ROLES


def _is_resubmit_role(role: UserRole | str) -> bool:
    return _role_value(role) in RESUBMIT_ROLES


def _role_value(role: UserRole | str) -> str:
    if isinstance(role, UserRole):
        return role.value
    return str(role)


def _has_reason(reason: Optional[str]) -> bool:
    return bool(reason and reason.strip())


def _allow(code: str, reason: str) -> TransitionResult:
    return TransitionResult(allowed=True, code=code, reason=reason)


def _deny(code: str, reason: str) -> TransitionResult:
    return TransitionResult(allowed=False, code=code, reason=reason)
