# Technical Handoff: Results Importer Feature

> **Status:** Architecture resolved (grilled & locked). This document is the authoritative
> spec. Build the feature from this version, not the original draft.

## Objective

Build a new `feature/results-importer` worktree and implement a standalone Results Importer
workflow for lab-result PDFs. Users drag and drop lab COA PDFs, OpenRouter extracts results,
the user reviews the matched sample/lot, confirms field-level actions, and applies selected
values as draft test results with the source PDF attached.

The Results Importer becomes the **only** PDF→results path in the app. The legacy folder-watch
parsing pipeline is removed as part of this work (see "Legacy Removal").

## Worktree Setup

- Current repo: `/Users/gregsimek/Code/COA-creator`
- First commit the existing `AGENTS.md` documentation update on `main`.
- Create sibling worktree:

```bash
git worktree add ../COA-creator-results-importer -b feature/results-importer main
```

- Do not commit local sample PDFs/backups from `files_to_import/`; use them only as manual QA fixtures.

## Legacy Removal (do this first, in the worktree)

The old folder-watch pipeline was built early and never used. Remove it entirely — the importer
replaces it. Verified blast radius: watcher is CLI-only, has no app-startup hook, no frontend, and
nothing FKs to `parsing_queue`, so removal is clean.

Delete / remove:
- `backend/app/services/pdf_watcher_service.py` (and its export in `services/__init__.py`)
- `backend/app/services/pdf_parser_service.py`
- `backend/app/services/pydantic_ai_provider.py` (Gemini provider — replaced by OpenRouter)
- `backend/app/models/parsing.py` (`ParsingQueue`) + its export in `models/__init__.py`
- The `parsing_queue` table (Alembic down-migration; no other table FKs to it)
- The `pdf parse` / `pdf watch` CLI commands in `backend/app/cli.py`
- Watcher config keys in `config.py`: `pdf_watch_folder`, `watch_folder_path`,
  `enable_folder_monitoring`, `watch_interval`
- Associated tests for the above (`test_pdf_parsing.py`, `test_pydantic_ai_provider.py`,
  watcher/parser cases in `test_comprehensive_coverage.py`)

Keep the *concept* of a mock extraction provider — reimplement it fresh for the importer (see
"LLM / Extraction") so backend tests never hit the network.

## Core Workflow

1. User opens the new `/results-importer` page.
2. User drops up to 5 PDFs, max 10 MB each, max 8 pages each.
3. Backend hashes (SHA-256) and stores each PDF, creates one `result_imports` row per PDF, and
   enqueues serial background parsing. A confirmed-hash match short-circuits (see "Dedup").
4. The in-process serial worker sends extracted text plus base64 PDF input to OpenRouter, one
   call at a time.
5. Backend stores structured extraction, warnings, usage metadata, and deterministic lot-match
   candidates; status moves to `needs_confirmation` (or `failed`).
6. Frontend polls; when ready, user reviews PDF preview beside extracted fields.
7. User confirms the correct active lot or manually links one.
8. User chooses per-row actions: apply, replace draft value, skip, or create ad-hoc mapped test.
9. On confirm (single atomic transaction), backend applies selected rows as draft `TestResult`s,
   attaches the PDF to `Lot.attached_pdfs`, writes audit/ledger data, completes any matching
   retest, and recalculates lot status.
10. Release/approval views show imported PDFs in the existing left-side source-documents panel,
    newest import first.

## LLM / Extraction (OpenRouter, global)

OpenRouter **replaces** Gemini everywhere — there is no Gemini/PydanticAI path left after the
legacy removal. The importer's extraction service is the sole AI consumer.

- Settings: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (default `google/gemini-2.5-flash`).
- Use OpenRouter chat completions with **structured JSON schema output**.
- Provide a `MockExtractionProvider` selected via config (e.g. `ai_provider="mock"`) so tests and
  local dev never hit the network.
- If `OPENROUTER_API_KEY` is missing, upload fails with a clear configuration error (surfaced in
  the UI as an upload error).
- Reject PDFs over 8 pages. If OpenRouter rejects PDF/file input but local text extraction
  succeeded, retry text-only.

### Universal extraction schema + normalization profiles

The LLM extracts into **one universal, lab-agnostic schema**; deterministic app code normalizes.

LLM returns:
- sample identifiers (reference/lot/sublot/sample numbers as printed)
- report metadata: `date_tested`, report/issue date, received date
- a `lab_name` / format hint
- a flat list of raw rows: `test_name_raw`, `result_value_raw`, `unit_raw`, `limit_raw`, plus
  optional `per_serving`, `lod`, `loq`
- per-field confidence where available

App-side normalization (deterministic, unit-tested — **not** in the prompt) picks a profile from
the `lab_name` hint and applies the rules in "Data Normalization". Unknown formats fall through to
a generic profile and surface as low-confidence for human review.

## Background Processing

- **In-process serial worker**: a module-level `asyncio` queue with a single consumer drains
  uploads one OpenRouter call at a time. No Celery/RQ/broker.
