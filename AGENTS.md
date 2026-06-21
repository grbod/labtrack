# Repository Guidelines

This file provides guidance to coding agents when working with code in this repository.

## Overview
LabTrack is a lab testing and COA management system that replaces the legacy Excel-based workflow with a web application. It handles lab sample tracking, PDF parsing, test result management, approval workflows, and automated COA generation.

## Architecture

### Technology Stack
- Backend: Python 3.10+ with FastAPI, SQLAlchemy ORM, and Pydantic settings
- Frontend: React + TypeScript + Vite + Tailwind CSS
- Database: SQLite locally, upgradeable to PostgreSQL
- AI integration: PydanticAI with Google Gemini; mock provider available
- PDF/document processing: PyPDF2 and python-docx
- Authentication: JWT-based with role-based access control

### Project Structure & Module Organization
Backend code lives in `backend/app`, with `api`, `services`, `models`, and `schemas` covering routing, logic, persistence, and IO contracts; helpers sit in `core` and `utils`. Alembic migrations and generated templates are in `backend/migrations` and `backend/templates`, while runtime uploads land in `backend/uploads`. The Vite + React frontend is colocated under `frontend/src`, with static assets in `frontend/public` and build output in `frontend/dist`. Repo-level automation (`Makefile`, scripts, env samples) stays at the root.

