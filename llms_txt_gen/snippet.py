"""Discoverability snippets for an llms.txt file."""

from __future__ import annotations


def link_tag(href: str = "/llms.txt", title: str = "llms.txt") -> str:
    return f'<link rel="alternate" type="text/markdown" href="{href}" title="{title}">'


def link_header(href: str = "/llms.txt") -> str:
    return f'Link: <{href}>; rel="alternate"; type="text/markdown"'


def snippet(href: str = "/llms.txt", full: bool = False, header: bool = False) -> str:
    if header:
        lines = [link_header(href)]
        if full:
            lines.append(link_header(href.replace("llms.txt", "llms-full.txt")))
        return "\n".join(lines) + "\n"
    lines = [link_tag(href)]
    if full:
        lines.append(link_tag(href.replace("llms.txt", "llms-full.txt"), "llms-full.txt"))
    return "\n".join(lines) + "\n"
