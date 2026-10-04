# Contributing

Thanks for considering a contribution. The project is small on purpose: discovery of pages, extraction of a title and a note per page, rendering, and a checker. Most useful contributions are better extraction for a documentation generator you use, new checks, and example inputs that show a gap.

## Set up

Requires Python 3.11 or newer. With [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/basitalisandhu/llms-txt-gen
cd llms-txt-gen
uv sync
uv run pytest -q
```

Without uv:

```bash
python3 -m venv .venv && . .venv/bin/activate
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
```

## Before you open a pull request

```bash
make check      # ruff check, ruff format --check, pytest
make example    # regenerate examples/llms.txt and examples/llms-full.txt
```

CI runs the same commands on Python 3.11 and 3.12 and fails when the committed example output is stale.

## Adding a check

1. Pick the next free code (`E` for errors that make the file invalid, `W` for warnings about things the convention recommends, `I` for information).
2. Add it to `check_text` in `llms_txt_gen/check.py`, with a one-line message that says what is wrong and what to do.
3. Add a test in `tests/test_check.py` with a positive and a negative case.
4. Add the row to the "Checks" table in the README.

## Style

- `ruff` formats and lints; line length 100.
- Standard library only at runtime. Development dependencies are fine.
- Deterministic output: no timestamps, no random ids, no ordering that depends on the file system.
- Network access only behind an explicit URL argument, always with a timeout and a size cap.
- Plain language in messages and documentation.

## Reporting security issues

See [SECURITY.md](SECURITY.md).
