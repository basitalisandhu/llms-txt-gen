.PHONY: install lint format test check build example clean

PY ?= uv run

install:
	uv sync

lint:
	$(PY) ruff check .
	$(PY) ruff format --check .

format:
	$(PY) ruff format .
	$(PY) ruff check --fix .

test:
	$(PY) pytest -q

check: lint test

build:
	rm -rf dist
	uv build

example:
	$(PY) llms-txt-gen generate examples/docs --out examples/llms.txt --full --base-url https://acme.example.com/docs --strip-ext --optional 'changelog*'
	$(PY) llms-txt-gen check examples/llms.txt --strict

clean:
	rm -rf dist build .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
