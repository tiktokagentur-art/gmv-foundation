"""Tests für den Kennzahlenprüfer."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/governance/examples/kpi-beispiel.json"
sys.path.insert(0, str(ROOT / "scripts"))

from validate_kpi import main, validate  # noqa: E402


@pytest.fixture
def document():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example(capsys):
    assert main([str(EXAMPLE)]) == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "field",
    ["id", "name", "definition", "ist_baseline", "messmethode", "zielwert", "status", "quelle"],
)
def test_required_field(document, field):
    entry = document[1]
    del entry[field]
    label = entry.get("id", "eintrag[0]")
    assert validate([entry]) == [f"{label}: {field}: Pflichtfeld fehlt"]


def test_unknown_field(document):
    document[0]["zusatz"] = "Fiktiver Zusatz"
    assert validate(document) == ['BEISPIEL-KPI-A: "zusatz": unbekanntes Feld']


@pytest.mark.parametrize(
    "field, value",
    [
        ("id", " \t"),
        ("id", []),
        ("name", " \t"),
        ("definition", 42),
        ("messmethode", ""),
        ("status", "bestätigt"),
        ("ist_baseline", False),
        ("ist_baseline", []),
        ("zielwert", True),
        ("zielwert", " \t"),
        ("quelle", " \t"),
        ("quelle", 42),
    ],
)
def test_invalid_field(document, field, value):
    document[1][field] = value
    label = "eintrag[1]" if field == "id" else "BEISPIEL-KPI-B"
    errors = validate(document)
    assert len(errors) == 1
    assert errors[0].startswith(f"{label}: {field}: ")


def test_duplicate_id(document):
    document[1]["id"] = document[0]["id"]
    assert validate(document) == ["BEISPIEL-KPI-A: id: doppelte ID"]


def test_candidate_with_target(document):
    document[0]["zielwert"] = 0
    assert validate(document) == ["BEISPIEL-KPI-A: zielwert: muss für kandidat null sein"]


def test_confirmed_without_target(document):
    document[1]["zielwert"] = None
    assert validate(document) == ["BEISPIEL-KPI-B: zielwert: für bestaetigt erforderlich"]


def test_baseline_without_source(document):
    document[1]["quelle"] = None
    assert validate(document) == ["BEISPIEL-KPI-B: quelle: bei gesetzter Ist-Baseline erforderlich"]


def test_text_values(document):
    document[1]["ist_baseline"] = "Fiktive Ausgangsstufe"
    document[1]["zielwert"] = "Fiktive Zielstufe"
    assert validate(document) == []


def test_entry_must_be_an_object():
    assert validate([None]) == ["eintrag[0]: eintrag: Objekt erwartet"]


@pytest.mark.parametrize(
    "content, code, error",
    [
        ("{}", 1, "datei: $: Liste von Kennzahlen erwartet"),
        ("{", 2, "datei: json: ungültiges JSON"),
        (None, 2, "datei: datei: Datei kann nicht als UTF-8 gelesen werden"),
    ],
)
def test_main_error_codes(tmp_path, capsys, content, code, error):
    path = tmp_path / "kpi.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    assert main([str(path)]) == code
    assert capsys.readouterr().err.splitlines() == [error]
