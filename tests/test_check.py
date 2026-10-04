from __future__ import annotations

from pathlib import Path

from llms_txt_gen.check import check_file, check_text, format_text

from .conftest import EXAMPLES, write

GOOD = """# Acme

> Acme is a widget service.

Some free text, no headings.

## Docs

- [Install](install.md): How to install.
- [API](https://docs.example.com/api): Reference.

## Optional

- [Changelog](changelog.md)
"""


def codes(result, level=None):
    return {f.code for f in result.findings if level is None or f.level == level}


def test_good_file_passes():
    r = check_text(GOOD)
    assert r.ok(strict=True), r.findings
    assert r.title == "Acme" and r.sections == ["Docs", "Optional"] and r.link_count == 3


def test_missing_h1_and_summary_and_sections():
    r = check_text("Just text\n")
    assert "E001" in codes(r, "error")
    assert {"W001", "W002"} <= codes(r, "warning")
    assert not r.ok()


def test_content_before_h1_and_multiple_h1():
    r = check_text("intro\n\n# A\n\n# B\n")
    assert {"E002", "E004"} <= codes(r, "error")


def test_h3_is_an_error():
    r = check_text("# A\n\n> s\n\n## S\n\n### Sub\n\n- [x](y)\n")
    assert "E003" in codes(r, "error")


def test_malformed_link_lines():
    r = check_text("# A\n\n> s\n\n## S\n\n- not a link\n- [name](url extra)\n* [n](u)\n")
    assert "E005" in codes(r, "error")
    assert len([f for f in r.findings if f.code == "E005"]) == 3


def test_prose_inside_section_is_a_warning():
    r = check_text("# A\n\n> s\n\n## S\n\nSome prose here.\n- [n](u)\n")
    assert "W009" in codes(r, "warning") and r.ok() and not r.ok(strict=True)


def test_duplicate_links_and_sections_and_empty_sections():
    r = check_text("# A\n\n> s\n\n## S\n\n- [n](u)\n- [m](u)\n\n## S\n\n## T\n")
    assert {"W004", "W007", "W003"} <= codes(r, "warning")


def test_optional_must_be_last():
    r = check_text("# A\n\n> s\n\n## Optional\n\n- [n](u)\n\n## S\n\n- [m](v)\n")
    assert "W005" in codes(r, "warning")


def test_short_summary_warning():
    r = check_text("# A\n\n> tiny\n\n## S\n\n- [n](u)\n")
    assert "W008" in codes(r, "warning")


def test_code_blocks_are_ignored():
    r = check_text(
        "# A\n\n> summary here\n\n```\n# not a heading\n- not a link\n```\n\n## S\n\n- [n](u)\n"
    )
    assert r.ok(strict=True), r.findings


def test_local_links_are_checked_for_files(tmp_path: Path):
    write(tmp_path, "install.md", "# I\n")
    f = write(
        tmp_path,
        "llms.txt",
        "# A\n\n> summary here\n\n## S\n\n- [ok](install.md)\n- [abs](/install.md)\n- [gone](missing.md)\n- [ext](https://x.dev/a)\n- [anchor](#top)\n",
    )
    r = check_file(f)
    broken = [x for x in r.findings if x.code == "E006"]
    assert len(broken) == 1 and "missing.md" in broken[0].message


def test_format_text_lists_findings():
    out = format_text(check_text("# A\n"), "llms.txt")
    assert out.startswith("llms.txt: ok") or out.startswith("llms.txt: problems")
    assert "W001" in out


def test_bundled_example_is_valid():
    r = check_file(EXAMPLES / "llms.txt")
    assert r.ok(strict=True), r.findings
