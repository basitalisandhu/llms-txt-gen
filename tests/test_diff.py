from pathlib import Path

import pytest

from .conftest import run, run_json, write


def document(*urls: str) -> str:
    return sections_document({"Pages": list(urls)})


def sections_document(sections: dict[str, list[str]]) -> str:
    body = "".join(
        f"## {name}\n\n" + "".join(f"- [Page]({url})\n" for url in urls)
        for name, urls in sections.items()
    )
    return f"# Docs\n\n> Documentation summary.\n\n{body}"


def test_diff_reports_sorted_added_removed_and_json(tmp_path: Path):
    before = write(tmp_path, "before.txt", document("/keep", "/z", "/a"))
    after = write(tmp_path, "after.txt", document("/keep", "/new", "/b"))
    rc, data = run_json("diff", str(before), str(after), "--format", "json")
    assert rc == 1
    assert data == {
        "added": {"Pages": ["/b", "/new"]},
        "removed": {"Pages": ["/a", "/z"]},
    }
    rc, out, _ = run("diff", str(before), str(after))
    assert rc == 1
    assert "Removed:\n  Pages:\n    - /a\n    - /z\n" in out
    assert "Added:\n  Pages:\n    + /b\n    + /new\n" in out


def test_diff_groups_changes_by_section(tmp_path: Path):
    before = write(
        tmp_path,
        "before.txt",
        sections_document({"Docs": ["/keep", "/old"], "Guides": ["/g-old"]}),
    )
    after = write(
        tmp_path,
        "after.txt",
        sections_document({"Docs": ["/keep", "/new"], "Guides": ["/g-new"]}),
    )
    rc, data = run_json("diff", str(before), str(after), "--format", "json")
    assert rc == 1
    assert data == {
        "added": {"Docs": ["/new"], "Guides": ["/g-new"]},
        "removed": {"Docs": ["/old"], "Guides": ["/g-old"]},
    }
    rc, out, _ = run("diff", str(before), str(after))
    assert rc == 1
    assert out == (
        "Removed:\n"
        "  Docs:\n"
        "    - /old\n"
        "  Guides:\n"
        "    - /g-old\n"
        "Added:\n"
        "  Docs:\n"
        "    + /new\n"
        "  Guides:\n"
        "    + /g-new\n"
    )


def test_diff_url_moved_between_sections_is_no_change(tmp_path: Path):
    before = write(
        tmp_path,
        "before.txt",
        sections_document({"Docs": ["/a", "/b"], "Guides": ["/c"]}),
    )
    after = write(
        tmp_path,
        "after.txt",
        sections_document({"Docs": ["/a"], "Guides": ["/b", "/c"]}),
    )
    assert run_json("diff", str(before), str(after), "--format", "json") == (
        0,
        {"added": {}, "removed": {}},
    )
    rc, out, _ = run("diff", str(before), str(after))
    assert rc == 0 and out == "No link changes.\n"


def test_diff_quiet_prints_nothing(tmp_path: Path):
    before = write(tmp_path, "before.txt", document("/a"))
    changed = write(tmp_path, "after.txt", document("/a", "/b"))
    same = write(tmp_path, "same.txt", document("/a"))
    rc, out, err = run("diff", str(before), str(changed), "--quiet")
    assert rc == 1 and out == "" and err == ""
    rc, out, err = run("diff", str(before), str(same), "--quiet")
    assert rc == 0 and out == "" and err == ""
    rc, out, _ = run("diff", str(before), str(tmp_path / "missing"), "--quiet")
    assert rc == 2 and out == ""


def test_diff_compares_link_sets_not_titles_order_or_duplicates(tmp_path: Path):
    before = write(tmp_path, "before.txt", document("/a", "/b", "/a"))
    after = write(
        tmp_path, "after.txt", "# Changed title\n\n## Other\n\n- [B](/b)\n- [A](/a): Updated.\n"
    )
    assert run_json("diff", str(before), str(after), "--format", "json") == (
        0,
        {"added": {}, "removed": {}},
    )


def test_diff_accepts_urls_and_local_files(monkeypatch, tmp_path: Path):
    before = write(tmp_path, "before.txt", document("https://x.dev/a"))
    monkeypatch.setattr(
        "llms_txt_gen.cli.fetch",
        lambda url, timeout: (document("https://x.dev/b").encode(), "text/plain"),
    )
    rc, data = run_json(
        "diff", str(before), "https://x.dev/llms.txt", "--format", "json", "--timeout", "2"
    )
    assert rc == 1 and data["removed"] == {"Pages": ["https://x.dev/a"]}


@pytest.mark.parametrize("content", ["not an llms file", "# Docs\n", b"\xff"])
def test_diff_rejects_invalid_inputs_without_reporting_removals(tmp_path: Path, content):
    before = write(tmp_path, "before.txt", document("/a"))
    after = tmp_path / "bad.txt"
    after.write_bytes(content if isinstance(content, bytes) else content.encode())
    rc, out, err = run("diff", str(before), str(after))
    assert rc == 2 and "error:" in err and not out


def test_diff_missing_file(tmp_path: Path):
    before = write(tmp_path, "before.txt", document("/a"))
    assert run("diff", str(before), str(tmp_path / "missing"))[0] == 2
