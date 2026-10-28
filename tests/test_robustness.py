"""Seeded fuzz, bad-input and scaling tests for the parsers and input readers.

Every case runs under a wall-clock limit, so a regular expression that backtracks or a
parser that loops fails the test instead of hanging CI.
"""

from __future__ import annotations

import os
import random
import signal
import sys
import time
from contextlib import contextmanager, suppress
from pathlib import Path

import pytest

from llms_txt_gen import check, extract, sitemap
from llms_txt_gen.sitemap import FetchError

from .conftest import run, write

SEED = 20261028
PIECES = [
    "#",
    "# ",
    "## ",
    "\n",
    "\r\n",
    "=",
    "===",
    "-",
    "---",
    "\n---\n",
    " ",
    "\t",
    "`",
    "```",
    "~~~",
    "<",
    ">",
    "> ",
    "<p>",
    "</p>",
    "<h1>",
    "</h1>",
    "<title>",
    "<meta name='description'",
    "<script>",
    "<!--",
    "<![CDATA[",
    "&#xffffffff;",
    "&amp;",
    "[",
    "](",
    ")",
    "- [a](b): c",
    "x",
    "word ",
    "é",
    "\x00",
    "﻿",
    "*",
    "_",
    "!",
    "|",
    "1.",
    "llms: false",
    ":",
]


