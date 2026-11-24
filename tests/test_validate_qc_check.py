"""Tests für den Prüfvermerk der Content Factory."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/content-factory/examples/qc-check-beispiel.json"
sys.path.insert(0, str(ROOT / "scripts"))

from validate_qc_check import main, validate  # noqa: E402


@pytest.fixture
def document():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example(capsys):
    assert main([str(EXAMPLE)]) == 0
    assert capsys.readouterr().err == ""


def test_missing_point(document):
    del document[0]["punkte"]["bild"]
    assert validate(document) == ["FIKTIV-QC-A: punkte.bild: Pflichtfeld fehlt"]


@pytest.mark.parametrize(
    "point, field, value, message",
    [
        ("bild", "pruefende_rolle", "  rOLLE a\t", "muss von der erstellenden Rolle abweichen"),
        ("bild", "pruefende_rolle", " ", "nicht leere Zeichenkette erwartet"),
        ("bild", "notiz", None, "Zeichenkette erwartet"),
        ("bild", "ergebnis", [], "ungültiges Ergebnis"),
        ("bild", "ergebnis", "nicht_bestanden", "Prüfvermerk unvollständig (nicht_bestanden)"),
        ("kennzeichnung", "ki_kennzeichnung_sichtbar", False, "true ist Pflicht"),
        ("kennzeichnung", "ki_kennzeichnung_sichtbar", 1, "true ist Pflicht"),
        ("kennzeichnung", "ergebnis", "nicht_anwendbar", "nicht_anwendbar ist hier unzulässig"),
        (
            "kennzeichnung",
            "c2pa",
            "vorhanden_ungueltig",
            "vorhanden_gueltig oder nicht_vorhanden erwartet",
        ),
        ("tool_lizenz", "tools", {}, "Liste von Tools erwartet"),
    ],
)
def test_invalid_point_field(document, point, field, value, message):
    document[0]["punkte"][point][field] = value
    assert validate(document) == [f"FIKTIV-QC-A: punkte.{point}.{field}: {message}"]


@pytest.mark.parametrize(
    "point, field",
    [
        ("bild", "ergebnis"),
        ("bild", "pruefende_rolle"),
        ("kennzeichnung", "ki_kennzeichnung_sichtbar"),
        ("kennzeichnung", "c2pa"),
        ("tool_lizenz", "tools"),
    ],
)
def test_missing_point_field(document, point, field):
    del document[0]["punkte"][point][field]
    assert validate(document) == [f"FIKTIV-QC-A: punkte.{point}.{field}: Pflichtfeld fehlt"]


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("name", "", "nicht leere Zeichenkette erwartet"),
        ("tarif", "test", "free oder kommerziell erwartet"),
        ("nutzung", "test", "intern oder extern erwartet"),
        ("nutzung", "extern", "Free-Tools sind nur intern zulässig"),
    ],
)
def test_invalid_tool_field(document, field, value, message):
    document[0]["punkte"]["tool_lizenz"]["tools"][0][field] = value
    assert validate(document) == [f"FIKTIV-QC-A: punkte.tool_lizenz.tools[0].{field}: {message}"]


@pytest.mark.parametrize(
    "path, prefix",
    [
        ((), ""),
        (("punkte",), "punkte."),
        (("punkte", "bild"), "punkte.bild."),
        (("punkte", "kennzeichnung"), "punkte.kennzeichnung."),
        (("punkte", "tool_lizenz"), "punkte.tool_lizenz."),
        (("punkte", "tool_lizenz", "tools", 0), "punkte.tool_lizenz.tools[0]."),
    ],
)
def test_unknown_field(document, path, prefix):
    target = document[0]
    for part in path:
        target = target[part]
    target["zusatz"] = "Fiktiver Zusatz"
    assert validate(document) == [f'FIKTIV-QC-A: {prefix}"zusatz": unbekanntes Feld']


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("id", [], "nicht leere Zeichenkette erwartet"),
        ("video", " ", "nicht leere Zeichenkette erwartet"),
        ("erstellende_rolle", None, "nicht leere Zeichenkette erwartet"),
        ("datum", "2026-02-30", "gültiges Kalenderdatum im Format JJJJ-MM-TT erwartet"),
        ("datum", "2026-1-15", "gültiges Kalenderdatum im Format JJJJ-MM-TT erwartet"),
        ("punkte", [], "Objekt erwartet"),
    ],
)
def test_invalid_record_field(document, field, value, message):
    document[0][field] = value
    label = "eintrag[0]" if field == "id" else "FIKTIV-QC-A"
    assert validate(document) == [f"{label}: {field}: {message}"]


def test_duplicate_id(document):
    document[1]["id"] = document[0]["id"]
    assert validate(document) == ["FIKTIV-QC-A: id: doppelte ID"]


@pytest.mark.parametrize(
    "content, code, error",
    [
        ("{}", 1, "datei: $: Liste von Prüfvermerken erwartet"),
        ("{", 2, "datei: json: ungültiges JSON"),
        (None, 2, "datei: datei: Datei kann nicht als UTF-8 gelesen werden"),
    ],
)
def test_main_error_codes(tmp_path, capsys, content, code, error):
    path = tmp_path / "qc.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    assert main([str(path)]) == code
    assert capsys.readouterr().err.splitlines() == [error]
