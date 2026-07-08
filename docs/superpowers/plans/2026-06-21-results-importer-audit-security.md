# Results Importer Audit & Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three highest-severity findings from the Results Importer review — (1) lab-data writes are not in the audit trail, (2) revert is entirely unaudited, (3) the `/uploads` DELETE endpoint lets any authenticated user (incl. READ_ONLY) delete any stored PDF.

**Architecture:** The importer service inherits `BaseService._log_audit`, but that helper hardcodes `table_name` to `self.model.__tablename__` (= `result_imports`), so it cannot attribute writes to `test_results` or `lots`. We add one small helper (`_audit_entity`) that calls `AuditLog.log_change` directly with an explicit `table_name`, then emit audit rows at every lab-data mutation in `confirm()` and `revert()` — all inside the existing single transaction (before `db.commit()`), and all non-fatal (swallowed on failure) to match the existing base-service convention. Separately, we tighten the `DELETE /uploads/{key}` role gate.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy ORM, Pytest (in-memory SQLite), FastAPI `TestClient`.

## Global Constraints

- Work in the worktree `/Users/gregsimek/Code/COA-creator/tmp/results-importer` (branch `feature/results-importer`). All paths below are relative to that worktree root.
- Use the venv Python for all backend commands: `backend/.venv/bin/python`. Run pytest with `--no-cov` for fast iteration: `backend/.venv/bin/python -m pytest <path> -v --no-cov` (run from the `backend/` directory).
- Audit calls must run **inside the caller's transaction, before `db.commit()`** so they roll back with the operation.
- Audit failures must be **non-fatal** (swallowed + logged), matching `BaseService._log_audit` (`backend/app/services/base.py:280-282`). Never let an audit write break or roll back a confirm/revert.
- `AuditAction` has **no `REVERT` member** (`backend/app/models/enums.py:54-63`). Use `INSERT` / `UPDATE` / `DELETE`.
- `AuditLog` requires a non-empty `reason` for `action in [DELETE, REJECT]` (`backend/app/models/audit.py:102-107`) — always pass `reason` on DELETE-action audits.
- `AuditLog.record_id` must be `>= 1` (`backend/app/models/audit.py:71-80`); only real positive ORM ids are used here.
- `AuditLog.log_change(session, table_name, record_id, action, old_values=None, new_values=None, user=None, ip_address=None, user_agent=None, reason=None)` — `user` accepts a User object or an int id; it `session.add`s but does **not** flush/commit.
- `_result_snapshot(result)` (`backend/app/services/result_import_service.py:1156-1177`) returns a JSON-serializable dict; reuse it verbatim for audit `old_values`/`new_values`.
- Do NOT change the existing confirm/revert behavior, transaction boundary, or ledger writes — only ADD audit rows and (Task 4) a role dependency.

---

### Task 1: Add the `_audit_entity` helper

**Files:**
- Modify: `backend/app/services/result_import_service.py` (add helper method on `ResultImportService`; ensure imports)
- Test: `backend/tests/test_result_import_service.py`

**Interfaces:**
- Produces: `ResultImportService._audit_entity(db, table_name, action, record_id, old_values=None, new_values=None, user_id=None, reason=None) -> None` — writes an `AuditLog` row for an arbitrary table; swallows failures.

- [ ] **Step 1: Confirm/add imports at the top of `backend/app/services/result_import_service.py`**

Ensure these are present (add any that are missing — `AuditAction` is already used at line ~598, so it is imported; verify `AuditLog`, `logger`, and the typing names):

```python
import logging
from typing import Any, Dict, Optional

from app.models.audit import AuditLog
from app.models.enums import AuditAction

logger = logging.getLogger(__name__)
```

If `logger` is already defined or `AuditAction` already imported, do not duplicate. Only add what's missing.

- [ ] **Step 2: Write the failing test**

Add to `backend/tests/test_result_import_service.py`:

