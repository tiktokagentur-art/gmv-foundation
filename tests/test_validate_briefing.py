import json
from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/content-factory/examples/briefing-beispiel.json"
main = run_path(str(ROOT / "scripts/validate_briefing.py"))["main"]


@pytest.fixture
def briefing() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "briefing.json"


def test_example(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(EXAMPLE)]) == 0
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    "field", ["thema", "zielgruppe", "quellen", "format", "rechteinformationen"]
)
def test_missing_required_field(
    field: str, briefing: dict, path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    del briefing[field]
    path.write_text(json.dumps(briefing), encoding="utf-8")

    assert main([str(path)]) == 1
    assert capsys.readouterr().err.splitlines() == [f"{path}: {field}: Pflichtfeld fehlt."]


@pytest.mark.parametrize("field", ["thema", "zielgruppe", "format", "rechteinformationen"])
@pytest.mark.parametrize("value", ["", " \t\n", 1])
def test_invalid_text_field(
    field: str, value: object, briefing: dict, path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    briefing[field] = value
    path.write_text(json.dumps(briefing), encoding="utf-8")

    assert main([str(path)]) == 1
    assert capsys.readouterr().err.splitlines() == [
        f"{path}: {field}: Eine nicht leere Zeichenkette wird erwartet."
    ]


@pytest.mark.parametrize(
    ("sources", "field"),
    [
        ([], "quellen"),
        ("Fiktive Beispielquelle", "quellen"),
        (["Fiktive Beispielquelle", " "], "quellen[1]"),
        ([None], "quellen[0]"),
    ],
)
def test_invalid_sources(
    sources: object, field: str, briefing: dict, path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    briefing["quellen"] = sources
    path.write_text(json.dumps(briefing), encoding="utf-8")

    assert main([str(path)]) == 1
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith(f"{path}: {field}: ")


def test_unknown_field(briefing: dict, path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    briefing["zusatz"] = "Fiktiver Zusatz"
    path.write_text(json.dumps(briefing), encoding="utf-8")

    assert main([str(path)]) == 1
    assert capsys.readouterr().err.splitlines() == [f"{path}: zusatz: Unbekanntes Feld."]


def test_json_must_be_an_object(path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path.write_text("[]", encoding="utf-8")

    assert main([str(path)]) == 1
    assert capsys.readouterr().err.splitlines() == [f"{path}: $: Ein JSON-Objekt wird erwartet."]


@pytest.mark.parametrize("content", ["{", '{"thema": NaN}'])
def test_invalid_json(content: str, path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path.write_text(content, encoding="utf-8")

    assert main([str(path)]) == 2
    assert capsys.readouterr().err.splitlines() == [f"{path}: $: Ungültiges JSON."]


def test_unreadable_file(path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(path)]) == 2
    assert capsys.readouterr().err.splitlines() == [
        f"{path}: $: Datei kann nicht als UTF-8 gelesen werden."
    ]


def test_multiple_files(path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path.write_text('{"zusatz": "Fiktiver Zusatz"}', encoding="utf-8")
    missing = path.with_name("fehlt.json")

    assert main([str(missing), str(EXAMPLE), str(path)]) == 2
    lines = capsys.readouterr().err.splitlines()
    assert lines[0] == f"{missing}: $: Datei kann nicht als UTF-8 gelesen werden."
    assert lines[-1] == f"{path}: zusatz: Unbekanntes Feld."
    assert len(lines) == 7