- Status persists in `result_imports`.
- The list endpoint runs a **stale reaper**: rows stuck in `processing` past a threshold are
  marked `failed` (handles server restart mid-parse).
- **Retry**: a failed/stale import can be re-queued from its already-stored PDF (no re-upload).

## Backend Design

`result_imports` table/model:

- `id`, `original_filename`, `storage_key`, `file_hash` (SHA-256), `status`
- statuses: `processing`, `needs_confirmation`, `confirmed`, `failed`, `cancelled`, `reverted`
- `extracted_data`, `match_candidates`, `warnings`, `error_message`
- `selected_lot_id`, `confirmed_by_id`, `confirmed_at`
- `openrouter_model`, token/usage metadata if returned
- timestamps/user fields

Apply-ledger table/model (drives safe revert):

- import id, lot id, action type
- created result ids
- updated result ids with old/new field values
- PDF attachment added (storage_key)
- enough fidelity to verify rows are still draft-and-unchanged before reverting

## API Surface

- `POST /api/v1/result-imports` — multipart upload, up to 5 PDFs; creates rows, enqueues parsing.
- `GET /api/v1/result-imports` — paginated queue/list; runs the stale-`processing` reaper.
- `GET /api/v1/result-imports/{id}` — detail: extracted rows, candidates, status.
- `GET /api/v1/result-imports/link-candidates?search=...` — active lot search.
- `POST /api/v1/result-imports/{id}/confirm` — body has `lot_id` + row actions; requires ≥1
  applied row; single atomic transaction; idempotency guard (only from `needs_confirmation`).
- `POST /api/v1/result-imports/{id}/retry` — re-queue a `failed`/stale import's stored PDF.
- `POST /api/v1/result-imports/{id}/cancel` — unconfirmed only; deletes stored PDF, keeps row.
- `POST /api/v1/result-imports/{id}/revert` — confirmed only, if rows still draft and unchanged
  per the ledger; allowed for original confirmer or QC/admin.

## Permissions

- Upload / confirm / apply: **Lab Tech and up** (Lab Tech, QC Manager, Admin). Read-Only excluded.
  Safe because results land as DRAFT, so QC still gates release.
- Revert: original confirmer or QC/admin.

## Matching Rules

OpenRouter extracts identifiers; **app code chooses and ranks candidates** (the LLM must not
directly choose the authoritative lot). Candidate lots are active only:

- `awaiting_results`, `partial_results`, `needs_attention`, `under_review`, `awaiting_release`

Match against:

- lot reference number, lot number, sublot number
- composite/component batch number
- extracted sample number
- filename hints

A high-confidence match pre-selects the lot, but a human confirm click is always required.
Low-confidence/no-match imports remain `needs_confirmation` for manual rescue.

## Result Application Rules

- Always require human confirmation.
- Save imported values as draft results only.
- Blank draft/spec rows: apply directly if selected.
- Non-empty draft rows: require explicit replace.
- Approved rows: importer cannot modify them.
- Unmatched extracted tests: user must map to an active Lab Test Type before creating an ad-hoc
  result.
- Ad-hoc tests use catalog default unit/spec/method; lab-provided limits go into notes/import
  metadata.
- Import cannot confirm with zero applied result rows.
- Partial apply is allowed; skipped extracted rows remain in import metadata.

### Apply write-path (atomicity)

The entire confirm/apply is a **single DB transaction** — create/replace draft `TestResult`s,
append the PDF to `Lot.attached_pdfs`, write the ledger row, write audit logs, complete any
matching retest, and recalculate lot status all commit together or not at all. Nothing slow or
non-deterministic (the OpenRouter call) is inside it. Idempotency guard: confirm is rejected
unless the import is in `needs_confirmation`.

## Data Normalization

- Preserve result display text: `1,300`, `<100`, `<LOD`, `Negative`.
- Normalize test names:
  - `Total Yeast & Mold Count` -> `Yeast & Mold`
  - `E. Coli` -> `Escherichia coli`
  - `Salmonella` -> `Salmonella spp.`
  - metals by exact analyte names: Lead, Arsenic, Cadmium, Mercury
- For Harken metals:
  - save concentration result in `ug/g`, normalized to ppm-compatible units.
  - do not save per-serving result as the primary value.
  - store LOD/LOQ and per-serving details in metadata/notes.
- Use target/catalog unit in `TestResult.unit`; store lab-reported unit separately.
- Use `Date Tested`; fallback to report/issue date, then received date.
- Serving size is compare-only; show mismatch warning, do not block or update products.

## Storage, Hashing & Dedup

- Hash PDF bytes (SHA-256) on upload; store as `result_imports.file_hash`.
- **Dedup only against `confirmed` imports, globally.** On upload, if a `confirmed` import has the
  same hash, short-circuit: don't store a second copy, don't call OpenRouter — surface/open the
  original with an explicit message: "this PDF was already imported on lot X on [date] by [user]."
