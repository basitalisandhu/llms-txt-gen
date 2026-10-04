# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | yes |

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting on this repository (Security tab, "Report a vulnerability") rather than a public issue. Include the version, the command you ran and a minimal input that reproduces the problem.

You will get an acknowledgement within 7 days and a fix or a mitigation plan within 30 days for confirmed issues. Credit is given in the release notes unless you prefer otherwise.

## Scope

llms-txt-gen reads local Markdown and HTML files, or fetches a sitemap and the pages it lists, and writes text files. It never executes content from the input. Network access happens only when a URL is passed on the command line; requests are limited to `http` and `https`, carry a timeout, are capped at 5 MB per response, and the number of pages fetched is capped by `--max-pages`.

Issues of interest: path handling in `--out` and `--full-out`, server-side request forgery through sitemap entries (for example a sitemap that lists internal addresses; the tool follows whatever the sitemap lists, so run it with the network access you would give a crawler), decompression bombs in gzip-encoded sitemaps, HTML parsing hazards, and dependency problems in the development tooling. Output that a model later misreads is not a vulnerability in the tool.
