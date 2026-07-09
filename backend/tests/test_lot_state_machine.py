"""Tests for the canonical lot workflow state machine core."""

from types import SimpleNamespace

import pytest

from app.config import settings
from app.models.audit import AuditLog
from app.models.enums import (
    AuditAction,
    LotStatus,
    TestResultStatus as ResultStatus,
    UserRole,
)
from app.models.lab_test_type import LabTestType
from app.models.product_test_spec import ProductTestSpecification
from app.models.test_result import TestResult as ResultRecord
from app.workflow.lot_state_machine import (
    TransitionContext,
    validate_transition,
)
from app.workflow.lot_workflow_service import (
    LotWorkflowService,
    WorkflowTransitionError,
    set_status_unchecked,
)


STATUSES = list(LotStatus)
ROLES = list(UserRole)
TRIGGERS = ["auto", "manual"]

GUARD_VARIANTS = [
    {
        "name": "no_results_missing",
        "results_total": 0,
        "results_approved": 0,
        "results_with_values": 0,
        "required_lab_tests_missing": ["Total Plate Count"],
        "machine_fail_tests": [],
        "is_legacy_import": False,
        "override": False,
        "override_reason": None,
    },
    {
        "name": "partial_missing",
        "results_total": 2,
        "results_approved": 2,
        "results_with_values": 1,
        "required_lab_tests_missing": ["Lead"],
        "machine_fail_tests": [],
        "is_legacy_import": False,
        "override": False,
        "override_reason": None,
    },
    {
        "name": "complete_pass",
        "results_total": 2,
        "results_approved": 2,
        "results_with_values": 2,
        "required_lab_tests_missing": [],
        "machine_fail_tests": [],
        "is_legacy_import": False,
        "override": False,
        "override_reason": None,
    },
    {
        "name": "complete_draft",
        "results_total": 2,
        "results_approved": 1,
        "results_with_values": 2,
        "required_lab_tests_missing": [],
        "machine_fail_tests": [],
        "is_legacy_import": False,
        "override": False,
        "override_reason": None,
    },
    {
        "name": "complete_fail",
        "results_total": 2,
        "results_approved": 2,
        "results_with_values": 2,
        "required_lab_tests_missing": [],
        "machine_fail_tests": ["Lead"],
        "is_legacy_import": False,
        "override": False,
        "override_reason": None,
    },
    {
        "name": "override_reason",
        "results_total": 2,
        "results_approved": 1,
        "results_with_values": 2,
        "required_lab_tests_missing": ["Lead"],
        "machine_fail_tests": ["Lead"],
        "is_legacy_import": False,
        "override": True,
        "override_reason": "QC deviation accepted",
    },
    {
        "name": "override_blank_reason",
        "results_total": 2,
        "results_approved": 1,
        "results_with_values": 2,
        "required_lab_tests_missing": ["Lead"],
        "machine_fail_tests": ["Lead"],
        "is_legacy_import": False,
        "override": True,
        "override_reason": "  ",
    },
    {
        "name": "legacy_missing",
        "results_total": 2,
        "results_approved": 2,
        "results_with_values": 2,
        "required_lab_tests_missing": ["Historical panel gap"],
        "machine_fail_tests": [],
        "is_legacy_import": True,
        "override": False,
        "override_reason": None,
    },
]


def _ctx(role, trigger, variant):
    payload = dict(variant)
    payload.pop("name")
    return TransitionContext(
        actor_role=role,
        actor_id=1,
        trigger=trigger,
        **payload,
    )


