"""Read the `nav` list of an MkDocs `mkdocs.yml` with a small YAML subset parser.

Only the `nav:` block is read; the rest of the file (themes, plugins, `!!python` tags) is
ignored. Supported inside `nav:`:

- block lists (`- item`) nested by indentation, with any consistent indent;
- `- path.md`, `- Title: path.md` and `- Title:` followed by a nested list;
- single- or double-quoted scalars, and `#` comments after whitespace.

Not supported: flow style (`[a, b]`, `{a: b}`), anchors and aliases, multi-line scalars.
These raise NavError with the line number instead of being guessed at.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .check import InputError, decode_text
from .model import Page

_NAV_KEY_RE = re.compile(r"^nav[ \t]*:[ \t]*(#.*)?$")
_TOP_LEVEL_RE = re.compile(r"^[^\s#-]")


class NavError(ValueError):
    """The nav block cannot be read; the message names the file and line."""


@dataclass(frozen=True)
class NavEntry:
    """A page listed in nav: its path relative to docs_dir, its section, title and position."""

    path: str
    section: str
    title: str | None
    position: int


def _strip_comment(text: str) -> str:
    quote = ""
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i].rstrip()
    return text.rstrip()


def _scalar(text: str, where: str) -> str:
    text = text.strip()
    if text[:1] in "[{&*|>":
        raise NavError(f"{where}: unsupported YAML ({text[:20]!r}); use block lists")
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        inner = text[1:-1]
        return inner.replace("''", "'") if text[0] == "'" else inner
    if text[:1] in "'\"":
        raise NavError(f"{where}: unterminated quote")
    return text


def _split_key(text: str) -> tuple[str, str] | None:
    """Split 'Title: value' at the first ': ' (or a trailing ':') outside quotes."""
    quote = ""
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch == ":" and (i + 1 == len(text) or text[i + 1] in " \t"):
            return text[:i], text[i + 1 :]
    return None


def _nav_lines(text: str, source: str) -> list[tuple[int, int, str]]:
    """Return (line number, indent, content) for each non-blank line of the nav block."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if _NAV_KEY_RE.match(line)), None)
    if start is None:
        inline = next((i for i, line in enumerate(lines) if re.match(r"^nav[ \t]*:", line)), None)
        if inline is not None:
            raise NavError(
                f"{source}:{inline + 1}: 'nav:' must be followed by a block list on the next "
                "lines; flow style ([...]) is not supported"
            )
        raise NavError(f"{source}: no top-level 'nav:' list found")
    out: list[tuple[int, int, str]] = []
    for number, raw in enumerate(lines[start + 1 :], start=start + 2):
        if _TOP_LEVEL_RE.match(raw):
            break
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise NavError(f"{source}:{number}: tab in indentation; YAML needs spaces")
        content = _strip_comment(raw.strip())
        if content:
            out.append((number, len(raw) - len(raw.lstrip()), content))
    return out


def parse_nav(text: str, source: str = "mkdocs.yml") -> list[NavEntry]:
    """Return the local pages listed in the nav block, in order.

    A page's section is the title of its top-level group; pages listed at the top level go
    to "Docs". External links (with a URL scheme) are skipped.
    """
    entries: list[NavEntry] = []
    # One (indent of the '-' items, section name) per nesting level.
    stack: list[tuple[int, str]] = []
    pending: str | None = None  # section for the children of the group on the line above
    for number, indent, content in _nav_lines(text, source):
        where = f"{source}:{number}"
        if not content.startswith("-") or content[1:2] not in ("", " "):
            raise NavError(f"{where}: expected a list item ('- ...') in nav")
        if pending is not None:
            if stack and indent <= stack[-1][0]:
                raise NavError(f"{where}: the group on the line above has no pages")
            stack.append((indent, pending))
            pending = None
        else:
            while stack and indent < stack[-1][0]:
                stack.pop()
            if not stack:
                stack.append((indent, "Docs"))
            elif indent != stack[-1][0]:
                raise NavError(f"{where}: indentation does not match the items above")
        item = content[1:].strip()
        if not item:
            raise NavError(f"{where}: empty list item")
        pair = _split_key(item)
        if pair is None:
            title, target = None, _scalar(item, where)
        else:
            title, value = _scalar(pair[0], where), pair[1].strip()
            if not value:
                # A group. A top-level group names a section; deeper groups stay in it.
                pending = title if len(stack) == 1 else stack[-1][1]
                continue
            target = _scalar(value, where)
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or not target:
            continue  # external link (https:, mailto:) or nothing to match
        target = target.removeprefix("./")
        entries.append(NavEntry(target, stack[-1][1], title or None, len(entries)))
    if pending is not None:
        raise NavError(f"{source}: the last group in nav has no pages")
    return entries


def read_nav(path: Path) -> list[NavEntry]:
    """Read and parse a mkdocs.yml, raising NavError with a clear message on any problem."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise NavError(f"cannot read {path}: {exc.strerror or exc}") from None
    try:
        text = decode_text(data, str(path))
    except InputError as exc:
        raise NavError(str(exc)) from None
    return parse_nav(text, str(path))


def apply_nav(pages: list[Page], entries: list[NavEntry]) -> tuple[list[str], list[str]]:
    """Give pages listed in nav their nav section, position and (when set) title.

    Pages not in nav keep their file order, after the nav pages. They keep their folder
    section too, unless nav pages from the same top-level folder went to a nav section: then
    they join it, so `user-guide/extra.md` is not split off from the "User Guide" pages.
    Returns (section names in nav order, nav paths that matched no page).
    """
    by_path = {e.path: e for e in reversed(entries)}  # first listing wins
    folder_section: dict[str, str] = {}
    for e in entries:
        if "/" in e.path:
            folder_section.setdefault(e.path.split("/", 1)[0], e.section)
    matched: set[str] = set()
    for page in pages:
        entry = by_path.get(page.rel)
        if entry is None:
            folder = page.rel.split("/", 1)[0] if "/" in page.rel else None
            if folder in folder_section:
                page.section = folder_section[folder]
            continue
        matched.add(entry.path)
        page.section = entry.section
        page.order = entry.position - len(entries) - 2  # before every non-nav page (>= -1)
        if entry.title:
            page.title = entry.title
    order: list[str] = []
    for e in entries:
        if e.section not in order:
            order.append(e.section)
    missing = [e.path for e in entries if e.path not in matched]
    return order, missing
