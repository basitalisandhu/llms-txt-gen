"""Command line interface: generate, check, diff and serve-snippet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .build import build_document, render_llms_full, render_llms_txt
from .check import DEFAULT_MAX_LINKS, check_file, check_links_live, check_text, format_text
from .discover import scan_directory
from .extract import humanise
from .sitemap import (
    DEFAULT_MAX_PAGES,
    DEFAULT_TIMEOUT,
    FetchError,
    fetch,
    is_url,
    pages_from_sitemap,
    probe,
)
from .snippet import snippet

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llms-txt-gen",
        description="Generate llms.txt for any docs site or repository, and check existing files.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser(
        "generate",
        help="build llms.txt (and optionally llms-full.txt) from a directory or a sitemap URL",
    )
    gen.add_argument("source", help="directory of Markdown/HTML files, or a sitemap.xml URL")
    gen.add_argument("--out", "-o", default="llms.txt", help="output path (default: llms.txt)")
    gen.add_argument("--full", action="store_true", help="also write llms-full.txt next to --out")
    gen.add_argument("--full-out", help="path for llms-full.txt (default: derived from --out)")
    gen.add_argument(
        "--title", help="H1 title (default: README title, or the directory or host name)"
    )
    gen.add_argument(
        "--summary", help="blockquote summary (default: first paragraph of the README)"
    )
    gen.add_argument(
        "--body", action="append", default=[], help="extra paragraph after the summary (repeatable)"
    )
    gen.add_argument("--base-url", help="prefix for links when generating from a directory")
    gen.add_argument("--strip-ext", action="store_true", help="drop .md/.html from generated links")
    gen.add_argument(
        "--include", action="append", default=[], help="glob of files to include (repeatable)"
    )
    gen.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="glob of files or directories to exclude (repeatable)",
    )
    gen.add_argument(
        "--optional",
        action="append",
        default=[],
        help="glob of URLs or section names to put under 'Optional' (repeatable)",
    )
    gen.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help=f"page cap when reading a sitemap (default {DEFAULT_MAX_PAGES})",
    )
    gen.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"per-request timeout in seconds (default {DEFAULT_TIMEOUT:g})",
    )
    gen.add_argument(
        "--stdout", action="store_true", help="print llms.txt instead of writing --out"
    )

    chk = sub.add_parser("check", help="validate an llms.txt file or URL against the convention")
    chk.add_argument("target", help="path to llms.txt, or an http(s) URL")
    chk.add_argument("--format", choices=["text", "json"], default="text")
    chk.add_argument("--strict", action="store_true", help="treat warnings as errors")
    chk.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"per-request timeout in seconds (default {DEFAULT_TIMEOUT:g})",
    )
    chk.add_argument(
        "--fetch",
        action="store_true",
        help="also request every http(s) link (HEAD, then GET) and report E007 for failures",
    )
    chk.add_argument(
        "--max-links",
        type=int,
        default=DEFAULT_MAX_LINKS,
        help=f"most links --fetch requests (default {DEFAULT_MAX_LINKS})",
    )

    diff = sub.add_parser("diff", help="compare link sets in two llms.txt files or URLs")
    diff.add_argument("before", help="previous llms.txt file or http(s) URL")
    diff.add_argument("after", help="current llms.txt file or http(s) URL")
    diff.add_argument("--format", choices=["text", "json"], default="text")
    diff.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)

    snip = sub.add_parser("serve-snippet", help='print the <link rel="alternate"> tag for llms.txt')
    snip.add_argument("--href", default="/llms.txt", help="href for the tag (default /llms.txt)")
    snip.add_argument("--full", action="store_true", help="also print the llms-full.txt tag")
    snip.add_argument(
        "--header", action="store_true", help="print HTTP Link headers instead of HTML"
    )
    return parser


def _generate(args: argparse.Namespace) -> int:
    body = list(args.body)
    if is_url(args.source):
        try:
            pages = pages_from_sitemap(
                args.source, max_pages=args.max_pages, timeout=args.timeout, fetcher=fetch
            )
        except FetchError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_USAGE
        if not pages:
            print("error: the sitemap yielded no pages", file=sys.stderr)
            return EXIT_USAGE
        from urllib.parse import urlsplit

        title = args.title or urlsplit(args.source).netloc
        summary = args.summary or ""
    else:
        root = Path(args.source)
        if not root.is_dir():
            print(f"error: {args.source} is not a directory or a URL", file=sys.stderr)
            return EXIT_USAGE
        pages, index = scan_directory(
            root,
            base_url=args.base_url,
            include=args.include or None,
            exclude=args.exclude or None,
            strip_ext=args.strip_ext,
        )
        if not pages and index is None:
            print(f"error: no Markdown or HTML files found under {root}", file=sys.stderr)
            return EXIT_USAGE
        title = args.title or (index.title if index else humanise(root.resolve().name))
        summary = args.summary or (index.summary if index else "")
    doc = build_document(pages, title=title, summary=summary, body=body, optional=args.optional)
    text = render_llms_txt(doc)
    if args.stdout:
        sys.stdout.write(text)
    else:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(
            f"wrote {out} ({len(doc.pages)} links in {len(doc.sections)} sections)", file=sys.stderr
        )
    if args.full:
        full_path = (
            Path(args.full_out) if args.full_out else Path(args.out).with_name("llms-full.txt")
        )
        full_text = render_llms_full(doc)
        if args.stdout:
            sys.stdout.write(full_text)
        else:
            full_path.write_text(full_text, encoding="utf-8")
            print(f"wrote {full_path} ({len(full_text)} characters)", file=sys.stderr)
    return EXIT_OK


def _check(args: argparse.Namespace) -> int:
    if is_url(args.target):
        try:
            body, _ = fetch(args.target, timeout=args.timeout)
        except FetchError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_USAGE
        result = check_text(body.decode("utf-8", errors="replace"))
    else:
        path = Path(args.target)
        if not path.is_file():
            print(f"error: {args.target} is not a file or a URL", file=sys.stderr)
            return EXIT_USAGE
        result = check_file(path)
    if args.fetch:
        if args.max_links < 0:
            print("error: --max-links must be 0 or more", file=sys.stderr)
            return EXIT_USAGE
        check_links_live(result, probe, timeout=args.timeout, max_links=args.max_links)
    if args.format == "json":
        payload = {
            "source": args.target,
            "ok": result.ok(args.strict),
            "title": result.title,
            "sections": result.sections,
            "links": result.link_count,
            "findings": [f.as_dict() for f in result.findings],
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    else:
        sys.stdout.write(format_text(result, args.target))
    return EXIT_OK if result.ok(args.strict) else EXIT_FINDINGS


def _diff(args: argparse.Namespace) -> int:
    link_sets: list[set[str]] = []
    for target in (args.before, args.after):
        try:
            if is_url(target):
                data, _ = fetch(target, timeout=args.timeout)
                text = data.decode("utf-8")
            else:
                text = Path(target).read_text(encoding="utf-8")
            result = check_text(text)
            if result.errors or not result.sections:
                raise ValueError("not a valid llms.txt file")
            link_sets.append({url for _, url in result.links})
        except (OSError, UnicodeError, FetchError, ValueError) as exc:
            print(f"error: {target}: {exc}", file=sys.stderr)
            return EXIT_USAGE
    before, after = link_sets
    added, removed = sorted(after - before), sorted(before - after)
    if args.format == "json":
        sys.stdout.write(json.dumps({"added": added, "removed": removed}, indent=2) + "\n")
    elif not added and not removed:
        sys.stdout.write("No link changes.\n")
    else:
        sys.stdout.write("".join(f"- {url}\n" for url in removed))
        sys.stdout.write("".join(f"+ {url}\n" for url in added))
    return EXIT_FINDINGS if added or removed else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "generate":
        return _generate(args)
    if args.command == "check":
        return _check(args)
    if args.command == "diff":
        return _diff(args)
    if args.command == "serve-snippet":
        sys.stdout.write(snippet(args.href, full=args.full, header=args.header))
        return EXIT_OK
    parser.print_help()
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
