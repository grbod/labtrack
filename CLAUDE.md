# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

LabTrack is a lab testing and COA management system that replaces the legacy Excel-based workflow with a comprehensive web application. The system handles lab sample tracking, PDF parsing, test result management, approval workflows, and automated COA generation.

## Architecture

### Technology Stack
- **Backend**: Python 3.10+ with FastAPI, SQLAlchemy ORM, Pydantic settings
- **Frontend**: React + TypeScript + Vite + Tailwind CSS
- **Database**: SQLite (upgradeable to PostgreSQL)
- **AI Integration**: LLM-based lab-report extraction via OpenRouter (`app/services/result_extraction_provider.py`)
- **PDF Processing**: PyPDF2 for reading; ReportLab for COA generation
- **Authentication**: JWT-based with role-based access control

### Project Structure
```
labtrack/
├── backend/
│   ├── app/
│   │   ├── models/      # SQLAlchemy ORM models
│   │   ├── services/    # Business logic layer
│   │   ├── api/         # FastAPI endpoints
│   │   ├── utils/       # Helper utilities
│   │   ├── database.py  # Database configuration
│   │   └── config.py    # Application settings
│   └── tests/           # Pytest test suite
├── frontend/            # React + Vite frontend
└── templates/           # Document templates
```

### Request Flow (Backend)
Endpoints in `backend/app/api/v1/endpoints/` handle routing and auth only; they call services in `backend/app/services/` which contain all business logic and persistence via SQLAlchemy models. Pydantic request/response schemas live in `backend/app/schemas/`. Adding a feature typically touches all four layers: model → schema → service → endpoint.

### Data Flow (Frontend)
`src/api/client.ts` is the shared axios instance (JWT auth header, base URL). Per-resource API modules in `src/api/*.ts` are wrapped by TanStack Query hooks in `src/hooks/use*.ts`, which pages and components consume; components never call axios directly. Auth state lives in a zustand store (`src/store/auth.ts`). A full-stack change typically mirrors the backend layers: `src/types/index.ts` → `src/api/` → `src/hooks/` → page/component.

## Key Features

### 1. Sample Management
- Create lots with auto-generated reference numbers (YYMMDD-XXX)
- Support for standard lots, parent lots with sublots, and multi-SKU composites
- Product catalog with standardized naming

### 2. Result Import (lab-report extraction)
- Drag-and-drop upload of a lab-report PDF
- Optional email intake: forward reports to a watched M365 mailbox (`EMAIL_INTAKE_*` env vars, off by default) — see `docs/email-intake-setup.md`
- LLM extraction via OpenRouter parses the report into candidate test rows
- A review modal lets the user confirm/edit the extracted rows before applying
- Confirmed rows are written as **DRAFT** test results for QC approval
- (There is no mock provider, parsing queue, or folder watcher — those are gone)

### 3. Approval & Release Workflow
- Test results: **DRAFT → APPROVED** (QC Manager/Admin)
- Lot lifecycle runs through the **canonical state machine** (8 statuses),
  enforced server-side — see "Release Flow & State Machine" below
- A **release gate** must pass before a COA can issue
- Role-based permissions (Admin, QC Manager, Lab Tech, Read-Only)
- Bulk approval; complete audit trail

### 4. COA Generation & Snapshots
- Rendered from the canonical `coa_context_builder` context (ReportLab PDF)
- On release the COA is frozen as an **immutable snapshot** with an issued
  serial `COA-YYYY-NNNNNN`; released COAs are served from the snapshot and
  never regenerated
- Void returns a lot to the queue; re-release mints the next snapshot revision

## Commands

A root `Makefile` wraps the common workflows: `make dev` (backend on :8009 + frontend on :5173), `make test`, `make format` (black + isort), `make lint` (flake8), `make migrate` (alembic upgrade head).

