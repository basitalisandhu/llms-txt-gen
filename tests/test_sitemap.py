from __future__ import annotations

import gzip

import pytest

from llms_txt_gen.sitemap import (
    MAX_SITEMAPS,
    FetchError,
    crawl_sitemap,
    fetch,
    gunzip_capped,
    is_url,
    page_from_response,
    pages_from_sitemap,
    parse_sitemap,
    probe,
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


class _Response:
    def __init__(self, body: bytes, content_type: str = "application/xml") -> None:
        self._body = body
        self.headers = {"Content-Type": content_type}

    def read(self, n: int) -> bytes:
        return self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _serve(monkeypatch, body: bytes) -> None:
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Response(body))


def test_fetch_decompresses_gzip_by_extension_or_magic(monkeypatch):
    _serve(monkeypatch, gzip.compress(URLSET))
    assert fetch("https://docs.example.com/sitemap.xml.gz") == (URLSET, "application/xml")
    assert fetch("https://docs.example.com/sitemap.xml")[0] == URLSET


@pytest.mark.parametrize("cut", [slice(0, 20), slice(0, -4)])
def test_fetch_reports_truncated_gzip_as_fetch_error(monkeypatch, cut):
    _serve(monkeypatch, gzip.compress(URLSET)[cut])
    with pytest.raises(FetchError, match="bad gzip data"):
        fetch("https://docs.example.com/sitemap.xml.gz")


def test_fetch_reports_corrupt_gzip_as_fetch_error(monkeypatch):
    good = gzip.compress(URLSET)
    _serve(monkeypatch, good[:10] + b"\xff" * 30 + good[-8:])
    with pytest.raises(FetchError, match="bad gzip data"):
        fetch("https://docs.example.com/sitemap.xml.gz")


def test_gunzip_caps_the_decompressed_size():
    bomb = gzip.compress(b"\0" * 10_000)
    assert len(bomb) < 1_000
    with pytest.raises(FetchError, match="decompressed response larger than 4096 bytes"):
        gunzip_capped(bomb, "https://x.dev/s.xml.gz", limit=4096)
    assert gunzip_capped(bomb, "https://x.dev/s.xml.gz", limit=10_000) == b"\0" * 10_000


def test_fetch_rejects_an_oversized_body(monkeypatch):
    from llms_txt_gen import sitemap

    monkeypatch.setattr(sitemap, "MAX_BYTES", 10)
    _serve(monkeypatch, b"x" * 11)
    with pytest.raises(FetchError, match="larger than 10 bytes"):
        fetch("https://docs.example.com/sitemap.xml")


@pytest.fixture
def local_site():
    """A loopback HTTP server with a few behaviours probe() has to handle."""
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def _route(self, head: bool) -> None:
            path = self.path
            if path == "/ok":
                code, headers = 200, {}
            elif path == "/no-head" and head:
                code, headers = 405, {}
            elif path == "/no-head":
                code, headers = 200, {}
            elif path == "/gone":
                code, headers = 404, {}
            elif path.startswith("/hop/"):
                n = int(path.rsplit("/", 1)[1])
                code, headers = 302, {"Location": f"/hop/{n + 1}" if n < 20 else "/ok"}
            elif path == "/to-ftp":
                code, headers = 302, {"Location": "ftp://example.com/x"}
            else:
                code, headers = 500, {}
            self.send_response(code)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_HEAD(self):
            self._route(head=True)

        def do_GET(self):
            self._route(head=False)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_probe_statuses_head_fallback_and_redirects(local_site):
    assert probe(local_site + "/ok", 5) == 200
    assert probe(local_site + "/no-head", 5) == 200
    assert probe(local_site + "/gone", 5) == 404
    assert probe(local_site + "/hop/17", 5) == 200  # 4 redirects, then /ok
    with pytest.raises(FetchError, match="more than 5 redirects"):
        probe(local_site + "/hop/0", 5)
    with pytest.raises(FetchError, match="unsupported URL"):
        probe(local_site + "/to-ftp", 5)


def test_probe_rejects_other_schemes_and_reports_refused_connections():
    with pytest.raises(FetchError, match="unsupported URL scheme"):
        probe("file:///etc/hosts")
    with pytest.raises(FetchError):
        probe("http://127.0.0.1:1/", 2)