```text
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
Endpoints in `backend/app/api/v1/endpoints/` handle routing and auth only. They call services in `backend/app/services/`, which contain business logic and persistence via SQLAlchemy models. Pydantic request/response schemas live in `backend/app/schemas/`. Adding a backend feature usually touches model, schema, service, and endpoint layers.

### Data Flow (Frontend)
`src/api/client.ts` is the shared axios instance with JWT auth header and base URL. Per-resource API modules in `src/api/*.ts` are wrapped by TanStack Query hooks in `src/hooks/use*.ts`, which pages and components consume. Components should not call axios directly. Auth state lives in `src/store/auth.ts`. A full-stack change usually mirrors backend layers with `src/types/index.ts`, `src/api/`, `src/hooks/`, and a page/component.

## Key Features
- Sample management: lots with auto-generated reference numbers (`YYMMDD-XXX`), standard lots, parent lots with sublots, multi-SKU composites, and product catalog naming.
- PDF processing: drag-and-drop PDF upload, AI-powered extraction that is currently mock-backed but ready for a real provider, manual review queue for low-confidence extractions, and folder watching.
- Approval workflow: Draft -> Reviewed -> Approved, role permissions, bulk approvals, and audit trail.
- COA generation: approved test results, multiple templates, Word export, and batch generation.

## Build, Test, and Development Commands
Run `make install` or scoped install targets after cloning. `make dev` launches FastAPI on `:8009` and the Vite dev server on `:5173`; `make backend` or `make frontend` targets a single stack. CI-style invocations include `cd frontend && npm run build` for optimized bundles and `cd backend && uvicorn app.main:app --workers 4` for production smoke tests.

The root `Makefile` wraps common workflows: `make dev`, `make test`, `make format` (black + isort), `make lint` (flake8), and `make migrate` (alembic upgrade head).

### Running the Application Locally
Always use `backend/.venv`, not the stale `backend/venv` and not system Python.

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --port 8009

cd frontend
npm run dev
```

The frontend serves on `http://localhost:5173` and proxies `/api/v1` to the backend.

Startup notes:
- Check ports first: `lsof -i :8009 -i :5173 -sTCP:LISTEN`. If the backend port is held but unresponsive, a crashed uvicorn reloader parent may still own the socket; kill it and restart.
- Run both as background tasks and verify. Frontend `curl http://localhost:5173/` should return 200. Backend `/docs` is disabled, so 404 is normal; verify with an API route such as `curl -X POST http://localhost:8009/api/v1/auth/login`, where 422 means the app is alive.
- If the backend crashes on import with `ModuleNotFoundError`, install the missing dependency into `.venv` with `cd backend && uv pip install <package> --python .venv/bin/python`. The `.venv` has no pip module. The `--reload` watcher does not recover from an import crash at startup, so restart uvicorn after installing.
- Successful startup runs Alembic migrations and the seed check automatically; look for `Database migrations applied successfully` in the log.

### Backend Tests
```bash
cd backend
.venv/bin/python -m pytest tests/ -v

# Single test file or test. pytest.ini enables coverage by default; --no-cov speeds iteration.
.venv/bin/python -m pytest tests/test_lot_service.py -v --no-cov
.venv/bin/python -m pytest tests/test_lot_service.py::test_name -v --no-cov
```

### Frontend
```bash
cd frontend
npm run build      # tsc -b + vite build; catches type errors
npm run lint       # eslint
npm run test       # vitest watch mode
npm run test:run   # vitest single run / CI
```

### Default Login Credentials
- Admin: username `admin`, password `admin123`
- QC Manager: username `qcmanager`, password `qc123`
- Lab Tech: username `labtech`, password `lab123`

## Coding Style & Naming Conventions
Python uses 4-space indentation, snake_case modules, and descriptive router/service names. Run `make format` before `make lint`; mypy can be run with `mypy app/` when needed. Define Pydantic models in `schemas` with PascalCase names and keep response/request objects versioned.

Frontend TypeScript follows ESLint + React Hooks rules. Use PascalCase for components, camelCase for hooks/utilities, and colocate files with their feature. Run `npm run lint` inside `frontend` before committing UI work.

## Service Layer Pattern
All services inherit from `BaseService` and follow this pattern:

```python
# Services do not take database in constructor.
service = ServiceName()

# Database session is passed as first parameter to methods.
result = service.method_name(db, other_params...)
```

Do not access models directly from UI code. Use services for backend business logic and persistence, and use BaseService for automatic audit logging where applicable.

## Development Guidelines
1. Always use database transactions; the base service handles this automatically.
2. Follow the service pattern and always pass `db` as the first parameter to service methods.
3. Add audit trails for sensitive or state-changing actions.
4. Validate user permissions and roles before sensitive operations.
5. Handle errors gracefully with user-friendly UI messages.
6. Backend test suites are named `test_<feature>.py`; frontend tests are named `<Component>.test.tsx`.
7. Format before committing: `make format` and `make lint` for Python; `npm run lint` for frontend changes.

## Testing Guidelines
Backend tests live in `backend/tests` and run via `make test` (`pytest -v --cov=app`) or `.venv/bin/python -m pytest tests/ -v`. Add fixtures beside the code they serve and regenerate `coverage.xml` locally; avoid lowering existing coverage. Frontend interaction and utility tests rely on Vitest + Testing Library, using `npm run test` or `npm run test:run`.

Known issues:
- Some test files have had pre-existing import errors around `test_result_service`; verify before treating these as regressions.
- `slowapi` was installed into `.venv` on 2026-06-12, so related import errors should already be resolved.
- Pytest markers available: `slow`, `integration`, and `unit`, for example `-m "not slow"`.

## Common Issues & Solutions
- Service method calls missing database parameter: always pass `db` as the first parameter.
- Excel export errors: use a `BytesIO` buffer.
- Status transition errors: follow valid transitions for TestResult and Lot.
- Authentication not working: use UserService for authentication, not hardcoded values.

```python
import io

buffer = io.BytesIO()
df.to_excel(buffer, index=False)
excel_data = buffer.getvalue()
```

Valid status transitions:
- TestResult: Draft -> Reviewed -> Approved
- Lot: Pending -> Tested -> Approved -> Released

## UI Terminology

### Sample Tracker Page
The Sample Tracker page displays all submitted samples/lots with their workflow status.

| Display Label | Backend Value | Description |
| --- | --- | --- |
| Awaiting Results | `pending` | Sample submitted, no test results yet |
| Partial Results | `partial_results` | Some results received, more expected |
| Under QC Review | `under_review` | All results in, awaiting QC approval |
| Approved | `approved` | QC approved, ready for COA generation |
| Released | `released` | COA generated and published |
| Rejected | `rejected` | QC rejected, can be retried |

## Database Models

### Core Models
- User: authentication and roles
- Product: standardized product catalog, seeded with 204 products across 40 brands
- ProductTestSpecification: links products to required lab tests with acceptance criteria; 954 specs are seeded from the legacy COA register
- Lot: production lots with parent/sublot relationships
- TestResult: lab test results with approval status
- ParsingQueue: PDF parsing queue and status
- AuditLog: complete audit trail

### Enums
- UserRole: `ADMIN`, `QC_MANAGER`, `LAB_TECH`, `READ_ONLY`
- LotType: `STANDARD`, `PARENT_LOT`, `SUBLOT`, `MULTI_SKU_COMPOSITE`
- LotStatus: `PENDING`, `TESTED`, `APPROVED`, `RELEASED`, `REJECTED`
- TestResultStatus: `DRAFT`, `REVIEWED`, `APPROVED`

## Seed Data
The database is seeded on first startup via `backend/app/seed.py`:
- Users: 3 default users (`admin`, `qcmanager`, `labtech`)
- Lab test types: 235 types from `backend/seed_tests.csv`
- Products: 204 products from `product_seed_data.csv`
- Product test specs: 954 specs from `backend/product_test_mapping.csv`, derived from the legacy `newcoaregister.csv`

Seed files:
- `product_seed_data.csv`: Brand, Product, Flavor columns
- `backend/seed_tests.csv`: lab test type definitions
- `backend/product_test_mapping.csv`: product-to-test mappings with specifications such as `Negative`, `< 10,000 CFU/g`, and `< 0.5 ppm`

The seed has a backfill mechanism: if the database has users but no product test specs, `seed_if_empty()` automatically populates the missing specs on next startup.

For existing databases, use:

```bash
cd backend
python scripts/seed_product_test_specs.py
```

## Bulk Data Import (COA Register)
Loading real historical lab records from a COA Register spreadsheet, such as `2.4.4 New COA Register.xlsx`, is a recurring task. The reusable loader is `backend/scripts/load_coa_register.py`. It wipes existing per-lot lab data and recreates lots, sublots, composites, test results, and releases from the spreadsheet.

### Lot Taxonomy
- Single SKU / standard lot: one row with a unique `Lot`; `lot_number` is `Lot`, `reference_number` is `RefID`, one product, one COA.
- Parent lot + sublots: multiple rows sharing the same `Lot` number; creates one `PARENT_LOT`, one product, and one `Sublot` per row.
- Multi-SKU composite: multiple rows sharing the same `C...`-prefixed `RefID`; creates one `MULTI_SKU_COMPOSITE`, one `LotProduct` per distinct SKU, and one COA/release per product.
- Edge case: a `C...` ref that is the same SKU across several lots loads as a parent lot because the model cannot hold one product twice in a composite.

### Status Rules
- `QC Approval` populated and not `NEEDS METALS`: `RELEASED`, with a released COA per product and approved test results. No COA PDF is generated; it is rendered on demand. Releases/approvals are attributed to `qcmanager`, with the real approver name stored in the release note.
- `ToPrint = "NEEDS METALS"`: `PARTIAL_RESULTS`; not released, even when `QC Approval` is populated.
- `QC Approval` empty but the row has results: `AWAITING_RELEASE`; appears in the Release Queue and results are marked `APPROVED`.
- `QC Approval` empty and no results: `AWAITING_RESULTS`; appears in the Sample Tracker.

### Running the Loader
```bash
cd backend
.venv/bin/python scripts/load_coa_register.py --file '<path.xlsx>' --dry-run   # report only; default behavior
.venv/bin/python scripts/load_coa_register.py --file '<path.xlsx>' --commit
```

Always run `--dry-run` first and read the report. `--commit` copies `labtrack.db` to `labtrack.db.bak-<ts>` first, then wipes and loads in a single transaction. Re-running is idempotent: it wipes and reloads; auto-created products persist and are matched, not duplicated, on the next run.

### Wiped vs Kept
- Wiped per-lot lab data: lots, sublots, lot_products, test_results, coa_releases, coa_history, retest_requests/items, email_history, audit_logs/annotations, parsing_queue, and `daane_coc_daily_counters`.
- Kept reference/config data: users, products, product_test_specifications, lab_test_types, customers, lab_info, coa_category_order, daane_test_mapping, and email_templates.

### Import Watchouts
- Products auto-create and get a test panel. Identity includes size, so the size-less seed catalog rarely matches and many new products are expected.
- Each created or earlier spec-less product gets a required test panel based on the union of populated test columns for that SKU. If none are populated, the floor is Total Plate Count, Yeast & Mold, Escherichia coli, and Salmonella spp.
- Products that already have specs, including seed catalog products, are left untouched.
- `NEEDS METALS` SKUs force metals into required specs so those lots stay genuinely partial.
- Product identity is `(brand, product, flavor, size)`, so misspelled brands create duplicate products. Fix the spreadsheet and re-import instead of editing the DB.
- Test column renames: `Yeast/Mold` to `Yeast & Mold`, `E. Coli` to `Escherichia coli`, and `Salmonella` to `Salmonella spp.`. Unmapped test columns are reported.
- A reused `RefID` gets a `-2` suffix on the second occurrence. A `Lot` cell of `NEEDS LOT` falls back to the `RefID`. `NEEDS METALS` rows load as `PARTIAL_RESULTS`, not released, with whatever results they have and metals blank.
- Enums store by NAME in SQLite, for example `RELEASED`, `PARENT_LOT`, and `AWAITING_RESULTS`; API serialization still uses lowercase values.
- `/archive` page size max is 100. Released COAs surface in History/Archive, one item per release. The Release Queue's Recently Released list only shows the last N days, so widen the History date filter to see older releases.
- `--commit` with the dev server running is fine with SQLite locking; refresh the UI afterward.
- The loader targets the local dev DB. To update production, run the same script on the VPS at `/opt/labtrack/backend`.

## Deployment
- VPS: `155.138.211.71` on Vultr
- Project path: `/opt/labtrack`
- Backend: uvicorn on port `8009` at `/opt/labtrack/backend`

## Commit & Pull Request Guidelines
Recent history uses short, imperative subjects, such as `Enhance audit trail...`; keep summary lines under about 72 characters and add detail bullets when needed. Every PR should link the tracking issue, summarize user-facing impact, document schema or config updates, attach screenshots or API traces for UI/data changes, and list manual steps such as `make migrate` or `.env` edits. Confirm `make test`, `npm run test:run`, and linting succeed before requesting review.
