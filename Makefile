.PHONY: setup test eval dev lint typecheck clean migrate

VENV := .venv
ifeq ($(OS),Windows_NT)
	PYTHON := $(VENV)/Scripts/python
	PIP := $(VENV)/Scripts/pip
else
	PYTHON := $(VENV)/bin/python
	PIP := $(VENV)/bin/pip
endif

setup:
	python -m venv $(VENV)
	$(PIP) install -e ".[dev]"
	$(PYTHON) -m alembic upgrade head

test:
	$(PYTHON) -m pytest tests/ -v --tb=short

test-cov:
	$(PYTHON) -m pytest tests/ -v --tb=short --cov=pgm --cov-report=html

eval:
	$(PYTHON) -m eval.run_experiment

dev:
	$(PYTHON) -m uvicorn pgm.api.main:app --reload --host 0.0.0.0 --port 8000

lint:
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m ruff format --check src/ tests/

typecheck:
	$(PYTHON) -m mypy src/pgm/

migrate:
	$(PYTHON) -m alembic upgrade head

migrate-new:
	$(PYTHON) -m alembic revision --autogenerate -m "$(MSG)"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache htmlcov .coverage
