# Lab Test Import Serving Basis + UI Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine Lab Test Import so serving-basis metal results are converted correctly, valid rows can apply reliably, and the UI explains summary buckets, match reasons, and extra-test mapping.

**Architecture:** Keep the importer's existing backend confirm flow and frontend review page. Add serving-basis normalization in the import service, improve row-action inference in the frontend, and make chip/match UI explanatory without changing the route.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, React, TypeScript, Vite, TanStack Query, Vitest.

## Global Constraints

- Do not add mock data, seed data, or backfilled data.
- Product database serving size is authoritative for serving-to-spec conversion.
- COA serving size is only used to flag mismatch.
- Valid rows apply even when other rows are blocked/skipped.
- Recognized off-panel lab tests auto-include as ad-hoc drafts.
- Unrecognized tests require user mapping.
- Keep the four summary chips.
- Keep route `/results-importer`.

---

## Task 1: Serving-Basis Metal Normalization

**Files:**
- Modify: `backend/app/services/result_import_service.py`
- Modify: `backend/tests/test_result_import_service.py`

**Interfaces:**
- Produces normalized rows where serving-basis metals have `result_value_raw` in the product spec unit.
- Stores original serving and mass-basis values in `metadata`.

- [ ] Write failing tests:
  - A Harken metal row with both `per_serving` and `mcg/g` saves the converted serving value.
  - Missing/unparseable product serving size blocks the row.
  - COA serving size mismatch adds a warning.

- [ ] Add helper logic:
  - Parse product serving size grams from selected lot product data.
  - Convert `mcg/serving / grams_per_serving` to `mcg/g`.
  - Treat `ppm` and `ug/g` as equivalent for metals.
  - Preserve original values in metadata keys:
    - `serving_value`
    - `serving_unit`
    - `mass_basis_value`
    - `mass_basis_unit`
    - `conversion_note`

- [ ] Replace current behavior that blanks per-serving Harken rows.
  - Do not set `result_value_raw = None` for serving-basis rows.
  - Set `blocked_reason` only when conversion is impossible.

- [ ] Run:
  - `cd backend && .venv/bin/python -m pytest tests/test_result_import_service.py -q --no-cov`

---

## Task 2: Extraction Prompt Preference

**Files:**
- Modify: `backend/app/services/result_extraction_provider.py`
- Modify: `backend/tests/test_result_import_service.py`

**Interfaces:**
- AI extraction should identify both basis columns when present.
- Serving column is preferred as authoritative source.

- [ ] Update OpenRouter prompt:
  - Explicitly say: when both `micrograms/gram` and `micrograms/serving` are printed, extract the serving value as `per_serving`.
  - Preserve mass-basis value in metadata-compatible fields if present.
  - Never discard `<LOD`, `<LOQ`, or less-than values.

- [ ] Ensure schema allows:
  - `per_serving`
  - `lod`
  - `loq`
  - serving size text if available.

- [ ] Add/adjust provider test that asserts prompt text includes serving-priority instruction.

---

## Task 3: Confirm Contract Safety

**Files:**
- Modify: `backend/app/schemas/result_import.py`
- Modify: `backend/app/services/result_import_service.py`
- Modify: `backend/tests/test_result_import_service.py`
- Modify: `frontend/src/types/index.ts`

**Interfaces:**
- `RowAction.result_value?: string | null`
- Backend confirm prefers `action.result_value` when present.

- [ ] Keep `result_value` optional for backward compatibility.
- [ ] Confirm uses:
  - `action.result_value` when not `None`
  - otherwise `row.result_value_raw`
- [ ] Relax existing-result validation:
  - If both existing result and target have non-null matching `lab_test_type_id`, accept the replacement even if old `test_type` text differs.
  - Still reject approved results.
- [ ] Add backend test for legacy `test_type` mismatch with matching `lab_test_type_id`.

---

## Task 4: Row Action Inference

**Files:**
- Modify: `frontend/src/lib/buildRowActions.ts`
- Modify: `frontend/src/lib/buildRowActions.test.ts`
- Modify: `frontend/src/pages/ResultsImporter.tsx`

**Interfaces:**
- `buildRowActions(rows, previews, existingByLabType)` returns valid `ResultRowAction[]`.

