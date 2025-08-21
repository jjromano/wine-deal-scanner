.PHONY: setup run fmt lint test clean help

# Default target
.DEFAULT_GOAL := help

## Install dependencies and setup environment
setup:
	pip install -e ".[dev]"
	playwright install

## Run the wine deal scanner
run:
	python -m app.main

## Format code with black
fmt:
	black app/ tests/
	ruff check --fix app/ tests/

## Lint code
lint:
	black --check app/ tests/
	ruff check app/ tests/
	mypy app/

## Run tests
test:
	pytest tests/ -v

## Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

## Show this help message
help:
	@echo "Wine Deal Scanner - Available commands:"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  /'
	@echo ""
	@echo "Usage: make <target>"