### Running the Application Locally
```bash
# Backend: ALWAYS use backend/.venv (NOT the stale backend/venv, NOT system Python)
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --port 8009

# Frontend (proxies /api/v1 to the backend)
cd frontend
npm run dev   # serves on http://localhost:5173
```

Startup notes:
- Check ports first: `lsof -i :8009 -i :5173 -sTCP:LISTEN`. If the backend port is held but unresponsive, a crashed uvicorn reloader parent may still own the socket; kill it and restart.
- Run both as background tasks and verify: frontend `curl http://localhost:5173/` should return 200; backend `/docs` is disabled (404 is normal), so verify with an API route instead, e.g. `curl -X POST http://localhost:8009/api/v1/auth/login` returning 422 means the app is alive.
- If the backend crashes on import with `ModuleNotFoundError`, a dependency is missing from `.venv`. Install with uv: `cd backend && uv pip install <package> --python .venv/bin/python` (`.venv` has no pip module). The `--reload` watcher does NOT recover from an import crash at startup; restart uvicorn after installing.
- Successful startup runs Alembic migrations and the seed check automatically (look for "Database migrations applied successfully" in the log).

### Backend Tests
```bash
cd backend
.venv/bin/python -m pytest tests/ -v

# Single test file or test (pytest.ini enables coverage by default; --no-cov speeds up iteration)
.venv/bin/python -m pytest tests/test_lot_service.py -v --no-cov
.venv/bin/python -m pytest tests/test_lot_service.py::test_name -v --no-cov
```

### Frontend
```bash
cd frontend
npm run build      # tsc -b + vite build (catches type errors)
npm run lint       # eslint
npm run test       # vitest watch mode
npm run test:run   # vitest single run (CI)
```

### Default Login Credentials
- **Admin**: username: `admin`, password: `admin123`
- **QC Manager**: username: `qcmanager`, password: `qc123`
- **Lab Tech**: username: `labtech`, password: `lab123`

## Service Layer Pattern

All services inherit from `BaseService` and follow this pattern:
```python
# Services don't take database in constructor
service = ServiceName()

# Database session is passed as first parameter to methods
result = service.method_name(db, other_params...)
```

## Common Issues & Solutions

### Issue: Service method calls missing database parameter
**Solution**: Always pass `db` as the first parameter to service methods

### Issue: Excel export errors
**Solution**: Use BytesIO buffer:
```python
import io
buffer = io.BytesIO()
df.to_excel(buffer, index=False)
excel_data = buffer.getvalue()
```

### Issue: Status transition errors
**Solution**: A lot's status must change through `LotWorkflowService` (see
"Release Flow & State Machine"), never a raw `lot.status = ...` assignment — the
enforcement guard rejects raw assignments. Test results go DRAFT → APPROVED.

### Issue: Authentication not working
**Solution**: Ensure UserService is used for authentication, not hardcoded values

## UI Terminology

### Sample Tracker Page
The "Sample Tracker" page displays all submitted samples/lots with their workflow status.

**Status Labels (display text → backend enum). There are 8 lot statuses:**
| Display Label | Backend Value | Description |
|---------------|---------------|-------------|
| Awaiting Results | `awaiting_results` | Sample submitted, no results yet |
| Partial Results | `partial_results` | Some results in, required tests still missing |
| Needs Attention | `needs_attention` | All required tests in but one or more FAIL specs |
| Under Review | `under_review` | All required tests in and passing; awaiting QC |
| Awaiting Release | `awaiting_release` | Submitted to the Release Queue for QC release |
| Approved | `approved` | Legacy/transitional; not part of the normal flow |
| Released | `released` | COA released (immutable snapshot issued) |
| Rejected | `rejected` | QC rejected; can be resubmitted to Under Review |

Frontend label source of truth: `frontend/src/lib/status-config.ts`.

## Release Flow & State Machine

