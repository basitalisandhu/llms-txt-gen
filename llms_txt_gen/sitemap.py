"""Fetch pages listed in a sitemap. This is the only part of the tool that uses the network."""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from collections.abc import Callable
from urllib.parse import urlsplit

from . import __version__
from .extract import (
    html_summary,
    html_text,
    html_title,
    humanise,
    markdown_summary,
    markdown_text,
    markdown_title,
)
from .model import Page

DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_PAGES = 200
MAX_SITEMAPS = 50
MAX_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
USER_AGENT = f"llms-txt-gen/{__version__} (+https://github.com/basitalisandhu/llms-txt-gen)"

Fetcher = Callable[[str, float], tuple[bytes, str]]
Prober = Callable[[str, float], int]


class FetchError(Exception):
    pass


def fetch(url: str, timeout: float = DEFAULT_TIMEOUT) -> tuple[bytes, str]:
    """GET a URL with a timeout and a size cap. Returns (body, content_type)."""
    scheme = urlsplit(url).scheme.lower()
    if scheme not in {"http", "https"}:
        raise FetchError(f"unsupported URL scheme: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read(MAX_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise FetchError(f"{url}: {exc}") from exc
    if len(body) > MAX_BYTES:
        raise FetchError(f"{url}: response larger than {MAX_BYTES} bytes")
    if url.endswith(".gz") or body[:2] == b"\x1f\x8b":
        body = gunzip_capped(body, url)
    return body, content_type


def gunzip_capped(data: bytes, url: str, limit: int = MAX_BYTES) -> bytes:
    """Decompress gzip data, refusing output over `limit` bytes and reporting bad data.

    The size cap on the download alone is not enough: a few megabytes of gzip can
    expand to gigabytes. Truncated or corrupt data raises FetchError instead of the
    EOFError or zlib.error the standard library would raise.
    """
    inflater = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
    try:
        out = inflater.decompress(data, limit + 1)
    except zlib.error as exc:
        raise FetchError(f"{url}: bad gzip data ({exc})") from exc
    if len(out) > limit:
        raise FetchError(f"{url}: decompressed response larger than {limit} bytes")
    if not inflater.eof:
        raise FetchError(f"{url}: bad gzip data (truncated)")
    return out


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def parse_sitemap(data: bytes) -> tuple[list[str], list[str]]:
    """Return (page_urls, nested_sitemap_urls) from a urlset or sitemapindex document."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise FetchError(f"sitemap is not well-formed XML: {exc}") from exc
    pages: list[str] = []
    nested: list[str] = []
    kind = _local(root.tag)
    for entry in root:
        if _local(entry.tag) not in {"url", "sitemap"}:
            continue
        loc = next((c.text.strip() for c in entry if _local(c.tag) == "loc" and c.text), None)
        if not loc:
            continue
        if kind == "sitemapindex" or _local(entry.tag) == "sitemap":
            nested.append(loc)
        else:
            pages.append(loc)
    return pages, nested


def crawl_sitemap(
    url: str,
    max_pages: int = DEFAULT_MAX_PAGES,
    timeout: float = DEFAULT_TIMEOUT,
    fetcher: Fetcher = fetch,
) -> list[str]:
    """Collect page URLs from a sitemap, following sitemap indexes, up to max_pages."""
    queue = [url]
    seen_maps: set[str] = set()
    urls: list[str] = []
    seen_urls: set[str] = set()
    while queue and len(seen_maps) < MAX_SITEMAPS and len(urls) < max_pages:
        current = queue.pop(0)
        if current in seen_maps:
            continue
        seen_maps.add(current)
        data, _ = fetcher(current, timeout)
        pages, nested = parse_sitemap(data)
        for p in pages:
            if p not in seen_urls:
                seen_urls.add(p)
                urls.append(p)
                if len(urls) >= max_pages:
                    break
        queue.extend(n for n in nested if n not in seen_maps)
    return urls


def section_for_url(url: str) -> str:
    path = urlsplit(url).path.strip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) <= 1:
        return "Docs"
    return humanise(parts[0])


def page_from_response(url: str, body: bytes, content_type: str) -> Page:
    text = body.decode("utf-8", errors="replace")
    path = urlsplit(url).path
    fallback = humanise(
        path.rstrip("/").rsplit("/", 1)[-1].rsplit(".", 1)[0] or urlsplit(url).netloc
    )
    is_markdown = "markdown" in content_type or path.lower().endswith((".md", ".markdown", ".mdx"))
    if is_markdown:
        title, summary, content = (
            markdown_title(text, fallback),
            markdown_summary(text),
            markdown_text(text),
        )
    else:
        title, summary, content = html_title(text, fallback), html_summary(text), html_text(text)
    rel = urlsplit(url).path.lstrip("/")
    return Page(
        title=title,
        url=url,
        summary=summary,
        section=section_for_url(url),
        content=content,
        rel=rel,
    )


def pages_from_sitemap(
    sitemap_url: str,
    max_pages: int = DEFAULT_MAX_PAGES,
    timeout: float = DEFAULT_TIMEOUT,
    fetcher: Fetcher = fetch,
    log: Callable[[str], None] | None = None,
) -> list[Page]:
    log = log or (lambda msg: print(msg, file=sys.stderr))
    urls = crawl_sitemap(sitemap_url, max_pages=max_pages, timeout=timeout, fetcher=fetcher)
    pages: list[Page] = []
    for order, url in enumerate(urls):
        try:
            body, content_type = fetcher(url, timeout)
        except FetchError as exc:
            log(f"skipped {exc}")
            continue
        page = page_from_response(url, body, content_type)
        page.order = order
        pages.append(page)
    return pages


class _HttpOnlyRedirects(urllib.request.HTTPRedirectHandler):
    """Follow at most MAX_REDIRECTS redirects, and only to http or https URLs."""

    max_redirections = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme.lower() not in {"http", "https"}:
            raise FetchError(f"{req.full_url}: redirect to unsupported URL {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def probe(url: str, timeout: float = DEFAULT_TIMEOUT) -> int:
    """Return the final HTTP status of `url` without reading the body.

    Sends HEAD first and falls back to GET when HEAD gets a status of 400 or
    above, since some servers refuse or mishandle HEAD. Follows at most
    MAX_REDIRECTS redirects. Network errors and redirect loops raise FetchError.
    """
    if urlsplit(url).scheme.lower() not in {"http", "https"}:
        raise FetchError(f"unsupported URL scheme: {url}")
    opener = urllib.request.build_opener(_HttpOnlyRedirects)
    status = 0
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(
            url, method=method, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
        )
        try:
            with opener.open(req, timeout=timeout) as resp:
                return resp.status
        except urllib.error.HTTPError as exc:
            if exc.code < 400:  # a redirect urllib gave up on
                raise FetchError(f"{url}: more than {MAX_REDIRECTS} redirects") from None
            status = exc.code
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise FetchError(f"{url}: {exc}") from exc
    return status


def is_url(value: str) -> bool:
    return bool(re.match(r"^https?://", value, re.I))