@contextmanager
def time_limit(seconds: float):
    """Fail if the block runs longer than `seconds` (POSIX only; elsewhere a plain block)."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def _raise(signum, frame):
        raise TimeoutError(f"took longer than {seconds}s")

    old = signal.signal(signal.SIGALRM, _raise)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _random_text(rng: random.Random, max_pieces: int = 120) -> str:
    return "".join(rng.choice(PIECES) for _ in range(rng.randint(0, max_pieces)))


TEXT_PARSERS = [
    lambda t: extract.markdown_title(t, "fallback"),
    extract.markdown_summary,
    extract.markdown_text,
    lambda t: extract.html_title(t, "fallback"),
    extract.html_summary,
    extract.html_text,
    extract.parse_frontmatter,
    check.check_text,
]


def test_fuzz_text_parsers_never_raise():
    rng = random.Random(SEED)
    with time_limit(60):
        for _ in range(1500):
            text = _random_text(rng)
            for parse in TEXT_PARSERS:
                parse(text)  # any exception fails the test


def test_fuzz_sitemap_parser_raises_only_fetch_error():
    rng = random.Random(SEED)
    xml_pieces = [
        "<urlset>",
        "</urlset>",
        "<url>",
        "</url>",
        "<loc>",
        "</loc>",
        "<sitemapindex>",
        "<sitemap>",
        "https://x/a",
        "<?xml version='1.0'?>",
        "&",
        "\x00",
        "\xff",
        "<",
    ]
    with time_limit(30):
        for _ in range(1000):
            data = "".join(rng.choice(xml_pieces) for _ in range(rng.randint(0, 40)))
            with suppress(FetchError):
                sitemap.parse_sitemap(data.encode("utf-8", "surrogatepass"))


def test_deeply_nested_inputs_do_not_crash():
    with time_limit(30):
        extract.html_text("<div>" * 50_000)
        check.check_text("> " * 50_000)
        with pytest.raises(FetchError):
            sitemap.parse_sitemap(b"<urlset>" + b"<url>" * 50_000)


def _many_blank_lines(n: int) -> str:
    return " \n" * n + "text"


def test_markdown_title_is_linear_in_blank_lines():
    """The Setext pattern used to rescan every following blank line: 40,000 blank lines took
    2.6s and doubling the input quadrupled the time. Now 10x the input stays well under a second."""
    small, large = _many_blank_lines(4_000), _many_blank_lines(40_000)
    with time_limit(10):
        start = time.perf_counter()
        extract.markdown_title(small, "f")
        t_small = time.perf_counter() - start
        start = time.perf_counter()
        extract.markdown_title(large, "f")
        t_large = time.perf_counter() - start
    assert t_large < 1.0
    # Linear growth is about 10x; allow noise, but quadratic (100x) must fail.
    assert t_large < max(t_small, 0.001) * 40


def test_hash_line_does_not_take_next_line_as_title():
    assert extract.markdown_title("#\nNot a title\n", "fallback") == "fallback"
    assert extract.markdown_title("# Real title\n", "fallback") == "Real title"


def test_byte_order_mark_is_ignored():
    text = "﻿---\ntitle: From front matter\n---\n# Body\n"
    assert extract.markdown_title(text, "f") == "From front matter"


def test_check_utf8_bom_is_accepted(tmp_path: Path):
    path = tmp_path / "llms.txt"
    path.write_bytes(
        b"\xef\xbb\xbf# Title\n\n> A summary of the project.\n\n## Docs\n\n- [A](https://example.com/a): b\n"
    )
    rc, out, _ = run("check", str(path))
    assert rc == 0, out


@pytest.mark.parametrize(
    ("data", "needle"),
    [
        (b"\xff\xfe#\x00 \x00T\x00", "is UTF-16 text"),
        (b"# Caf\xe9\n", "is not UTF-8 text (byte 0xe9 at offset 5)"),
    ],
)
def test_check_non_utf8_exits_2_naming_the_file(tmp_path: Path, data: bytes, needle: str):
    path = tmp_path / "llms.txt"
    path.write_bytes(data)
    rc, out, err = run("check", str(path))
    assert rc == 2
    assert out == ""
    assert str(path) in err and needle in err
    assert "Traceback" not in err


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="needs POSIX non-root")
def test_check_unreadable_file_exits_2(tmp_path: Path):
    path = write(tmp_path, "llms.txt", "# T\n")
    path.chmod(0)
    try:
        rc, _, err = run("check", str(path))
    finally:
        path.chmod(0o644)
    assert rc == 2
    assert err.startswith(f"error: cannot read {path}")


def test_generate_out_is_a_directory_exits_2(tmp_path: Path):
    write(tmp_path, "docs/a.md", "# A\n\nHello.\n")
    (tmp_path / "outdir").mkdir()
    rc, _, err = run("generate", str(tmp_path / "docs"), "--out", str(tmp_path / "outdir"))
    assert rc == 2
    assert err.startswith(f"error: cannot write {tmp_path / 'outdir'}")


def test_generate_full_out_unwritable_exits_2(tmp_path: Path):
    write(tmp_path, "docs/a.md", "# A\n\nHello.\n")
    (tmp_path / "full").mkdir()
    rc, _, err = run(
        "generate",
        str(tmp_path / "docs"),
        "--out",
        str(tmp_path / "llms.txt"),
        "--full",
        "--full-out",
        str(tmp_path / "full"),
    )
    assert rc == 2
    assert "cannot write" in err


def test_generate_max_pages_must_be_positive(tmp_path: Path):
    rc, _, err = run("generate", "https://example.com/sitemap.xml", "--max-pages", "0")
    assert rc == 2
    assert "--max-pages must be 1 or more" in err


def test_generate_scales_linearly_with_pages(tmp_path: Path):
    """10x the pages should cost about 10x the time, not 100x."""

    def build(n: int, root: Path) -> float:
        for i in range(n):
            write(root, f"sec{i % 20}/page{i}.md", f"# Page {i}\n\nAbout page {i}.\n" + "x\n" * 40)
        start = time.perf_counter()
        rc, _, _ = run("generate", str(root), "--out", str(root / "llms.txt"), "--full")
        assert rc == 0
        return time.perf_counter() - start

    with time_limit(60):
        t_small = build(200, tmp_path / "small")
        t_large = build(2_000, tmp_path / "large")
    assert t_large < max(t_small, 0.005) * 40