```python
from app.models.audit import AuditLog
from app.models.enums import AuditAction


def test_audit_entity_writes_row_for_arbitrary_table(test_db, sample_user):
    service = ResultImportService()
    service._audit_entity(
        test_db,
        table_name="test_results",
        action=AuditAction.INSERT,
        record_id=12345,
        new_values={"result_value": "Negative"},
        user_id=sample_user.id,
    )
    test_db.commit()

    entry = (
        test_db.query(AuditLog)
        .filter(AuditLog.table_name == "test_results", AuditLog.record_id == 12345)
        .first()
    )
    assert entry is not None
    assert entry.action == AuditAction.INSERT
    assert entry.user_id == sample_user.id
    assert entry.get_new_values_dict().get("result_value") == "Negative"


def test_audit_entity_swallows_failures(test_db, sample_user):
    service = ResultImportService()
    # DELETE without a reason raises inside AuditLog; helper must swallow it.
    service._audit_entity(
        test_db,
        table_name="test_results",
        action=AuditAction.DELETE,
        record_id=999,
        old_values={"result_value": "x"},
        user_id=sample_user.id,
        reason=None,
    )
    # No exception should propagate; no row should be written.
    test_db.commit()
    entry = (
        test_db.query(AuditLog)
        .filter(AuditLog.table_name == "test_results", AuditLog.record_id == 999)
        .first()
    )
    assert entry is None
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_result_import_service.py::test_audit_entity_writes_row_for_arbitrary_table tests/test_result_import_service.py::test_audit_entity_swallows_failures -v --no-cov`
Expected: FAIL with `AttributeError: 'ResultImportService' object has no attribute '_audit_entity'`.

- [ ] **Step 4: Implement the helper**

Add this method inside `class ResultImportService` (place it near the other private helpers, e.g. just above `_result_snapshot`):

```python
def _audit_entity(
    self,
    db: Session,
    table_name: str,
    action: AuditAction,
    record_id: int,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> None:
    """Write an AuditLog row for an arbitrary table.

    BaseService._log_audit hardcodes table_name to result_imports, so the
    importer uses this to attribute lab-data writes to ``test_results``/``lots``.
    Must run inside the caller's transaction (before db.commit()). Failures are
    swallowed to match BaseService._log_audit — an audit write must never break
    or roll back the underlying operation.
    """
    try:
        AuditLog.log_change(
            session=db,
            table_name=table_name,
            record_id=record_id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            user=user_id,
            reason=reason,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(
            "Failed to create audit log for %s#%s: %s", table_name, record_id, exc
        )
```

(`Session` is already imported in this module — it is used in every service method signature.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_result_import_service.py::test_audit_entity_writes_row_for_arbitrary_table tests/test_result_import_service.py::test_audit_entity_swallows_failures -v --no-cov`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/result_import_service.py backend/tests/test_result_import_service.py
git commit -m "feat: add _audit_entity helper for cross-table importer audit"
```

---

### Task 2: Audit lab-data writes in `confirm()` (Finding #1)

**Files:**
- Modify: `backend/app/services/result_import_service.py` — `confirm()` create path (~lines 539-567), replace path (~lines 495-533), PDF-attach site (~line 579), awaiting-release pullback (~lines 608-609)
- Test: `backend/tests/test_result_import_service.py`

**Interfaces:**
- Consumes: `_audit_entity(...)` (Task 1), `_result_snapshot(result)` (existing, line 1156).
- Produces: per-applied-row `test_results` audit rows (INSERT for created/ad-hoc, UPDATE for replaced) + one `lots` UPDATE audit for the PDF attachment, all written before the existing `db.commit()` at line 615.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_result_import_service.py`:

```python
def test_confirm_audits_created_result(test_db, sample_lot, sample_user):
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/coa.pdf",
        file_hash="hash-create-audit",
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        extracted_data={
            "rows": [
                {
                    "row_id": "row-1",
                    "test_name": "Total Plate Count",
                    "result_value": "< 10,000 CFU/g",
                    "unit": "CFU/g",
                }
            ]
        },
        uploaded_by_id=sample_user.id,
    )
    test_db.add(import_row)
    test_db.commit()

    result = ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="apply")],
        sample_user.id,
    )
    created_id = result["created_result_ids"][0]

    entry = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "test_results",
            AuditLog.record_id == created_id,
            AuditLog.action == AuditAction.INSERT,
        )
        .first()
    )
    assert entry is not None
    assert entry.user_id == sample_user.id
    assert entry.get_new_values_dict().get("result_value") == "< 10,000 CFU/g"


