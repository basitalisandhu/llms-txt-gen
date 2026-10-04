"""Group pages into sections and render llms.txt and llms-full.txt."""

from __future__ import annotations

import fnmatch

from .model import Document, Page, Section

OPTIONAL = "Optional"


def _is_optional(page: Page, section: str, patterns: list[str]) -> bool:
    """A page is optional when a glob matches its URL, its path relative to the source, the last
    path segment, its section name or its title (all case-insensitive)."""
    candidates = [page.url, page.rel, page.url.rstrip("/").rsplit("/", 1)[-1], section, page.title]
    return any(fnmatch.fnmatch(c.lower(), pat.lower()) for pat in patterns for c in candidates if c)


def build_document(
    pages: list[Page],
    title: str,
    summary: str = "",
    body: list[str] | None = None,
    optional: list[str] | None = None,
) -> Document:
    """Group pages by section. Pages whose URL or section matches an `optional` glob go to the
    conventional "Optional" section, which is always rendered last."""
    optional = optional or []
    groups: dict[str, list[Page]] = {}
    for page in pages:
        name = page.section or "Docs"
        if _is_optional(page, name, optional):
            name = OPTIONAL
        groups.setdefault(name, []).append(page)

    def section_key(name: str) -> tuple[int, str]:
        if name == "Docs":
            return (0, "")
        if name == OPTIONAL:
            return (2, "")
        return (1, name.lower())

    sections = [
        Section(name, sorted(groups[name], key=lambda p: (p.order, p.title.lower())))
        for name in sorted(groups, key=section_key)
    ]
    return Document(title=title, summary=summary, body=list(body or []), sections=sections)


def render_llms_txt(doc: Document) -> str:
    lines = [f"# {doc.title.strip()}", ""]
    if doc.summary:
        lines += [f"> {' '.join(doc.summary.split())}", ""]
    for paragraph in doc.body:
        text = paragraph.strip()
        if text:
            lines += [text, ""]
    for section in doc.sections:
        if not section.pages:
            continue
        lines.append(f"## {section.name}")
        lines.append("")
        lines.extend(p.link_line() for p in section.pages)
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def render_llms_full(doc: Document) -> str:
    parts = [f"# {doc.title.strip()}", ""]
    if doc.summary:
        parts += [f"> {' '.join(doc.summary.split())}", ""]
    for section in doc.sections:
        for page in section.pages:
            parts.append("---")
            parts.append("")
            parts.append(f"# {page.title.strip()}")
            parts.append("")
            parts.append(f"Source: {page.url}")
            parts.append("")
            content = page.content.strip()
            if content:
                parts.append(content)
                parts.append("")
    return "\n".join(parts).rstrip("\n") + "\n"
