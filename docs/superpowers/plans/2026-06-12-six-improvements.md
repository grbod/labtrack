# Six Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the ad-hoc test feature, archive/re-download chain of custody PDFs with 7-day post-terminal retention, add Reject + Return for Review to the Release Queue, add tab autoscroll + sticky submit on Create Sample, differentiate Create Sample sections visually, and ship a Kanagawa Dragon dark mode.

**Architecture:** Backend follows the existing model → schema → service → endpoint layering (FastAPI + SQLAlchemy + Alembic). Frontend follows types → api → hooks → components (React + TanStack Query + Tailwind v4). Dark mode uses Tailwind v4's CSS-variable palette: a `.dark` scope remaps the default color variables (`--color-slate-*`, `--color-white`, etc.) to the Kanagawa Dragon palette, so existing hardcoded classes theme automatically; a page-by-page audit fixes stragglers before the toggle ships.

**Tech Stack:** Python 3.10/FastAPI/SQLAlchemy/Alembic/pytest; React/TypeScript/Vite/Tailwind v4/TanStack Query/Vitest.

**Spec:** `docs/superpowers/specs/2026-06-12-six-improvements-design.md`

**Commands cheat-sheet** (run from repo root unless noted):
- Backend tests: `cd backend && .venv/bin/python -m pytest tests/<file> -v --no-cov`
- New migration: `cd backend && .venv/bin/python -m alembic revision -m "<msg>"` (then fill in; `down_revision` must point at `t1u2v3w4x5y6`, or the latest at execution time — check `ls backend/migrations/versions/`)
- Apply migrations: `cd backend && .venv/bin/python -m alembic upgrade head`
- Frontend type check + build: `cd frontend && npm run build`
- Frontend tests: `cd frontend && npm run test:run`

---

## Feature 1: Fix Ad-hoc Additional Tests

### Task 1: TestResult model + migration: `lab_test_type_id`, `include_on_coa`

**Files:**
- Modify: `backend/app/models/test_result.py`
- Create: `backend/migrations/versions/u1v2w3x4y5z6_add_test_result_adhoc_fields.py`
- Modify: `backend/app/schemas/test_result.py`

- [ ] **Step 1: Add columns to the model**

In `backend/app/models/test_result.py`, after the `method` column (line ~60):

```python
    # Ad-hoc test support
    lab_test_type_id = Column(
        Integer, ForeignKey("lab_test_types.id"), nullable=True
    )
    include_on_coa = Column(Boolean, default=True, nullable=False)
```

Add `Boolean` to the existing `sqlalchemy` import list at the top of the file.

- [ ] **Step 2: Create the Alembic migration**

Create `backend/migrations/versions/u1v2w3x4y5z6_add_test_result_adhoc_fields.py`:

```python
"""Add lab_test_type_id and include_on_coa to test_results

Revision ID: u1v2w3x4y5z6
Revises: t1u2v3w4x5y6
"""

import sqlalchemy as sa
from alembic import op

revision = "u1v2w3x4y5z6"
down_revision = "t1u2v3w4x5y6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("test_results") as batch_op:
        batch_op.add_column(
            sa.Column("lab_test_type_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "include_on_coa",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.create_foreign_key(
            "fk_test_results_lab_test_type_id",
            "lab_test_types",
            ["lab_test_type_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("test_results") as batch_op:
        batch_op.drop_constraint(
            "fk_test_results_lab_test_type_id", type_="foreignkey"
        )
        batch_op.drop_column("include_on_coa")
        batch_op.drop_column("lab_test_type_id")
```

NOTE: SQLite requires `batch_alter_table` for FK changes. Check `ls backend/migrations/versions/` first — if a newer head exists, point `down_revision` at it.

- [ ] **Step 3: Update schemas**

In `backend/app/schemas/test_result.py`, add to `TestResultBase` (after `notes`):

```python
    lab_test_type_id: Optional[int] = None
    include_on_coa: bool = True
```

Add to `TestResultUpdate`:

```python
    include_on_coa: Optional[bool] = None
```

Confirm `TestResultResponse` includes both new fields (it should inherit or list fields explicitly — if explicit, add `lab_test_type_id: Optional[int]` and `include_on_coa: bool`).

- [ ] **Step 4: Apply migration and run existing tests**

Run: `cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m pytest tests/test_api_endpoints.py -v --no-cov -x -q`
Expected: migration applies; existing tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/test_result.py backend/migrations/versions/u1v2w3x4y5z6_add_test_result_adhoc_fields.py backend/app/schemas/test_result.py
git commit -m "feat: add lab_test_type_id and include_on_coa to test results"
```

### Task 2: Shared specification matcher utility

The pass/fail matching logic lives in `ProductTestSpecification.matches_result` (`backend/app/models/product_test_spec.py:108`). Ad-hoc tests have no ProductTestSpecification — they carry their own `specification` string — so extract the logic into a reusable function and delegate.

**Files:**
- Create: `backend/app/utils/spec_matcher.py`
- Modify: `backend/app/models/product_test_spec.py`
- Test: `backend/tests/test_spec_matcher.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_spec_matcher.py`:

```python
"""Tests for the shared specification matcher."""

from app.utils.spec_matcher import specification_matches


class TestSpecificationMatches:
    def test_negative_spec_accepts_negative(self):
        assert specification_matches("Negative", None, "Negative") is True

    def test_negative_spec_rejects_positive(self):
        assert specification_matches("Negative", None, "Positive") is False

    def test_less_than_spec_passes_lower_value(self):
        assert specification_matches("< 10,000 CFU/g", "CFU/g", "5000") is True

    def test_less_than_spec_fails_higher_value(self):
        assert specification_matches("< 10,000 CFU/g", "CFU/g", "20000") is False

    def test_empty_result_fails(self):
        assert specification_matches("< 10", None, "") is False

    def test_no_specification_passes_anything(self):
        # Ad-hoc tests may have no spec; any entered result counts as passing
        assert specification_matches(None, None, "whatever") is True
        assert specification_matches("", None, "whatever") is True
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_spec_matcher.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: app.utils.spec_matcher`

- [ ] **Step 3: Extract the matcher**

Create `backend/app/utils/spec_matcher.py`. Move the **body** of `ProductTestSpecification.matches_result` (and the `NEGATIVE_ACCEPTED_VALUES` / `POSITIVE_ACCEPTED_VALUES` constants it uses) into:

```python
"""Shared test-result-vs-specification matching logic."""

NEGATIVE_ACCEPTED_VALUES = ...  # moved verbatim from ProductTestSpecification
POSITIVE_ACCEPTED_VALUES = ...  # moved verbatim from ProductTestSpecification


def specification_matches(specification, test_unit, result_value) -> bool:
    """Return True if result_value satisfies the specification string."""
    if specification is None or not str(specification).strip():
        return True  # no spec to enforce
    if not result_value:
        return False
    spec = str(specification).strip().lower()
    value = str(result_value).strip().lower()
    # ... remainder of matches_result body, with `self.specification` -> spec,
    #     `self.test_unit` -> test_unit, and class constants -> module constants
```

Copy the existing logic faithfully — do not redesign it. Then in `backend/app/models/product_test_spec.py` replace the body of `matches_result` with:

```python
    def matches_result(self, result_value):
        from app.utils.spec_matcher import specification_matches

        return specification_matches(self.specification, self.test_unit, result_value)
```

Keep the class constants as aliases if other code references them (grep first: `grep -rn "NEGATIVE_ACCEPTED_VALUES\|POSITIVE_ACCEPTED_VALUES" backend/app backend/tests`).

- [ ] **Step 4: Run new tests + the existing spec-matching tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_spec_matcher.py tests/test_lot_with_specs.py -v --no-cov`
Expected: PASS (existing product-spec behavior unchanged)

- [ ] **Step 5: Commit**

```bash
git add backend/app/utils/spec_matcher.py backend/app/models/product_test_spec.py backend/tests/test_spec_matcher.py
git commit -m "refactor: extract shared specification matcher for ad-hoc tests"
```

