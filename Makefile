.PHONY: help install install-dev test format lint type-check clean run migrate

help:
	@echo "Available commands:"
	@echo "  make install      Install production dependencies"
	@echo "  make install-dev  Install development dependencies"
	@echo "  make test         Run tests with coverage"
	@echo "  make format       Format code with black and isort"
	@echo "  make lint         Run linting with flake8"
	@echo "  make type-check   Run type checking with mypy"
	@echo "  make clean        Clean up temporary files"
	@echo "  make run          Run the Streamlit application"
	@echo "  make migrate      Run database migrations"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -e .

test:
	pytest

format:
	black src/ tests/
	isort src/ tests/

lint:
	flake8 src/ tests/

type-check:
	mypy src/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info

run:
	streamlit run src/ui/app.py

migrate:
	alembic upgrade head

init-db:
	alembic init migrations
	alembic revision --autogenerate -m "Initial migration"
	alembic upgrade head