- [ ] Add tests:
  - recognized off-panel row creates `create_adhoc`
  - unrecognized off-panel row skips until mapped
  - blocked row skips with no action
  - edited result sends `result_value`
  - mapped existing draft sends `replace`
  - approved existing sends `skip`

- [ ] Update row state:
  - Add `blockedReason?: string | null`
  - Treat blocked rows as skipped.
  - Include `result_value` for all nonblank action rows.

- [ ] Auto-include recognized off-panel rows:
  - If `resolvedLabTypeId` exists, do not require mapper.
  - Show `Ad-hoc draft` badge instead.

---

## Task 5: Searchable Extra-Test Mapper

**Files:**
- Modify: `frontend/src/pages/ResultsImporter.tsx`

**Interfaces:**
- Mapper only appears for unmapped/unrecognized rows.

- [ ] Replace ambiguous select copy:
  - Label: `Map extra test`
  - Helper: `This parsed test is not recognized. Choose a lab test type to include it as an ad-hoc draft.`

- [ ] Add local search input for mapper:
  - Filter by `test_name`
  - Filter by `abbreviations`
  - Filter by category if useful.
  - Confirm `arsenic` and `as` can find Arsenic when it exists in the loaded lab types.

- [ ] If the active lab type list is paginated too narrowly, fetch with `page_size=500` and show a warning if total exceeds loaded count.

---

## Task 6: Summary Chip Popovers

**Files:**
- Modify: `frontend/src/pages/ResultsImporter.tsx`

**Interfaces:**
- Summary model should expose display rows for each chip.

- [ ] Extend summary calculation to return:
  - `parsingNowItems`
  - `completedPassedItems`
  - `pendingItems`
  - `otherItems`

- [ ] Change `Other` chip from red to amber.
- [ ] Change caption from `failed or off-panel` to `off-panel or needs attention`.
- [ ] Add hover/focus popovers:
  - test name
  - value when available
  - reason text
- [ ] Keep four-chip layout.

---

## Task 7: Apply Button Disabled Reasons

**Files:**
- Modify: `frontend/src/pages/ResultsImporter.tsx`

**Interfaces:**
- Button area exposes one clear disabled reason.

- [ ] Add computed `applyDisabledReason`:
  - no selected lot
  - preview not ready
  - no applyable rows
  - all rows blocked/skipped
- [ ] Display disabled reason below the button.
- [ ] Keep partial apply:
  - valid rows apply
  - skipped/blocked rows stay unapplied and visible.

---

## Task 8: Match Reasons And Identifier Display

**Files:**
- Modify: `backend/app/services/result_import_service.py`
- Modify: `backend/tests/test_result_import_service.py`
- Modify: `frontend/src/pages/ResultsImporter.tsx`

**Interfaces:**
- Match candidate reasons include matched field and value.

- [ ] Backend match reasons should include exact values:
  - `Batch 26137 matched COA batch number`
  - `Reference 2614900001 matched COA reference`
  - `Lot X matched COA lot`
  - `Sublot X matched COA sublot`

- [ ] Frontend card:
  - Show strongest reason inline under/beside match percent.
  - Put all reasons in title/tooltip or popover.
  - If `reference_number === lot_number`, show identifier once.
  - If distinct, show both as labeled `Lot` and `Lab Ref`.

---

## Task 9: Verification And Review

**Files:**
- All touched files.

- [ ] Run backend importer tests:
  - `cd backend && .venv/bin/python -m pytest tests/test_result_import_service.py tests/test_result_import_endpoints.py -q --no-cov`

- [ ] Run frontend focused tests:
  - `cd frontend && npm run test:run -- src/lib/buildRowActions.test.ts`

- [ ] Run build:
  - `cd frontend && npm run build`

- [ ] Run targeted lint:
  - `cd frontend && npx eslint src/pages/ResultsImporter.tsx src/lib/buildRowActions.ts src/lib/buildRowActions.test.ts`

- [ ] Manual checks:
  - Serving-basis metal COA applies converted values.
  - Other chip is amber.
  - Chip popovers list tests.
  - Arsenic is searchable in mapper when mapping is needed.
  - Recognized off-panel Arsenic auto-includes without mapper.
  - Match card explains why it matched.
  - Apply button explains why disabled.
  - No mock/backfill/seed files changed.