### Task 3: Ad-hoc tests become binding in lot status calculation

`LotService.calculate_lot_status` (`backend/app/services/lot_service.py:497-612`) only looks at product required specs. Ad-hoc tests (TestResults whose `test_type` is not a required spec) must also gate the workflow: empty result ⇒ treat like a missing test (cannot reach UNDER_REVIEW); entered result failing its own `specification` ⇒ NEEDS_ATTENTION.

**Files:**
- Modify: `backend/app/services/lot_service.py:497-612`
- Test: `backend/tests/test_adhoc_test_binding.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_adhoc_test_binding.py` (use existing fixtures from `backend/tests/conftest.py` — check how `test_lot_with_specs.py` builds a lot with a product + specs and reuse that pattern):

```python
"""Ad-hoc tests gate lot status like required tests."""

import pytest
from app.models.enums import LotStatus
from app.models.test_result import TestResult
from app.services.lot_service import LotService

# Reuse/adapt the lot-with-specs fixture pattern from tests/test_lot_with_specs.py:
# a lot whose product has required specs, with all required results entered & passing.


def _add_adhoc(db, lot, result_value, specification="< 10"):
    tr = TestResult(
        lot_id=lot.id,
        test_type="Ad Hoc Lead",
        result_value=result_value,
        specification=specification,
        lab_test_type_id=None,
    )
    db.add(tr)
    db.commit()
    return tr


def test_adhoc_without_result_blocks_under_review(db, lot_all_required_passing):
    _add_adhoc(db, lot_all_required_passing, result_value=None)
    calc = LotService().calculate_lot_status(db, lot_all_required_passing)
    assert calc.new_status == LotStatus.PARTIAL_RESULTS


def test_adhoc_failing_spec_sends_needs_attention(db, lot_all_required_passing):
    _add_adhoc(db, lot_all_required_passing, result_value="50", specification="< 10")
    calc = LotService().calculate_lot_status(db, lot_all_required_passing)
    assert calc.new_status == LotStatus.NEEDS_ATTENTION


def test_adhoc_passing_spec_allows_under_review(db, lot_all_required_passing):
    _add_adhoc(db, lot_all_required_passing, result_value="5", specification="< 10")
    calc = LotService().calculate_lot_status(db, lot_all_required_passing)
    assert calc.new_status == LotStatus.UNDER_REVIEW
```

Adapt fixture names to what conftest actually provides; if no suitable fixture exists, build the lot inline the way `test_lot_with_specs.py` does.

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_adhoc_test_binding.py -v --no-cov`
Expected: FAIL (ad-hoc tests currently ignored, all three return UNDER_REVIEW or wrong status)

- [ ] **Step 3: Implement in calculate_lot_status**

In `backend/app/services/lot_service.py`, after `failing_tests` is computed (line ~561), add ad-hoc evaluation:

```python
        from app.utils.spec_matcher import specification_matches

        # Ad-hoc tests (not part of required product specs) are binding too:
        # empty result blocks review; failing own spec flags the lot.
        adhoc_results = [
            r for r in test_results if r.test_type not in required_specs
        ]
        adhoc_missing = [
            r.test_type
            for r in adhoc_results
            if r.result_value is None or not str(r.result_value).strip()
        ]
        adhoc_failing = [
            r.test_type
            for r in adhoc_results
            if r.test_type not in adhoc_missing
            and not specification_matches(r.specification, r.unit, r.result_value)
        ]
        missing_tests = missing_tests + adhoc_missing
        failing_tests = failing_tests + adhoc_failing
```

Then update the completeness checks that follow to use the combined lists. The existing logic computes `completed_required = len(required_specs) - len(missing_tests)` — with ad-hoc tests folded in, change the two branch conditions to:

```python
        total_required = len(required_specs) + len(adhoc_results)
        completed_required = total_required - len(missing_tests)
```

(keeping the `completed_required == 0` ⇒ AWAITING_RESULTS, `< total_required` ⇒ PARTIAL_RESULTS/NEEDS_ATTENTION-hold, `failing_tests` ⇒ NEEDS_ATTENTION, else UNDER_REVIEW structure intact). Also handle the `not required_specs` early-return branch (line ~532): when there are no required specs but ad-hoc tests exist, fall through to the main logic instead of returning UNDER_REVIEW immediately — move the early return so it only triggers when there are neither required specs nor any test results with the new gating applied. Simplest correct restructure: when `not required_specs and adhoc results exist`, skip the early return and let the combined logic run with `required_specs = {}`.

- [ ] **Step 4: Run new + regression tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_adhoc_test_binding.py tests/test_lot_with_specs.py tests/test_lot_service.py -v --no-cov`
Expected: PASS. If `test_lot_service.py` has cases asserting "extra results don't affect status", update them to the new intended behavior (they describe the old bug).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/lot_service.py backend/tests/test_adhoc_test_binding.py
git commit -m "feat: ad-hoc tests gate lot status (block review when empty, flag on fail)"
```

### Task 4: COA respects include_on_coa

**Files:**
- Modify: `backend/app/api/v1/endpoints/release.py:823-832`
- Test: `backend/tests/test_deployment_fixes.py` or the existing release/COA test file (find with `grep -rln "coa-data\|COATestResult" backend/tests`)

- [ ] **Step 1: Write failing test**

In the test file that already exercises the COA data endpoint (find it; if none covers the test list, add to `backend/tests/test_adhoc_test_binding.py`):

```python
def test_excluded_adhoc_test_not_on_coa(db, client, released_lot_fixture):
    # Add an ad-hoc result excluded from the COA
    tr = TestResult(
        lot_id=released_lot_fixture.id,
        test_type="Internal Investigation",
        result_value="ok",
        include_on_coa=False,
    )
    db.add(tr)
    db.commit()
    resp = client.get(f"/api/v1/release/{released_lot_fixture.id}/{product_id}/coa-data", headers=auth_headers)
    names = [t["name"] for t in resp.json()["tests"]]
    assert "Internal Investigation" not in names
```

Adapt the route path/fixtures to the actual COA-data endpoint signature found in `release.py` (~line 800, the function containing the query at 823).

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/bin/python -m pytest <chosen test file> -v --no-cov -k excluded_adhoc`
Expected: FAIL — excluded test appears in the COA list.

- [ ] **Step 3: Add the filter**

In `backend/app/api/v1/endpoints/release.py` (the query at lines 824-832), add one filter line:

```python
    test_results = (
        db.query(TestResult)
        .filter(
            TestResult.lot_id == lot_id,
            TestResult.result_value.isnot(None),
            TestResult.result_value != "",
            TestResult.include_on_coa.is_(True),
        )
        .all()
    )
```

Check for other COA data assembly paths: `grep -rn "TestResult.lot_id ==" backend/app/api/v1/endpoints/release.py backend/app/services/coa_generation_service.py backend/app/services/coa_generator_service.py` and apply the same filter anywhere results are collected for a customer-facing COA (NOT for internal views or the sample modal).

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/bin/python -m pytest <chosen test file> -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/release.py backend/tests/
git commit -m "feat: respect include_on_coa when assembling COA test results"
```

### Task 5: Frontend — fix dropdown clipping, autofill, COA toggle, guarded delete

**Files:**
- Modify: `frontend/src/components/domain/SampleModal/AdditionalTestsAccordion.tsx`
- Modify: `frontend/src/components/domain/SampleModal/index.tsx:514-530`
- Modify: `frontend/src/types/index.ts:149-169` (TestResult), `frontend/src/api/testResults.ts` (create/update payload types)
- Test: `frontend/src/components/domain/SampleModal/AdditionalTestsAccordion.test.tsx`

- [ ] **Step 1: Write failing component test**

Create `frontend/src/components/domain/SampleModal/AdditionalTestsAccordion.test.tsx` (follow the patterns in `PassFailBadge.test.tsx` / `FilterPills.test.tsx`):

```tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { AdditionalTestsAccordion } from "./AdditionalTestsAccordion"
import type { LabTestType } from "@/types"

