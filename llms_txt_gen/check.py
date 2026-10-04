"""Validate an llms.txt file against the llmstxt.org convention."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

LINK_LINE_RE = re.compile(r"^- \[(?P<name>[^\]]+)\]\((?P<url>[^)\s]+)\)(?::\s*(?P<notes>.*))?$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")

ERROR = "error"
WARNING = "warning"
INFO = "info"


@dataclass
class Finding:
    level: str
    code: str
    message: str
    line: int | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class CheckResult:
    findings: list[Finding]
    title: str | None
    sections: list[str]
    link_count: int

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.level == WARNING]

    def ok(self, strict: bool = False) -> bool:
        return not self.errors and not (strict and self.warnings)


def _local_target(url: str, base_dir: Path) -> Path | None:
    """Return the path a relative link points at, or None for external and anchor links."""
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or url.startswith(("#", "mailto:", "tel:")):
        return None
    path = unquote(parts.path)
    if not path:
        return None
    if path.startswith("/"):
        return (base_dir / path.lstrip("/")).resolve()
    return (base_dir / path).resolve()


def check_text(text: str, base_dir: Path | None = None) -> CheckResult:
    findings: list[Finding] = []
    lines = text.splitlines()
    title: str | None = None
    sections: list[str] = []
    current_section: str | None = None
    section_links: dict[str, int] = {}
    seen_urls: dict[str, int] = {}
    link_count = 0
    summary_seen = False
    in_code = False
    first_content_line: int | None = None

    for number, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code or not stripped:
            continue
        if first_content_line is None:
            first_content_line = number
        heading = HEADING_RE.match(line)
        if heading:
            level, name = len(heading.group(1)), heading.group(2).strip()
            if level == 1:
                if title is None:
                    title = name
                    if number != first_content_line:
                        findings.append(
                            Finding(ERROR, "E002", "content appears before the H1 title", number)
                        )
                    if not name:
                        findings.append(Finding(ERROR, "E001", "H1 title is empty", number))
                else:
                    findings.append(
                        Finding(ERROR, "E004", f"more than one H1 heading ('{name}')", number)
                    )
            elif level == 2:
                if title is None:
                    findings.append(Finding(ERROR, "E002", "section before the H1 title", number))
                if name in section_links:
                    findings.append(Finding(WARNING, "W007", f"duplicate section '{name}'", number))
                current_section = name
                sections.append(name)
                section_links.setdefault(name, 0)
            else:
                findings.append(
                    Finding(
                        ERROR,
                        "E003",
                        f"H{level} heading '{name}'; only H1 (title) and H2 (sections) are allowed",
                        number,
                    )
                )
            continue
        if stripped.startswith(">") and current_section is None and not summary_seen:
            summary_seen = True
            if len(stripped.lstrip("> ").strip()) < 10:
                findings.append(
                    Finding(WARNING, "W008", "summary blockquote is very short", number)
                )
            continue
        if current_section is not None:
            m = LINK_LINE_RE.match(line)
            if not m:
                if stripped.startswith(("-", "*", "+")):
                    findings.append(
                        Finding(
                            ERROR,
                            "E005",
                            "list item is not of the form '- [name](url): notes'",
                            number,
                        )
                    )
                else:
                    findings.append(
                        Finding(
                            WARNING,
                            "W009",
                            "prose inside a section; sections should contain only link lines",
                            number,
                        )
                    )
                continue
            url = m.group("url")
            link_count += 1
            section_links[current_section] += 1
            if not m.group("name").strip():
                findings.append(Finding(ERROR, "E005", "link has an empty name", number))
            if url in seen_urls:
                findings.append(
                    Finding(
                        WARNING,
                        "W004",
                        f"duplicate link {url} (first seen on line {seen_urls[url]})",
                        number,
                    )
                )
            else:
                seen_urls[url] = number
            if base_dir is not None:
                target = _local_target(url, base_dir)
                if target is not None and not target.exists():
                    findings.append(Finding(ERROR, "E006", f"broken local link: {url}", number))

    if title is None:
        findings.append(Finding(ERROR, "E001", "missing H1 title; the first line must be '# Name'"))
    if not summary_seen:
        findings.append(Finding(WARNING, "W001", "no summary blockquote ('> ...') after the title"))
    if not sections:
        findings.append(Finding(WARNING, "W002", "no H2 sections with links"))
    for name, count in section_links.items():
        if count == 0:
            findings.append(Finding(WARNING, "W003", f"section '{name}' has no links"))
    if "Optional" in sections and sections[-1] != "Optional":
        findings.append(
            Finding(WARNING, "W005", "the 'Optional' section should be the last section")
        )
    findings.append(Finding(INFO, "I001", f"{len(sections)} section(s), {link_count} link(s)"))
    return CheckResult(findings=findings, title=title, sections=sections, link_count=link_count)


def check_file(path: Path) -> CheckResult:
    text = path.read_text(encoding="utf-8", errors="replace")
    return check_text(text, base_dir=path.resolve().parent)


def format_text(result: CheckResult, source: str) -> str:
    out = [f"{source}: {'ok' if result.ok() else 'problems found'}"]
    for f in result.findings:
        where = f":{f.line}" if f.line else ""
        out.append(f"  {f.level:<7} {f.code} {source}{where}: {f.message}")
    return "\n".join(out) + "\n"