def test_confirm_audits_replaced_result(test_db, sample_lot, sample_user):
    existing = TestResult(
        lot_id=sample_lot.id,
        test_type="Total Plate Count",
        result_value="old value",
        status=TestResultStatus.DRAFT,
    )
    test_db.add(existing)
    test_db.commit()

    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/coa2.pdf",
        file_hash="hash-replace-audit",
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        extracted_data={
            "rows": [
                {
                    "row_id": "row-1",
                    "test_name": "Total Plate Count",
                    "result_value": "new value",
                }
            ]
        },
        uploaded_by_id=sample_user.id,
    )
    test_db.add(import_row)
    test_db.commit()

    ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="replace")],
        sample_user.id,
    )

    entry = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "test_results",
            AuditLog.record_id == existing.id,
            AuditLog.action == AuditAction.UPDATE,
        )
        .first()
    )
    assert entry is not None
    assert entry.get_old_values_dict().get("result_value") == "old value"
    assert entry.get_new_values_dict().get("result_value") == "new value"


def test_confirm_audits_pdf_attachment_on_lot(test_db, sample_lot, sample_user):
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/coa3.pdf",
        file_hash="hash-pdf-audit",
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        extracted_data={
            "rows": [
                {"row_id": "row-1", "test_name": "Total Plate Count", "result_value": "Negative"}
            ]
        },
        uploaded_by_id=sample_user.id,
    )
    test_db.add(import_row)
    test_db.commit()

    ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="apply")],
        sample_user.id,
    )

    entry = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "lots",
            AuditLog.record_id == sample_lot.id,
            AuditLog.action == AuditAction.UPDATE,
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert entry is not None
    assert "attached_pdfs" in entry.get_new_values_dict()


def test_confirm_audits_awaiting_release_pullback(test_db, sample_lot, sample_user):
    sample_lot.status = LotStatus.AWAITING_RELEASE
    test_db.add(sample_lot)
    test_db.commit()

    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/coa-pullback.pdf",
        file_hash="hash-pullback-audit",
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        extracted_data={
            "rows": [
                {"row_id": "row-1", "test_name": "Total Plate Count", "result_value": "Negative"}
            ]
        },
        uploaded_by_id=sample_user.id,
    )
    test_db.add(import_row)
    test_db.commit()

    ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="apply")],
        sample_user.id,
    )

    lot_audits = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "lots",
            AuditLog.record_id == sample_lot.id,
            AuditLog.action == AuditAction.UPDATE,
        )
        .all()
    )
    pullback = [
        e
        for e in lot_audits
        if e.get_old_values_dict().get("status") == "awaiting_release"
        and e.get_new_values_dict().get("status") == "under_review"
    ]
    assert pullback, "expected an explicit AWAITING_RELEASE->UNDER_REVIEW pullback audit"
```

(`LotStatus` is already imported in this test module via `from app.models.enums import LotStatus, LotType`.)

(If `sample_lot` already has a non-empty `attached_pdfs` and the test for replace requires a blank existing value, the `test_type` string must match the row's normalized test name — `"Total Plate Count"` normalizes to itself. Adjust the `existing.test_type` only if `_resolve_test_fields` maps differently; the rename table in `result_import_service.py:51-73` leaves "Total Plate Count" unchanged.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_result_import_service.py -k "confirm_audits" -v --no-cov`
Expected: FAIL — no matching `AuditLog` rows yet (assert `entry is not None` fails).

- [ ] **Step 3: Add the INSERT audit in the create path**

In `confirm()`, the create path appends `result.id` to `created_ids` right after `db.flush()` (around lines 558-559). Immediately after `created_ids.append(result.id)`, add:

```python
            self._audit_entity(
                db,
                table_name="test_results",
                action=AuditAction.INSERT,
                record_id=result.id,
                new_values=self._result_snapshot(result),
                user_id=user_id,
                reason=(
                    f"Result import: ad-hoc test '{action.test_name}' created"
                    if action.action == "create_adhoc"
                    else "Result import: draft result created"
                ),
            )
```

- [ ] **Step 4: Add the UPDATE audit in the replace path**

