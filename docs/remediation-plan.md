# LabTrack Remediation Plan (Detailed Architecture)

Derived from the 2026-07-06 six-agent audit of `main` and `feature/results-importer` @ 209b53c.
Phases: 0 Safety → 1 Importer merge-blockers → 2 Certificate integrity core → 3 COA content → 4 UX → 5 Loader/ops.
This document details the target architecture and workflow logic for Phases 1-3; Phase 0/4/5 task lists are in the audit summary.

---

## A. Canonical lot workflow state machine (Phase 2.6)

### A.1 The problem
Three competing state machines exist (`Lot.update_status`, `LotService.update_lot_status`, `calculate_lot_status`) and the real endpoints bypass all of them with direct `lot.status = X` assignment. Release does not require approved results; rejected lots skip re-review.

### A.2 Target design
One module: `backend/app/workflow/lot_state_machine.py`.

Two layers:
1. **Pure validation core** — no DB, fully unit-testable:
   `validate_transition(current: LotStatus, target: LotStatus, ctx: TransitionContext) -> TransitionResult`
   `TransitionContext` carries: actor role, actor id, results summary (counts by status, created_by set), spec verdict summary, required-panel completeness, override reason (optional).
2. **`LotWorkflowService.transition(db, lot, target, actor, *, reason=None, override=False)`** — loads context, calls the core, applies the change, writes the audit row, commits nothing itself (caller's transaction).

**Transition table (the only legal edges):**

| From | To | Trigger | Guards |
|---|---|---|---|
| AWAITING_RESULTS | PARTIAL_RESULTS | auto (recalc) | ≥1 result value present, panel incomplete |
| AWAITING_RESULTS / PARTIAL_RESULTS | UNDER_REVIEW | auto (recalc) | all required panel tests have values |
| UNDER_REVIEW | NEEDS_ATTENTION | auto (recalc) | any spec verdict FAIL or INDETERMINATE |
| NEEDS_ATTENTION | UNDER_REVIEW | auto (recalc) | verdicts resolve after correction/retest |
| UNDER_REVIEW | AWAITING_RELEASE | manual submit | **all results APPROVED**; panel complete; all verdicts PASS (or `override=True` + reason, QC+ only) |
| NEEDS_ATTENTION | AWAITING_RELEASE | manual submit w/ override | QC+/Admin, mandatory reason, audited as OVERRIDE |
| AWAITING_RELEASE | RELEASED | approve & release | QC+/Admin; signature on file; release gate (B.4); snapshot created (C) |
| AWAITING_RELEASE | UNDER_REVIEW | return for review | QC+, mandatory reason |
| any pre-RELEASED | REJECTED | reject | QC+, mandatory reason |
| REJECTED | UNDER_REVIEW | resubmit | any tech; **never straight to AWAITING_RELEASE** |
| RELEASED | (none) | — | terminal; corrections = new revision (C.5), never mutation |

**Auto vs manual domains:** `calculate_lot_status` may only move a lot within
`{AWAITING_RESULTS, PARTIAL_RESULTS, UNDER_REVIEW, NEEDS_ATTENTION}`. It never crosses a manual gate and never touches AWAITING_RELEASE/RELEASED/REJECTED.

**Enforcement (both belts):**
- All endpoints/services replace `lot.status = X` with `LotWorkflowService.transition(...)`. Known call sites to convert: `release.py:547,579`, `lots.py:881,1086`, `release_service.py:407`, plus the two legacy service maps (delete `Lot.update_status` and `LotService.update_lot_status`'s map — keep one).
- SQLAlchemy attribute guard: `@event.listens_for(Lot.status, "set")` validator that raises unless a `_transition_token` set by the workflow service is present on the instance. This makes raw assignment fail loudly in tests and future code.
- Test: parametrized matrix over all (from, to, role, guards) combinations asserting exactly the table above.

### A.3 TestResult sub-machine
`DRAFT → APPROVED` (approve) and `APPROVED → DRAFT` (unapprove/return), nothing else.
- **New column `test_results.created_by_id`** (migration; nullable for backfill; set on every create path: manual entry, importer, loader).
- Guard on approve: `approver.id != result.created_by_id` unless `settings.allow_self_approval` (default **false**; admin-only escape hatch, audited as SELF_APPROVAL_OVERRIDE) — a 3-person lab needs the hatch, but it must leave a trace.
- Consolidate the two divergent approval implementations: `test_results.py:350-474` (the endpoints the frontend actually calls) must delegate to `ApprovalService`, which becomes the only place approval logic lives, and it triggers lot recalc.

### A.4 Completeness definition (single source)
`required_panel(lot) = ProductTestSpecification` rows for the lot's product(s), keyed by `lab_test_type_id`.
`coverage = results with non-empty value, keyed by lab_test_type_id (alias-resolved)`.
`missing = required − covered`. Used by: auto-recalc (PARTIAL vs UNDER_REVIEW), release gate, COA "Not Tested" rows. Composite lots: per-product panels once `test_results.product_id` exists (Phase 3); until then panel = union with a documented caveat.

---

## B. Specification engine (Phase 2.1-2.3)

### B.1 The problem
Three inconsistent matchers; COA hardcodes "Pass" (`coa_generation_service.py:375-384`, `release.py:909`); release never consults specs; frontend duplicates spec logic; the UI blocks techs from submitting failing lots while the certificate would print them as passing.

### B.2 Target design
New package `backend/app/specs/`:
- `parser.py` — `parse_spec(text) -> SpecRule` and `parse_result(text) -> ResultValue` (pure, no DB).
  - `SpecRule.kind ∈ {LT, LTE, GT, GTE, RANGE, NEGATIVE_REQUIRED, ABSENT_REQUIRED, TEXT_MATCH, INFORMATIONAL}` + threshold(s) + unit.
  - `ResultValue.kind ∈ {NUMERIC, CENSORED_LT, CENSORED_GT, ND, TNTC, TEXT, EMPTY}` + value + unit.
- `engine.py` — `evaluate(spec: SpecRule|None, result: ResultValue) -> Verdict`
  `Verdict ∈ {PASS, FAIL, INDETERMINATE, NO_SPEC, NOT_TESTED}` + machine-readable reason.

**Non-negotiable evaluation rules:**
- `"<10"` result vs `"< 100 CFU/g"` spec → PASS iff censor bound ≤ threshold; `"<500"` vs `"< 100"` → INDETERMINATE (not pass, not provably fail).
- ND → PASS for LT/NEGATIVE specs; TNTC → FAIL for count-based LT specs.
- Unit mismatch (ppm vs ppb, /g vs /25g) → INDETERMINATE, never silent coercion.
- Unparseable spec or result → INDETERMINATE with reason. **Never default to pass** (this replaces `_check_test_passes_spec`'s "assume pass" at `approval_service.py:536-543`).
- Golden-table unit tests: one table of (spec_text, result_text, expected verdict) covering every real spec format in `product_test_mapping.csv` (extract distinct formats as the fixture).

**Consolidation:** `utils/spec_matcher.py`, `ProductTestSpecification.matches_result`, `ApprovalService._check_test_passes_spec` all become thin wrappers over (or are deleted in favor of) `specs.engine`. Frontend `spec-validation` logic is retired as authority: verdicts are computed server-side and shipped in every payload that carries results (preview-data, lot detail, importer rows); the client may keep an instant-feedback copy but renders server verdicts when present.

### B.3 Where verdicts flow
1. **COA renderers** — Status column shows PASS/FAIL/INDETERMINATE/NO SPEC (D).
2. **Auto-recalc** — FAIL/INDETERMINATE ⇒ NEEDS_ATTENTION (A.2).
3. **Release gate** (B.4).
4. **Result entry + importer review UI** — per-row verdict chip at the moment of entry, so the "tech can't submit failing lot" dead-end becomes "submit with justification → NEEDS_ATTENTION → QC override or retest," replacing the hard block at `SampleModal/index.tsx:393-400`.

### B.4 Release gate (server-side, in `LotWorkflowService`)
`AWAITING_RELEASE → RELEASED` requires, atomically re-checked inside the release transaction:
1. every result APPROVED;
2. required panel complete (else the specific missing tests are named in the 409 response);
3. every verdict PASS — or an override by QC+/Admin with mandatory reason, recorded in the audit log **and printed on the COA** as a deviation note;
4. approver has signature + title on file;
5. no existing RELEASED release for (lot, product) — enforced by DB constraint (E.3), not just the check.

---

## C. COA immutability: snapshot architecture (Phase 2.4)

### C.1 The problem
Released COAs re-render live (`release.py:789-981`): current product/spec/user/lab data, `generated_date=now()`, current-viewer signature fallback (`release.py:952-953`). Register-imported releases have no PDF at all (`release.py:721-724` 404s).

### C.2 Data model
New table `coa_snapshots` (new migration):

```
coa_snapshots
  id                PK
  coa_release_id    FK coa_releases.id, UNIQUE, ondelete=RESTRICT
  coa_serial        TEXT UNIQUE NOT NULL      -- "COA-2026-000123", issued at release
  revision          INT NOT NULL DEFAULT 1
  supersedes_id     FK coa_snapshots.id NULL  -- amendment chain
  context_json      TEXT NOT NULL             -- full COAContext (D), schema-versioned
  context_schema_version INT NOT NULL
  pdf_storage_key   TEXT NOT NULL
  signature_storage_key TEXT NULL             -- frozen COPY of the approver signature file
  content_hash      TEXT NOT NULL             -- sha256(context_json) for tamper-evidence
  reconstructed     BOOL NOT NULL DEFAULT 0   -- true for register backfills
  created_at        DATETIME NOT NULL
```

Plus `coa_serial_counters(year, last_value)` with an atomic `UPDATE ... SET last_value = last_value + 1` claim (same pattern as the importer's status-claim UPDATE).

### C.3 Release-time flow (one transaction + one file phase)
1. Gate checks (B.4) with the release row locked (E.3).
2. `build_context()` (D) → `COAContext`.
3. Issue serial from the counter (atomic UPDATE, rowcount check).
4. Copy the approver's signature file to `uploads/coa-snapshots/{serial}/signature.png` — later signature re-uploads must not touch history.
5. Render PDF to a UUID-keyed storage path (files first, DB second: an orphaned file on rollback is harmless; a DB row pointing at a missing file is not).
6. Insert snapshot row; transition lot RELEASED via the state machine; audit; single commit. Any failure rolls back the row + status; a weekly job sweeps orphaned snapshot files.

### C.4 Read paths after the change
- `GET .../preview-data`: if the release is RELEASED → deserialize `context_json` and return it with `"source": "snapshot"`; the live builder runs **only** for pre-release previews. `generated_date` comes from the snapshot. The current-viewer signature fallback is deleted outright.
- Download: serves `pdf_storage_key` from the snapshot, always. The `get_or_generate_pdf` lazy path is removed for released COAs.
- Frontend: `ReleasedCOAPreviewModal` and Archive need no structural change (same payload shape), but render a "Reconstructed from register" watermark/banner when `reconstructed=true`.

### C.5 Amendments (design now, build in Phase 3)
A correction to a released COA = new `COARelease` + new snapshot with `revision = n+1`, `supersedes_id` set; the old snapshot is never modified; the new PDF prints "Revision 2 — supersedes COA-2026-000123". Both remain in History.

### C.6 Backfill
`backend/scripts/backfill_coa_snapshots.py`: iterate releases with no snapshot in release-date order, build context from current data, snapshot with `reconstructed=true`, issue serials. Idempotent (skips existing), dry-run default, report at end. Run once locally and once on the VPS after deploy.

### C.7 Immutability test (the acceptance test for this whole section)
Integration test: release a lot → capture rendered context + PDF bytes → rename the product, change a spec, change the approver's title, swap the lab logo → re-fetch preview-data and download → assert byte/structure equality with the captured versions.

---

## D. Unified render pipeline (Phase 2.5 + Phase 3 content)

### D.1 The problem
Two live context builders (endpoint inline at `release.py:789-981` vs `_build_context` in `coa_generation_service.py`) have drifted (spec fallback, notes source, PDF drops units); a third dead renderer (`coa_generator_service.py`, 818 lines, CLI-only) invites accidents.

### D.2 Target design
`backend/app/services/coa_context_builder.py`:

```
build_context(db, lot_id, product_id, *, release=None) -> COAContext
```

`COAContext` is a **Pydantic model** (typed, serializable, `context_schema_version` constant bumped on shape changes — snapshots store it, renderers branch on it if ever needed). Contents:
- `lab`: name, address, logo key, **accreditation fields** (new `lab_info` columns: `accreditation_body`, `accreditation_number`, `accreditation_statement`);
- `document`: coa_serial, revision, release/issue date, template_version, override/deviation note if the release gate was overridden;
- `product`, `lot` (numbers, mfg/exp dates), `customer`;
- `approver`: name, title, signature key (frozen copy for snapshots);
- `test_rows[]`: name, **method** (`TestResult.method` — currently dropped by every renderer), result_value, **unit** (PDF currently omits it, `coa_generation_service.py:754`), spec_text, **verdict** (from specs.engine), category + order (via `coa_category_order`);
- `not_tested_rows[]`: required-panel tests with no result, rendered as "Not Tested" — a COA must not look complete when it isn't (closes the silent-omission gap).

Consumers: (1) preview endpoint serializes it; (2) the ReportLab renderer renders it (add page numbers via `onPage` footer: "Page X of Y — {coa_serial}"); (3) snapshots persist it. The inline builder in `release.py` and `_build_context` are deleted; **`coa_generator_service.py` and its CLI path are deleted** (dead code, confirmed only referenced from `services/__init__.py` and `cli.py`).

### D.3 Spec display rule
If no spec exists for a rendered result: display `—` with verdict NO_SPEC. Both the endpoint's invented `"Within limits"` (`release.py:901`) and `_get_default_spec()`'s invented real-looking limits are removed — a certificate must not fabricate acceptance criteria.

---

## E. Authorization & audit architecture (Phase 2.6)

### E.1 Role policy (single documented matrix)
Reusable dependency `RequireRole(*roles)` in `api/dependencies.py`; every mutating route gets one:

| Capability | READ_ONLY | LAB_TECH | QC_MANAGER | ADMIN |
|---|---|---|---|---|
| View everything | ✓ | ✓ | ✓ | ✓ |
| Create/update lots, enter DRAFT results, upload PDFs, importer upload/confirm | | ✓ | ✓ | ✓ |
| Submit for review / resubmit rejected | | ✓ | ✓ | ✓ |
| Approve/unapprove results, reject, return, retest, release, overrides, alias approve | | | ✓ | ✓ |
| Config (products/specs/test types/customers), user mgmt, self-approval override | | | | ✓ |

**Safety net for the whole class:** an ASGI middleware that rejects any non-GET request from a READ_ONLY user (except `/auth/*`) with 403. Per-route deps are the primary control; the middleware guarantees no future route ships open. Parametrized test: roles × mutating endpoints asserting 403/2xx per the matrix.

### E.2 Audit hardening
- `delete_lot` / `delete_test_result` route through service deletes that write audit rows (currently raw `db.delete`, `lots.py:1220`, `test_results.py:498`).
- `_log_audit` failure **raises** for approval/release/delete actions (audit is part of the transaction, not best-effort); stays log-only for low-stakes reads/updates.
- Delete the forgeable `override_user_id` query param (`lots.py:813,887-900`); the actor is always the authenticated user.

### E.3 Concurrency
- Partial unique index: `CREATE UNIQUE INDEX uq_release_released ON coa_releases(lot_id, product_id) WHERE status = 'RELEASED'` — valid in SQLite and Postgres; makes double-release structurally impossible regardless of races.
- `with_for_update()` on the lot + release rows inside `transition()` and release (no-op on SQLite, correct on the planned Postgres migration).
- Importer: unique index on `result_imports.file_hash` scoped `WHERE status IN ('processing','needs_confirmation','confirmed')` so a cancelled/failed upload can be retried but identical bytes can't be live twice.

---

## F. Importer merge-blockers, architectural detail (Phase 1)

1. **Mock guard:** Pydantic validator in `config.py`: `environment == "production" and ai_provider == "mock"` → raise at import time; `create_uploads` re-checks. Dev keeps mock but logs a WARNING banner per upload.
2. **Server-side existing-result resolution:** extend the import detail payload rows with `existing_result: {id, status, value, matched_by: "lab_test_type" | "test_name"} | null`, computed by the same `_find_existing_result` used at confirm time. `buildRowActions.ts` consumes it; delete the client-side `existingByLabType` reconstruction and the 100-row `RESULT_IMPORTER_EXISTING_RESULTS_PAGE_SIZE` fetch. One source of truth = the frontend can never disagree with the backend about replace-vs-apply again.
3. **UI role gating:** shared `RequireRole` route-guard component in `App.tsx`; sidebar filtering; expose `applied_by_id` on confirmed imports and show Revert only to confirmer/QC/Admin.
4. **UX batch:** styled confirms on Revert/Cancel/alias-Approve ("approving remaps ALL future imports of '{phrase}'"); confirm toast reports `created/updated/skipped` from the response; pending-alias-suggestion notice on confirm; stuck-import messaging after 20 min (mirrors the backend reaper window); replace `window.prompt`/`confirm` in alias UI.
   - DONE 2026-07-06 (commit f8b84ff on feature/results-importer): importer redesigned as inbox list (`/results-importer`, filter chips + search + row actions) + routed review view (`/results-importer/:importId`, back/prev-next/Esc), replacing the queue dropdown. Revert/Cancel now confirm via the new shared `ConfirmActionDialog`. Still open from this batch: alias-approve confirm, skipped-count toast, alias-suggestion notice, stuck-import messaging, alias `window.prompt` replacement. Also added `API_TARGET` env override for the vite dev proxy (parallel worktree stacks).
5. **Tests:** dedup short-circuit, concurrent double-confirm (the `NEEDS_CONFIRMATION` claim), direct approved-result-modification guard.
6. **Merge order:** commit main's working tree (released-COA-preview UI + loader append mode) → merge `feature/results-importer` → prune both `tmp/` worktrees → full suites + `npm run build` + alembic upgrade on a DB copy.
7. **Post-merge synergy:** importer review rows get spec-engine verdict chips (B.3) once Phase 2 lands — OOS visible at import time, before anything is applied.

---

## G. Target end-to-end workflow (narrative spec)

1. **Intake** — tech creates lot (AWAITING_RESULTS); success dialog deep-links to "enter results".
2. **Results** — via importer (PDF → LLM extract → deterministic match → human confirm → DRAFT, `created_by` = confirmer) or manual entry beside the source PDF (DRAFT, `created_by` = tech). Auto-recalc: PARTIAL_RESULTS → UNDER_REVIEW when the required panel is covered; verdict FAIL/INDETERMINATE → NEEDS_ATTENTION.
3. **QC approval** — QC approves each result (or bulk); SoD blocks approving own entries. All approved + panel complete + verdicts PASS → tech/QC submits → AWAITING_RELEASE. Failing lot: submit-with-justification → NEEDS_ATTENTION → QC override (audited, printed as deviation) or retest.
4. **Release** — QC clicks Approve & Release: gate re-checked under lock → serial issued → context built once → PDF rendered → snapshot persisted → lot RELEASED → audit — one transaction.
5. **After release** — every view and download reads the snapshot; the lot is terminal; corrections create Revision 2 superseding the original; History/Archive is the single search surface.

---

## H. Migration sequence

| # | Migration | Phase |
|---|---|---|
| 1 | `result_imports.file_hash` scoped unique index | 1 |
| 2 | `test_results.created_by_id` (nullable, FK users) | 2 |
| 3 | `coa_snapshots` + `coa_serial_counters` | 2 |
| 4 | partial unique index `uq_release_released` | 2 |
| 5 | `lab_info` accreditation columns | 3 |
| 6 | `test_results.product_id` (nullable, FK products) — composite attribution | 3 |

Deploy choreography (one maintenance event after Phase 1 or 2): VPS DB backup (sqlite3 `.backup`) → push main (auto-deploy) → alembic upgrade → register reload with the fixed loader → snapshot backfill → smoke test (login, tracker, release one test lot, download its COA).

---

## I. Test strategy per layer

- **State machine:** exhaustive (from, to, role, guard) matrix — pure, fast.
- **Spec engine:** golden table from real `product_test_mapping.csv` spec formats.
- **Snapshot immutability:** the C.7 integration test.
- **AuthZ:** parametrized roles × endpoints matrix.
- **Release race:** two concurrent approve calls → exactly one RELEASED (constraint catches the loser).
- **Importer:** the three named gaps + a contract test that `buildRowActions` output for a payload with `existing_result.matched_by="test_name"` is `replace`.
- **Loader (Phase 5):** fixture spreadsheet exercising standard/parent/composite/NEEDS METALS/dup-RefID rows + reconciliation report assertion.
