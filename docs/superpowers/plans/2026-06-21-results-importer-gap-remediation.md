# Results Importer — gap remediation plan

## Context
Code review of the fuzzy-matching / ad-hoc-metadata / alias implementation (branch
`feature/results-importer`, worktree `/Users/gregsimek/Code/COA-creator/tmp/results-importer`) found
the work ~85% complete and structurally sound (backend 67 tests green, build clean, single migration
head), but with a user-visible regression and several plan gaps. This plan closes them. Severity order;
each item names the file + fix and a test.

Ground-truth verification after each phase:
- `cd backend && /Users/gregsimek/Code/COA-creator/backend/.venv/bin/python -m pytest tests/test_result_import_service.py tests/test_result_import_endpoints.py tests/test_lab_test_aliases.py -q --no-cov`
- `cd frontend && npm run test:run -- src/lib/buildRowActions.test.ts && npm run build`
- targeted `eslint` on touched files.

---

## P0 — Per-serving Unit label regression (user-reported)
**Symptom:** metal rows correctly store the per-serving *value* (Lead 0.842…) but the Unit cell shows
`ppm` instead of `µg/serving`.

**Root cause:** `frontend/src/pages/ResultsImporter.tsx:598-612` — for off-panel (ad-hoc) rows the
prefill orders `selectedLabType?.default_unit` **before** `preview?.unit`, shadowing the backend's
per-serving unit (`_resolve_test_fields:1057` already returns `µg/serving`). Same shadowing risk for
spec/method.

**Fix:** prefer `preview` values when the row is still on the **backend-resolved** type, and only fall
back to the chosen lab-type's catalog defaults when the operator has **manually overridden** to a
different type (whose preview is stale). Introduce `usePreview = resolvedLabTypeId === (preview?.lab_test_type_id ?? null)`:
```
const baseUnit = onPanel
  ? preview?.unit || row.target_unit || row.unit_raw || null
  : usePreview
    ? preview?.unit || selectedLabType?.default_unit || row.target_unit || row.unit_raw || null
    : selectedLabType?.default_unit || row.target_unit || row.unit_raw || null
```
Apply the same `usePreview` ordering to `baseSpecification` and `baseMethod` (preview first when on the
resolved type; lab-type defaults first only on manual override). This keeps the plan's "lab-type
defaults for a freshly chosen alternate" behavior while preserving the per-serving unit for
auto-resolved metals.

**Verify:** reload the `26DL53070` import → Lead/Arsenic/Cadmium/Mercury Unit cells read `µg/serving`;
override one to a different off-panel type → that type's `default_unit` prefills. (No new vitest harness
for the page; verify via build + manual.)

---

## P1 — Frontend plan gaps that block sign-off

### 1. Fuzzy tooltip copy is missing
**Gap:** the plan's exact string is absent (`grep "Fuzzy matched" src/` → none). Fuzzy rows render only a
static "Fuzzy match" pill (`ResultsImporter.tsx:1245-1247`) with no tooltip / no X→Y.
**Fix:** on fuzzy rows, render the warning triangle (reuse the `TriangleAlert` pattern) with the exact
title, substituting the parsed source and resolved target:
`Fuzzy matched "${row.fuzzy_source ?? row.test_name_raw}" to "${vm.testName}". Applying will suggest this alias for QC review.`
Surface `fuzzy_source`/`fuzzy_target`/`fuzzy_warning` on the row VM (already in `ExtractedResultRow`
metadata / `types/index.ts`). Prefer rendering the backend-provided `fuzzy_warning` verbatim if present
to avoid copy drift.

### 2. Approved-target disabled-Apply reason is missing
**Gap:** when a fuzzy/mapped row points to an approved existing result it silently skips; the mandated
reason is absent.
**Fix:** in the page's disabled-reason computation (near the existing `missingAdhocMetadata` reason,
~`ResultsImporter.tsx:705-709`), when a visible row resolves to an approved existing result and is not
overridden, surface: `Fuzzy match points to an approved result; choose an alternate test or leave it skipped.`
Keep the row visible and non-applyable (already the behavior).