### Canonical lot state machine (enforced)
Lot status is owned by `app/workflow/lot_workflow_service.py`. `settings.workflow_enforce_transitions` defaults to **True**: a raw `lot.status = ...` on a persisted lot raises. Change status only via:
- `LotWorkflowService().transition(db, lot, target, actor, ...)` — validated gate/manual transitions; raises `WorkflowTransitionError` on a denied move.
- `.apply_auto(...)` — applies a status computed by `LotService.calculate_lot_status` (trigger="auto").
- `.apply_system(...)` — system moves the manual gates don't model (e.g. result-import pullback).
- `set_status_unchecked(lot, status)` — seed/fixture scaffolding only. Loaders/seeders set status at object construction (id is None → exempt).

`transition()` acquires a `SELECT ... FOR UPDATE` row lock on the lot (real on Postgres, no-op on SQLite).

### Release gate
Before a lot can go AWAITING_RELEASE → RELEASED the gate (`app/services/release_gate_service.py`) must pass:
- **Missing required lab tests** block (legacy-import lots exempt).
- **FAIL** verdicts block; a QC Manager/Admin **override** (with a reason) may release anyway — the reason prints on the COA as a **deviation**.
- **INDETERMINATE** verdicts are a non-blocking **warning**.
- Each **sensory/organoleptic** row of the product panel must be **attested** on that release; attested rows print "Pass".
- All test results must be APPROVED.
A blocked release returns HTTP 409 `{code, reason, missing_tests, failing_tests}`.

### Snapshots (immutability)
Releasing freezes an **immutable snapshot** (`coa_snapshot_service.create_snapshot`) inside the release transaction — an issued serial `COA-YYYY-NNNNNN` (yearly reset), the frozen render context, and the rendered PDF. Released COAs (preview-data, preview/download PDFs) are served **from the snapshot**, never regenerated; a released COA with no snapshot 404s and points at the backfill script. **Void** (admin) voids the snapshot and returns the lot to AWAITING_RELEASE; **re-release** creates the next revision (`supersedes_id`) and keeps the voided one. At most one active (non-voided) snapshot per release (partial unique index).

Backfill snapshots for pre-snapshot released COAs:
```bash
cd backend && .venv/bin/python scripts/backfill_coa_snapshots.py --dry-run   # report only
cd backend && .venv/bin/python scripts/backfill_coa_snapshots.py --commit    # reconstructed snapshots (no serial)
```

## Database Models

### Core Models
- **User**: Authentication and roles
- **Product**: Standardized product catalog (204 products, 40 brands)
- **ProductTestSpecification**: Links products to required lab tests with acceptance criteria (954 specs seeded from legacy COA register)
- **Lot**: Production lots with parent/sublot relationships
- **TestResult**: Lab test results with approval status (+ `created_by_id`)
- **ResultImport / ResultImportLedger**: LLM-extracted lab-report import + review
- **COARelease**: Per-(lot, product) release record (+ deviation/void trail)
- **COASnapshot / COASerialCounter**: Immutable released-COA snapshot + serial issuance
- **ReleaseSensoryAttest**: QC sign-off of a sensory row for a release
- **AuditLog**: Complete audit trail

### Enums
- **UserRole**: ADMIN, QC_MANAGER, LAB_TECH, READ_ONLY
- **LotType**: STANDARD, PARENT_LOT, SUBLOT, MULTI_SKU_COMPOSITE
- **LotStatus** (8): AWAITING_RESULTS, PARTIAL_RESULTS, NEEDS_ATTENTION, UNDER_REVIEW, AWAITING_RELEASE, APPROVED (legacy/transitional), RELEASED, REJECTED
- **TestResultStatus**: DRAFT, APPROVED
- **COAReleaseStatus**: AWAITING_RELEASE, RELEASED

## Seed Data

The database is seeded on first startup via `backend/app/seed.py`:
- **Users**: 3 default users (admin, qcmanager, labtech)
- **Lab test types**: 235 types from `backend/seed_tests.csv`
- **Products**: 204 products from `product_seed_data.csv`
- **Product test specs**: 954 specs from `backend/product_test_mapping.csv` (links products to their required tests with acceptance criteria like "Negative", "< 10,000 CFU/g", "< 0.5 ppm")

