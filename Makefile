.PHONY: help install install-backend install-frontend test format lint clean dev backend frontend migrate

help:
	@echo "Available commands:"
	@echo "  make install         Install all dependencies (backend + frontend)"
	@echo "  make install-backend Install backend Python dependencies"
	@echo "  make install-frontend Install frontend Node dependencies"
	@echo "  make dev             Start both backend and frontend dev servers"
	@echo "  make backend         Start FastAPI backend server"
	@echo "  make frontend        Start Vite frontend dev server"
	@echo "  make test            Run backend tests with coverage"
	@echo "  make format          Format Python code with black and isort"
	@echo "  make lint            Run linting with flake8"
	@echo "  make clean           Clean up temporary files"
	@echo "  make migrate         Run database migrations"
	@echo "  make init-db         Initialize demo data"

# Installation
install: install-backend install-frontend

install-backend:
	cd backend && pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

# Development servers
dev:
	@echo "Starting backend on http://localhost:8009 and frontend on http://localhost:5173"
	@make backend & make frontend

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8009

frontend:
	cd frontend && npm run dev

# Testing
test:
	cd backend && pytest tests/ -v --cov=app

# Code quality
format:
	cd backend && black app/ tests/ && isort app/ tests/

lint:
	cd backend && flake8 app/ tests/

# Database
migrate:
	cd backend && alembic upgrade head

init-db:
	cd backend && python init_demo_data.py

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf htmlcov/ .pytest_cache/ .mypy_cache/ dist/ build/ *.egg-info 2>/dev/null || true
	rm -rf frontend/node_modules/.cache frontend/dist 2>/dev/null || true