In `confirm()`, the replace path captures `old = self._result_snapshot(existing)` at line 504 and overwrites fields through ~line 516. After the overwrite and before/after the `updated.append({...})` block (lines 517-523), add:

```python
            self._audit_entity(
                db,
                table_name="test_results",
                action=AuditAction.UPDATE,
                record_id=existing.id,
                old_values=old,
                new_values=self._result_snapshot(existing),
                user_id=user_id,
                reason="Result import: replaced existing draft value",
            )
```

- [ ] **Step 5: Add the `lots` audits (PDF attach + awaiting-release pullback)**

(a) PDF attach — `confirm()` line 579 assigns `lot.attached_pdfs = self._append_pdf_attachment(...)`. Immediately BEFORE that line, capture the previous value; immediately AFTER it, audit:

```python
        previous_attachments = list(lot.attached_pdfs or [])
        lot.attached_pdfs = self._append_pdf_attachment(...)  # existing line 579, unchanged
        self._audit_entity(
            db,
            table_name="lots",
            action=AuditAction.UPDATE,
            record_id=lot.id,
            old_values={"attached_pdfs": previous_attachments},
            new_values={"attached_pdfs": lot.attached_pdfs},
            user_id=user_id,
            reason="Result import: source PDF attached",
        )
```

(Keep the existing line 579 exactly as-is; only add the capture line before and the audit call after.)

(b) Awaiting-release pullback — `confirm()` lines 608-609 set `lot.status = LotStatus.UNDER_REVIEW` when the lot was `AWAITING_RELEASE`, *before* `calculate_lot_status()` runs (line 611). The subsequent `_apply_lot_status_calculation` audits `UNDER_REVIEW → final`, so the `AWAITING_RELEASE → UNDER_REVIEW` transition would otherwise be **lost** from the audit trail. Add an explicit audit inside the pullback branch:

```python
        if lot.status == LotStatus.AWAITING_RELEASE:
            lot.status = LotStatus.UNDER_REVIEW  # existing line 609, unchanged
            self._audit_entity(
                db,
                table_name="lots",
                action=AuditAction.UPDATE,
                record_id=lot.id,
                old_values={"status": LotStatus.AWAITING_RELEASE.value},
                new_values={"status": LotStatus.UNDER_REVIEW.value},
                user_id=user_id,
                reason="Result import: lot pulled back from release queue into review",
            )
```

(`LotStatus` is already imported in this module — the pullback branch references it today. This audit and the later recalc audit are complementary: together they record the full `awaiting_release → under_review → <final>` chain.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_result_import_service.py -k "confirm_audits" -v --no-cov`
Expected: PASS (3 passed).

- [ ] **Step 7: Run the full importer suite to confirm no regressions**

Run: `cd backend && .venv/bin/python -m pytest tests/test_result_import_service.py -v --no-cov`
Expected: PASS (all prior tests + the 3 new ones).

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/result_import_service.py backend/tests/test_result_import_service.py
git commit -m "feat: audit created/replaced results and PDF attach in importer confirm"
```

---

### Task 3: Audit the revert path (Finding #2)

**Files:**
- Modify: `backend/app/services/result_import_service.py` — `revert()` (~lines 625-718): created-result deletion (~668), updated-result restore (~684-687), PDF detach (~692-696), status→REVERTED (~705-706)
- Test: `backend/tests/test_result_import_service.py`

**Interfaces:**
- Consumes: `_audit_entity(...)` (Task 1), `_result_snapshot(result)` (existing), ledger entries `entry["old"]` / `entry["new"]` (existing snapshots in `ledger.updated_results`).
- Produces: `test_results` DELETE audits (per removed created result), `test_results` UPDATE audits (per restored updated result), one `lots` UPDATE audit (PDF detach), and one `result_imports` UPDATE audit (the revert event) — all before the existing `db.commit()` at line 712.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_result_import_service.py`:

```python
from app.models import UserRole


def test_revert_audits_deletes_and_revert_event(test_db, sample_lot, sample_user):
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/coa-revert.pdf",
        file_hash="hash-revert-audit",
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        extracted_data={
            "rows": [
                {"row_id": "row-1", "test_name": "Total Plate Count", "result_value": "Negative"}
            ]
        },
        uploaded_by_id=sample_user.id,
    )
    test_db.add(import_row)
    test_db.commit()

    service = ResultImportService()
    result = service.confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="apply")],
        sample_user.id,
    )
    created_id = result["created_result_ids"][0]

    service.revert(test_db, import_row.id, sample_user.id, UserRole.QC_MANAGER)

    delete_entry = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "test_results",
            AuditLog.record_id == created_id,
            AuditLog.action == AuditAction.DELETE,
        )
        .first()
    )
    assert delete_entry is not None
    assert delete_entry.reason  # DELETE audits require a reason

    revert_event = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "result_imports",
            AuditLog.record_id == import_row.id,
            AuditLog.action == AuditAction.UPDATE,
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert revert_event is not None
    assert revert_event.get_new_values_dict().get("status") == "reverted"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_result_import_service.py::test_revert_audits_deletes_and_revert_event -v --no-cov`
Expected: FAIL — `delete_entry is None` (revert writes no audit today).

- [ ] **Step 3: Audit created-result deletions**

In `revert()`, the created-result loop reaches `db.delete(result)` at ~line 668 after the DRAFT/unchanged guards. Immediately BEFORE `db.delete(result)`, add:

```python
            self._audit_entity(
                db,
                table_name="test_results",
                action=AuditAction.DELETE,
                record_id=result.id,
                old_values=self._result_snapshot(result),
                user_id=user_id,
                reason="Result import reverted: draft result removed",
            )
            db.delete(result)  # existing line ~668, unchanged
