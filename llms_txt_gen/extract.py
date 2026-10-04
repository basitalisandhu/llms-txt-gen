"""Title, summary and text extraction from Markdown and HTML sources."""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser

MAX_SUMMARY = 200
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_H1_RE = re.compile(r"^#\s+(.+?)\s*#*\s*$", re.M)
_SETEXT_H1_RE = re.compile(r"^(?!\s*$)(.+)\n=+\s*$", re.M)
_INLINE_MD_RE = re.compile(r"(\*\*|__|`|\*|_)")
_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def truncate(text: str, limit: int = MAX_SUMMARY) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit + 1]
    for sep in (". ", "; ", ", ", " "):
        idx = cut.rfind(sep)
        minimum = limit // 4 if sep == ". " else limit // 2
        if idx >= minimum:
            return cut[: idx + 1] if sep == ". " else cut[:idx].rstrip(" ,;") + "..."
    return cut[:limit].rstrip() + "..."


def strip_inline_markdown(text: str) -> str:
    text = _LINK_RE.sub(r"\1", text)
    text = _HTML_TAG_RE.sub("", text)
    text = _INLINE_MD_RE.sub("", text)
    return unescape(text).strip()


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return simple key: value pairs from YAML-style front matter and the remaining body."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t", "-")):
            key, _, value = line.partition(":")
            meta[key.strip().lower()] = value.strip().strip("'\"")
    return meta, text[m.end() :]


def markdown_title(text: str, fallback: str) -> str:
    meta, body = parse_frontmatter(text)
    if meta.get("title"):
        return meta["title"]
    m = _H1_RE.search(body)
    if m:
        return strip_inline_markdown(m.group(1))
    m = _SETEXT_H1_RE.search(body)
    if m:
        return strip_inline_markdown(m.group(1))
    return fallback


def markdown_summary(text: str) -> str:
    """First prose paragraph after the title, or the front matter description."""
    meta, body = parse_frontmatter(text)
    for key in ("description", "summary"):
        if meta.get(key):
            return truncate(meta[key])
    lines = body.splitlines()
    paragraph: list[str] = []
    in_code = False
    seen_title = False
    for raw in lines:
        line = raw.rstrip()
        if line.startswith("```") or line.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if not seen_title and (line.startswith("#") or _SETEXT_H1_RE.match(line + "\n=")):
            seen_title = True
            continue
        stripped = line.strip()
        if not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith(("#", ">", "-", "*", "+", "|", "<", "!", "[")) or re.match(
            r"^\d+\.", stripped
        ):
            if paragraph:
                break
            continue
        if re.match(r"^=+$|^-+$", stripped):
            continue
        paragraph.append(stripped)
    return truncate(strip_inline_markdown(" ".join(paragraph)))


def markdown_text(text: str) -> str:
    _, body = parse_frontmatter(text)
    return body.strip() + "\n"


class _HTMLExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.h1 = ""
        self.first_p = ""
        self.text_parts: list[str] = []
        self._stack: list[str] = []
        self._skip = 0
        self._collect: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header", "template"}:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "meta":
            a = {k.lower(): (v or "") for k, v in attrs}
            is_description = (
                a.get("name", "").lower() in {"description", "og:description"}
                or a.get("property", "").lower() == "og:description"
            )
            if is_description and not self.description:
                self.description = a.get("content", "")
        if tag in {"title", "h1", "p"} and self._collect is None:
            self._collect = tag
            self._buf = []
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "pre"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header", "template"}:
            if self._skip:
                self._skip -= 1
            return
        if self._skip:
            return
        if self._collect == tag:
            value = " ".join("".join(self._buf).split())
            if tag == "title" and not self.title:
                self.title = value
            elif tag == "h1" and not self.h1:
                self.h1 = value
            elif tag == "p" and not self.first_p and value:
                self.first_p = value
            self._collect = None
        if tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "pre"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._collect is not None:
            self._buf.append(data)
        self.text_parts.append(data)


def parse_html(text: str) -> _HTMLExtractor:
    parser = _HTMLExtractor()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        pass
    return parser


def html_title(text: str, fallback: str) -> str:
    p = parse_html(text)
    title = p.h1 or p.title
    if title:
        # "Page name | Site name" and "Page name - Site name" are common; keep the page part.
        for sep in (" | ", " - ", " :: ", " · "):
            if sep in title and p.h1 == "":
                title = title.split(sep)[0].strip()
                break
    return title or fallback


def html_summary(text: str) -> str:
    p = parse_html(text)
    return truncate(p.description or p.first_p)


def html_text(text: str) -> str:
    p = parse_html(text)
    raw = "".join(p.text_parts)
    lines = [" ".join(line.split()) for line in raw.splitlines()]
    out: list[str] = []
    blank = False
    for line in lines:
        if line:
            out.append(line)
            blank = False
        elif not blank and out:
            out.append("")
            blank = True
    return "\n".join(out).strip() + "\n"


def humanise(name: str) -> str:
    """Turn 'getting-started' or 'api_reference' into 'Getting started'."""
    name = re.sub(r"^\d+[-_.]\s*", "", name)
    name = name.replace("-", " ").replace("_", " ").strip()
    if not name:
        return "Docs"
    return name[0].upper() + name[1:]
