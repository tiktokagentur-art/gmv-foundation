"""Unit tests for handbook validation."""

from pathlib import Path
from runpy import run_path

# The repository packages only app/, so load the standalone CLI by file path.
module = run_path(str(Path(__file__).resolve().parents[1] / "scripts/check_docs.py"))
check_links = module["check_links"]
validate = module["validate"]


def test_relative_link(tmp_path: Path) -> None:
    page = tmp_path / "docs" / "README.md"
    page.parent.mkdir()
    (tmp_path / "README.md").write_text("# Root\n", encoding="utf-8")
    page.write_text("[root](../README.md#section)\n", encoding="utf-8")
    assert check_links(page, tmp_path) == []


def test_missing_and_escaping_link(tmp_path: Path) -> None:
    page = tmp_path / "README.md"
    page.write_text("[lost](missing.md)\n[bad](../outside.md)\n", encoding="utf-8")
    issues = check_links(page, tmp_path)
    assert len(issues) == 2
    assert "missing" in issues[0]
    assert "outside repo" in issues[1]


def test_external_and_fenced_links_ignored(tmp_path: Path) -> None:
    page = tmp_path / "README.md"
    page.write_text(
        "[web](https://example.com)\n[section](#anchor)\n"
        "```md\n[example](missing.md)\n```\n",
        encoding="utf-8",
    )
    assert check_links(page, tmp_path) == []


def test_required_pages(tmp_path: Path) -> None:
    assert any("missing" in issue for issue in validate(tmp_path))
