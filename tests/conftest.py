from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from llms_txt_gen.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(list(argv))
    return rc, out.getvalue(), err.getvalue()


def run_json(*argv: str) -> tuple[int, dict]:
    rc, out, _ = run(*argv)
    return rc, json.loads(out)


@pytest.fixture
def docs_dir(tmp_path: Path) -> Path:
    write(
        tmp_path,
        "README.md",
        "# Acme Docs\n\nAcme is a **widget** service. This paragraph becomes the summary.\n\n## More\n\nText.\n",
    )
    write(
        tmp_path,
        "getting-started/install.md",
        "---\ntitle: Installing Acme\ndescription: How to install Acme on any platform.\n---\n\nBody.\n",
    )
    write(tmp_path, "getting-started/index.md", "# Getting started\n\nStart here.\n")
    write(
        tmp_path,
        "reference/api.md",
        "# API reference\n\n```python\nignored = True\n```\n\nEvery endpoint, with examples.\n",
    )
    write(
        tmp_path,
        "reference/cli.html",
        '<html><head><title>CLI | Acme</title><meta name="description" content="Command line usage."></head><body><h1>Command line</h1><p>Use the CLI.</p></body></html>\n',
    )
    write(tmp_path, "changelog.md", "Changelog\n=========\n\nAll notable changes.\n")
    write(tmp_path, "node_modules/pkg/README.md", "# Ignored\n\nShould not appear.\n")
    write(tmp_path, "notes.txt", "not a doc\n")
    return tmp_path