const labTestTypes = [
  {
    id: 7,
    test_name: "Organoleptic Evaluation",
    test_category: "Organoleptic",
    default_unit: "n/a",
    test_method: "In-house",
    default_specification: "Conforms",
  },
] as LabTestType[]

describe("AdditionalTestsAccordion", () => {
  it("shows matching test types in dropdown and adds with id", async () => {
    const onAddTest = vi.fn().mockResolvedValue(undefined)
    render(
      <AdditionalTestsAccordion
        additionalTests={[]}
        labTestTypes={labTestTypes}
        onUpdateResult={vi.fn()}
        onAddTest={onAddTest}
      />
    )
    fireEvent.click(screen.getByText(/Additional Tests/))
    fireEvent.click(screen.getByText("Add Test"))
    fireEvent.change(screen.getByPlaceholderText("Search test types..."), {
      target: { value: "organolep" },
    })
    const option = await screen.findByText("Organoleptic Evaluation")
    fireEvent.click(option)
    expect(onAddTest).toHaveBeenCalledWith("Organoleptic Evaluation", 7)
  })
})
```

- [ ] **Step 2: Run to check current state**

Run: `cd frontend && npm run test:run -- AdditionalTestsAccordion`
This may PASS in jsdom (clipping is a CSS bug invisible to jsdom). Either way it pins the contract `onAddTest(name, id)`.

- [ ] **Step 3: Fix the dropdown clipping**

In `AdditionalTestsAccordion.tsx:113`, the wrapper `overflow-hidden` clips the absolutely-positioned dropdown. Change:

```tsx
<div className="border border-t-0 border-slate-200 rounded-b-lg overflow-hidden">
```

to:

```tsx
<div className="border border-t-0 border-slate-200 rounded-b-lg">
```

and add `rounded-b-lg overflow-hidden` to the inner table wrapper (`<div className="relative">` at line 116 → `<div className="relative overflow-hidden rounded-b-lg">`) so the table corners stay clipped while the add-row dropdown can overflow. Verify visually later in Step 7.

- [ ] **Step 4: Fix handleAddTest to use the test type and autofill**

In `frontend/src/components/domain/SampleModal/index.tsx`, replace `handleAddTest` (lines 514-530):

```tsx
  // Handle adding a new ad-hoc test (autofills from the LabTestType definition)
  const handleAddTest = useCallback(
    async (testName: string, labTestTypeId: number) => {
      if (!lot) return
      const labTestType = labTestTypesData?.items.find((lt) => lt.id === labTestTypeId)
      try {
        await createTestResultMutation.mutateAsync({
          lot_id: lot.id,
          test_type: testName,
          lab_test_type_id: labTestTypeId,
          unit: labTestType?.default_unit ?? undefined,
          specification: labTestType?.default_specification ?? undefined,
          method: labTestType?.test_method ?? undefined,
          include_on_coa: true,
        })
        toast.success("Test added")
        queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
        if (lot) {
          await queryClient.refetchQueries({ queryKey: lotKeys.detailWithSpecs(lot.id) })
        }
      } catch {
        toast.error("Failed to add test")
      }
    },
    [lot, createTestResultMutation, labTestTypesData, queryClient]
  )
```

Update the dependency array and add `lab_test_type_id` / `include_on_coa` to the create payload type in `frontend/src/api/testResults.ts` and the `TestResult` interface in `frontend/src/types/index.ts` (`lab_test_type_id: number | null`, `include_on_coa: boolean`).

- [ ] **Step 5: Include-on-COA toggle + delete-only-when-empty**

In `AdditionalTestsAccordion.tsx`, the per-row overlay (lines 124-143) currently always shows Trash. Change to show, per test row:
- A small toggle (use existing `Checkbox` from `@/components/ui/checkbox` with title "Include on COA") bound to `test.include_on_coa`, calling `onUpdateResult(test.id, "include_on_coa", String(!test.include_on_coa))` — but since `onUpdateResult` sends string values, add a dedicated prop instead: `onToggleCoa?: (id: number, include: boolean) => Promise<void>` wired in `index.tsx` to `updateTestResultMutation.mutateAsync({ id, data: { include_on_coa: include } })`.
- The Trash button ONLY when `!test.result_value?.trim()` (removable while no result, per spec).

```tsx
{additionalTests.map((test) => (
  <div key={test.id} className="h-[41px] flex items-center gap-1 pr-2">
    {onToggleCoa && (
      <Checkbox
        checked={test.include_on_coa}
        onCheckedChange={(v) => onToggleCoa(test.id, v === true)}
        title="Include on COA"
      />
    )}
    {!test.result_value?.trim() && onDeleteResult && (
      <button ... existing trash button ... />
    )}
  </div>
))}
```

- [ ] **Step 6: Build + tests**

Run: `cd frontend && npm run build && npm run test:run -- AdditionalTestsAccordion`
Expected: type check passes, tests pass.

- [ ] **Step 7: Manual verify in the running app**

Start backend + frontend per CLAUDE.md. Open a sample in Sample Tracker → Additional Tests → Add Test → type "organo". Expected: dropdown appears with matching tests; selecting adds a row with spec/unit/method prefilled; checkbox ON; trash only on empty rows.

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "fix: ad-hoc test autocomplete dropdown, autofill from test type, COA toggle"
```

---

## Feature 2: Chain of Custody Archive + Re-download

### Task 6: Lot model + migration: `coc_storage_key`

**Files:**
- Modify: `backend/app/models/lot.py` (after `daane_po_number`, line 52)
- Create: `backend/migrations/versions/v1w2x3y4z5a6_add_lot_coc_storage_key.py`
- Modify: `backend/app/schemas/lot.py` (LotResponse), `frontend/src/types/index.ts` (Lot interface)

- [ ] **Step 1: Model + migration + schema**

Model:
```python
    coc_storage_key = Column(String(255), nullable=True)  # Archived COC PDF
```

Migration (down_revision = `u1v2w3x4y5z6`):
```python
def upgrade() -> None:
    op.add_column("lots", sa.Column("coc_storage_key", sa.String(255), nullable=True))

def downgrade() -> None:
    op.drop_column("lots", "coc_storage_key")
```

Add `coc_storage_key: Optional[str] = None` to `LotResponse` in `backend/app/schemas/lot.py`, and `coc_storage_key: string | null` to `Lot` in `frontend/src/types/index.ts`.

- [ ] **Step 2: Apply + sanity test + commit**

Run: `cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m pytest tests/test_api_endpoints.py -q --no-cov -x`

```bash
git add backend/app/models/lot.py backend/migrations/versions/v1w2x3y4z5a6_add_lot_coc_storage_key.py backend/app/schemas/lot.py frontend/src/types/index.ts
git commit -m "feat: add coc_storage_key to lots"
```

### Task 7: Archive COC PDF on generation; re-download endpoint

Every explicit COC PDF generation (`GET /lots/{lot_id}/daane-coc/pdf`, used by the Create Sample success screen) overwrites the archive — the last explicitly generated COC is "what was sent to the lab". The new re-download endpoint NEVER regenerates for terminal lots; for active lots with no archive yet (pre-feature lots) it generates once with defaults and archives.

**Files:**
- Modify: `backend/app/api/v1/endpoints/lots.py:521-566` (daane-coc/pdf endpoint)
- Modify: same file — new endpoint `GET /lots/{lot_id}/coc-archive`
- Test: `backend/tests/test_coc_archive.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_coc_archive.py` (reuse client/auth fixtures from `tests/test_api_endpoints.py`; the storage backend in tests is local — files land under the configured storage dir):

