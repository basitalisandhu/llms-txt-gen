from __future__ import annotations

from llms_txt_gen.extract import (
    html_summary,
    html_text,
    html_title,
    humanise,
    markdown_summary,
    markdown_title,
    parse_frontmatter,
    truncate,
)


def test_markdown_title_prefers_frontmatter_then_h1_then_setext_then_fallback():
    assert markdown_title("---\ntitle: From meta\n---\n# Heading\n", "fb") == "From meta"
    assert markdown_title("# Heading *here*\n\ntext", "fb") == "Heading here"
    assert markdown_title("Setext title\n============\n\ntext", "fb") == "Setext title"
    assert markdown_title("no heading at all\n", "fb") == "fb"


def test_markdown_summary_skips_code_lists_and_headings():
    text = "# T\n\n```\ncode\n```\n\n- a list\n\n> quote\n\nThe real [summary](x) with `code`.\nSecond line.\n\nNext paragraph.\n"
    assert markdown_summary(text) == "The real summary with code. Second line."


def test_markdown_summary_uses_description_frontmatter():
    assert markdown_summary("---\ndescription: Short desc.\n---\n# T\n\nBody.\n") == "Short desc."


def test_frontmatter_parsing_ignores_nested_keys():
    meta, body = parse_frontmatter("---\ntitle: X\ntags:\n  - a\n---\nrest\n")
    assert meta == {"title": "X", "tags": ""}
    assert body == "rest\n"


def test_truncate_cuts_at_sentence_or_word_boundary():
    long = "First sentence here. " + "word " * 80
    out = truncate(long, 60)
    assert out == "First sentence here."
    assert truncate("short", 60) == "short"
    words = truncate("a" * 10 + " " + "b" * 70, 40)
    assert words.endswith("...") and len(words) <= 44


def test_html_extraction():
    html = (
        "<html><head><title>Page | Site</title>"
        '<meta name="description" content="Meta description."></head>'
        "<body><nav>skip me</nav><h1>Real title</h1><p>First para.</p><script>x()</script></body></html>"
    )
    assert html_title(html, "fb") == "Real title"
    assert html_summary(html) == "Meta description."
    text = html_text(html)
    assert "Real title" in text and "First para." in text
    assert "skip me" not in text and "x()" not in text


def test_html_title_falls_back_to_title_tag_without_site_suffix():
    assert html_title("<title>Page - Site</title><p>x</p>", "fb") == "Page"
    assert html_title("<p>no title</p>", "fb") == "fb"
    assert html_summary("<p>First para here.</p>") == "First para here."


def test_humanise():
    assert humanise("getting-started") == "Getting started"
    assert humanise("01-api_reference") == "Api reference"
    assert humanise("") == "Docs"
