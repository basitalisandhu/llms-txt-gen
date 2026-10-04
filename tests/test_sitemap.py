from __future__ import annotations

import pytest

from llms_txt_gen.sitemap import (
    MAX_SITEMAPS,
    FetchError,
    crawl_sitemap,
    fetch,
    is_url,
    page_from_response,
    pages_from_sitemap,
    parse_sitemap,
)

URLSET = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://docs.example.com/</loc></url>
  <url><loc>https://docs.example.com/guides/start</loc><lastmod>2026-01-01</lastmod></url>
  <url><loc>https://docs.example.com/guides/start</loc></url>
  <url><loc>https://docs.example.com/api/ref.md</loc></url>
</urlset>
"""
INDEX = b"""<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://docs.example.com/sitemap-a.xml</loc></sitemap>
  <sitemap><loc>https://docs.example.com/sitemap-b.xml</loc></sitemap>
</sitemapindex>
"""


def fake_fetcher(responses: dict[str, tuple[bytes, str]]):
    calls: list[tuple[str, float]] = []

    def _fetch(url: str, timeout: float) -> tuple[bytes, str]:
        calls.append((url, timeout))
        if url not in responses:
            raise FetchError(f"{url}: 404")
        return responses[url]

    _fetch.calls = calls  # type: ignore[attr-defined]
    return _fetch


def test_parse_sitemap_urlset_and_index():
    pages, nested = parse_sitemap(URLSET)
    assert pages[:2] == ["https://docs.example.com/", "https://docs.example.com/guides/start"]
    assert nested == []
    pages, nested = parse_sitemap(INDEX)
    assert pages == [] and len(nested) == 2


def test_parse_sitemap_rejects_bad_xml():
    with pytest.raises(FetchError):
        parse_sitemap(b"<urlset><url>")


def test_crawl_follows_index_dedupes_and_caps_pages():
    f = fake_fetcher(
        {
            "https://docs.example.com/sitemap.xml": (INDEX, "application/xml"),
            "https://docs.example.com/sitemap-a.xml": (URLSET, "application/xml"),
            "https://docs.example.com/sitemap-b.xml": (URLSET, "application/xml"),
        }
    )
    urls = crawl_sitemap("https://docs.example.com/sitemap.xml", max_pages=100, fetcher=f)
    assert urls == [
        "https://docs.example.com/",
        "https://docs.example.com/guides/start",
        "https://docs.example.com/api/ref.md",
    ]
    capped = crawl_sitemap("https://docs.example.com/sitemap.xml", max_pages=2, fetcher=f)
    assert len(capped) == 2


def test_crawl_stops_at_sitemap_limit():
    responses = {}
    for i in range(MAX_SITEMAPS + 20):
        nxt = f"https://x.dev/s{i + 1}.xml"
        responses[f"https://x.dev/s{i}.xml"] = (
            f"<sitemapindex><sitemap><loc>{nxt}</loc></sitemap></sitemapindex>".encode(),
            "application/xml",
        )
    f = fake_fetcher(responses)
    crawl_sitemap("https://x.dev/s0.xml", fetcher=f)
    assert len(f.calls) <= MAX_SITEMAPS


def test_pages_from_sitemap_extracts_and_skips_failures(capsys):
    html = b"<html><head><title>Start | Docs</title><meta name='description' content='Begin here.'></head><body><p>Hi</p></body></html>"
    md = b"# Reference\n\nThe API reference.\n"
    f = fake_fetcher(
        {
            "https://docs.example.com/sitemap.xml": (URLSET, "application/xml"),
            "https://docs.example.com/guides/start": (html, "text/html; charset=utf-8"),
            "https://docs.example.com/api/ref.md": (md, "text/markdown"),
        }
    )
    logged: list[str] = []
    pages = pages_from_sitemap(
        "https://docs.example.com/sitemap.xml", timeout=3.5, fetcher=f, log=logged.append
    )
    assert [p.title for p in pages] == ["Start", "Reference"]
    assert pages[0].section == "Guides" and pages[0].summary == "Begin here."
    assert pages[1].section == "Api" and pages[1].summary == "The API reference."
    assert all(call[1] == 3.5 for call in f.calls)
    assert logged and "404" in logged[0]


def test_page_from_response_fallback_title():
    page = page_from_response("https://x.dev/", b"<p>no title</p>", "text/html")
    assert page.title == "X.dev" and page.section == "Docs"


def test_fetch_rejects_non_http_schemes():
    with pytest.raises(FetchError):
        fetch("file:///etc/passwd")
    with pytest.raises(FetchError):
        fetch("ftp://example.com/x")


def test_fetch_times_out(monkeypatch):
    import urllib.request

    def boom(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(FetchError):
        fetch("https://example.com/sitemap.xml", timeout=0.01)


def test_is_url():
    assert is_url("https://x.dev/sitemap.xml") and is_url("HTTP://x")
    assert not is_url("./docs") and not is_url("docs/sitemap.xml")