```python
"""COC archive: generation archives, re-download serves archive."""


def test_coc_pdf_generation_archives(client, auth_headers, lot_fixture, db):
    resp = client.get(f"/api/v1/lots/{lot_fixture.id}/daane-coc/pdf", headers=auth_headers)
    assert resp.status_code == 200
    db.refresh(lot_fixture)
    assert lot_fixture.coc_storage_key is not None


def test_coc_archive_download_serves_archived_bytes(client, auth_headers, lot_fixture, db):
    first = client.get(f"/api/v1/lots/{lot_fixture.id}/daane-coc/pdf", headers=auth_headers)
    archived = client.get(f"/api/v1/lots/{lot_fixture.id}/coc-archive", headers=auth_headers)
    assert archived.status_code == 200
    assert archived.content == first.content


def test_coc_archive_fallback_generates_for_active_lot(client, auth_headers, lot_fixture, db):
    # No prior generation: fallback generates + archives
    resp = client.get(f"/api/v1/lots/{lot_fixture.id}/coc-archive", headers=auth_headers)
    assert resp.status_code == 200
    db.refresh(lot_fixture)
    assert lot_fixture.coc_storage_key is not None


def test_coc_archive_404_for_terminal_lot_without_archive(client, auth_headers, released_lot_no_archive, db):
    resp = client.get(f"/api/v1/lots/{released_lot_no_archive.id}/coc-archive", headers=auth_headers)
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_coc_archive.py -v --no-cov`
Expected: FAIL (no archiving, endpoint 404s)

- [ ] **Step 3: Implement**

In `download_daane_coc_pdf` (lots.py:521), after `content, test_count = ...` succeeds:

```python
        # Archive: the most recent explicit generation is the COC of record
        from app.services.storage_service import get_storage_service

        storage = get_storage_service()
        key = f"coc/{lot.reference_number}.pdf"
        storage.upload(content, key, content_type="application/pdf")
        lot.coc_storage_key = key
        db.commit()
```

New endpoint in the same file:

```python
TERMINAL_LOT_STATUSES = [LotStatus.RELEASED, LotStatus.REJECTED]


@router.get("/{lot_id}/coc-archive")
async def download_coc_archive(
    lot_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Re-download the archived Chain of Custody PDF (immutable record)."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lot not found")

    from app.services.storage_service import get_storage_service

    storage = get_storage_service()

    if not lot.coc_storage_key or not storage.exists(lot.coc_storage_key):
        if lot.status in TERMINAL_LOT_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chain of custody is no longer available for this lot",
            )
        # Pre-feature lot still in flight: generate once with defaults and archive
        content, _ = daane_coc_service.generate_coc_pdf_for_lot(db, lot_id, current_user)
        key = f"coc/{lot.reference_number}.pdf"
        storage.upload(content, key, content_type="application/pdf")
        lot.coc_storage_key = key
        db.commit()
    else:
        content = storage.download(lot.coc_storage_key)

    filename = f"daane-coc-{lot.reference_number}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 4: Run tests, fix fixture names against conftest reality**

Run: `cd backend && .venv/bin/python -m pytest tests/test_coc_archive.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/lots.py backend/tests/test_coc_archive.py
git commit -m "feat: archive COC PDF on generation, add re-download endpoint"
```

### Task 8: 7-day retention cleanup

**Files:**
- Modify: `backend/app/services/lot_service.py` (new method on LotService)
- Modify: `backend/app/main.py:20-26` (lifespan)
- Test: `backend/tests/test_coc_archive.py` (append)

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_coc_archive.py`:

```python
from datetime import datetime, timedelta


def test_cleanup_purges_old_terminal_lot_archives(db, released_lot_with_archive):
    from app.services.lot_service import LotService

    # Backdate beyond retention
    released_lot_with_archive.updated_at = datetime.utcnow() - timedelta(days=8)
    db.commit()
    purged = LotService().cleanup_expired_coc_archives(db)
    assert purged == 1
    db.refresh(released_lot_with_archive)
    assert released_lot_with_archive.coc_storage_key is None


def test_cleanup_keeps_recent_and_active_lots(db, released_lot_with_archive, active_lot_with_archive):
    from app.services.lot_service import LotService

    purged = LotService().cleanup_expired_coc_archives(db)  # both recent
    assert purged == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_coc_archive.py -v --no-cov -k cleanup`
Expected: FAIL (method missing)

- [ ] **Step 3: Implement service method + startup task**

In `LotService`:

```python
    COC_RETENTION_DAYS = 7

    def cleanup_expired_coc_archives(self, db: Session) -> int:
        """Delete archived COC PDFs for lots released/rejected > 7 days ago."""
        from app.services.storage_service import get_storage_service

        cutoff = datetime.utcnow() - timedelta(days=self.COC_RETENTION_DAYS)
        lots = (
            db.query(Lot)
            .filter(
                Lot.coc_storage_key.isnot(None),
                Lot.status.in_([LotStatus.RELEASED, LotStatus.REJECTED]),
                Lot.updated_at < cutoff,
            )
            .all()
        )
        storage = get_storage_service()
        purged = 0
        for lot in lots:
            try:
                storage.delete(lot.coc_storage_key)
            except Exception:
                logger.warning("Failed to delete COC archive {}", lot.coc_storage_key)
            lot.coc_storage_key = None
            purged += 1
        if purged:
            db.commit()
            logger.info("Purged {} expired COC archives", purged)
        return purged
```

(`datetime`/`timedelta` are already imported in lot_service.py — verify; `timedelta` is imported at the bottom, line 725; move it to the top imports.)

In `backend/app/main.py` lifespan, run at startup + daily:

```python
import asyncio


async def _coc_cleanup_loop():
    from app.database import SessionLocal
    from app.services.lot_service import LotService

    while True:
        try:
            db = SessionLocal()
            try:
                LotService().cleanup_expired_coc_archives(db)
            finally:
                db.close()
        except Exception:
            logger.exception("COC archive cleanup failed")
        await asyncio.sleep(24 * 60 * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    cleanup_task = asyncio.create_task(_coc_cleanup_loop())
    yield
    cleanup_task.cancel()
```

(Check the actual session factory name in `app/database.py` — adjust `SessionLocal` import to match.)

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_coc_archive.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/lot_service.py backend/app/main.py backend/tests/test_coc_archive.py
git commit -m "feat: purge COC archives 7 days after lot release/rejection"
```

### Task 9: Frontend — Download Chain of Custody button in sample modal

**Files:**
- Modify: `frontend/src/api/daaneCoc.ts` (new `downloadCocArchive`)
- Modify: `frontend/src/hooks/useDaaneCoc.ts` (new hook)
- Modify: `frontend/src/components/domain/SampleModal/index.tsx` (button near "Send for Retest" in the footer, line region ~1090-1110 — locate the footer with `grep -n "Send for Retest" index.tsx`)

- [ ] **Step 1: API + hook**

`frontend/src/api/daaneCoc.ts`:

```typescript
  downloadCocArchive: async (lotId: number): Promise<{ blob: Blob; filename: string }> => {
    const response = await api.get(`/lots/${lotId}/coc-archive`, { responseType: "blob" })
    const contentDisposition = response.headers["content-disposition"]
    let filename = `daane-coc-${lotId}.pdf`
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?([^";\n]+)"?/)
      if (match?.[1]) filename = match[1]
    }
    return { blob: response.data, filename }
  },
