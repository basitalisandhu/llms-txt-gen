"""Tests for `generate --nav mkdocs.yml` and the nav subset parser."""

from __future__ import annotations

import contextlib
import random
from pathlib import Path

import pytest

from llms_txt_gen.nav import NavError, parse_nav

from .conftest import run, write
from .test_robustness import time_limit

MKDOCS = """\
site_name: Acme
theme:
  name: material
  features: [navigation.tabs]
nav:
  - Home: index.md
  - 'User Guide':
      - 'Writing your docs': 'user-guide/writing.md'
      - user-guide/styling.md   # a plain path
      - Advanced:
          - user-guide/advanced/deep.md
  - About:
    - "License": about/license.md
    - Source: https://github.com/example/acme
  - ./changelog.md
markdown_extensions:
  - toc
"""


def test_parse_two_level_nav():
    entries = parse_nav(MKDOCS)
    assert [(e.path, e.section, e.title) for e in entries] == [
        ("index.md", "Docs", "Home"),
        ("user-guide/writing.md", "User Guide", "Writing your docs"),
        ("user-guide/styling.md", "User Guide", None),
        ("user-guide/advanced/deep.md", "User Guide", None),
        ("about/license.md", "About", "License"),
        ("changelog.md", "Docs", None),
    ]


@pytest.fixture
def mkdocs_project(tmp_path: Path) -> Path:
    for rel in [
        "index",
        "user-guide/writing",
        "user-guide/styling",
        "user-guide/advanced/deep",
        "user-guide/extra",
        "about/license",
        "changelog",
        "zeta/z",
    ]:
        write(tmp_path, f"docs/{rel}.md", f"# Page {rel}\n\nAbout {rel}.\n")
    write(tmp_path, "mkdocs.yml", MKDOCS)
    return tmp_path


def test_generate_with_nav_uses_sections_and_order(mkdocs_project: Path):
    rc, out, err = run(
        "generate",
        str(mkdocs_project / "docs"),
        "--nav",
        str(mkdocs_project / "mkdocs.yml"),
        "--stdout",
        "--strip-ext",
    )
    assert rc == 0, err
    headings = [line for line in out.splitlines() if line.startswith("## ")]
    # Nav sections in nav order; the folder-only section follows alphabetically.
    assert headings == ["## Docs", "## User Guide", "## About", "## Zeta"]
    guide = out.split("## User Guide\n\n", 1)[1].split("\n\n", 1)[0].splitlines()
    assert guide == [
        "- [Writing your docs](user-guide/writing): About user-guide/writing.",
        "- [Page user-guide/styling](user-guide/styling): About user-guide/styling.",
        "- [Page user-guide/advanced/deep](user-guide/advanced/deep): About user-guide/advanced/deep.",
        # Not in nav, same folder: joins the nav section after the nav pages.
        "- [Page user-guide/extra](user-guide/extra): About user-guide/extra.",
    ]
    assert "- [License](about/license)" in out
    assert out.startswith("# Page index\n")  # the root index still gives the title
    assert err == ""


def test_generate_without_nav_is_unchanged(mkdocs_project: Path):
    rc, out, _ = run("generate", str(mkdocs_project / "docs"), "--stdout")
    assert rc == 0
    headings = [line for line in out.splitlines() if line.startswith("## ")]
    assert headings == ["## Docs", "## About", "## User guide", "## Zeta"]


def test_nav_from_wrong_source_gives_a_hint(mkdocs_project: Path):
    rc, _, err = run(
        "generate", str(mkdocs_project), "--nav", str(mkdocs_project / "mkdocs.yml"), "--stdout"
    )
    assert rc == 0
    assert "note: nav lists user-guide/writing.md, which is not under" in err
    assert "SOURCE should be the MkDocs docs_dir" in err


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("site_name: x\n", "no top-level 'nav:' list found"),
        ("nav: [a.md, b.md]\n", "flow style"),
        ("nav:\n  - Group:\n  - b.md\n", "has no pages"),
        ("nav:\n  - Group:\n", "last group in nav has no pages"),
        ("nav:\n  - a.md\n    - b.md\n", "indentation does not match"),
        ("nav:\n  a.md\n", "expected a list item"),
        ("nav:\n\t- a.md\n", "tab in indentation"),
        ("nav:\n  - 'unterminated\n", "unterminated quote"),
        ("nav:\n  - &anchor a.md\n", "unsupported YAML"),
    ],
)
def test_nav_errors_name_the_problem(text: str, needle: str):
    with pytest.raises(NavError, match=None) as info:
        parse_nav(text, "mkdocs.yml")
    assert needle in str(info.value)
    assert str(info.value).startswith("mkdocs.yml")


def test_cli_nav_errors_exit_2(tmp_path: Path):
    write(tmp_path, "docs/a.md", "# A\n\nHello.\n")
    (tmp_path / "latin1.yml").write_bytes(b"nav:\n  - Caf\xe9: a.md\n")
    for nav, needle in [
        (tmp_path / "missing.yml", "cannot read"),
        (tmp_path / "latin1.yml", "is not UTF-8 text"),
    ]:
        rc, _, err = run("generate", str(tmp_path / "docs"), "--nav", str(nav), "--stdout")
        assert rc == 2
        assert needle in err and "Traceback" not in err
    rc, _, err = run("generate", "https://example.com/sitemap.xml", "--nav", "mkdocs.yml")
    assert rc == 2 and "--nav needs a directory SOURCE" in err


def test_fuzz_nav_parser_raises_only_nav_error():
    rng = random.Random(20261028)
    pieces = [
        "nav:\n",
        "  ",
        "    ",
        "- ",
        "-",
        "a.md",
        "Title: ",
        "Title:",
        "'q'",
        '"q',
        "\n",
        "# c",
        "\t",
        ":",
        "x: y",
        "https://e",
        "[",
        "{",
        "&",
        "\x00",
        "é",
        "site: 1\n",
    ]
    with time_limit(30):
        for _ in range(2000):
            text = "nav:\n" + "".join(rng.choice(pieces) for _ in range(rng.randint(0, 40)))
            with contextlib.suppress(NavError):
                parse_nav(text)
