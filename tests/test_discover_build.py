from __future__ import annotations

from pathlib import Path

from llms_txt_gen.build import build_document, render_llms_full, render_llms_txt
from llms_txt_gen.discover import make_url, scan_directory
from llms_txt_gen.model import Page

from .conftest import write


def test_scan_directory_finds_pages_and_index(docs_dir: Path):
    pages, index = scan_directory(docs_dir)
    assert index is not None and index.title == "Acme Docs"
    assert index.summary == "Acme is a widget service. This paragraph becomes the summary."
    urls = [p.url for p in pages]
    assert "getting-started/install.md" in urls
    assert "reference/cli.html" in urls
    assert "changelog.md" in urls
    assert not any("node_modules" in u for u in urls)
    assert not any(u.endswith(".txt") for u in urls)


def test_scan_directory_sections_and_titles(docs_dir: Path):
    pages, _ = scan_directory(docs_dir)
    by_url = {p.url: p for p in pages}
    assert by_url["getting-started/install.md"].section == "Getting started"
    assert by_url["getting-started/install.md"].title == "Installing Acme"
    assert by_url["getting-started/install.md"].summary == "How to install Acme on any platform."
    assert by_url["reference/cli.html"].title == "Command line"
    assert by_url["reference/cli.html"].summary == "Command line usage."
    assert by_url["changelog.md"].section == "Docs"
    assert by_url["changelog.md"].title == "Changelog"
    # a folder index is listed first inside its section
    assert by_url["getting-started/index.md"].order == -1


def test_scan_directory_include_exclude(docs_dir: Path):
    pages, _ = scan_directory(docs_dir, exclude=["reference"])
    assert not any(p.url.startswith("reference/") for p in pages)
    pages, _ = scan_directory(docs_dir, include=["reference/*"])
    assert all(p.url.startswith("reference/") for p in pages) and pages


def test_make_url_base_and_strip_ext():
    assert make_url("a/b.md", None, False) == "a/b.md"
    assert make_url("a/b.md", "https://x.dev/docs/", False) == "https://x.dev/docs/a/b.md"
    assert make_url("a/b.md", "https://x.dev", True) == "https://x.dev/a/b"
    assert make_url("a/index.html", "https://x.dev", True) == "https://x.dev/a/"
    assert make_url("index.md", None, True) == "./"


def test_build_document_orders_sections_and_optional():
    pages = [
        Page("Z page", "z/z.md", section="Zeta", order=0),
        Page("Root", "root.md", section="Docs", order=1),
        Page("A page", "a/a.md", section="Alpha", order=2),
        Page("Old", "legacy/old.md", section="Legacy", order=3),
    ]
    doc = build_document(pages, "T", optional=["legacy/*"])
    assert [s.name for s in doc.sections] == ["Docs", "Alpha", "Zeta", "Optional"]
    assert doc.sections[-1].pages[0].title == "Old"


def test_render_llms_txt_matches_convention():
    doc = build_document(
        [Page("Install", "install.md", "How to [install].", "Docs", order=0)],
        "Acme",
        "A widget service.",
        body=["Extra context paragraph."],
    )
    text = render_llms_txt(doc)
    assert text == (
        "# Acme\n\n> A widget service.\n\nExtra context paragraph.\n\n"
        "## Docs\n\n- [Install](install.md): How to (install).\n"
    )


def test_render_llms_full_includes_content_and_sources():
    doc = build_document(
        [Page("Install", "install.md", "x", "Docs", content="# Install\n\nSteps.\n")], "Acme"
    )
    text = render_llms_full(doc)
    assert text.startswith(
        "# Acme\n\n---\n\n# Install\n\nSource: install.md\n\n# Install\n\nSteps.\n"
    )


def test_generation_is_deterministic(docs_dir: Path):
    a = render_llms_txt(build_document(scan_directory(docs_dir)[0], "T"))
    b = render_llms_txt(build_document(scan_directory(docs_dir)[0], "T"))
    assert a == b


def test_large_files_are_skipped(tmp_path: Path):
    write(tmp_path, "small.md", "# Small\n\nok\n")
    big = tmp_path / "big.md"
    big.write_bytes(b"# Big\n" + b"x" * (5 * 1024 * 1024 + 1))
    pages, _ = scan_directory(tmp_path)
    assert [p.url for p in pages] == ["small.md"]