```

`frontend/src/hooks/useDaaneCoc.ts` — follow the existing mutation pattern in that file (it triggers a browser download from a blob); add `useDownloadCocArchive` wrapping `daaneCocApi.downloadCocArchive` with an error toast: `"Chain of custody not available"` on 404.

- [ ] **Step 2: Button in the modal footer**

In `SampleModal/index.tsx` footer (next to "Send for Retest"), render when the archive can exist:

```tsx
{lot && !(["released", "rejected"].includes(lot.status) && !lot.coc_storage_key) && (
  <Button
    variant="outline"
    size="sm"
    onClick={() => downloadCocArchive.mutate(lot.id)}
    disabled={downloadCocArchive.isPending}
  >
    {downloadCocArchive.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileDown className="h-4 w-4" />}
    Chain of Custody
  </Button>
)}
```

(`FileDown` from lucide-react; the field `coc_storage_key` was added to the Lot type in Task 6. The modal's lot comes from `detailWithSpecs` — confirm that response includes the field; it inherits from LotResponse so it should.)

- [ ] **Step 3: Build + manual verify + commit**

Run: `cd frontend && npm run build`
Manual: open a sample → click "Chain of Custody" → PDF downloads.

```bash
git add frontend/src
git commit -m "feat: chain of custody re-download from sample modal"
```

---

## Feature 3: Release Queue — Reject + Return for Review

### Task 10: Lot model — return fields + transition + status-calc hold

**Files:**
- Modify: `backend/app/models/lot.py` (fields ~line 52, transitions 125-134)
- Create: `backend/migrations/versions/w1x2y3z4a5b6_add_lot_return_fields.py` (down_revision `v1w2x3y4z5a6`)
- Modify: `backend/app/services/lot_service.py` (calculate_lot_status)
- Test: `backend/tests/test_return_for_review.py`

- [ ] **Step 1: Write failing tests**

```python
"""Return for Review: transitions, status-calc hold."""

import pytest
from app.models.enums import LotStatus
from app.models.lot import Lot
from app.services.lot_service import LotService


def test_awaiting_release_can_return_to_needs_attention(db, awaiting_release_lot):
    awaiting_release_lot.update_status(LotStatus.NEEDS_ATTENTION)
    assert awaiting_release_lot.status == LotStatus.NEEDS_ATTENTION


def test_returned_lot_holds_needs_attention_despite_passing_tests(db, awaiting_release_lot):
    awaiting_release_lot.update_status(LotStatus.NEEDS_ATTENTION)
    awaiting_release_lot.return_reason = "Wrong lot number on COC"
    awaiting_release_lot.return_response_note = None
    db.commit()
    calc = LotService().calculate_lot_status(db, awaiting_release_lot)
    assert calc.new_status == LotStatus.NEEDS_ATTENTION


def test_resolved_return_recalculates_normally(db, awaiting_release_lot):
    awaiting_release_lot.update_status(LotStatus.NEEDS_ATTENTION)
    awaiting_release_lot.return_reason = "Wrong lot number on COC"
    awaiting_release_lot.return_response_note = "Data entry mistake, corrected"
    db.commit()
    calc = LotService().calculate_lot_status(db, awaiting_release_lot)
    assert calc.new_status == LotStatus.UNDER_REVIEW  # all tests passing fixture
```

(`awaiting_release_lot`: a lot in AWAITING_RELEASE whose required tests all pass — adapt from existing fixtures.)

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_return_for_review.py -v --no-cov`
Expected: FAIL — `Invalid status transition from awaiting_release to needs_attention`

- [ ] **Step 3: Implement**

Model fields:
```python
    return_reason = Column(Text, nullable=True)  # Set when returned from release queue
    return_response_note = Column(Text, nullable=True)  # Required response before re-approval
```

Transition map line 130:
```python
            LotStatus.AWAITING_RELEASE: [LotStatus.APPROVED, LotStatus.REJECTED, LotStatus.NEEDS_ATTENTION],
```

