# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `diff BEFORE AFTER` compares distinct link URLs in local or remote llms.txt files. Sorted text or JSON additions/removals and exit codes (0 unchanged, 1 changed, 2 invalid/unreadable input) let deployment checks detect lost documentation links without fetching the linked pages. (#11)

## [0.3.0] - 2026-10-20

### Added

- `check --fetch`: request every distinct `http(s)` link (`HEAD`, then `GET` when `HEAD` gets 400 or above, body never read, at most 5 redirects and only to HTTP URLs) and report `E007` for a status of 400 or above or a network error. `--max-links` (default 100) caps the requests and `I002` counts the rest. (#10)

### Fixed

- `generate` from a gzipped sitemap no longer stops with a Python traceback when the gzip data is truncated or corrupt; it reports `bad gzip data` like any other fetch error. The 5 MB response cap now also applies after decompression, so a small compressed sitemap cannot expand without limit in memory.

### Changed

- README: a "who it is for" line and the exact command that produces the example output.

## [0.2.0] - 2026-10-09

### Added

- Honour local Markdown `llms: false` exclusions and `llms-section` overrides.

## [0.1.1] - 2026-10-06

### Changed

- Removed the umbrella branding; this project stands alone and links its sibling repositories directly.

## [0.1.0] - 2026-10-04

### Added

- Container image `ghcr.io/basitalisandhu/llms-txt-gen` for linux/amd64 and linux/arm64, published on each version tag with an SPDX SBOM, a build provenance attestation and a keyless cosign signature. The image runs as uid 1000 with `/work` as the working directory.
- `llms-txt-gen generate` for directories of Markdown or HTML and for sitemap URLs (sitemap indexes followed, page cap, per-request timeout, 5 MB response cap), with `--full` for `llms-full.txt`, `--base-url`, `--strip-ext`, `--include`, `--exclude`, `--optional`, `--title`, `--summary` and `--body`.
- `llms-txt-gen check` with text and JSON output, `--strict`, exit codes, and local link checking for files.
- `llms-txt-gen serve-snippet` for the `<link rel="alternate">` tag and the equivalent `Link:` header.
- Composite GitHub Action, pre-commit hook, CI and release workflows, worked example under `examples/`.

### Changed

- Renamed the umbrella project from Hisar to Masoon; links, names and identifiers updated.
- PyPI publishing (release.yml) is off until the repository variable `PYPI_PUBLISH` is set to `true`.

[Unreleased]: https://github.com/basitalisandhu/llms-txt-gen/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/basitalisandhu/llms-txt-gen/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/basitalisandhu/llms-txt-gen/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/basitalisandhu/llms-txt-gen/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/basitalisandhu/llms-txt-gen/releases/tag/v0.1.0