```

- [ ] **Step 4: Audit restored (updated) results**

In `revert()`, the updated-result loop restores old values via `setattr(...)` at ~lines 684-687. After the restore loop for each `entry`/`result` completes (right after the last `setattr`), add:

```python
            self._audit_entity(
                db,
                table_name="test_results",
                action=AuditAction.UPDATE,
                record_id=result.id,
                old_values=entry["new"],
                new_values=entry["old"],
                user_id=user_id,
                reason="Result import reverted: draft value restored",
            )
```

(`entry["old"]` / `entry["new"]` are the ledger snapshots already used by the guards above. The audit's `old_values` is the post-confirm state being undone; `new_values` is the restored pre-import state.)

- [ ] **Step 5: Audit the PDF detach**

In `revert()`, the PDF detach filters `lot.attached_pdfs` at ~lines 692-696. Capture the previous value before the filter assignment and audit after:

```python
            previous_attachments = list(lot.attached_pdfs or [])
            lot.attached_pdfs = [  # existing filter assignment ~692-696, unchanged
                ...
            ]
            self._audit_entity(
                db,
                table_name="lots",
                action=AuditAction.UPDATE,
                record_id=lot.id,
                old_values={"attached_pdfs": previous_attachments},
                new_values={"attached_pdfs": lot.attached_pdfs},
                user_id=user_id,
                reason="Result import reverted: source PDF detached",
            )
```

(Only add the capture line and the audit call; leave the existing filter assignment unchanged. Guard with the same `if lot:` context the detach already runs under.)

- [ ] **Step 6: Audit the revert event itself**

In `revert()`, the status is set at ~lines 705-706 (`item.status = ResultImportStatus.REVERTED`). Immediately after those lines, add:

```python
        self._audit_entity(
            db,
            table_name="result_imports",
            action=AuditAction.UPDATE,
            record_id=item.id,
            old_values={"status": ResultImportStatus.CONFIRMED.value},
            new_values={"status": ResultImportStatus.REVERTED.value},
            user_id=user_id,
            reason="Result import reverted",
        )
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_result_import_service.py::test_revert_audits_deletes_and_revert_event -v --no-cov`
Expected: PASS.

- [ ] **Step 8: Run the full importer suite**

Run: `cd backend && .venv/bin/python -m pytest tests/test_result_import_service.py -v --no-cov`
Expected: PASS (all tests).

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/result_import_service.py backend/tests/test_result_import_service.py
git commit -m "feat: audit revert (deletes, restores, PDF detach, revert event) in importer"
```

---

### Task 4: Audit the retry action (audit-trail completeness)

