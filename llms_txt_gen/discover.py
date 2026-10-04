"""Discover pages in a local directory of Markdown or HTML files."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

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

MARKDOWN_SUFFIXES = {".md", ".mdx", ".markdown"}
HTML_SUFFIXES = {".html", ".htm"}
DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "_build",
    "site-packages",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}
INDEX_NAMES = {"readme.md", "index.md", "index.mdx", "index.html", "index.htm"}
MAX_FILE_BYTES = 5 * 1024 * 1024


def _excluded(rel: str, patterns: list[str]) -> bool:
    parts = rel.split("/")
    for pat in patterns:
        if fnmatch.fnmatch(rel, pat) or any(fnmatch.fnmatch(part, pat) for part in parts):
            return True
    return False


def iter_files(root: Path, include: list[str] | None, exclude: list[str] | None) -> list[Path]:
    """Return candidate files under root, sorted, honouring include and exclude globs."""
    root = root.resolve()
    patterns = list(exclude or [])
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in DEFAULT_EXCLUDE_DIRS and not d.startswith(".")
        )
        for name in sorted(filenames):
            p = Path(dirpath) / name
            suffix = p.suffix.lower()
            if suffix not in MARKDOWN_SUFFIXES | HTML_SUFFIXES:
                continue
            rel = p.relative_to(root).as_posix()
            if include and not any(fnmatch.fnmatch(rel, pat) for pat in include):
                continue
            if _excluded(rel, patterns):
                continue
            if name.lower() in {"llms.txt", "llms-full.txt"}:
                continue
            found.append(p)
    return found


def make_url(rel: str, base_url: str | None, strip_ext: bool) -> str:
    path = rel
    if strip_ext:
        stem, _, ext = path.rpartition(".")
        if stem and ext.lower() in {"md", "mdx", "markdown", "html", "htm"}:
            path = stem
            if path.endswith("/index") or path == "index":
                path = path[: -len("index")] or "./"
    if base_url:
        return base_url.rstrip("/") + "/" + path.lstrip("/")
    return path


def section_for(rel: str) -> str:
    parts = rel.split("/")
    if len(parts) == 1:
        return "Docs"
    return humanise(parts[0])


def read_page(path: Path, rel: str, url: str) -> Page | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    fallback = humanise(path.stem)
    if path.suffix.lower() in HTML_SUFFIXES:
        title, summary, content = html_title(text, fallback), html_summary(text), html_text(text)
    else:
        title = markdown_title(text, fallback)
        summary, content = markdown_summary(text), markdown_text(text)
    return Page(
        title=title, url=url, summary=summary, section=section_for(rel), content=content, rel=rel
    )


def scan_directory(
    root: Path,
    base_url: str | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    strip_ext: bool = False,
) -> tuple[list[Page], Page | None]:
    """Return (pages, index_page). The root README or index, when present, is returned separately
    so the caller can use it for the document title and summary."""
    root = root.resolve()
    pages: list[Page] = []
    index: Page | None = None
    for order, path in enumerate(iter_files(root, include, exclude)):
        rel = path.relative_to(root).as_posix()
        page = read_page(path, rel, make_url(rel, base_url, strip_ext))
        if page is None:
            continue
        page.order = order
        if "/" not in rel and path.name.lower() in INDEX_NAMES and index is None:
            index = page
            continue
        if path.name.lower() in INDEX_NAMES and "/" in rel:
            # docs/guides/index.md describes its folder; list it first in that section.
            page.order = -1
        pages.append(page)
    return pages, index
