from __future__ import annotations

import json
from pathlib import Path

import pytest

import llms_txt_gen.cli as cli
from llms_txt_gen.sitemap import FetchError

from .conftest import run, run_json, write


def test_generate_from_directory(docs_dir: Path, tmp_path: Path):
    out = tmp_path / "out" / "llms.txt"
    rc, _, err = run(
        "generate", str(docs_dir), "--out", str(out), "--base-url", "https://docs.acme.dev"
    )
    assert rc == 0 and "wrote" in err
    text = out.read_text()
    assert text.startswith("# Acme Docs\n\n> Acme is a widget service.")
    assert "## Getting started\n" in text and "## Reference\n" in text
    assert (
        "- [Installing Acme](https://docs.acme.dev/getting-started/install.md): How to install Acme on any platform."
        in text
    )
    # the generated file passes the checker
    rc, out_text, _ = run("check", str(out), "--strict")
    assert rc == 0, out_text


def test_generate_full(docs_dir: Path, tmp_path: Path):
    out = tmp_path / "llms.txt"
    rc, _, _ = run("generate", str(docs_dir), "--out", str(out), "--full")
    assert rc == 0
    full = (tmp_path / "llms-full.txt").read_text()
    assert "Source: reference/api.md" in full and "Every endpoint, with examples." in full
    rc, _, _ = run(
        "generate",
        str(docs_dir),
        "--out",
        str(out),
        "--full",
        "--full-out",
        str(tmp_path / "x.txt"),
    )
    assert (tmp_path / "x.txt").exists()


def test_generate_stdout_title_summary_optional(docs_dir: Path):
    rc, out, _ = run(
        "generate",
        str(docs_dir),
        "--stdout",
        "--title",
        "Custom",
        "--summary",
        "Custom summary.",
        "--body",
        "Extra.",
        "--optional",
        "changelog*",
        "--strip-ext",
    )
    assert rc == 0
    assert out.startswith("# Custom\n\n> Custom summary.\n\nExtra.\n")
    assert "## Optional\n\n- [Changelog](changelog)" in out


def test_generate_rejects_missing_dir(tmp_path: Path):
    rc, _, err = run("generate", str(tmp_path / "nope"), "--out", str(tmp_path / "o.txt"))
    assert rc == 2 and "not a directory" in err
    empty = tmp_path / "empty"
    empty.mkdir()
    rc, _, err = run("generate", str(empty), "--out", str(tmp_path / "o.txt"))
    assert rc == 2 and "no Markdown" in err


def test_generate_from_sitemap_uses_cap_and_timeout(monkeypatch, tmp_path: Path):
    seen = {}

    def fake_pages(url, max_pages, timeout, fetcher):
        seen.update(url=url, max_pages=max_pages, timeout=timeout)
        from llms_txt_gen.model import Page

        return [Page("Home", "https://docs.x.dev/", "Hi.", "Docs")]

    monkeypatch.setattr(cli, "pages_from_sitemap", fake_pages)
    out = tmp_path / "llms.txt"
    rc, _, _ = run(
        "generate",
        "https://docs.x.dev/sitemap.xml",
        "--out",
        str(out),
        "--max-pages",
        "7",
        "--timeout",
        "2",
    )
    assert rc == 0
    assert seen == {"url": "https://docs.x.dev/sitemap.xml", "max_pages": 7, "timeout": 2.0}
    assert out.read_text().startswith(
        "# docs.x.dev\n\n## Docs\n\n- [Home](https://docs.x.dev/): Hi."
    )


def test_generate_sitemap_errors(monkeypatch, tmp_path: Path):
    def boom(*a, **k):
        raise FetchError("https://x/sitemap.xml: timed out")

    monkeypatch.setattr(cli, "pages_from_sitemap", boom)
    rc, _, err = run("generate", "https://x/sitemap.xml", "--out", str(tmp_path / "o"))
    assert rc == 2 and "timed out" in err
    monkeypatch.setattr(cli, "pages_from_sitemap", lambda *a, **k: [])
    rc, _, err = run("generate", "https://x/sitemap.xml", "--out", str(tmp_path / "o"))
    assert rc == 2 and "no pages" in err


def test_check_exit_codes_and_json(tmp_path: Path):
    good = write(
        tmp_path, "llms.txt", "# A\n\n> Summary long enough.\n\n## S\n\n- [n](https://x.dev)\n"
    )
    rc, out, _ = run("check", str(good))
    assert rc == 0 and out.startswith(f"{good}: ok")
    bad = write(tmp_path, "bad.txt", "no title\n")
    rc, out, _ = run("check", str(bad))
    assert rc == 1
    rc, data = run_json("check", str(bad), "--format", "json")
    assert rc == 1 and data["ok"] is False and any(f["code"] == "E001" for f in data["findings"])
    warn = write(tmp_path, "warn.txt", "# A\n\n## S\n\n- [n](https://x.dev)\n")
    assert run("check", str(warn))[0] == 0
    assert run("check", str(warn), "--strict")[0] == 1


def test_check_missing_file_and_url(monkeypatch, tmp_path: Path):
    rc, _, err = run("check", str(tmp_path / "none.txt"))
    assert rc == 2 and "not a file" in err
    monkeypatch.setattr(
        cli,
        "fetch",
        lambda url, timeout: (
            b"# Remote\n\n> Remote summary.\n\n## S\n\n- [n](https://x.dev)\n",
            "text/plain",
        ),
    )
    rc, out, _ = run("check", "https://x.dev/llms.txt")
    assert rc == 0 and "ok" in out

    def boom(url, timeout):
        raise FetchError("nope")

    monkeypatch.setattr(cli, "fetch", boom)
    assert run("check", "https://x.dev/llms.txt")[0] == 2


def test_serve_snippet():
    rc, out, _ = run("serve-snippet")
    assert (
        rc == 0
        and out == '<link rel="alternate" type="text/markdown" href="/llms.txt" title="llms.txt">\n'
    )
    rc, out, _ = run("serve-snippet", "--href", "https://x.dev/llms.txt", "--full")
    assert out.count("<link") == 2 and "llms-full.txt" in out
    rc, out, _ = run("serve-snippet", "--header")
    assert out.startswith('Link: </llms.txt>; rel="alternate"')


def test_version_and_help():
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    with pytest.raises(SystemExit):
        cli.main([])


def test_check_json_is_valid_json(tmp_path: Path):
    f = write(
        tmp_path, "llms.txt", "# A\n\n> Summary long enough.\n\n## S\n\n- [n](https://x.dev)\n"
    )
    _, out, _ = run("check", str(f), "--format", "json")
    data = json.loads(out)
    assert data["title"] == "A" and data["links"] == 1 and data["sections"] == ["S"]