**Files:**
- Modify: `backend/app/services/result_import_service.py` — `retry()` (~lines 360-380)
- Modify: `backend/app/api/v1/endpoints/result_imports.py` — `retry_result_import` handler (~lines 121-132)
- Test: `backend/tests/test_result_import_service.py`

**Why:** `retry()` is a user action (endpoint gated `LabTechOrAbove`) that flips an import `FAILED`/stale → `PROCESSING` and commits, but writes no audit row — and its signature `retry(self, db, import_id)` doesn't even receive the actor. Upload, cancel, and confirm are all audited; retry is the lifecycle gap.

**Interfaces:**
- Consumes: `_audit_entity(...)` (Task 1).
- Produces: `retry(self, db, import_id, user_id: Optional[int] = None) -> ResultImport` (new `user_id` param, default `None` for backward-compat) + a `result_imports` UPDATE audit on re-queue.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_result_import_service.py`:

```python
def test_retry_audits_requeue(test_db, sample_user, tmp_path, monkeypatch):
    # A failed import whose stored PDF still exists.
    from app.services import result_import_service as ris

    monkeypatch.setattr(
        ris, "get_storage_service", lambda: type("S", (), {"exists": staticmethod(lambda key: True)})()
    )

    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/coa-retry.pdf",
        file_hash="hash-retry-audit",
        status=ResultImportStatus.FAILED,
        error_message="Failed to process PDF: boom",
        uploaded_by_id=sample_user.id,
    )
    test_db.add(import_row)
    test_db.commit()

    ResultImportService().retry(test_db, import_row.id, sample_user.id)

    entry = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "result_imports",
            AuditLog.record_id == import_row.id,
            AuditLog.action == AuditAction.UPDATE,
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert entry is not None
    assert entry.user_id == sample_user.id
    assert entry.get_new_values_dict().get("status") == "processing"
```

(Confirm the exact name `get_storage_service` and its module path while implementing; the monkeypatch target must match the symbol `retry()` actually calls.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_result_import_service.py::test_retry_audits_requeue -v --no-cov`
Expected: FAIL — `retry()` takes no `user_id` (TypeError) or no audit row exists.

- [ ] **Step 3: Add `user_id` to `retry()` and audit the re-queue**

Change the signature and add the audit immediately before the existing `db.commit()`:

```python
    def retry(
        self, db: Session, import_id: int, user_id: Optional[int] = None
    ) -> ResultImport:
        item = self.get(db, import_id)
        if not item:
            raise ValueError("Import not found")
        if item.status not in [
            ResultImportStatus.FAILED,
            ResultImportStatus.PROCESSING,
        ]:
            raise ValueError("Only failed or stale imports can be retried")
        if (
            item.status == ResultImportStatus.PROCESSING
            and item.updated_at > datetime.utcnow() - self.STALE_AFTER
        ):
            raise ValueError("Import is still processing")
        if not item.storage_key or not get_storage_service().exists(item.storage_key):
            raise ValueError("Stored PDF is no longer available")
        old_status = item.status.value
        item.status = ResultImportStatus.PROCESSING
        item.error_message = None
        self._audit_entity(
            db,
            table_name="result_imports",
            action=AuditAction.UPDATE,
            record_id=item.id,
            old_values={"status": old_status},
            new_values={"status": ResultImportStatus.PROCESSING.value},
            user_id=user_id,
            reason="Result import retried (re-queued from stored PDF)",
        )
        db.commit()
        db.refresh(item)
        return item
```

- [ ] **Step 4: Pass the actor from the endpoint**

In `backend/app/api/v1/endpoints/result_imports.py`, the `retry_result_import` handler already has `current_user: LabTechOrAbove`. Change the service call from `service.retry(db, import_id)` to:

```python
        item = service.retry(db, import_id, current_user.id)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_result_import_service.py::test_retry_audits_requeue -v --no-cov`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/result_import_service.py backend/app/api/v1/endpoints/result_imports.py backend/tests/test_result_import_service.py
