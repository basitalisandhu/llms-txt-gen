# llms-txt-gen: generate llms.txt for any docs site or repository

Generate llms.txt for any docs site or repository: point `llms-txt-gen` at a directory of Markdown or HTML, or at a sitemap URL, and it writes an `llms.txt` (and, with `--full`, an `llms-full.txt`) that follows the convention published at [llmstxt.org](https://llmstxt.org). It also checks an existing file against that convention and prints the HTML tag that tells crawlers where the file lives. Standard library only, no model in the loop, deterministic output, runs in CI.

[![CI](https://github.com/basitalisandhu/llms-txt-gen/actions/workflows/ci.yml/badge.svg)](https://github.com/basitalisandhu/llms-txt-gen/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

## Why llms.txt

Language models and the tools built on them read documentation the same way a hurried person does: they land on a page, skim, and give up when the navigation, cookie banners and scripts crowd out the text. `llms.txt` is a plain Markdown file at the root of a site (`/llms.txt`) that says, in a few hundred words, what the project is and which pages matter, with one line per page: a name, a link and a short note. A model that reads it first spends its limited context on the right pages. `llms-full.txt` goes one step further and inlines the content of those pages so a tool can load the whole documentation set in one request. Keeping either file by hand drifts out of date within weeks; this tool regenerates them from the source files or the live sitemap on every build.

## Quickstart

```bash
pipx install git+https://github.com/basitalisandhu/llms-txt-gen      # see "Install" below

llms-txt-gen generate docs/ --out llms.txt --base-url https://docs.example.com
llms-txt-gen generate https://docs.example.com/sitemap.xml --out llms.txt --full
llms-txt-gen check llms.txt
llms-txt-gen serve-snippet
```

Output for the bundled [`examples/docs/`](examples/docs/) (committed as [`examples/llms.txt`](examples/llms.txt)):

```text
# Acme Widgets

> Acme Widgets is a small HTTP service for creating and shipping widgets. These pages are the example input for llms-txt-gen; run llms-txt-gen generate examples/docs --stdout to see the output.

## Guides

- [Authentication](https://acme.example.com/docs/guides/authentication): Every request carries a short-lived token in the Authorization header. Tokens expire after one hour and can be rotated at any time.
- [Quickstart](https://acme.example.com/docs/guides/quickstart): Create your first widget in five minutes.

## Reference

- [HTTP API](https://acme.example.com/docs/reference/api): Every endpoint, with request and response examples.
- [Command line](https://acme.example.com/docs/reference/cli): Flags and subcommands of the acme command.

## Optional

- [Changelog](https://acme.example.com/docs/changelog): All notable changes to Acme Widgets, newest first.
```

`llms-txt-gen check examples/llms.txt` then reports `ok` and one info line: `3 section(s), 5 link(s)`.

## Install

Container image (linux/amd64 and linux/arm64), published to GitHub Packages on every release. Mount the docs or repository at `/work`; relative paths, including `--out`, resolve from there:

```bash
docker run --rm -v "$PWD:/work" ghcr.io/basitalisandhu/llms-txt-gen:0.1.1 generate docs --out llms.txt --full
docker run --rm -v "$PWD:/work:ro" ghcr.io/basitalisandhu/llms-txt-gen:0.1.1 check llms.txt --strict
```

The image runs as uid 1000, so the mounted directory must be writable by that user for `generate`. Each image is signed with cosign (keyless) and has a build provenance attestation and an SPDX SBOM (attached to the GitHub Release). To verify:

```bash
cosign verify ghcr.io/basitalisandhu/llms-txt-gen:0.1.1 \
  --certificate-identity-regexp '^https://github.com/basitalisandhu/llms-txt-gen/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
gh attestation verify oci://ghcr.io/basitalisandhu/llms-txt-gen:0.1.1 --owner basitalisandhu
```

Python package: requires Python 3.11 or newer and nothing else. PyPI publication is pending, so install from the repository:

```bash
pipx install git+https://github.com/basitalisandhu/llms-txt-gen                      # isolated CLI install
uvx --from git+https://github.com/basitalisandhu/llms-txt-gen llms-txt-gen --help    # run without installing
pip install git+https://github.com/basitalisandhu/llms-txt-gen                       # into the current environment
git clone https://github.com/basitalisandhu/llms-txt-gen && cd llms-txt-gen && uv sync   # for development
```

Once published to PyPI:

```bash
pip install llms-txt-gen
```

The other short forms work then too: `pipx install llms-txt-gen`, `uvx llms-txt-gen --help`.

## Commands

| Command | What it does |
|---|---|
| `llms-txt-gen generate SOURCE --out llms.txt` | Build `llms.txt` from a directory of `.md`, `.mdx`, `.markdown`, `.html` or `.htm` files, or from a sitemap URL (`sitemap.xml` or a sitemap index). `--full` also writes `llms-full.txt`; `--stdout` prints instead of writing. |
| `llms-txt-gen check FILE-OR-URL` | Validate against the convention: H1 title first, optional blockquote summary, H2 sections of `- [name](url): notes` lines, no deeper headings, `Optional` last, no duplicate links, and for local files no broken relative links. `--format json`, `--strict` (warnings fail). Exit 1 on errors, 2 on usage errors. |
| `llms-txt-gen serve-snippet` | Print `<link rel="alternate" type="text/markdown" href="/llms.txt" title="llms.txt">` for the site `<head>`. `--full` adds the `llms-full.txt` tag, `--header` prints HTTP `Link:` headers instead, `--href` sets the location. |

### generate options

| Option | Meaning |
|---|---|
| `--title`, `--summary`, `--body TEXT` | Override the H1, the blockquote and add free paragraphs after it. Defaults come from the root `README.md` or `index.md` (title and first paragraph); for a sitemap the host name is the title. |
| `--base-url URL` | Prefix for links generated from a directory, so `guides/start.md` becomes `https://docs.example.com/guides/start.md`. |
| `--strip-ext` | Drop `.md` and `.html` from generated links and turn `index` pages into their folder URL. |
| `--include GLOB`, `--exclude GLOB` | Restrict or skip files (repeatable). `node_modules`, `.git`, virtual environments and build directories are always skipped. |
| `--optional GLOB` | URLs or section names matching the glob go to the conventional `## Optional` section, which models may skip when context is short. |
| `--max-pages N` | Page cap when reading a sitemap (default 200). Sitemap indexes are followed, at most 50 sitemaps are read. |
| `--timeout SECONDS` | Per-request timeout for sitemap and page fetches (default 10). Responses over 5 MB are rejected. |

### How the content is chosen

For local Markdown pages, front matter `llms: false` excludes the page from both
outputs, including a root README or index. Front matter `llms-section: Name`
overrides the folder-derived section; an empty value keeps the default section.

- **Title**: front matter `title:`, else the first `# Heading` (or Setext underline heading), else the HTML `<h1>`, else `<title>` with a trailing ` | Site` or ` - Site` removed, else the file name humanised.
- **Note after the link**: front matter `description:`, else the first prose paragraph after the title (code blocks, lists, quotes and tables are skipped), else the HTML `<meta name="description">`, else the first `<p>`. Truncated to 200 characters at a sentence or word boundary.
- **Section**: the first path segment, humanised (`getting-started/` becomes `## Getting started`). Files at the root go under `## Docs`, which is rendered first. A folder's `index.md` is listed first in its section. The root `README.md` or `index.md` supplies the document title and summary and is not listed.
- **Order**: sections alphabetical (`Docs` first, `Optional` last), pages in file order. Two runs over the same input give byte-identical output.
- **`llms-full.txt`**: the title and summary, then every page as `# Title`, `Source: url` and its content (Markdown verbatim without front matter, HTML reduced to text with navigation, scripts and styles removed).

### Network use

`generate` with a URL fetches the sitemap and each page it lists; `check` with a URL fetches that file. Nothing else touches the network. Only `http` and `https` URLs are accepted, every request has a timeout, bodies are capped at 5 MB, the page count is capped by `--max-pages`, and the User-Agent identifies the tool. Pages that fail to fetch are skipped with a message on stderr and do not fail the run.

## Checks

| Code | Level | Meaning |
|---|---|---|
| E001 | error | No H1 title, or an empty one. The first content line must be `# Name`. |
| E002 | error | Content or a section before the H1. |
| E003 | error | A heading deeper than H2. The convention allows only the H1 title and H2 section names. |
| E004 | error | More than one H1. |
| E005 | error | A list item in a section that is not `- [name](url)` or `- [name](url): notes`. |
| E006 | error | A relative link that does not resolve next to the file (local files only; URLs are not fetched). |
| W001 | warning | No blockquote summary after the title. |
| W002 | warning | No H2 sections. |
| W003 | warning | A section with no links. |
| W004 | warning | The same URL linked twice. |
| W005 | warning | `Optional` is not the last section. |
| W007 | warning | Duplicate section name. |
| W008 | warning | The summary is shorter than ten characters. |
| W009 | warning | Prose inside a section; sections should contain only link lines. |
| I001 | info | Section and link counts. |

## CI usage

Regenerate on every change to the docs and fail the build when the committed file is stale or invalid:

```bash
llms-txt-gen generate docs/ --out llms.txt --base-url https://docs.example.com
git diff --exit-code llms.txt
llms-txt-gen check llms.txt --strict
```

### GitHub Action

```yaml
name: llms-txt
on:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  llms-txt:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: basitalisandhu/llms-txt-gen@v0.1.1      # pin a release tag
        with:
          source: docs
          out: llms.txt
          base-url: https://docs.example.com
          full: "true"
      - run: git diff --exit-code llms.txt llms-full.txt || echo "llms.txt changed; commit it"
```

Inputs: `source` (directory or sitemap URL), `out`, `full`, `base-url`, `strip-ext`, `optional` (space-separated globs), `max-pages`, `timeout`, `check` (run `check --strict` on the result, default `true`), `python-version`, `version` (PyPI version; empty installs the action's own checkout). Outputs: `out`, `links`, `sections`. See [action.yml](action.yml).

### pre-commit

Validate `llms.txt` before every commit:

```yaml
repos:
  - repo: https://github.com/basitalisandhu/llms-txt-gen
    rev: v0.1.1
    hooks:
      - id: llms-txt-check
```

## Frequently asked questions

**What goes in llms.txt?**
An H1 with the project name, a one-paragraph blockquote summary, optionally a few paragraphs of context without headings, then H2 sections each holding a list of `- [page name](url): one line about the page`. A section named `Optional` holds pages a model may skip. That is the whole convention; `llms-txt-gen check` enforces it and the README of [llmstxt.org](https://llmstxt.org) documents it.

**Does it need network access?**
Only when you pass a sitemap URL to `generate` or a URL to `check`. Directory mode and file mode never make a request, which is why they are safe in CI and in pre-commit hooks.

**Can I keep the file by hand and only check it?**
Yes. `check` is independent of `generate`. Many projects write the summary by hand and generate only the link lists; use `--title`, `--summary` and `--body` to keep the prose fixed while the lists are regenerated.

**How do I tell crawlers the file exists?**
Serve it at `/llms.txt`, and add the tag from `serve-snippet` to the site `<head>` (or the `Link:` header from `serve-snippet --header`). The tag is a discoverability hint, not part of the convention, so leaving it out does not make the file invalid.

## Roadmap

- `--from-nav` mode that reads MkDocs, Docusaurus and Sphinx navigation files for section names and order.
- Front matter `llms: false` and `llms-section:` keys to exclude or re-home a page.
- A `diff` command that shows which links were added or removed since the committed file.
- Optional link liveness check (`check --fetch`) with the same timeout and cap rules as `generate`.

## Contributing

Issues and pull requests are welcome; the starter list is in [docs/good-first-issues.md](docs/good-first-issues.md). Run `make check` (ruff and pytest) before opening a pull request; see [CONTRIBUTING.md](CONTRIBUTING.md). Security problems: see [SECURITY.md](SECURITY.md).

## Sibling projects

More tools by the same author: https://github.com/basitalisandhu

- [agent-threat-model](https://github.com/basitalisandhu/agent-threat-model): describe an agent system in YAML, get a STRIDE and OWASP Agentic threat model.
- [agent-config-audit](https://github.com/basitalisandhu/agent-config-audit): audit AI agent configuration files for security risks.
- [mcp-server-template](https://github.com/basitalisandhu/mcp-server-template): secure MCP server template in TypeScript and Python.
- [awesome-agent-security](https://github.com/basitalisandhu/awesome-agent-security): curated list of AI agent security tools, papers and datasets.

## Licence

MIT, see [LICENSE](LICENSE). Copyright 2026 Muhammad Basit Ali.