def _expected(current, target, ctx):
    if current == target:
        return False, "NOOP"

    if ctx.trigger == "auto":
        auto_domain = {
            LotStatus.AWAITING_RESULTS,
            LotStatus.PARTIAL_RESULTS,
            LotStatus.UNDER_REVIEW,
            LotStatus.NEEDS_ATTENTION,
        }
        if current not in auto_domain:
            return False, "AUTO_CURRENT_FORBIDDEN"
        if target not in auto_domain:
            return False, "AUTO_TARGET_FORBIDDEN"
        expected_target = _expected_auto_target(ctx)
        if target != expected_target:
            return False, "AUTO_GUARD_FAILED"
        return True, "OK"

    if target in {
        LotStatus.AWAITING_RESULTS,
        LotStatus.PARTIAL_RESULTS,
        LotStatus.NEEDS_ATTENTION,
    }:
        return False, "MANUAL_AUTO_DOMAIN_FORBIDDEN"

    if target == LotStatus.UNDER_REVIEW and current not in {
        LotStatus.AWAITING_RELEASE,
        LotStatus.REJECTED,
    }:
        return False, "MANUAL_AUTO_DOMAIN_FORBIDDEN"

    qc_role = ctx.actor_role in {UserRole.QC_MANAGER, UserRole.ADMIN}
    resubmit_role = ctx.actor_role in {
        UserRole.LAB_TECH,
        UserRole.QC_MANAGER,
        UserRole.ADMIN,
    }
    has_reason = bool(ctx.override_reason and ctx.override_reason.strip())
    override_allowed = ctx.override and qc_role and has_reason

    if (
        current in {LotStatus.UNDER_REVIEW, LotStatus.NEEDS_ATTENTION}
        and target == LotStatus.AWAITING_RELEASE
    ):
        if ctx.results_total != ctx.results_approved and not override_allowed:
            return False, "RESULTS_NOT_APPROVED"
        if (
            ctx.required_lab_tests_missing
            and not ctx.is_legacy_import
            and not override_allowed
        ):
            return False, "REQUIRED_TESTS_MISSING"
        if ctx.machine_fail_tests and not override_allowed:
            return False, "MACHINE_FAILS_PRESENT"
        if ctx.override and not override_allowed:
            return False, "OVERRIDE_FORBIDDEN"
        return True, "OK"

    if current == LotStatus.AWAITING_RELEASE and target == LotStatus.RELEASED:
        if not qc_role:
            return False, "ROLE_FORBIDDEN"
        if ctx.machine_fail_tests and not override_allowed:
            return False, "MACHINE_FAILS_PRESENT"
        if ctx.override and not override_allowed:
            return False, "OVERRIDE_FORBIDDEN"
        return True, "OK"

    if current == LotStatus.AWAITING_RELEASE and target == LotStatus.UNDER_REVIEW:
        if not qc_role:
            return False, "ROLE_FORBIDDEN"
        if not has_reason:
            return False, "REASON_REQUIRED"
        return True, "OK"

    if target == LotStatus.REJECTED and current != LotStatus.RELEASED:
        if not qc_role:
            return False, "ROLE_FORBIDDEN"
        if not has_reason:
            return False, "REASON_REQUIRED"
        return True, "OK"

    if current == LotStatus.REJECTED:
        if target == LotStatus.UNDER_REVIEW:
            if not resubmit_role:
                return False, "ROLE_FORBIDDEN"
            return True, "OK"
        return False, "REJECTED_TARGET_FORBIDDEN"

    if current == LotStatus.RELEASED:
        if target == LotStatus.AWAITING_RELEASE:
            if ctx.actor_role != UserRole.ADMIN:
                return False, "ROLE_FORBIDDEN"
            if not has_reason:
                return False, "REASON_REQUIRED"
            return True, "VOID"
        return False, "RELEASED_TERMINAL"

    return False, "TRANSITION_FORBIDDEN"


def _expected_auto_target(ctx):
    complete = not ctx.required_lab_tests_missing
    if complete and ctx.machine_fail_tests:
        return LotStatus.NEEDS_ATTENTION
    if complete:
        return LotStatus.UNDER_REVIEW
    if ctx.results_with_values > 0:
        return LotStatus.PARTIAL_RESULTS
    return LotStatus.AWAITING_RESULTS


@pytest.mark.parametrize("current", STATUSES)
@pytest.mark.parametrize("target", STATUSES)
@pytest.mark.parametrize("trigger", TRIGGERS)
@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize(
    "variant", GUARD_VARIANTS, ids=[v["name"] for v in GUARD_VARIANTS]
)
def test_lot_state_machine_exhaustive_policy_matrix(
    current, target, trigger, role, variant
):
    ctx = _ctx(role, trigger, variant)

    result = validate_transition(current, target, ctx)
    expected_allowed, expected_code = _expected(current, target, ctx)

    assert result.allowed is expected_allowed
    assert result.code == expected_code


def test_service_context_counts_results_and_excludes_sensory_required_tests(
    test_db, sample_lot, sample_product
):
    tpc = LabTestType(
        test_name="Total Plate Count",
        test_category="Microbiological",
        default_unit="CFU/g",
    )
    appearance = LabTestType(
        test_name="Appearance",
        test_category="Organoleptic",
        default_unit="",
    )
    test_db.add_all([tpc, appearance])
    test_db.flush()
    test_db.add_all(
        [
            ProductTestSpecification(
                product_id=sample_product.id,
                lab_test_type_id=tpc.id,
                specification="< 10000",
                is_required=True,
            ),
            ProductTestSpecification(
                product_id=sample_product.id,
                lab_test_type_id=appearance.id,
                specification="Typical",
                is_required=True,
            ),
        ]
    )
    test_db.add(
        ResultRecord(
            lot_id=sample_lot.id,
            lab_test_type_id=tpc.id,
            test_type="Total Plate Count",
            result_value="< 10",
            status=ResultStatus.APPROVED,
        )
    )
    test_db.commit()

    service = LotWorkflowService()
    actor = SimpleNamespace(id=7, role=UserRole.QC_MANAGER)

    ctx = service.build_context(
        test_db,
        sample_lot,
        actor,
        reason=None,
        override=False,
        trigger="manual",
    )

    assert ctx.results_total == 1
    assert ctx.results_approved == 1
    assert ctx.results_with_values == 1
    assert ctx.required_lab_tests_missing == []