git commit -m "feat: audit importer retry re-queue with actor attribution"
```

---

### Task 5: Gate `DELETE /uploads/{key}` to Lab Tech and up (Finding #3)

**Files:**
- Modify: `backend/app/api/v1/endpoints/uploads.py` — DELETE handler (lines 151-176), imports (line 12)
- Test: `backend/tests/test_result_import_endpoints.py` (create)

**Interfaces:**
- Consumes: `LabTechOrAbove` dependency from `app.dependencies` (defined `backend/app/dependencies.py:94-97`).
- Produces: `DELETE /api/v1/uploads/{filename}` now returns 403 for READ_ONLY users and logs a warning with actor + key.

**Decision (documented, not a task):** `GET /uploads/{key}` stays `CurrentUser` — the importer's PDF preview (`frontend/src/api/resultImports.ts:72`) and the Release source-PDF viewer both need broad read access, and PDFs are served `Content-Disposition: inline` (low risk). Only the destructive DELETE is tightened. A stricter `QCManagerOrAdmin` gate was considered but rejected because lab techs legitimately remove attachments; `LabTechOrAbove` closes the actual reported hole (READ_ONLY deletion).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_result_import_endpoints.py`:

```python
"""Endpoint auth tests for upload/importer routes."""

import pytest
from fastapi.testclient import TestClient

from app.database import Base
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import User
from app.models.enums import UserRole
from tests.test_api_endpoints import TestingSessionLocal, engine, override_get_db


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _make_user(db, role):
    user = User(username=f"u_{role.value}", email=f"{role.value}@x.com", role=role, active=True)
    user.set_password("pw12345678")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _client_as(user):
    app.dependency_overrides[get_db] = override_get_db

    async def _override_user():
        return user

    app.dependency_overrides[get_current_user] = _override_user
    return TestClient(app)


def test_delete_upload_forbidden_for_read_only(db):
    read_only = _make_user(db, UserRole.READ_ONLY)
    client = _client_as(read_only)
    try:
        resp = client.delete("/api/v1/uploads/pdfs/anything.pdf")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_delete_upload_allowed_for_lab_tech_returns_404_when_missing(db):
    lab_tech = _make_user(db, UserRole.LAB_TECH)
    client = _client_as(lab_tech)
    try:
        # Authorized past the role gate; file does not exist -> 404, not 403.
        resp = client.delete("/api/v1/uploads/pdfs/does-not-exist.pdf")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_result_import_endpoints.py -v --no-cov`
Expected: `test_delete_upload_forbidden_for_read_only` FAILS (currently returns 404, not 403, because there is no role gate).

- [ ] **Step 3: Update imports and the DELETE handler in `uploads.py`**

Change the import on line 12 from:

```python
from app.dependencies import DbSession, CurrentUser
```

to:

```python
import logging

from app.dependencies import CurrentUser, DbSession, LabTechOrAbove

logger = logging.getLogger(__name__)
```

(If `logging`/`logger` already exist at the top of the file, do not duplicate.)

Change the DELETE handler signature (lines 151-156) from `current_user: CurrentUser = None` to `current_user: LabTechOrAbove = None`, and add a warning log after the successful `storage.delete(storage_key)` call (~line 174):

```python
@router.delete("/{filename:path}")
async def delete_upload(
    filename: str,
    db: DbSession = None,
    current_user: LabTechOrAbove = None,
) -> dict:
    ...
    storage.delete(storage_key)  # existing ~line 174
    logger.warning(
        "Upload deleted: key=%s by user_id=%s",
        storage_key,
        getattr(current_user, "id", None),
    )
    return {"message": "File deleted successfully"}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_result_import_endpoints.py -v --no-cov`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/uploads.py backend/tests/test_result_import_endpoints.py
