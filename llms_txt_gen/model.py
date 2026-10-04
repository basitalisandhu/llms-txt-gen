"""Data model shared by the discovery, build and check steps."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Page:
    """One document that will become a link line in llms.txt."""

    title: str
    url: str
    summary: str = ""
    section: str = "Docs"
    content: str = ""
    order: int = 0
    rel: str = ""

    def link_line(self) -> str:
        title = _clean_inline(self.title) or self.url
        line = f"- [{title}]({self.url})"
        if self.summary:
            line += f": {_clean_inline(self.summary)}"
        return line


@dataclass
class Section:
    name: str
    pages: list[Page] = field(default_factory=list)


@dataclass
class Document:
    title: str
    summary: str = ""
    body: list[str] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)

    @property
    def pages(self) -> list[Page]:
        return [p for s in self.sections for p in s.pages]


def _clean_inline(text: str) -> str:
    """Collapse whitespace and escape characters that would break a link line."""
    text = " ".join(text.split())
    return text.replace("[", "(").replace("]", ")")
