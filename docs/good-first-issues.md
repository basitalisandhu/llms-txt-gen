# Good first issues

Issues the maintainer intends to open under the `good first issue` label, written out so they
can be filed in one sitting. Each is self-contained and has acceptance criteria that `make check`
can verify. Read [CONTRIBUTING.md](../CONTRIBUTING.md) first: `ruff` must pass, the committed
example output under `examples/` must be regenerated when generation changes, and output must
stay deterministic.

## 1. Honour `llms: false` in front matter

**Context.** Some pages (drafts, redirects, internal notes) should never be listed. Today the only
way to skip them is `--exclude`.

**Acceptance criteria.**

- A Markdown file whose front matter contains `llms: false` is skipped by `scan_directory`.
- `llms-section: Name` in front matter overrides the folder-derived section.
- Tests in `tests/test_discover_build.py` for both keys; README "How the content is chosen" documents them.

## 2. Read the MkDocs `nav` for section names and order

**Context.** MkDocs projects already declare their navigation in `mkdocs.yml`. Using it gives
human-chosen section names and page order instead of folder names and file order.

**Acceptance criteria.**

- `llms-txt-gen generate --nav mkdocs.yml` reads the `nav` list (nested mappings and plain paths)
  with the standard library only (a small YAML subset parser is acceptable; document its limits).
- Pages found in `nav` take their section and order from it; pages not in `nav` keep today's rules.
- Tests with a two-level nav fixture; README option table gains a row.

## 3. Add `check --fetch` for link liveness

**Context.** `check` verifies relative links on disk but never fetches URLs. An optional liveness
check helps when the file is kept by hand.

**Acceptance criteria.**

- `check --fetch` issues a HEAD request (GET fallback) for each `http(s)` link with the same
  timeout, scheme and size rules as `generate`, reporting `E007` for status 400 and above or a
  network error.
- Requests are capped at `--max-links` (default 100) and never follow more than 5 redirects.
- Tests use a fake fetcher; no test touches the network.

## 4. Add a `diff` command

**Context.** Reviewers want to see which links a regeneration adds or removes.

**Acceptance criteria.**

- `llms-txt-gen diff OLD NEW` prints added and removed link URLs grouped by section and exits 1
  when anything changed (`--quiet` suppresses output).
- Implemented on top of `check_text` so malformed files are reported, not crashed on.
- Tests in `tests/test_cli.py`; README "Commands" table gains a row.

## 5. Issue form for reporting a documentation generator the tool handles badly

**Context.** Most bug reports will be "my Docusaurus/Sphinx output produced odd titles". A form
captures the generator, a sample file and the expected line.

**Acceptance criteria.**

- `.github/ISSUE_TEMPLATE/extraction-problem.yml` with fields: generator and version, a minimal
  input file, the line `generate` produced, the line you expected.
- `.github/ISSUE_TEMPLATE/config.yml` disabling blank issues and linking SECURITY.md for
  vulnerabilities.
- Both parse as YAML; CONTRIBUTING links the form.

## 6. Document the JSON output of `check`

**Context.** `check --format json` is what the GitHub Action and other scripts consume, but its
shape is only visible by running it.

**Acceptance criteria.**

- `docs/check-json.md` describes every key (`source`, `ok`, `title`, `sections`, `links`,
  `findings[]` with `level`, `code`, `message`, `line`) with one example value each.
- A test parses the table in that document and asserts the key set equals the keys the CLI emits,
  so the document cannot drift.
- README links the document from the `check` row of the "Commands" table.