git commit -m "fix: gate DELETE /uploads to Lab Tech and up, log deletions"
```

---

### Task 6: Full-suite verification, format, lint

**Files:** none (verification only)

- [ ] **Step 1: Run the importer + uploads tests together**

Run: `cd backend && .venv/bin/python -m pytest tests/test_result_import_service.py tests/test_result_import_endpoints.py -v --no-cov`
Expected: PASS (all).

- [ ] **Step 2: Run the broader backend suite to catch regressions from the audit additions**

Run: `cd backend && .venv/bin/python -m pytest tests/ -q --no-cov -k "result_import or audit or upload or lot_service"`
Expected: PASS. If any pre-existing-but-unrelated import errors appear (e.g. legacy `test_result_service` module), note them but they are out of scope for this plan.

- [ ] **Step 3: Format and lint (from repo root)**

Run: `make format && make lint`
Expected: black/isort make no further changes to the touched files; flake8 reports no new errors in `result_import_service.py`, `uploads.py`, or the new test file.

- [ ] **Step 4: Commit any formatting-only changes**

```bash
git add -A
git commit -m "style: format importer audit/security changes" || echo "nothing to format"
```

---

## Self-Review

**Spec coverage (the three findings):**
- Finding #1 (lab-data writes unaudited) → Task 2 (INSERT for created/ad-hoc, UPDATE for replaced) + the `lots` PDF-attach audit + the awaiting-release pullback audit. Ad-hoc creation is distinguished via the audit `reason`. ✓
- Finding #2 (revert unaudited) → Task 3 (DELETE for removed created results, UPDATE for restored results, `lots` UPDATE for PDF detach, `result_imports` UPDATE for the revert event). ✓
- Finding #3 (uploads DELETE auth hole) → Task 5 (role gate `LabTechOrAbove` + deletion logging + 403 test). ✓
- Enabling infrastructure → Task 1 (`_audit_entity`, since `_log_audit` can't target `test_results`/`lots`). ✓

**Full audit-trail coverage check (every importer state mutation):**
| Event | Audited by | Status |
|---|---|---|
| Upload created | existing `_log_audit` (`create_uploads:173`) | pre-existing ✓ |
| Cancel | existing `_log_audit` (`cancel:396`) | pre-existing ✓ |
| Confirm: import status → confirmed | existing `_log_audit` (`confirm:598`) | pre-existing ✓ |
| Confirm: TestResult created / ad-hoc | Task 2 (INSERT) | added ✓ |
| Confirm: TestResult replaced | Task 2 (UPDATE, old/new) | added ✓ |
| Confirm: PDF attached to lot | Task 2 (`lots` UPDATE) | added ✓ |
| Confirm: awaiting_release → under_review pullback | Task 2 (`lots` UPDATE) | added ✓ |
| Confirm/revert: final lot status recalc | existing `_apply_lot_status_calculation` | pre-existing ✓ |
| Confirm: retest completion | existing `retest_service` audit | pre-existing ✓ |
| Revert: created results deleted | Task 3 (DELETE) | added ✓ |
| Revert: updated results restored | Task 3 (UPDATE) | added ✓ |
| Revert: PDF detached | Task 3 (`lots` UPDATE) | added ✓ |
| Revert: import status → reverted | Task 3 (`result_imports` UPDATE) | added ✓ |
| Retry: failed/stale → processing | Task 4 (`result_imports` UPDATE, actor) | added ✓ |
| DELETE /uploads | logged warning (Task 5); no DB row (storage op, no DB record id) | logged ✓ |

**Deliberately NOT audited (documented exclusions — system events, no human actor, no applied lab-data change):**
- `reap_stale_processing` (background timeout sweep, PROCESSING→FAILED) — housekeeping, no actor; the user can still retry, which *is* audited.
- Worker `process_import` status flips (PROCESSING→NEEDS_CONFIRMATION/FAILED) — automated extraction outcome; nothing is yet applied to a lot. Operational logging, not audit-trail.

**Constraint compliance:** all audit calls are placed before the operation's existing `db.commit()` (confirm line 615, revert line 712, retry's commit); DELETE-action audits always pass `reason`; failures are swallowed via the helper's try/except; no `REVERT` enum used (UPDATE/DELETE only). ✓

**Type/name consistency:** `_audit_entity` signature, `_result_snapshot`, ledger `entry["old"]`/`entry["new"]`, and `LabTechOrAbove` are referenced identically across tasks and match the grounded source (`result_import_service.py:1156`, `dependencies.py:94-97`). ✓

**Out of scope (deferred, not in this plan):** PDF magic-byte validation + parse timeout (Finding #4), dedup TOCTOU unique-index (Finding #5), and the OpenRouter data-egress compliance question (Finding #6). The "failed imports retain PDFs" deviation is an accepted design choice (enables retry-from-stored-PDF) and is documented separately; it is not changed here.