### 3. Alias "Approve" is not role-gated in the UI
**Gap:** `LabTestTypes.tsx` has no role checks; any role sees/clicks Approve (backend still enforces, so
not a security hole — but plan requires the gate and it's a confusing 403 UX).
**Fix:** read `useAuthStore` (pattern used in `Settings`/`Products`/`ReleaseQueue`); compute
`canManageAliases = user?.role === "admin" || user?.role === "qc_manager"`. Hide/disable Approve, Edit,
and Disable for other roles, and ideally hide the whole "Test aliases" section for non-managers.

---

## P2 — Should-fix (correctness / robustness)

### 4. Fuzzy guardrail is brittle (hardcoded blocklist + length heuristic)
**Gap:** `lab_test_alias_service.py:40` `BROAD_REJECT_KEYS = {"mold","total count","heavy metals"}` plus
`len(key) < 5` single-token gate. Variants bypass: `Heavy Metal` (singular), `Metals Panel`, and 5+char
single tokens (`Yeast`, `Protein`). On the real catalog the panel's full name keeps similarity under the
0.65 floor today, but the approach is fragile.
**Fix:** make the category guard semantic, not literal — reject when the *normalized key* is a token-subset
of, or matches, a known category label (e.g. derived from `LabTestType.test_category` values like
"Heavy Metals", plus a small synonym set) regardless of singular/plural; and reject any single-token raw
phrase that is itself a category word. Keep the 0.65 / 0.08 thresholds. Add boundary tests:
`Heavy Metal`, `Metals Panel`, `Yeast` (single 5-char token), and a genuine near-tie → all `unmatched`;
keep `Yst Mold`/`Plate Count` matching.

### 5. `create_adhoc` on an on-panel test silently coerces to apply
**Gap:** `result_import_service.py:494-528` — a `create_adhoc` action whose resolved name *is* on-panel
validates the spec-derived values and behaves like `apply`, ignoring the client metadata path.
**Fix:** when `action == "create_adhoc"` and `is_on_panel`, either (a) reject with a clear error, or
(b) explicitly treat it as `apply` and document the coercion. Add a test asserting the chosen behavior.

### 6. Confirm-contract test coverage hole (largest gap)
**Gap:** ad-hoc blank-rejection, `unit` present in **both** audit snapshots, ignore-client-metadata on
on-panel, the **three** suggestion triggers (fuzzy / unmatched-then-mapped / override≠fuzzy-target),
suppression for exact/builtin/approved, and **transaction rollback when alias-suggestion write fails** are
all implemented but untested.
**Fix:** add `tests/test_result_import_service.py` cases:
- `confirm()` rejects `create_adhoc` with blank/whitespace unit | spec | method.
- `confirm()` persists ad-hoc unit/spec/method and both audit snapshots include `unit`.
- on-panel `apply`/`replace` ignores client-sent unit/spec/method (uses product spec).
- suggestion created for fuzzy-accepted, for unmatched-then-manually-mapped, and for
  override≠fuzzy-target (`source == "manual_override"`); NOT created for exact/builtin/approved.
- monkeypatch `record_alias_suggestion` to raise → assert no `TestResult` rows persist (rollback).

---

## P3 — Minor (batch, low risk)
- Add the untested preview branches: fuzzy→on-panel uses product Unit/Spec/Method; fuzzy+approved→skip;
  existing-draft+fuzzy→replace (`result_import_service.py:892-905`).
- Add a direct `normalize_alias_key` unit test (all four transforms) and a `buildRowActions` test that an
  on-panel row drops editable unit/spec/method from the `apply` payload.
- Alias table: surface `last_lot_id` alongside `last_filename` (header "Last file/lot"); prompt for an
  optional disable reason instead of the hardcoded string.
- Replace deprecated `datetime.utcnow()` in `lab_test_alias_service.py` with timezone-aware UTC (codebase
  has the same warning elsewhere — optional consistency).
- Make the fuzzy "Override" control compact/hidden-by-default per the plan (currently an always-visible
  combobox); functional but not the specified affordance.

---

## Sequencing
P0 first (user-visible, 1-line-ish fix), then P1 (sign-off blockers), then P2 (correctness + the big
test gap), then P3 as a cleanup batch. Re-run the full verification set after P0/P1 and again after P2.