Seed files:
- `product_seed_data.csv` - Brand, Product, Flavor columns
- `backend/seed_tests.csv` - Lab test type definitions
- `backend/product_test_mapping.csv` - Product-to-test mappings with specifications (derived from legacy `newcoaregister.csv`)

The seed has a **backfill mechanism**: if the DB has users but no product test specs (e.g. after a partial seed failure), `seed_if_empty()` will automatically populate the missing specs on next startup.

For existing databases, use the standalone script:
```bash
cd backend && python scripts/seed_product_test_specs.py
```

## Bulk Data Import (COA Register)

Loading real historical lab records from a "COA Register" spreadsheet (the lab's master log, e.g. `2.4.4 New COA Register.xlsx`) is a recurring task. The reusable loader is `backend/scripts/load_coa_register.py`. It wipes the existing per-lot lab data and recreates lots/sublots/composites/test-results/releases from the spreadsheet.

### Lot taxonomy (how register rows map to lots)
The register has one row per lab reference (`RefID`). Rows group into three lot types:
- **Single SKU (Standard lot)**: one row with a unique `Lot`. `lot_number` = `Lot`, `reference_number` = `RefID`, one product, one COA.
- **Parent lot + sublots**: multiple rows sharing the same `Lot` number (same product/SKU, a different `RefID` per batch). Becomes one `PARENT_LOT` (lot_number = the shared `Lot`, reference auto-generated `YYMMDD-XXX`), one product, and one `Sublot` per row (sublot_number = that row's `RefID`). One COA covers the master lot.
- **Multi-SKU composite**: multiple rows sharing the same `C…`-prefixed `RefID` (different SKUs combined under one COA). Becomes one `MULTI_SKU_COMPOSITE` (reference = the `C…` code), one `LotProduct` per distinct SKU (component `Lot` numbers go in `batch_number`), and one COA/release per product.
  - Edge case: a `C…` ref that is the **same SKU** across several lots loads as a **parent lot** (the model cannot hold one product twice in a composite); the component lots become its sublots.

### Status rules (per lot)
The lead row's `QC Approval`, the `ToPrint` flag, and whether the row has any results together set status:
- `QC Approval` populated **and not** `NEEDS METALS` → `RELEASED`, with a `COARelease(status=RELEASED)` per product and test results `APPROVED`. No COA PDF is generated (rendered on demand). Releases/approvals are attributed to the `qcmanager` user; the release note currently carries a **hardcoded** approver name (`"Loaded from COA register (QC: Tattyana Villegas)"`), NOT the per-row approver — known Phase 5 fix.
- `ToPrint = "NEEDS METALS"` → `PARTIAL_RESULTS` (micro tests in, metals pending). **Not** released, even when `QC Approval` is populated.
- `QC Approval` empty **but the row has results** → `AWAITING_RELEASE`. Appears in the **Release Queue**; results are marked `APPROVED` so a COA can generate on Approve & Release.
- `QC Approval` empty **and no results** → `AWAITING_RESULTS`. Appears in the Sample Tracker.

### Running the loader
```bash
cd backend
.venv/bin/python scripts/load_coa_register.py --file '<path.xlsx>' --dry-run   # report only (DEFAULT)
.venv/bin/python scripts/load_coa_register.py --file '<path.xlsx>' --commit    # backup + wipe + load
```
- **Always `--dry-run` first** and read the report (lot counts by type, products to create, flagged rows).
- `--commit` copies `labtrack.db` to `labtrack.db.bak-<ts>` first, then wipes and loads in a single transaction (atomic: any error rolls back the wipe too).
- Idempotent: re-running wipes and reloads; auto-created products persist and are matched (not duplicated) on the next run.

### Wiped vs kept
- **Wiped** (per-lot lab data): lots, sublots, lot_products, test_results, coa_releases, coa_history, retest_requests/items, email_history, audit_logs/annotations, parsing_queue; resets daane_coc_daily_counters.
- **Kept** (reference/config): users, products, product_test_specifications, lab_test_types, customers, lab_info, coa_category_order, daane_test_mapping, email_templates.

### Things to watch out for
- **Products auto-create + get a test panel**: a SKU not already in the catalog is created (brand/product/flavor/size). Identity includes size, so the size-less seed catalog rarely matches and many new products are expected. Each created (or earlier spec-less) product is given a **required test panel** = the union of test columns populated across that SKU's rows, with the **4 common micro** (Total Plate Count, Yeast & Mold, Escherichia coli, Salmonella spp.) as the floor when none are populated. **Metals are forced onto `NEEDS METALS` SKUs** so those lots stay genuinely partial. Products that already have specs (the seed catalog) are left untouched.
- **Verify brand spellings in the source first**: product identity is `(brand, product, flavor, size)`, so a misspelled brand creates a **duplicate product** on import (e.g. "Wellious" once mistyped "Welliouc" produced two products). Fix the spreadsheet, not the DB, then re-import.
- **Test column renames**: columns map to lab test types by name, with three renames: `Yeast/Mold` to `Yeast & Mold`, `E. Coli` to `Escherichia coli`, `Salmonella` to `Salmonella spp.`. Unmapped test columns are reported.
- **De-dup/flags**: a `RefID` reused across rows gets a `-2` suffix on the second; a `Lot` cell of `"NEEDS LOT"` falls back to the `RefID`; `NEEDS METALS` rows load as `PARTIAL_RESULTS` (not released) with whatever results they have (metals blank). Eyeball the flag list after every run.
- **Enums store by NAME** in SQLite (`RELEASED`, `PARENT_LOT`, `AWAITING_RESULTS`), not the lowercase value. Raw-SQL checks must use the uppercase name; the API still serializes the lowercase value.
- **`/archive` page_size max is 100.** Released COAs surface in History/Archive (one item per release). The Release Queue's "Recently Released" only shows the last N days, so use History (widen the date filter) to see older releases.
- **`--commit` with the dev server running** is fine (SQLite locking); the server shares the DB, so just refresh the UI to see new data.
- **VPS**: the loader targets the local dev DB. To update production, run the same script on the VPS (`/opt/labtrack/backend`) against its own `labtrack.db`.

## Testing

See Commands above for invocation. Always use the venv Python (`backend/.venv/bin/python`), not system Python.

Known issues:
- Some test files have pre-existing import errors (`test_result_service` module missing). `slowapi` was installed into `.venv` on 2026-06-12, so those import errors are resolved.
- pytest markers available: `slow`, `integration`, `unit` (e.g. `-m "not slow"`).

## Development Guidelines

1. **Always use database transactions** - The base service handles this automatically
2. **Follow the service pattern** - Don't access models directly from UI
3. **Add audit trails** - Use BaseService for automatic audit logging
4. **Validate user permissions** - Check roles before sensitive operations
5. **Handle errors gracefully** - Show user-friendly messages in the UI
6. **Test naming** - Backend suites are `test_<feature>.py`; frontend tests are `<Component>.test.tsx` (Vitest + Testing Library)
7. **Format before committing** - `make format` (black + isort) and `make lint` for Python; `npm run lint` for frontend changes

## Deployment

- **VPS**: 155.138.211.71 (Vultr)
- **Project path**: `/opt/labtrack`
- **Backend**: uvicorn on port 8009 at `/opt/labtrack/backend`
- **Database**: `/opt/labtrack/backend/labtrack.db`
- **Auto-deploy**: pushes to `main` are automatically pulled to VPS

## Future Enhancements

1. **Email Notifications**: Implement approval notifications
2. **Advanced Reporting**: Add trend analysis and KPI dashboards
3. **API Integration**: RESTful API for external systems
4. **Multi-tenancy**: Support for multiple companies/divisions