def test_service_transition_applies_status_and_writes_audit(
    test_db, sample_lot, sample_user
):
    set_status_unchecked(sample_lot, LotStatus.UNDER_REVIEW)
    test_db.add(
        ResultRecord(
            lot_id=sample_lot.id,
            test_type="Total Plate Count",
            result_value="< 10",
            status=ResultStatus.APPROVED,
        )
    )
    test_db.commit()

    service = LotWorkflowService()
    service.transition(
        test_db,
        sample_lot,
        LotStatus.AWAITING_RELEASE,
        sample_user,
        trigger="manual",
    )

    assert sample_lot.status == LotStatus.AWAITING_RELEASE
    audit = (
        test_db.query(AuditLog)
        .filter(AuditLog.table_name == "lots", AuditLog.record_id == sample_lot.id)
        .one()
    )
    assert audit.table_name == "lots"
    assert audit.action == AuditAction.UPDATE
    assert audit.get_old_values_dict()["status"] == LotStatus.UNDER_REVIEW.value
    assert audit.get_new_values_dict()["status"] == LotStatus.AWAITING_RELEASE.value


def test_service_legacy_import_exempts_completeness_only(
    test_db, sample_lot, sample_user
):
    set_status_unchecked(sample_lot, LotStatus.UNDER_REVIEW)
    sample_lot.legacy_import = True
    tpc = LabTestType(
        test_name="Total Plate Count",
        test_category="Microbiological",
        default_unit="CFU/g",
    )
    test_db.add(tpc)
    test_db.flush()
    test_db.add(
        ProductTestSpecification(
            product_id=sample_lot.lot_products[0].product_id,
            lab_test_type_id=tpc.id,
            specification="< 10000",
            is_required=True,
        )
    )
    test_db.commit()

    service = LotWorkflowService()
    service.transition(
        test_db,
        sample_lot,
        LotStatus.AWAITING_RELEASE,
        sample_user,
        trigger="manual",
    )

    assert sample_lot.status == LotStatus.AWAITING_RELEASE


def test_service_legacy_import_does_not_exempt_unapproved_results(
    test_db, sample_lot, sample_user
):
    set_status_unchecked(sample_lot, LotStatus.UNDER_REVIEW)
    sample_lot.legacy_import = True
    test_db.add(
        ResultRecord(
            lot_id=sample_lot.id,
            test_type="Total Plate Count",
            result_value="< 10",
            status=ResultStatus.DRAFT,
        )
    )
    test_db.commit()

    service = LotWorkflowService()
    with pytest.raises(WorkflowTransitionError) as exc_info:
        service.transition(
            test_db,
            sample_lot,
            LotStatus.AWAITING_RELEASE,
            sample_user,
            trigger="manual",
        )

    assert exc_info.value.code == "RESULTS_NOT_APPROVED"


def test_lot_status_guard_is_inert_by_default(test_db, sample_lot, monkeypatch):
    monkeypatch.setattr(settings, "workflow_enforce_transitions", False)

    sample_lot.status = LotStatus.PARTIAL_RESULTS

    assert sample_lot.status == LotStatus.PARTIAL_RESULTS


def test_lot_status_guard_blocks_raw_assignment_when_enabled(
    test_db, sample_lot, monkeypatch
):
    monkeypatch.setattr(settings, "workflow_enforce_transitions", True)

    with pytest.raises(ValueError, match="Lot.status assignment"):
        sample_lot.status = LotStatus.PARTIAL_RESULTS


def test_lot_status_guard_allows_workflow_service_token(
    test_db, sample_lot, sample_user, monkeypatch
):
    monkeypatch.setattr(settings, "workflow_enforce_transitions", False)
    sample_lot.status = LotStatus.AWAITING_RELEASE
    test_db.commit()
    monkeypatch.setattr(settings, "workflow_enforce_transitions", True)

    service = LotWorkflowService()
    service.transition(
        test_db,
        sample_lot,
        LotStatus.UNDER_REVIEW,
        sample_user,
        reason="Needs lab clarification",
        trigger="manual",
    )

    assert sample_lot.status == LotStatus.UNDER_REVIEW
