# Repository Guidelines

## Project Structure & Module Organization
Backend code lives in `backend/app`, with `api`, `services`, `models`, and `schemas` covering routing, logic, persistence, and IO contracts; helpers sit in `core` and `utils`. Alembic migrations and generated templates are in `backend/migrations` and `backend/templates`, while runtime uploads land in `backend/uploads`. The Vite + React frontend is colocated under `frontend/src`, with static assets in `frontend/public` and build output in `frontend/dist`. Repo-level automation (`Makefile`, scripts, env samples) stays at the root.

## Build, Test, and Development Commands
Run `make install` (or the scoped install targets) after cloning. `make dev` launches FastAPI on :8009 and the Vite dev server on :5173; `make backend` or `make frontend` target a single stack. CI-style invocations include `cd frontend && npm run build` for optimized bundles and `cd backend && uvicorn app.main:app --workers 4` for production smoke tests.

## Coding Style & Naming Conventions
Python uses 4-space indentation, snake_case modules, and descriptive router/service names. Run `make format` (black + isort) before `make lint` (flake8, with mypy optional via `mypy app/`). Define Pydantic models in `schemas` with PascalCase names and keep response/request objects versioned. Frontend TypeScript follows ESLint + React Hooks rules; use PascalCase for components, camelCase for hooks/utilities, and colocate files with their feature. Run `npm run lint` inside `frontend` prior to committing UI work.

## Testing Guidelines
Backend tests live in `backend/tests` and run via `make test` (`pytest -v --cov=app`). Add fixtures beside the code they serve and regenerate `coverage.xml` locally; avoid lowering existing coverage. Frontend interaction and utility tests rely on Vitest + Testing Library, using `npm run test` (watch) or `npm run test:run` (CI). Name suites `test_<feature>.py` and `<Component>.test.tsx` for quick discovery.

## Commit & Pull Request Guidelines
Recent history uses short, imperative subjects (e.g., “Enhance audit trail…”); keep summary lines under ~72 characters and add detail bullets when needed. Every PR should link the tracking issue, summarize user-facing impact, document schema or config updates, attach screenshots or API traces for UI/Data changes, and list manual steps (`make migrate`, `.env` edits). Confirm `make test`, `npm run test:run`, and linting succeed before requesting review.