Migration: two nullable Text columns on `lots` (same shape as Task 6's migration).

In `calculate_lot_status` (lot_service.py, immediately after the AUTO_RECALCULATION_STATUSES guard at line ~507):

```python
        # A lot returned from the release queue stays in NEEDS_ATTENTION until
        # the return is answered with a response note (resolved at submit time).
        if (
            old_status == LotStatus.NEEDS_ATTENTION
            and lot.return_reason
            and not lot.return_response_note
        ):
            return LotStatusCalculation(
                lot=lot,
                old_status=old_status,
                new_status=LotStatus.NEEDS_ATTENTION,
                reason="Returned for review; awaiting response note",
                missing_tests=[],
                failing_tests=[],
            )
```

Add both fields to `LotResponse` (`backend/app/schemas/lot.py`) and the frontend `Lot` interface (`return_reason: string | null`, `return_response_note: string | null`).

- [ ] **Step 4: Run tests + apply migration**

Run: `cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m pytest tests/test_return_for_review.py tests/test_lot_service.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/lot.py backend/migrations/versions/w1x2y3z4a5b6_add_lot_return_fields.py backend/app/services/lot_service.py backend/app/schemas/lot.py frontend/src/types/index.ts backend/tests/test_return_for_review.py
git commit -m "feat: return-for-review lot state with response-note hold"
```

### Task 11: Endpoints — return-for-review + response note on submit

**Files:**
- Modify: `backend/app/api/v1/endpoints/lots.py` (new endpoint after `resubmit_lot` ~line 850; modify `submit_for_review` at 724)
- Modify: `backend/app/schemas/lot.py` (request schemas)
- Test: `backend/tests/test_return_for_review.py` (append)

- [ ] **Step 1: Write failing endpoint tests**

```python
def test_return_for_review_endpoint(client, qc_auth_headers, awaiting_release_lot):
    resp = client.post(
        f"/api/v1/lots/{awaiting_release_lot.id}/return-for-review",
        json={"reason": "COC lot number mismatch"},
        headers=qc_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "needs_attention"
    assert body["return_reason"] == "COC lot number mismatch"


def test_return_requires_reason(client, qc_auth_headers, awaiting_release_lot):
    resp = client.post(
        f"/api/v1/lots/{awaiting_release_lot.id}/return-for-review",
        json={"reason": "  "},
        headers=qc_auth_headers,
    )
    assert resp.status_code == 400


def test_return_forbidden_for_lab_tech(client, labtech_auth_headers, awaiting_release_lot):
    resp = client.post(
        f"/api/v1/lots/{awaiting_release_lot.id}/return-for-review",
        json={"reason": "x"},
        headers=labtech_auth_headers,
    )
    assert resp.status_code == 403


def test_submit_returned_lot_requires_response_note(client, auth_headers, returned_lot_all_passing):
    resp = client.post(
        f"/api/v1/lots/{returned_lot_all_passing.id}/submit-for-review",
        headers=auth_headers,
    )
    assert resp.status_code == 400

    resp = client.post(
        f"/api/v1/lots/{returned_lot_all_passing.id}/submit-for-review",
        json={"return_response_note": "Data entry mistake; corrected lot number"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "awaiting_release"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_return_for_review.py -v --no-cov -k endpoint or requires`
Expected: FAIL (404 route / missing behavior)

- [ ] **Step 3: Implement**

Schemas in `backend/app/schemas/lot.py`:

```python
class LotReturnRequest(BaseModel):
    reason: str


class LotSubmitRequest(BaseModel):
    return_response_note: Optional[str] = None
```

New endpoint (auth dependency `QCManagerOrAdmin`, same as `update_lot_status`):

```python
@router.post("/{lot_id}/return-for-review", response_model=LotResponse)
async def return_lot_for_review(
    lot_id: int,
    payload: LotReturnRequest,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> LotResponse:
    """Return an awaiting-release lot to the tracker for correction (QC/Admin)."""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lot not found")
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A reason is required to return a lot for review",
        )
    old_values = {"status": lot.status.value, "return_reason": lot.return_reason}
    try:
        lot.update_status(LotStatus.NEEDS_ATTENTION)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    lot.return_reason = payload.reason.strip()
    lot.return_response_note = None
    db.flush()
    AuditService().log_action(
        db=db,
        table_name="lots",
        record_id=lot.id,
        action=AuditAction.UPDATE,
        user_id=current_user.id,
        old_values=old_values,
        new_values={"status": lot.status.value, "return_reason": lot.return_reason},
        reason=f"Returned for review: {lot.return_reason}",
    )
    db.commit()
    db.refresh(lot)
    return LotResponse.model_validate(lot)
```

Modify `submit_for_review` (lots.py:724): add `payload: Optional[LotSubmitRequest] = None` body param. Before the recalculation block (line 744):

```python
    # A returned lot must be answered before it can move on
    if lot.return_reason and not lot.return_response_note:
        note = payload.return_response_note if payload else None
        if not note or not note.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A response note is required: explain what happened and how it was addressed",
            )
        lot.return_response_note = note.strip()
        AuditService().log_action(
            db=db,
            table_name="lots",
            record_id=lot.id,
            action=AuditAction.UPDATE,
            user_id=current_user.id,
            old_values={"return_response_note": None},
            new_values={"return_response_note": lot.return_response_note},
            reason=f"Return resolved: {lot.return_response_note}",
        )
        db.flush()
```

(The existing recalc then sees the resolved return and promotes to UNDER_REVIEW; the rest of submit proceeds unchanged.)

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_return_for_review.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/lots.py backend/app/schemas/lot.py backend/tests/test_return_for_review.py
git commit -m "feat: return-for-review endpoint and response-note gate on submit"
```

### Task 12: Frontend — Release Queue actions

**Files:**
- Modify: `frontend/src/api/lots.ts` (returnForReview call; check existing `updateStatus`), `frontend/src/hooks/useLots.ts` (useReturnLotForReview, useRejectLot — reuse existing status-update hook if present: `grep -n "status" frontend/src/hooks/useLots.ts`)
- Modify: `frontend/src/pages/ReleaseQueue.tsx`

- [ ] **Step 1: API + hooks**

`frontend/src/api/lots.ts`:

```typescript
  returnForReview: async (lotId: number, reason: string): Promise<Lot> => {
    const response = await api.post<Lot>(`/lots/${lotId}/return-for-review`, { reason })
    return response.data
  },
```

For reject, reuse the existing status-update API (`PATCH /lots/{id}/status` with `{ status: "rejected", rejection_reason }`) — check `lots.ts` for an existing `updateStatus`; add if missing. Hooks in `useLots.ts` follow the existing mutation pattern and must invalidate `lotKeys.lists()`, `lotKeys.statusCounts()`, and the release queue query key (find it in `frontend/src/hooks/useRelease.ts` — import and invalidate `releaseKeys.queue()` or equivalent).

- [ ] **Step 2: Actions on the Awaiting Release table**

In `ReleaseQueue.tsx`, get the user role from the auth store (`import { useAuthStore } from "@/store/auth"`; check exact export with `grep -n "role" frontend/src/store/auth.ts`). `const canAct = user?.role === "admin" || user?.role === "qc_manager"` (match the exact role string casing used elsewhere: `grep -rn "qc_manager\|QC_MANAGER" frontend/src | head`).

Add an Actions column to the Awaiting Release table (only when `canAct`): two small outline buttons, "Return for Review" (amber accent) and "Reject" (red accent), each `e.stopPropagation()`.

Add one shared reason dialog (pattern: the email dialog already in this file, lines 352-409):

```tsx
const [actionDialog, setActionDialog] = useState<{
  mode: "return" | "reject"
  item: ReleaseQueueItem
} | null>(null)
const [actionReason, setActionReason] = useState("")
```

Dialog content: title "Return for Review" / "Reject Lot", a required `Textarea` ("Reason — what needs to be corrected?" / "Rejection reason"), confirm button disabled while `!actionReason.trim()`, calling the matching mutation then closing and toasting (`"Lot returned to Sample Tracker"` / `"Lot rejected"`).

- [ ] **Step 3: Build + manual verify + commit**

Run: `cd frontend && npm run build`
Manual: as admin, Release Queue shows both actions; returning a lot removes it from the queue and it appears in Sample Tracker under Needs Attention; as labtech (login `labtech`/`lab123`) no action buttons.

```bash
git add frontend/src
git commit -m "feat: reject and return-for-review actions on release queue"
```

### Task 13: Frontend — amber Returned card + modal banner + response-note dialog

**Files:**
- Modify: `frontend/src/components/domain/KanbanBoard.tsx` (card component, ~line 131-300)
- Modify: `frontend/src/components/domain/SampleModal/index.tsx` and `SampleModalHeader.tsx`

- [ ] **Step 1: Kanban card amber treatment**

In the card component in `KanbanBoard.tsx`, derive `const isReturned = !!lot.return_reason && !lot.return_response_note`. When `isReturned`:
- Card container gets `bg-amber-50 border-amber-300` (replacing its white/default classes via `cn(...)`).
- Add a chip next to the status area: `<span className="inline-flex items-center rounded bg-amber-100 px-1.5 py-0.5 text-[9px] font-medium text-amber-700">Returned</span>` (same style as the existing amber chip at line 245).
- Below the product line, the reason: `<p className="mt-1 text-[11px] text-amber-700 line-clamp-2" title={lot.return_reason}>↩ {lot.return_reason}</p>`

- [ ] **Step 2: Modal banner + submit gate**

In `SampleModal/index.tsx`, when `lot?.return_reason && !lot.return_response_note`, render a banner above the test results (near the FilterPills):

```tsx
<div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3">
  <p className="text-sm font-semibold text-amber-800">Returned for review</p>
  <p className="mt-0.5 text-sm text-amber-700">{lot.return_reason}</p>
</div>
```

The "Submit for Review" action (find it: `grep -n "submit-for-review\|submitForReview\|SubmitForReview" frontend/src -rn`): when the lot is returned-unresolved, intercept the submit and open a small dialog "Respond to return" with a required textarea ("What happened and how was it addressed? e.g. data entry mistake, corrected") and pass `return_response_note` in the submit call. Update the submit API function in `frontend/src/api/lots.ts` to accept an optional `{ return_response_note?: string }` body.

- [ ] **Step 3: Build + manual verify + commit**

Run: `cd frontend && npm run build && npm run test:run`
Manual: return a lot from Release Queue → tracker card is amber with reason → open modal, banner shows → Submit for Review prompts for response → after submit, lot lands back in Awaiting Release and the amber clears.

```bash
git add frontend/src
git commit -m "feat: amber returned cards, return banner, response-note on submit"
```

---

## Feature 4: Tab Autoscroll + Sticky Submit (Create Sample)

### Task 14: Autoscroll focused rows and pin the submit bar

**Files:**
- Modify: `frontend/src/pages/CreateSample.tsx` (sub-batches table keyboard nav ~lines 811-988; composite table ~584-809; submit button container at the end of the form — locate with `grep -n "type=\"submit\"\|Submit" frontend/src/pages/CreateSample.tsx`)

- [ ] **Step 1: Autoscroll on focus**

Both editable tables move focus programmatically (refs + `.focus()` calls in the Tab/Shift+Tab/Enter handlers). Add a helper near the top of the component and call it wherever focus is moved (after each `.focus()` call) — or, simpler and DRY: attach one `onFocus` handler on each table's container:

```tsx
const handleTableFocusScroll = (e: React.FocusEvent<HTMLElement>) => {
  // Keep the focused cell visible above the sticky submit bar
  e.target.scrollIntoView({ block: "nearest", behavior: "smooth" })
}
```

```tsx
<div onFocus={handleTableFocusScroll}> ... table ... </div>
```

`scrollIntoView({block: "nearest"})` respects `scroll-margin`; add `scroll-mb-24` (scroll-margin-bottom: 6rem) to the table row/cell elements so "nearest" clears the sticky bar.

- [ ] **Step 2: Sticky submit bar**

Wrap the existing submit button (and its siblings, e.g. Cancel) in:

```tsx
<div className="sticky bottom-0 z-10 -mx-6 mt-6 border-t border-slate-200 bg-white/95 px-6 py-3 backdrop-blur supports-[backdrop-filter]:bg-white/80">
  ...existing buttons...
</div>
```

The page scroll container is `<main className="flex-1 overflow-y-auto">` in `AppLayout.tsx:57` — `sticky bottom-0` works within it. Verify the form's parent doesn't clip (`overflow-hidden` ancestors would break sticky; the section cards do use `overflow-hidden` but the submit bar must sit OUTSIDE the cards, directly in the form's top-level flow).

- [ ] **Step 3: Manual verify + tests + commit**

Manual: Parent Lot mode → add 10+ sub-batches → tab through; rows scroll into view, submit bar always visible. Same in Multi-SKU composite mode.
Run: `cd frontend && npm run build`

```bash
git add frontend/src/pages/CreateSample.tsx
git commit -m "feat: autoscroll focused rows and sticky submit on create sample"
```

---

## Feature 5: Create Sample Section Differentiation

### Task 15: Darker canvas, floating cards, tinted headers

**Files:**
- Modify: `frontend/src/pages/CreateSample.tsx` (page wrapper + section containers/headers at ~1008, 1043, 1200, 1243)

- [ ] **Step 1: Page canvas + card depth**

The page content wrapper (top-level div of the page, before the Lot Type card): set `bg-slate-100` on the page wrapper (`<main>` already has `bg-slate-50` from AppLayout; add a page-level wrapper class `min-h-full bg-slate-100` or change the page container div) and increase section spacing to `space-y-8`.

Section containers change from `rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden` to:

```
rounded-xl border border-slate-200 bg-white shadow-[0_4px_12px_-2px_rgba(0,0,0,0.08)] overflow-hidden
```

- [ ] **Step 2: Tinted headers per section**

Replace each header div (`border-b border-slate-200 bg-slate-50/80 px-6 py-4`) with a per-section tint; icons get matching color:

| Section | Header classes | Icon color |
|---|---|---|
| Lot Type | `border-b border-blue-100 bg-blue-50/70 px-6 py-4` | `text-blue-600` |
| Lot Details | `border-b border-violet-100 bg-violet-50/70 px-6 py-4` | `text-violet-600` |
| Lab Reference # | `border-b border-amber-100 bg-amber-50/70 px-6 py-4` | `text-amber-600` |

Any additional section cards on the page (e.g. sub-batches, composite products, customer) keep the neutral `bg-slate-50/80` header so the three primary steps stand out. Header title text stays `text-slate-900`.

- [ ] **Step 3: Manual verify + build + commit**

Manual check against the approved mockup (darker canvas, floating cards, blue/violet/amber tints) in all three lot-type modes.
Run: `cd frontend && npm run build`

```bash
git add frontend/src/pages/CreateSample.tsx
git commit -m "feat: differentiate create-sample sections with canvas depth and tinted headers"
```

---

## Feature 6: Kanagawa Dragon Dark Mode

### Task 16: Theme infrastructure — dark variant, Dragon palette remap, theme store

Tailwind v4 compiles color utilities to CSS variables (`bg-white` → `var(--color-white)`), so overriding the variables inside a `.dark` scope re-themes every existing class without touching components. This is the all-or-nothing lever.

**Files:**
- Modify: `frontend/src/index.css`
- Create: `frontend/src/hooks/useTheme.ts`
- Modify: `frontend/src/main.tsx` or `frontend/src/App.tsx` (apply stored theme class on boot — check which exists: `ls frontend/src/*.tsx`)
- Test: `frontend/src/hooks/useTheme.test.ts`

- [ ] **Step 1: Write failing hook test**

```typescript
import { describe, it, expect, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { useTheme } from "./useTheme"

describe("useTheme", () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove("dark")
  })

  it("defaults to light", () => {
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe("light")
    expect(document.documentElement.classList.contains("dark")).toBe(false)
  })

  it("toggles to dark, persists, applies class", () => {
    const { result } = renderHook(() => useTheme())
    act(() => result.current.toggleTheme())
    expect(result.current.theme).toBe("dark")
    expect(localStorage.getItem("labtrack-theme")).toBe("dark")
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  })
})
```

Run: `cd frontend && npm run test:run -- useTheme` → FAIL (module missing)

- [ ] **Step 2: Implement the hook**

`frontend/src/hooks/useTheme.ts`:

```typescript
import { useCallback, useSyncExternalStore } from "react"

const STORAGE_KEY = "labtrack-theme"
type Theme = "light" | "dark"

let listeners: Array<() => void> = []

function getTheme(): Theme {
  return localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light"
}

export function applyStoredTheme() {
  document.documentElement.classList.toggle("dark", getTheme() === "dark")
}

function setTheme(theme: Theme) {
  localStorage.setItem(STORAGE_KEY, theme)
  document.documentElement.classList.toggle("dark", theme === "dark")
  listeners.forEach((l) => l())
}

export function useTheme() {
  const theme = useSyncExternalStore(
    (cb) => {
      listeners.push(cb)
      return () => {
        listeners = listeners.filter((l) => l !== cb)
      }
    },
    getTheme,
    () => "light" as Theme
  )
  const toggleTheme = useCallback(
    () => setTheme(getTheme() === "dark" ? "light" : "dark"),
    []
  )
  return { theme, toggleTheme }
}
```

Call `applyStoredTheme()` at the top of `frontend/src/main.tsx` before render.

- [ ] **Step 3: Dragon palette remap in index.css**

In `frontend/src/index.css`, after the `@import "tailwindcss";` line add the dark variant, and after the existing `@theme` block add the `.dark` override. Kanagawa Dragon values (from rebelot/kanagawa.nvim):

```css
@custom-variant dark (&:where(.dark, .dark *));

/* ── Kanagawa Dragon dark theme ─────────────────────────────────────────
   Tailwind v4 utilities resolve to var(--color-*), so remapping the
   variables under .dark re-themes every hardcoded class. Surfaces invert
   (slate-50 was a light bg, becomes a dark raised surface); text inverts
   (slate-900 dark text becomes near-white). */
.dark {
  /* base */
  --color-white: #181616;            /* dragonBlack3: card/header surfaces */
  --color-black: #c5c9c5;            /* dragonWhite */

  /* slate scale: bg end -> dragon blacks, text end -> dragon whites/grays */
  --color-slate-50: #1d1c19;         /* dragonBlack2: subtle bg bands */
  --color-slate-100: #282727;        /* dragonBlack4: page canvas, hovers */
  --color-slate-150: #282727;
  --color-slate-200: #393836;        /* dragonBlack5: borders */
  --color-slate-300: #625e5a;        /* dragonBlack6: stronger borders */
  --color-slate-400: #737c73;        /* dragonAsh: muted icons/text */
  --color-slate-500: #9e9b93;        /* dragonGray2: secondary text */
  --color-slate-600: #a6a69c;        /* dragonGray */
  --color-slate-700: #c5c9c5;        /* dragonWhite: primary-ish text */
  --color-slate-800: #c5c9c5;
  --color-slate-900: #c5c9c5;        /* primary text */
  --color-slate-950: #c5c9c5;

  /* gray (some components use gray-*) — mirror slate */
  --color-gray-50: #1d1c19; --color-gray-100: #282727; --color-gray-200: #393836;
  --color-gray-300: #625e5a; --color-gray-400: #737c73; --color-gray-500: #9e9b93;
  --color-gray-600: #a6a69c; --color-gray-700: #c5c9c5; --color-gray-800: #c5c9c5;
  --color-gray-900: #c5c9c5;

  /* semantic accents — muted Dragon hues
     light-step variants (50-200) become dark tinted surfaces via color-mix */
  --color-blue-50: color-mix(in srgb, #8ba4b0 14%, #181616);
  --color-blue-100: color-mix(in srgb, #8ba4b0 22%, #181616);
  --color-blue-200: color-mix(in srgb, #8ba4b0 32%, #181616);
  --color-blue-500: #8ba4b0;         /* dragonBlue2 */
  --color-blue-600: #8ba4b0;
  --color-blue-700: #a3bcc8;

  --color-red-50: color-mix(in srgb, #c4746e 14%, #181616);
  --color-red-100: color-mix(in srgb, #c4746e 22%, #181616);
  --color-red-200: color-mix(in srgb, #c4746e 32%, #181616);
  --color-red-500: #c4746e;          /* dragonRed */
  --color-red-600: #c4746e;
  --color-red-700: #d68f89;

  --color-green-50: color-mix(in srgb, #8a9a7b 14%, #181616);
  --color-green-100: color-mix(in srgb, #8a9a7b 22%, #181616);
  --color-green-500: #8a9a7b;        /* dragonGreen2 */
  --color-green-600: #87a987;        /* dragonGreen */
  --color-green-700: #9fb592;
  --color-emerald-50: color-mix(in srgb, #8a9a7b 14%, #181616);
  --color-emerald-100: color-mix(in srgb, #8a9a7b 22%, #181616);
  --color-emerald-500: #8a9a7b;
  --color-emerald-600: #87a987;
  --color-emerald-700: #9fb592;

  --color-amber-50: color-mix(in srgb, #c4b28a 14%, #181616);
  --color-amber-100: color-mix(in srgb, #c4b28a 24%, #181616);
  --color-amber-200: color-mix(in srgb, #c4b28a 34%, #181616);
  --color-amber-300: color-mix(in srgb, #c4b28a 50%, #181616);
  --color-amber-500: #c4b28a;        /* dragonYellow */
  --color-amber-600: #c4b28a;
  --color-amber-700: #d6c69e;
  --color-yellow-100: color-mix(in srgb, #c4b28a 24%, #181616);
  --color-yellow-500: #c4b28a;
  --color-yellow-700: #d6c69e;

  --color-violet-50: color-mix(in srgb, #8992a7 14%, #181616);
  --color-violet-100: color-mix(in srgb, #8992a7 24%, #181616);
  --color-violet-500: #8992a7;       /* dragonViolet */
  --color-violet-600: #8992a7;

  /* shadcn semantic tokens from the @theme block */
  --color-background: #12120f;       /* dragonBlack1 */
  --color-foreground: #c5c9c5;
  --color-card: #181616;
  --color-card-foreground: #c5c9c5;
  --color-popover: #0d0c0c;          /* dragonBlack0 */
  --color-popover-foreground: #c5c9c5;
  --color-primary: #c5c9c5;
  --color-primary-foreground: #181616;
  --color-secondary: #282727;
  --color-secondary-foreground: #c5c9c5;
  --color-muted: #282727;
  --color-muted-foreground: #9e9b93;
  --color-accent: #282727;
  --color-accent-foreground: #c5c9c5;
  --color-destructive: #c4746e;
  --color-destructive-foreground: #181616;
  --color-border: #393836;
  --color-input: #393836;
  --color-ring: #8ba4b0;
}
```

Extend any blue/red/green/amber/violet steps the codebase actually uses — audit first: `grep -rhoE "(bg|text|border|ring|from|to)-(blue|red|green|emerald|amber|yellow|violet|indigo|sky|rose|orange)-[0-9]+" frontend/src | sort -u` and add a `.dark` override for every step found, mapping to the nearest Dragon hue (indigo/sky→dragonBlue2 `#8ba4b0`, rose→dragonRed `#c4746e`, orange→dragonOrange `#b6927b`, teal→dragonTeal `#949fb5`, etc.). Also override the hardcoded `hsl(...)` literals in index.css (simplebar track/thumb, scrollbar-visible) with `.dark` rules using dragonBlack5/6.

- [ ] **Step 4: Run tests + build + commit**

Run: `cd frontend && npm run test:run -- useTheme && npm run build`

```bash
git add frontend/src/index.css frontend/src/hooks/useTheme.ts frontend/src/hooks/useTheme.test.ts frontend/src/main.tsx
git commit -m "feat: kanagawa dragon dark theme infrastructure (palette remap + theme hook)"
```

### Task 17: Document previews stay light (dimmed)

**Files:**
- Modify: `frontend/src/index.css` (one utility class)
- Modify: `frontend/src/components/domain/COAPreview.tsx`, `COAPreviewDocument.tsx`, `SourcePDFViewer.tsx`, and any PDF iframe/embed container (find: `grep -rln "iframe\|embed\|object" frontend/src/components frontend/src/pages`)

- [ ] **Step 1: Comfort-dim utility**

In `index.css`:

```css
/* Printable-document previews: keep paper light but dim it in dark mode */
.dark .document-preview {
  filter: brightness(0.85) sepia(0.04);
}
.document-preview {
  background-color: #ffffff; /* paper is always white, not themed */
}
```

- [ ] **Step 2: Apply the class**

Add `document-preview` to the root container of each document-rendering component (COA preview document, PDF viewers, label previews). These components must keep their hardcoded light styling — since the `.dark` remap changes `--color-white`, any preview using `bg-white` would go dark; replace `bg-white` with `bg-[#ffffff]`-style literals or rely on the `.document-preview` background rule. Audit each preview component for slate text classes that would invert; pin them with literal values (e.g. `text-[#0f172a]`) so certificate content renders print-faithful.

- [ ] **Step 3: Build + commit**

Run: `cd frontend && npm run build`

```bash
git add frontend/src
git commit -m "feat: document previews stay paper-white with comfort dim in dark mode"
```

### Task 18: Dark audit of every page, then ship the header toggle

**Files:**
- Modify: any component with dark-mode regressions
- Modify: `frontend/src/components/domain/AppLayout.tsx:23-35` (toggle button — LAST step)

- [ ] **Step 1: Temporarily force dark for audit**

In devtools: `document.documentElement.classList.add("dark")` (or temporarily set localStorage `labtrack-theme=dark` + applyStoredTheme). Walk EVERY page as admin: Dashboard, Lab Test Types, Products, Customers, Create Sample (all 3 lot types + success screen), Sample Tracker (+ sample modal, all accordions, PDF upload), Release Queue (+ dialogs), Release detail, History/Archive, Audit Trail, Settings (all tabs), Login.

Checklist per page: backgrounds inverted, text readable (no dark-on-dark), borders visible, hover states sensible, badges/chips legible, focus rings visible, charts/graphs legible, gradients (`from-slate-700 to-slate-900` avatar etc.) acceptable, shadows not glowing. Record findings in a scratch list.

- [ ] **Step 2: Fix findings**

Typical fixes: add missing color-step overrides to the `.dark` block in index.css (preferred — fixes globally); for one-off components (e.g. `ring-white`, gradients, rgba shadows), add `dark:` variant classes (`dark:ring-slate-800`). The `glow-fade` keyframe (index.css:143-148) uses literal rgba amber — acceptable as-is. Box shadows with literal rgba (cards) are subtle enough on dark; only fix if they look wrong.

- [ ] **Step 3: Frontend test suite + build**

Run: `cd frontend && npm run test:run && npm run build`
Expected: all green.

- [ ] **Step 4: Ship the toggle**

In `AppLayout.tsx` header (before the HelpCircle button at line 24):

```tsx
import { Moon, Sun } from "lucide-react"
import { useTheme } from "@/hooks/useTheme"

// inside the component:
const { theme, toggleTheme } = useTheme()

// in the header button group:
<Button
  variant="ghost"
  size="sm"
  onClick={toggleTheme}
  title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
  className="h-9 w-9 p-0 text-slate-400 hover:text-slate-600 hover:bg-slate-100/80 rounded-lg transition-colors"
>
  {theme === "dark" ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
</Button>
```

- [ ] **Step 5: Final verify + commit**

Manual: toggle in header flips the whole app; preference survives reload; default for a fresh browser is light; document previews render dimmed-paper in dark.

```bash
git add frontend/src
git commit -m "feat: kanagawa dragon dark mode toggle"
```

---

## Final Verification

- [ ] Backend full suite: `cd backend && .venv/bin/python -m pytest tests/ -v` (coverage on)
- [ ] Frontend: `cd frontend && npm run lint && npm run test:run && npm run build`
- [ ] `make format && make lint` for Python changes
- [ ] End-to-end manual pass of all six features in the running app (light AND dark)
