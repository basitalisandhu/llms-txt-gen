# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-03

### Added

- `llms-txt-gen generate` for directories of Markdown or HTML and for sitemap URLs (sitemap indexes followed, page cap, per-request timeout, 5 MB response cap), with `--full` for `llms-full.txt`, `--base-url`, `--strip-ext`, `--include`, `--exclude`, `--optional`, `--title`, `--summary` and `--body`.
- `llms-txt-gen check` with text and JSON output, `--strict`, exit codes, and local link checking for files.
- `llms-txt-gen serve-snippet` for the `<link rel="alternate">` tag and the equivalent `Link:` header.
- Composite GitHub Action, pre-commit hook, CI and release workflows, worked example under `examples/`.

[Unreleased]: https://github.com/basitalisandhu/llms-txt-gen/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/basitalisandhu/llms-txt-gen/releases/tag/v0.1.0
