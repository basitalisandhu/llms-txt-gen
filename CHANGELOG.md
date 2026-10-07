# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/basitalisandhu/llms-txt-gen/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/basitalisandhu/llms-txt-gen/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/basitalisandhu/llms-txt-gen/releases/tag/v0.1.0