- Hashes matching `failed`/`cancelled`/`processing` imports do **not** block (that's the retry
  path).
- Reuse the existing storage service. Failed/cancelled imports delete stored bytes but keep the
  `result_imports` row (hash history + audit survive). Confirmed imports keep PDFs attached.

## Source-PDF Surfacing (Release left panel)

Imported PDFs must appear in the existing Release/approval source-documents viewer, newest first.

- **Migrate `Lot.attached_pdfs` from a flat list of filename strings to a list of objects**:
  `{filename, storage_key, source ("import"|"manual"|"legacy"), import_id, added_at}`.
  One-shot backfill: existing strings become
  `{filename, storage_key: <derived>, source: "legacy", import_id: null, added_at: lot.created_at}`.
- **Rework `release_service.get_source_pdfs()`** (currently an unordered `set` union of
  `Lot.attached_pdfs` strings + distinct `TestResult.pdf_source`) into an **ordered,
  storage-key-deduped merge**:
  - read object-shaped `attached_pdfs` (use each entry's real `added_at`)
  - union with `TestResult.pdf_source` entries (order those by the result's `created_at`)
  - de-dup by normalized storage key, preferring the `attached_pdfs` object's timestamp on
    collision; fall back to the result's `created_at` only when there's no object entry
  - return newest-first
- The existing Release UI renders whatever ordered list it receives — no frontend change needed
  there. The importer-applied results carry `pdf_source = <imported storage_key>`, so the same PDF
  appears via both sources and is de-duped to one entry.
- Filename/storage-key convention stays compatible with `_normalize_pdf_storage_key` (the `pdfs/`
  prefix handling) so serving via the existing source-pdf endpoint keeps working.

## Frontend Design

- Single route `/results-importer` (list/inbox page) + sidebar item under Sample Management.
  There is no separate review route/URL — the importer never deep-links into a specific import.
- The list page owns uploads, filtering, search, and per-row actions (retry/cancel/revert).
  Clicking any row (or its "Review" action) opens a near-fullscreen review modal
  (`ResultsImporterReviewModal`, 95vw x 92vh) with the PDF preview on the left and the extracted
  result review pane on the right, split by a draggable divider.
- The modal header has queue prev/next chevrons to step through other `needs_confirmation`
  imports without closing back to the list.
- Applying (confirm) auto-advances the modal to the next pending import in the queue, and closes
  the modal once the queue is empty. Cancel/Revert close the modal after their confirm dialog.
- Overlay click is blocked (no accidental dismiss mid-review); Esc/X close the modal immediately
  without a confirmation prompt.
- **Progress**: TanStack Query polling via `refetchInterval` while any import is `processing`;
  stop polling once everything is terminal. No WebSocket/SSE.
- **Review state**: per-row choices (lot selection, apply/replace/skip, ad-hoc mappings) live in
  local React state and submit as one confirm payload (matches the atomic confirm; an abandoned
  review leaves zero server cruft).
- Existing Sample Modal upload stays attachment-only.
- Show low-confidence warnings below `0.70`, but allow user-applied fields.
- Missing OpenRouter config surfaces as a clear upload error.

## PDF Handling

- Use existing storage service and source-PDF serving pattern.
- Failed and cancelled imports delete stored PDFs but keep import records.
- Confirmed imports keep PDFs attached.
- Revert removes import-added PDFs from lot/storage only if no remaining source references use
  them.
- Release source-PDF list ordered newest-imported first (see "Source-PDF Surfacing").

## Workflow Edge Cases

- If linked lot is `awaiting_release`, applying imported data pulls it back into review via
  existing status recalculation.
- Returned release-thread lots remain unresolved; importer does not satisfy return-response notes.
- Pending retest lots are allowed; result updates must reuse existing retest completion/audit
  logic.
- Multi-SKU composite PDFs apply once at lot level.
- Multi-sample PDFs are rejected and require splitting/re-upload.
- Duplicate confirmed PDF hash auto-links/opens the original confirmed import, not re-import.

## Tests

Backend:

- mocked OpenRouter structured extraction (`MockExtractionProvider`)
- text+PDF fallback
- missing API key
- page/file/batch limits
- stale processing handling + retry re-queue
- deterministic candidate matching
- confirm/upsert/conflict handling
- atomic apply rollback on mid-transaction failure
- approved-row blocking
- cancel cleanup
- safe revert (and revert refusal when a row was edited/approved)
- confirmed-hash dedup short-circuit
- awaiting-release status pullback
- retest integration
- `get_source_pdfs()` newest-first ordering + storage-key de-dup
- `attached_pdfs` object backfill migration

Frontend:

- upload queue
- polling statuses
- manual lot link
- PDF preview
- conflict default keep-existing
- unmatched-test mapping
- low-confidence warnings
- cancel/revert eligibility

Manual QA:

- use `/Users/gregsimek/Code/COA-creator/files_to_import`
- verify Harken metals and Daane micro imports
- verify draft results in Sample Tracker
- verify source PDFs appear in Release left panel newest-first
