# Makefile for Logbook Scanner
VENV_BIN = venv/bin
PYTHON = $(VENV_BIN)/python
PIP = $(VENV_BIN)/pip
UVICORN = $(VENV_BIN)/uvicorn
PYTEST = $(VENV_BIN)/pytest

.PHONY: install run test clean lint

# Default target
all: install test

# Install dependencies
install:
	$(PIP) install -r requirements.txt

# Run the local development server
run:
	$(UVICORN) backend.app.main:app --reload --port 8000

# Run tests
test:
	PYTHONPATH=. $(PYTEST) backend/tests/

# Clean up temporary files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Lint (placeholder for now, can add flake8/mypy later)
lint:
	@echo "Linting not configured yet."
